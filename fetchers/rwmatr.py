"""식품원재료 표준 사전 API (FoodRwmatrInfoService01/getFoodRwmatrList01) 래퍼.

원료명→학명/영문명/부위/사용조건 매핑. 총 18,542건 전체 캐싱 권장.
"""
from __future__ import annotations

from config import URL_RWMATR
from fetchers._dg_base import call_dg, extract_items, paginate


def fetch_all(page_size: int = 500) -> list[dict]:
    """원재료 사전 전체 다운로드."""
    return paginate(URL_RWMATR, {}, page_size=page_size, sleep=0.4)


def search_by_name(name: str, *, page_size: int = 50) -> list[dict]:
    """원재료명(rprsnt_rawmtrl_nm) 부분 검색."""
    payload = call_dg(URL_RWMATR, {
        "pageNo": "1",
        "numOfRows": str(page_size),
        "rprsnt_rawmtrl_nm": name,
    })
    return extract_items(payload)
