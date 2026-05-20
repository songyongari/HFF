"""C002 일반식품 품목제조보고 라이브 호출 — 클라우드 캐시 우회 신규 모듈.

식약처 C002 는 1M+ 건이라 사전 수집 불가. 라이브 호출 유지하되:
- 짧은 타임아웃(8초) — 클라우드 → 한국 정부 API 가 느리거나 차단되면 빠른 실패
- KEY_FSKR 빈 문자열이면 호출 안 함
- 모든 예외 → 빈 결과 (앱 다운 방지)
"""
from __future__ import annotations

import threading
import time

import requests

from config import FSKR_BASE, KEY_FSKR, SID_MFC_RPT

_LOCK = threading.Lock()
_LAST_CALL: list[float] = [0.0]
_MIN_INTERVAL = 1.2
_TIMEOUT = 8


def _call(end: int, extras: dict[str, str]) -> dict:
    if not KEY_FSKR:
        return {}
    parts = [f"{FSKR_BASE}/{KEY_FSKR}/{SID_MFC_RPT}/json/1/{end}"]
    for k, v in extras.items():
        parts.append(f"{k}={v}")
    url = "/".join(parts)
    with _LOCK:
        gap = time.time() - _LAST_CALL[0]
        if gap < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - gap)
        try:
            r = requests.get(url, headers={"User-Agent": "biocom"}, timeout=_TIMEOUT)
        except requests.RequestException:
            _LAST_CALL[0] = time.time()
            return {}
        finally:
            _LAST_CALL[0] = time.time()
    if r.status_code == 200 and r.text.startswith("{"):
        try:
            return r.json()
        except ValueError:
            pass
    return {}


def _rows(payload: dict) -> list[dict]:
    body = payload.get(SID_MFC_RPT, {}) if isinstance(payload, dict) else {}
    rows = body.get("row", []) or [] if isinstance(body, dict) else []
    return rows if isinstance(rows, list) else []


def fetch_by_report_no(report_no: str) -> dict | None:
    """보고번호 정확 매칭 — 1건."""
    rs = _rows(_call(5, {"PRDLST_REPORT_NO": str(report_no).strip()}))
    return rs[0] if rs else None


def search_by_product_name(name: str, *, limit: int = 20) -> list[dict]:
    """품목명 검색."""
    return _rows(_call(limit, {"PRDLST_NM": name.strip()}))


def search_by_company(company: str, *, limit: int = 100) -> list[dict]:
    """업소명 검색."""
    return _rows(_call(limit, {"BSSH_NM": company.strip()}))


def search_by_raw_material(rawmtrl: str, *, limit: int = 50) -> list[dict]:
    """원재료명 역검색."""
    return _rows(_call(limit, {"RAWMTRL_NM": rawmtrl.strip()}))
