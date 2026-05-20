"""공용 UI 렌더러 — 페이지 간 중복 로직을 한 곳으로."""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd
import streamlit as st

from lib import lookup_rwmatr


# ================================================================
# 원재료 관련
# ================================================================

def material_table(raw_list: Iterable[str], *, title: str | None = None,
                   include_scn: bool = True) -> None:
    """원재료명 리스트 → 표준사전 매핑 테이블.

    사용처: 자사제품·시장제품검색·성분탐색 등 4곳에서 동일 로직.
    """
    raws = [r for r in (raw_list or []) if r and str(r).strip()]
    if title:
        st.markdown(f"##### {title}")
    if not raws:
        st.caption("원재료 정보 없음")
        return

    rows = []
    for mat in raws:
        e = lookup_rwmatr(mat)
        row = {
            "원재료(라벨)": mat,
            "표준명": e.get("RPRSNT_RAWMTRL_NM") if e else "—",
            "영문명": (e.get("ENG_NM") or "—") if e else "—",
        }
        if include_scn:
            row["학명"] = ((e.get("SCNM") or "")[:50]) if e else ""
        row["분류"] = e.get("MLSFC_NM") if e else ""
        row["부위"] = (e.get("REGN_CD_NM") or "") if e else ""
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def foodhist_origin_table(rows: list[dict], *, title: str | None = None) -> None:
    """식품이력 API 결과 → 원산지·GMO 테이블."""
    if not rows:
        return
    if title:
        st.markdown(f"##### {title}")
    df = pd.DataFrame([
        {"원재료": r.get("ORM_NM", ""),
         "원산지": r.get("PRV", ""),
         "GMO": r.get("GMONM") or "—"}
        for r in rows
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)


# ================================================================
# 제품 정보 카드 (공통 헤더)
# ================================================================

def product_header(title: str, subtitle: str | None = None,
                   left: dict[str, Any] | None = None,
                   right: dict[str, Any] | None = None) -> None:
    """제품 상세 카드 상단 2컬럼 헤더.

    left / right: 표시할 key → value 딕셔너리.
    """
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)
    c1, c2 = st.columns(2)
    for key, val in (left or {}).items():
        c1.markdown(f"**{key}**: {val if val else '—'}")
    for key, val in (right or {}).items():
        c2.markdown(f"**{key}**: {val if val else '—'}")


# ================================================================
# 영양성분
# ================================================================

def nutri_metric_cards(item: dict, labels: dict[str, str], *, per_row: int = 4,
                        empty_msg: str = "등록된 영양성분 값 없음") -> None:
    """영양성분 딕셔너리 + 라벨맵 → metric 카드 그리드."""
    shown = 0
    cols = st.columns(per_row)
    for code, label in labels.items():
        v = item.get(code)
        if v in (None, "", "0", 0, "0.00"):
            continue
        cols[shown % per_row].metric(label, v)
        shown += 1
    if shown == 0:
        st.caption(empty_msg)


# ================================================================
# 5-bucket 배지
# ================================================================

_BUCKET_COLOR = {
    "①": "#2E7D32", "②": "#1976D2", "③": "#F57C00",
    "③-H": "#E64A19", "④": "#C62828", "?": "#757575",
}
_BUCKET_LABEL = {
    "①": "현재 판매 가능", "②": "직구 대행 가능",
    "③": "미국 법인 기회", "③-H": "호르몬/성 제약",
    "④": "반입차단", "?": "미분류",
}


def bucket_badge(bucket: str) -> str:
    """5-bucket 배지 HTML. st.markdown(unsafe_allow_html=True) 로 렌더."""
    color = _BUCKET_COLOR.get(bucket, "#757575")
    label = _BUCKET_LABEL.get(bucket, "")
    return (f"<span style='background:{color}; color:white; padding:2px 8px; "
            f"border-radius:4px; font-size:0.85em; font-weight:bold;'>"
            f"{bucket} {label}</span>")


def render_bucket_block(bucket: str) -> None:
    """5-bucket 헤더 박스 (큰 사이즈)."""
    color = _BUCKET_COLOR.get(bucket, "#757575")
    label = _BUCKET_LABEL.get(bucket, "")
    st.markdown(
        f"<div style='padding:10px 14px; background:{color}; color:white; "
        f"border-radius:6px; text-align:center; font-weight:bold;'>"
        f"{bucket} {label}</div>",
        unsafe_allow_html=True,
    )


# ================================================================
# 섬네일 스타일 유틸
# ================================================================

def info_line(items: list[tuple[str, Any]]) -> str:
    """여러 key-value를 ` · ` 구분으로 한 줄에 합침."""
    out = []
    for k, v in items:
        if v in (None, "", "해당없음"):
            v = "—"
        out.append(f"**{k}**: {v}")
    return "  ·  ".join(out)
