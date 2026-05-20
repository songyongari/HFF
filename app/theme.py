"""디자인 시스템 — 색·패턴·공용 컴포넌트.

모든 페이지는 이 모듈을 통해 일관된 헤더·배지·섹션을 사용한다.
"""
from __future__ import annotations

import streamlit as st


# ================================================================
# Color tokens
# ================================================================
COLOR = {
    # 5-bucket 법적 분류
    "bucket_1":   "#2E7D32",  # 녹색 — 판매 가능
    "bucket_2":   "#1976D2",  # 파랑 — 직구 가능
    "bucket_3":   "#F57C00",  # 주황 — 기회
    "bucket_3h":  "#E64A19",  # 진주황 — 호르몬 제약
    "bucket_4":   "#C62828",  # 빨강 — 차단
    "bucket_q":   "#757575",  # 회색 — 미분류

    # 의미 색
    "primary":    "#1e3a8a",  # 네이비 — 주요 헤더
    "muted":      "#6B7280",  # 서브 텍스트
    "surface":    "#F9FAFB",  # 박스 배경
    "border":     "#E5E7EB",  # 구분선
    "success":    "#10B981",
    "warning":    "#F59E0B",
    "danger":     "#EF4444",
    "info":       "#3B82F6",
}

BUCKET_COLOR = {
    "①": COLOR["bucket_1"],
    "②": COLOR["bucket_2"],
    "③": COLOR["bucket_3"],
    "③-H": COLOR["bucket_3h"],
    "④": COLOR["bucket_4"],
    "?": COLOR["bucket_q"],
}
BUCKET_LABEL = {
    "①": "현재 판매 가능",
    "②": "직구 대행 가능",
    "③": "미국 법인 기회",
    "③-H": "호르몬/성 제약",
    "④": "반입차단",
    "?": "미분류",
}


# ================================================================
# Page header
# ================================================================

def page(title: str, caption: str | None = None, *,
         icon: str = "", page_title: str | None = None) -> None:
    """모든 페이지 상단에 호출 — 일관된 헤더 + set_page_config.

    icon: 제목 앞 이모지 (예: "🧪")
    page_title: 브라우저 탭 제목 (기본: title)
    """
    st.set_page_config(
        page_title=page_title or title,
        page_icon=icon or "🧬",
        layout="wide",
    )
    if icon:
        st.markdown(f"## {icon}  {title}")
    else:
        st.markdown(f"## {title}")
    if caption:
        st.markdown(
            f"<div style='color:{COLOR['muted']}; margin-top:-10px; "
            f"margin-bottom:14px; font-size:0.9em;'>{caption}</div>",
            unsafe_allow_html=True,
        )


# ================================================================
# Section headers (단일 스타일)
# ================================================================

def section(title: str, *, caption: str | None = None) -> None:
    """페이지 내 섹션 소제목 — `##### title` + optional caption."""
    st.markdown(f"##### {title}")
    if caption:
        st.markdown(
            f"<div style='color:{COLOR['muted']}; margin-top:-8px; "
            f"margin-bottom:8px; font-size:0.85em;'>{caption}</div>",
            unsafe_allow_html=True,
        )


# ================================================================
# Badges
# ================================================================

def bucket_badge(bucket: str, *, small: bool = False) -> str:
    """5-bucket 배지 HTML. unsafe_allow_html=True 로 렌더."""
    color = BUCKET_COLOR.get(bucket, COLOR["bucket_q"])
    label = BUCKET_LABEL.get(bucket, "")
    size = "0.75em" if small else "0.85em"
    pad = "2px 6px" if small else "3px 8px"
    return (f"<span style='background:{color}; color:white; padding:{pad}; "
            f"border-radius:4px; font-size:{size}; font-weight:600;'>"
            f"{bucket} {label}</span>")


def bucket_block(bucket: str, label_override: str | None = None,
                  *, extra: str = "") -> None:
    """큰 버킷 헤더 박스 (성분 상세 등에서 사용)."""
    color = BUCKET_COLOR.get(bucket, COLOR["bucket_q"])
    label = label_override or BUCKET_LABEL.get(bucket, "")
    extra_html = (f"<div style='font-size:0.85em; margin-top:4px; opacity:0.9;'>{extra}</div>"
                  if extra else "")
    st.markdown(
        f"<div style='padding:12px 16px; background:{color}; color:white; "
        f"border-radius:8px; margin-bottom:10px;'>"
        f"<div style='font-size:1.1em; font-weight:bold;'>{bucket}  {label}</div>"
        f"{extra_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def info_pill(text: str, tone: str = "info") -> str:
    """작은 정보 pill. tone: info · success · warning · danger · muted."""
    bg = {
        "info": COLOR["info"],
        "success": COLOR["success"],
        "warning": COLOR["warning"],
        "danger": COLOR["danger"],
        "muted": COLOR["muted"],
    }.get(tone, COLOR["muted"])
    return (f"<span style='background:{bg}; color:white; padding:2px 8px; "
            f"border-radius:10px; font-size:0.75em; margin-right:4px;'>{text}</span>")


# ================================================================
# Layout helpers
# ================================================================

def metric_row(items: list[tuple[str, str]]) -> None:
    """간단 메트릭 한 줄 (2~5개 권장). items: [(label, value), ...]"""
    cols = st.columns(len(items))
    for i, (label, value) in enumerate(items):
        cols[i].metric(label, value)


def nav_card(title: str, description: str, page_path: str,
             icon: str = "→") -> None:
    """홈 네비게이션 카드."""
    with st.container(border=True):
        st.markdown(f"### {title}")
        st.markdown(
            f"<div style='color:{COLOR['muted']}; font-size:0.88em; "
            f"margin-bottom:8px;'>{description}</div>",
            unsafe_allow_html=True,
        )
        st.page_link(page_path, label=f"열기 {icon}")
