"""전국건강기능식품영양성분정보 표준데이터 API.

End Point: https://api.data.go.kr/openapi/tn_pubr_public_health_functional_food_nutrition_info_api
총 4,380건. 파라미터 필터 미지원 → 전체 다운로드 후 로컬 필터링.

필드:
  foodCd                 식품코드
  foodNm                 제품명
  typeNm                 종류 ("건강기능식품")
  foodLv3Nm              대분류 (영양성분 / 기능성 원료)
  foodLv4Nm, foodLv5Nm   세분류 (엠에스엠, 셀레늄 등)
  ntrtIgrdPvsnUnitAmnt   영양성분 기준량 (예: 800mg)
  enerc                  에너지(kcal)
  water prot fatce ash chocdf sugar fibtg
  ca fe p k nat
  vitaRae retol cartb thia ribf nia vitc vitd
  chole fasat fatrn
  onetmQnt              1회 섭취량
  onetmQntWghtVolm      1회 섭취 중량/용량
  onetmIntkNmtm         1일 섭취 횟수
  intkTrgt              섭취대상
  foodWght              총 제품 중량
  itemMnftrRptNo        품목제조보고번호 (건기식 STTEMNT_NO와 동일 체계)
  mfrNm imptNm distNm   제조·수입·유통
  imptYn cooNm          수입여부·원산지국
  crtYmd dataCrtrYmd    작성일·기준일자
"""
from __future__ import annotations

import time

import requests

from config import KEY_DATAGO

URL = ("https://api.data.go.kr/openapi/"
       "tn_pubr_public_health_functional_food_nutrition_info_api")

_TIMEOUT = 120


# 사용자 친화 라벨
FIELD_LABELS = {
    "enerc": "에너지(kcal)",
    "water": "수분(g)",
    "prot": "단백질(g)",
    "fatce": "지방(g)",
    "ash": "회분(g)",
    "chocdf": "탄수화물(g)",
    "sugar": "당류(g)",
    "fibtg": "식이섬유(g)",
    "nat": "나트륨(mg)",
    "ca": "칼슘(mg)",
    "fe": "철(mg)",
    "p": "인(mg)",
    "k": "칼륨(mg)",
    "vitaRae": "비타민A(μg RAE)",
    "retol": "레티놀(μg)",
    "cartb": "베타카로틴(μg)",
    "thia": "비타민B1(mg)",
    "ribf": "비타민B2(mg)",
    "nia": "니아신(mg)",
    "vitc": "비타민C(mg)",
    "vitd": "비타민D(μg)",
    "chole": "콜레스테롤(mg)",
    "fasat": "포화지방산(g)",
    "fatrn": "트랜스지방산(g)",
}


def _call(params: dict, retries: int = 4) -> dict:
    merged = {"serviceKey": KEY_DATAGO, "type": "json", **params}
    last_err = ""
    for attempt in range(retries):
        try:
            r = requests.get(URL, params=merged, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2 ** attempt)   # exponential backoff
    return {"_error": last_err}


def _items(payload: dict) -> list[dict]:
    body = payload.get("response", {}).get("body", {})
    items = body.get("items", [])
    return items if isinstance(items, list) else []


def _total(payload: dict) -> int:
    body = payload.get("response", {}).get("body", {})
    try:
        return int(body.get("totalCount", 0))
    except (TypeError, ValueError):
        return 0


def fetch_all(page_size: int = 1000) -> list[dict]:
    """4,380건 전체 다운로드."""
    first = _call({"pageNo": 1, "numOfRows": page_size})
    total = _total(first)
    if total == 0:
        return []
    pages = (total + page_size - 1) // page_size
    all_items = _items(first)
    for p in range(2, pages + 1):
        payload = _call({"pageNo": p, "numOfRows": page_size})
        all_items.extend(_items(payload))
        time.sleep(0.3)
    return all_items


def find_by_report_no(items: list[dict], report_no: str) -> dict | None:
    """STTEMNT_NO(건기식 신고번호) 기반 정확 매칭 — itemMnftrRptNo 와 동일 체계."""
    rn = str(report_no).strip()
    for it in items:
        if str(it.get("itemMnftrRptNo", "")).strip() == rn:
            return it
    return None


def filter_by_product_name(items: list[dict], name: str) -> list[dict]:
    """foodNm 부분 매칭 (공백 무시)."""
    target = "".join(name.split()).lower()
    return [
        it for it in items
        if target in "".join(str(it.get("foodNm", "")).split()).lower()
    ]
