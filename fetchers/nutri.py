"""식품영양성분DB API (FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02) 래퍼.

총 275K+건. 제품명(FOOD_NM_KR)/업체명(MAKER_NM)으로 서버측 검색 지원.
필드 AMT_NUM1~157 에 에너지/단백/지방/탄수/당/나트륨/비타민/미네랄/지방산/아미노산 상세.
"""
from __future__ import annotations

from config import URL_NUTRI
from fetchers._dg_base import call_dg, extract_items


# UI에 자주 쓰는 핵심 영양성분 라벨 매핑 (AMT_NUM 코드 → 한글명)
CORE_NUTRIENTS: dict[str, str] = {
    "AMT_NUM1": "에너지(kcal)",
    "AMT_NUM2": "수분(g)",
    "AMT_NUM3": "단백질(g)",
    "AMT_NUM4": "지방(g)",
    "AMT_NUM6": "탄수화물(g)",
    "AMT_NUM7": "당류(g)",
    "AMT_NUM8": "식이섬유(g)",
    "AMT_NUM13": "나트륨(mg)",
    "AMT_NUM9": "칼슘(mg)",
    "AMT_NUM10": "철(mg)",
    "AMT_NUM21": "비타민C(mg)",
    "AMT_NUM23": "콜레스테롤(mg)",
    "AMT_NUM24": "포화지방산(g)",
    "AMT_NUM25": "트랜스지방산(g)",
    "AMT_NUM116": "아연(mg)",
}


def search(
    *,
    food_nm_kr: str | None = None,
    maker_nm: str | None = None,
    page_size: int = 20,
) -> list[dict]:
    """제품명/업체명으로 검색. ITEM_REPORT_NO로는 서버측 필터가 안 돼서 클라이언트측 후필터링 필요."""
    params = {"pageNo": "1", "numOfRows": str(page_size)}
    if food_nm_kr:
        params["FOOD_NM_KR"] = food_nm_kr
    if maker_nm:
        params["MAKER_NM"] = maker_nm
    return extract_items(call_dg(URL_NUTRI, params))


def search_by_report_no(report_no: str, *, maker_hint: str | None = None) -> dict | None:
    """품목제조보고번호로 조회. API가 이 번호로 서버 필터를 안 해서 업체명으로 좁혀 스캔.

    maker_hint를 주면 그 업체 전수 페이지를 돌며 번호 일치 한 건을 찾음.
    """
    target = report_no.strip()
    page = 1
    while True:
        params = {"pageNo": str(page), "numOfRows": "100"}
        if maker_hint:
            params["MAKER_NM"] = maker_hint
        items = extract_items(call_dg(URL_NUTRI, params))
        if not items:
            return None
        for it in items:
            if str(it.get("ITEM_REPORT_NO", "")).strip() == target:
                return it
        if len(items) < 100:
            return None
        page += 1
        if page > 20:  # 안전장치
            return None
