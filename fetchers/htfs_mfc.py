"""C003 건강기능식품 품목제조신고(원재료) 래퍼.

총 44,369건. 서버측 필터: PRDLST_REPORT_NO / PRDLST_NM / BSSH_NM / LCNS_NO / PRMS_DT / CHNG_DT
필드:
  PRDLST_REPORT_NO   신고번호 (HtfsInfoService03의 STTEMNT_NO와 동일)
  PRDLST_NM          제품명
  BSSH_NM            업소명
  LCNS_NO            인허가번호
  PRMS_DT            신고일자
  LAST_UPDT_DTM      최종수정
  PRDT_SHAP_CD_NM    제형 (캡슐/분말/액상 등)
  SHAP DISPOS        형태/성상
  PRIMARY_FNCLTY     주요 기능성 (MAIN_FNCTN과 유사)
  STDR_STND          기준·규격 (BASE_STANDARD와 유사)
  IFTKN_ATNT_MATR_CN 섭취 주의사항 (INTAKE_HINT1과 유사)
  NTK_MTHD           섭취방법 (SRV_USE와 유사)
  POG_DAYCNT         유통기한
  CSTDY_MTHD         보관방법 (PRSRV_PD와 유사)
  RAWMTRL_NM         원재료명 (전체 텍스트, 콤마 구분) ← 핵심
"""
from __future__ import annotations

from functools import lru_cache

from config import SID_HTFS_MFC
from fetchers._fskr_base import call_fskr, extract_rows


@lru_cache(maxsize=512)
def fetch_by_report_no(report_no: str) -> dict | None:
    """신고번호 정확 매칭."""
    payload = call_fskr(SID_HTFS_MFC, start=1, end=5,
                        extras={"PRDLST_REPORT_NO": str(report_no).strip()})
    rows = extract_rows(payload, SID_HTFS_MFC)
    return rows[0] if rows else None


def search_by_product_name(name: str, *, limit: int = 50) -> list[dict]:
    payload = call_fskr(SID_HTFS_MFC, start=1, end=limit,
                        extras={"PRDLST_NM": name.strip()})
    return extract_rows(payload, SID_HTFS_MFC)


def search_by_company(company: str, *, limit: int = 100) -> list[dict]:
    payload = call_fskr(SID_HTFS_MFC, start=1, end=limit,
                        extras={"BSSH_NM": company.strip()})
    return extract_rows(payload, SID_HTFS_MFC)


def parse_raw_materials(rawmtrl_nm: str) -> list[str]:
    """RAWMTRL_NM 콤마구분 텍스트를 리스트로."""
    if not rawmtrl_nm:
        return []
    return [s.strip() for s in rawmtrl_nm.split(",") if s.strip()]
