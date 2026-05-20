"""해외직구식품 국내 반입차단 대상 원료·성분 API.

End Point: https://apis.data.go.kr/1471000/BlockRawIrdntInfoService/getBlockRawIrdntInfo
총 282종 (마약류 9 + 의약성분·한약 139 + 식품에 사용 불가 원료 134)

필드 (실제 응답):
  APPN_RELS_DVS       지정/해제 구분 (Y=지정, N=해제)
  RAW_IRDNT_NM        원료·성분명(한글)
  RAW_IRDNT_ENG_NM    원료·성분명(영문)
  RAW_IRDNT_ETC_NM    기타명칭 (이명)
  APPN_DT             지정일자
  RELS_DT             해제일자
  APPN_RSN            지정사유
  RELS_RSN            해제사유
"""
from __future__ import annotations

import time

import requests

from config import KEY_DATAGO

URL = "https://apis.data.go.kr/1471000/BlockRawIrdntInfoService/getBlockRawIrdntInfo"
_TIMEOUT = 90


def _call(params: dict, retries: int = 4) -> dict:
    merged = {"serviceKey": KEY_DATAGO, "type": "json", **params}
    last_err = ""
    for attempt in range(retries):
        try:
            r = requests.get(URL, params=merged, timeout=_TIMEOUT)
            r.raise_for_status()
            try:
                return r.json()
            except ValueError:
                return {"_error": "json parse", "_raw": r.text[:300]}
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2 ** attempt)
    return {"_error": last_err}


def _items(payload: dict) -> list[dict]:
    # 응답 경로: response > body > items 혹은 body > items
    body = payload.get("response", {}).get("body", {}) or payload.get("body", {})
    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", [])
    if not isinstance(items, list):
        return []
    if items and isinstance(items[0], dict) and set(items[0].keys()) == {"item"}:
        return [it["item"] for it in items]
    return items


def _total(payload: dict) -> int:
    body = payload.get("response", {}).get("body", {}) or payload.get("body", {})
    try:
        return int(body.get("totalCount", 0))
    except (TypeError, ValueError):
        return 0


def fetch_all(page_size: int = 500) -> list[dict]:
    """282종 전체 수신."""
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


import re as _re

def _norm(s) -> str:
    """공백·하이픈·콤마·괄호·슬래시·언더스코어 제거 후 소문자."""
    if not s:
        return ""
    return _re.sub(r"[\s\-_,.·()\[\]/]+", "", str(s)).lower()


def is_blocked(name: str, blocklist: list[dict]) -> dict | None:
    """성분명이 반입차단 리스트에 있는지 확인.

    APPN_RELS_DVS='Y' (지정) 항목만 유효. 해제된 건 제외.
    한글/영문/기타명칭 비교 (공백 제거 후 정확매칭 우선, 다음 쌍방 포함).
    """
    if not name:
        return None
    q = _norm(name)
    if len(q) < 2:
        return None
    # 1차: 정확 매칭
    for row in blocklist:
        if row.get("APPN_RELS_DVS") != "Y":
            continue
        for key in ("RAW_IRDNT_NM", "RAW_IRDNT_ENG_NM", "RAW_IRDNT_ETC_NM"):
            c = _norm(row.get(key))
            if c and c == q:
                return row
    # 2차: 포함 매칭 (단어 길이 3자 이상일 때만, 부분매칭 노이즈 방지)
    if len(q) >= 3:
        for row in blocklist:
            if row.get("APPN_RELS_DVS") != "Y":
                continue
            for key in ("RAW_IRDNT_NM", "RAW_IRDNT_ENG_NM", "RAW_IRDNT_ETC_NM"):
                c = _norm(row.get(key))
                if c and len(c) >= 3 and (q in c or c in q):
                    return row
    return None


def active_list(blocklist: list[dict]) -> list[dict]:
    """지정 상태(Y)만 필터."""
    return [r for r in blocklist if r.get("APPN_RELS_DVS") == "Y"]
