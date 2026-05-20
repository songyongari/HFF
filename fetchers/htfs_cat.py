"""I0760 건강기능식품 영양DB (실제 성격: 건기식 원료/기능성 분류 사전) 래퍼.

585건 전체 캐싱 권장. HELT_ITM_GRP_NM(원료명)으로 필터 가능.
필드: LCLAS_NM/CD, MLSFC_NM/CD, SCLAS_NM/CD, HELT_ITM_GRP_NM/CD
"""
from __future__ import annotations

from config import SID_HTFS_CAT
from fetchers._fskr_base import call_fskr, extract_rows, total_count


def fetch_all() -> list[dict]:
    """585건 전량 수신. 한 호출당 max 1000개라 한 번에 가능."""
    payload = call_fskr(SID_HTFS_CAT, start=1, end=1000)
    return extract_rows(payload, SID_HTFS_CAT)


def search_by_ingredient(name: str, *, limit: int = 20) -> list[dict]:
    """원료명으로 분류 정보 찾기."""
    payload = call_fskr(SID_HTFS_CAT, start=1, end=limit,
                        extras={"HELT_ITM_GRP_NM": name})
    return extract_rows(payload, SID_HTFS_CAT)
