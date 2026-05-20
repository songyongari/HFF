"""건강기능식품정보 API (HtfsInfoService03/getHtfsItem01) 래퍼."""
from __future__ import annotations

from config import URL_HTFS
from fetchers._dg_base import paginate


def fetch_all_htfs(page_size: int = 500) -> list[dict]:
    """건기식 전체 44K+건 수신. 서버측 검색 파라미터 미지원 → 전체 받아 로컬 필터."""
    return paginate(URL_HTFS, {}, page_size=page_size, sleep=0.4)


def filter_by_product_name(items: list[dict], names: list[str]) -> dict[str, list[dict]]:
    """제품명(PRDUCT) 부분 매칭. 공백 제거 비교."""
    def norm(s: str) -> str:
        return "".join(str(s).split()).lower()

    keys = {n: norm(n) for n in names}
    hits: dict[str, list[dict]] = {n: [] for n in names}
    for it in items:
        pn = norm(it.get("PRDUCT", ""))
        for name, key in keys.items():
            if key and key in pn:
                hits[name].append(it)
    return hits


def filter_by_company(items: list[dict], company: str) -> list[dict]:
    """업체(ENTRPS) 부분 매칭."""
    return [it for it in items if company in str(it.get("ENTRPS", ""))]
