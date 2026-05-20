"""전국통합식품영양성분정보(가공식품) 표준데이터 API.

End Point: https://api.data.go.kr/openapi/tn_pubr_public_nutri_process_info_api
총 753,215건 (기존 FoodNtrCpntDbInfo02 275K의 확장판).
필터: foodNm / itemMnftrRptNo / mfrNm (정확매칭).
"""
from __future__ import annotations

import time

import requests

from config import KEY_DATAGO

URL = ("https://api.data.go.kr/openapi/"
       "tn_pubr_public_nutri_process_info_api")

_TIMEOUT = 120


# 24개 영양소 라벨 (htfs_nutri와 동일 스키마)
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
            time.sleep(2 ** attempt)
    return {"_error": last_err}


def _items(payload: dict) -> list[dict]:
    body = payload.get("response", {}).get("body", {})
    items = body.get("items", []) if isinstance(body, dict) else []
    return items if isinstance(items, list) else []


def _result_code(payload: dict) -> str:
    return payload.get("response", {}).get("header", {}).get("resultCode", "")


def search_by_report_no(report_no: str) -> list[dict]:
    """품목제조번호 정확 매칭."""
    payload = _call({"pageNo": 1, "numOfRows": 10,
                      "itemMnftrRptNo": str(report_no).strip()})
    if _result_code(payload) == "03":  # NODATA
        return []
    return _items(payload)


def search_by_food_name(name: str, limit: int = 30) -> list[dict]:
    """제품명 정확 매칭 (부분 매칭 미지원 — 정식 등록명 필요)."""
    payload = _call({"pageNo": 1, "numOfRows": limit,
                      "foodNm": name.strip()})
    if _result_code(payload) == "03":
        return []
    return _items(payload)


def search_by_maker(name: str, limit: int = 50) -> list[dict]:
    """제조사 정확 매칭."""
    payload = _call({"pageNo": 1, "numOfRows": limit,
                      "mfrNm": name.strip()})
    if _result_code(payload) == "03":
        return []
    return _items(payload)
