"""식품안전나라 OpenAPI 공통 호출 헬퍼.

주의: 동일 인증키로 요청이 처리 중이면 alert 스크립트로 차단됨.
→ 프로세스 전역 락으로 순차 호출 보장 + 호출 간 최소 지연.
"""
from __future__ import annotations

import threading
import time
from typing import Any

import requests

from config import FSKR_BASE, KEY_FSKR

_LOCK = threading.Lock()
_LAST_CALL: list[float] = [0.0]   # list로 감싸야 closure에서 mutation 가능
_MIN_INTERVAL = 1.2               # 동일 키 동시차단 회피용 최소 간격(초)
_DEFAULT_TIMEOUT = 15             # 클라우드 환경 — 짧게 잡고 빠르게 실패


def _build_url(service_id: str, data_type: str, start: int, end: int,
               extras: dict[str, str] | None) -> str:
    base = f"{FSKR_BASE}/{KEY_FSKR}/{service_id}/{data_type}/{start}/{end}"
    if extras:
        for k, v in extras.items():
            base += f"/{k}={v}"
    return base


def call_fskr(service_id: str, *, start: int = 1, end: int = 5,
              data_type: str = "json", extras: dict[str, str] | None = None,
              timeout: int = _DEFAULT_TIMEOUT, retries: int = 2) -> dict[str, Any]:
    """식품안전나라 공통 GET. 동시차단/alert 응답 자동 재시도."""
    url = _build_url(service_id, data_type, start, end, extras)
    headers = {"User-Agent": "Mozilla/5.0 (biocom-hff-internal)"}
    for attempt in range(retries + 1):
        with _LOCK:
            gap = time.time() - _LAST_CALL[0]
            if gap < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - gap)
            try:
                r = requests.get(url, headers=headers, timeout=timeout)
            except requests.RequestException as e:
                _LAST_CALL[0] = time.time()
                return {"_error": f"network: {type(e).__name__}"}
            finally:
                _LAST_CALL[0] = time.time()

        text = r.text
        if r.status_code == 200 and text.startswith("{"):
            try:
                return r.json()
            except ValueError:
                pass
        if "현재 접속 중인 인증키" in text or "alert(" in text:
            # 동시차단 — 백오프 후 재시도
            time.sleep(2.0 * (attempt + 1))
            continue
        return {"_error": f"HTTP {r.status_code}", "_raw": text[:300]}
    return {"_error": "동시차단 재시도 초과"}


def extract_rows(payload: dict, service_id: str) -> list[dict]:
    """서비스ID별 wrap 제거 → row 리스트 반환."""
    if "_error" in payload:
        return []
    body = payload.get(service_id, {})
    rows = body.get("row", []) or []
    return rows if isinstance(rows, list) else []


def total_count(payload: dict, service_id: str) -> int:
    if "_error" in payload:
        return 0
    try:
        return int(payload.get(service_id, {}).get("total_count", 0))
    except (TypeError, ValueError):
        return 0
