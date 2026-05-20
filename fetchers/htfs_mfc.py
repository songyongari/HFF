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

import json
import time
from functools import lru_cache

from config import DATA_DIR, SID_HTFS_MFC
from fetchers._fskr_base import call_fskr, extract_rows, total_count

_CACHE_FILE = DATA_DIR / "htfs_mfc_all.json"


def fetch_all(*, page_size: int = 1000, sleep: float = 0.3) -> list[dict]:
    """C003 전체 44K+건 수신. 식약처 API max 1000/call → 약 45회 호출."""
    first = call_fskr(SID_HTFS_MFC, start=1, end=page_size)
    total = total_count(first, SID_HTFS_MFC)
    if total == 0:
        return []
    all_rows = extract_rows(first, SID_HTFS_MFC)
    print(f"  C003 total={total:,}, 1-{page_size}: {len(all_rows)} rows")
    cursor = page_size + 1
    while cursor <= total:
        end = min(cursor + page_size - 1, total)
        payload = call_fskr(SID_HTFS_MFC, start=cursor, end=end)
        rows = extract_rows(payload, SID_HTFS_MFC)
        all_rows.extend(rows)
        print(f"  C003 {cursor:,}-{end:,}: {len(rows)} rows (누적 {len(all_rows):,})")
        cursor = end + 1
        time.sleep(sleep)
    return all_rows


@lru_cache(maxsize=1)
def _load_index() -> dict[str, dict]:
    """htfs_mfc_all.json 을 PRDLST_REPORT_NO → row dict 로 인덱싱."""
    if not _CACHE_FILE.exists():
        return {}
    rows = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    return {str(r.get("PRDLST_REPORT_NO", "")).strip(): r for r in rows if r.get("PRDLST_REPORT_NO")}


def fetch_by_report_no(report_no: str) -> dict | None:
    """신고번호 정확 매칭. 로컬 사전수집 JSON에서 즉시 조회 (라이브 호출 없음)."""
    return _load_index().get(str(report_no).strip())


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
