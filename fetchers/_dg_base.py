"""공공데이터포털(data.go.kr) 공통 호출 헬퍼"""
from __future__ import annotations

import time
from typing import Any

import requests

from config import KEY_DATAGO

_DEFAULT_TIMEOUT = 90


def call_dg(url: str, params: dict[str, Any], *, timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """공공데이터포털 공통 GET 호출. 실패 시 {'_error': ...} 반환."""
    merged = {"serviceKey": KEY_DATAGO, "type": "json", **params}
    try:
        r = requests.get(url, params=merged, timeout=timeout)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return {"_error": "JSON parse failed", "_raw": r.text[:500]}
    except requests.RequestException as e:
        return {"_error": str(e)}


def extract_items(payload: dict) -> list[dict]:
    """응답에서 items 리스트 추출. `body > items` 또는 `response > body > items` 둘 다 지원."""
    if "_error" in payload:
        return []
    body = payload.get("body") or payload.get("response", {}).get("body", {})
    items = body.get("items", []) if isinstance(body, dict) else []
    if isinstance(items, dict):
        items = items.get("item", [])
    if not isinstance(items, list):
        return []
    if items and isinstance(items[0], dict) and set(items[0].keys()) == {"item"}:
        return [it["item"] for it in items]
    return items


def total_count(payload: dict) -> int:
    body = payload.get("body") or payload.get("response", {}).get("body", {})
    try:
        return int(body.get("totalCount", 0)) if isinstance(body, dict) else 0
    except (TypeError, ValueError):
        return 0


def paginate(url: str, base_params: dict, *, page_size: int = 500, sleep: float = 0.4,
             max_pages: int | None = None) -> list[dict]:
    """전체 페이지 순회 — 호출량이 많으면 sleep으로 쓰로틀."""
    first = call_dg(url, {**base_params, "pageNo": "1", "numOfRows": str(page_size)})
    total = total_count(first)
    if total == 0:
        return []
    pages = (total + page_size - 1) // page_size
    if max_pages:
        pages = min(pages, max_pages)
    all_items = extract_items(first)
    for p in range(2, pages + 1):
        payload = call_dg(url, {**base_params, "pageNo": str(p), "numOfRows": str(page_size)})
        all_items.extend(extract_items(payload))
        time.sleep(sleep)
    return all_items
