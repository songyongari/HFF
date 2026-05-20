"""식품이력 원재료 API (FoodHistInfoService03/getPrductRawmtrlList03) 래퍼.

이 API는 총 8.3M+건. 전체 다운로드는 비현실적이므로 PDTNM(제품명)으로만 조회.
출력 필드: PDTNM, ENTPCD, REGNUM, FOODHISTRACENUM, ORM_NM(원재료), PRV(원산지), GMOFLAG, GMONM, INCMYN, INCM_NM
"""
from __future__ import annotations

from functools import lru_cache

from config import URL_FOODHIST
from fetchers._dg_base import call_dg, extract_items


@lru_cache(maxsize=512)
def fetch_by_product_name(product_name: str, *, page_size: int = 100) -> list[dict]:
    """제품명으로 원재료 리스트 조회. 제품 1개당 원재료별 row가 여러 개 반환됨."""
    payload = call_dg(URL_FOODHIST, {
        "pageNo": "1",
        "numOfRows": str(page_size),
        "PDTNM": product_name,
    }, timeout=8)
    return extract_items(payload)
