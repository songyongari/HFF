"""C003 건기식 품목제조신고 로컬 인덱스 조회 — 라이브 API 호출 없음.

배포 환경(Streamlit Cloud)에서 모듈 캐시 문제를 우회하기 위해 별도 모듈로 분리.
실제 데이터 수집은 fetchers.htfs_mfc.fetch_all 사용.
"""
from __future__ import annotations

import json
from functools import lru_cache

from config import DATA_DIR

_CACHE_FILE = DATA_DIR / "htfs_mfc_all.json"


@lru_cache(maxsize=1)
def _load_index() -> dict[str, dict]:
    if not _CACHE_FILE.exists():
        return {}
    rows = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    return {str(r.get("PRDLST_REPORT_NO", "")).strip(): r
            for r in rows if r.get("PRDLST_REPORT_NO")}


def fetch_by_report_no(report_no: str) -> dict | None:
    """신고번호 정확 매칭. 로컬 JSON 인덱스 즉시 조회."""
    return _load_index().get(str(report_no).strip())
