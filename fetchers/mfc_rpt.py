"""C002 식품(첨가물)품목제조보고(원재료) 래퍼.

총 1M+건. 서버측 필터: PRDLST_REPORT_NO, PRDLST_NM, BSSH_NM, LCNS_NO, RAWMTRL_NM, PRMS_DT, PRDLST_DCNM, CHNG_DT
출력: PRDLST_NM, BSSH_NM, PRDLST_REPORT_NO, RAWMTRL_NM(전체 원재료 콤마 리스트), PRDLST_DCNM(품목유형)
"""
from __future__ import annotations

from config import SID_MFC_RPT
from fetchers._fskr_base import call_fskr, extract_rows


def fetch_by_report_no(report_no: str) -> dict | None:
    """품목제조보고번호로 1건 조회."""
    payload = call_fskr(SID_MFC_RPT, start=1, end=5,
                        extras={"PRDLST_REPORT_NO": report_no})
    rows = extract_rows(payload, SID_MFC_RPT)
    return rows[0] if rows else None


def search_by_product_name(name: str, *, limit: int = 20) -> list[dict]:
    """품목명으로 검색."""
    payload = call_fskr(SID_MFC_RPT, start=1, end=limit,
                        extras={"PRDLST_NM": name})
    return extract_rows(payload, SID_MFC_RPT)


def search_by_company(company: str, *, limit: int = 100) -> list[dict]:
    """업소명으로 검색."""
    payload = call_fskr(SID_MFC_RPT, start=1, end=limit,
                        extras={"BSSH_NM": company})
    return extract_rows(payload, SID_MFC_RPT)


def search_by_raw_material(rawmtrl: str, *, limit: int = 50) -> list[dict]:
    """원재료명이 포함된 제품 검색 (역검색)."""
    payload = call_fskr(SID_MFC_RPT, start=1, end=limit,
                        extras={"RAWMTRL_NM": rawmtrl})
    return extract_rows(payload, SID_MFC_RPT)


def parse_raw_materials(rawmtrl_nm: str) -> list[str]:
    """RAWMTRL_NM 콤마구분 텍스트를 리스트로."""
    if not rawmtrl_nm:
        return []
    return [s.strip() for s in rawmtrl_nm.split(",") if s.strip()]
