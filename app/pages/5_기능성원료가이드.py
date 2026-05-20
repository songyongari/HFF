"""기능성원료 가이드 — 식약처 I0760 분류 기반 정보성 카탈로그.

I0760 의 585건 원료를 4 카테고리(영양소·복합혼합·기능성원료·개별인정형)
탭으로 둘러보고, 항목 클릭 시 다음 정보를 모아 표시:
  - 분류·인정번호 (I0760)
  - 표준 효능 (HtfsInfoService03 의 MAIN_FNCTN 에서 집계)
  - 원재료 사전 매칭 (FoodRwmatrInfoService01)
  - 이 원료를 쓰는 시장 건기식 제품 상위 N개
"""
from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from lib import (
    load_htfs_cat_all,
    norm,
    parse_functionality,
    search_htfs_by_ingredient,
    search_rwmatr,
)
from theme import info_pill, page, section

page(
    "기능성원료 가이드",
    caption="식약처 I0760 분류 585종 · 표준 효능 · 사용 제품 · 학명 매칭",
    icon="📚",
)

_MIXED_SCLAS = {"혼합기능성원료", "복합영양소제품", "영양보충용제품"}

catalog = load_htfs_cat_all()
nutri_rows = [r for r in catalog
              if r.get("MLSFC_NM") == "영양소"
              and r.get("SCLAS_NM") not in _MIXED_SCLAS]
mixed_rows = [r for r in catalog
              if r.get("MLSFC_NM") == "영양소"
              and r.get("SCLAS_NM") in _MIXED_SCLAS]
func_rows  = [r for r in catalog if r.get("MLSFC_NM") == "기능성원료"]
indiv_rows = [r for r in catalog if r.get("MLSFC_NM") == "개별인정형 건강기능식품"]


# ===== 상세 패널 (선택된 원료) =====
def render_detail(name: str, source_row: dict) -> None:
    st.divider()

    # 헤더 + 분류 뱃지
    mlsfc = source_row.get("MLSFC_NM", "")
    sclas = source_row.get("SCLAS_NM", "")
    grp_cd = source_row.get("HELT_ITM_GRP_CD", "")

    if mlsfc == "개별인정형 건강기능식품":
        badge = info_pill("🟢 개별인정형", tone="success")
    elif mlsfc == "기능성원료":
        badge = info_pill("🌿 고시형 · 기능성원료", tone="info")
    elif sclas in _MIXED_SCLAS:
        badge = info_pill("🥣 고시형 · 복합/혼합", tone="info")
    else:
        badge = info_pill("🥗 고시형 · 영양소", tone="info")

    st.markdown(f"### 📋 {name}  {badge}", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**중분류**: {mlsfc or '—'}")
    c2.markdown(f"**세부분류**: {sclas or '—'}")
    c3.markdown(f"**식약처 코드**: `{grp_cd or '—'}`")

    # 이 원료를 쓰는 건기식 검색 (집계용)
    with st.spinner("관련 건기식 조회..."):
        products = search_htfs_by_ingredient(name, limit=200)

    # ===== 1. 표준 효능 =====
    st.markdown("##### 💪 표준 효능 (시장 건기식의 기능성 문구에서 집계)")
    benefit_counter: Counter[str] = Counter()
    nq = norm(name)
    for p in products:
        secs = parse_functionality(p.get("MAIN_FNCTN") or "")
        for sec in secs:
            ing = sec.get("ingredient") or ""
            if nq and nq in norm(ing):
                for b in sec.get("benefits", []):
                    benefit_counter[b] += 1

    if benefit_counter:
        # 상위 5개, 빈도 표시
        for benefit, n in benefit_counter.most_common(5):
            st.markdown(f"- {benefit}  <span style='color:#888; font-size:0.85em;'>"
                        f"({n}개 제품에서 표기)</span>",
                        unsafe_allow_html=True)
    else:
        st.caption("관련 효능 문구 자동 추출 실패 — 아래 사용 제품의 기능성 문구 참고.")

    # ===== 2. 원재료 표준사전 매칭 =====
    rw_hits = search_rwmatr(name, limit=3)
    if rw_hits:
        st.markdown("##### 🌱 원재료 표준사전 매칭")
        for rh in rw_hits:
            ko = rh.get("RPRSNT_RAWMTRL_NM", "")
            en = rh.get("ENG_NM", "")
            sc = rh.get("SCNM", "")
            part = rh.get("REGN_CD_NM", "")
            line = f"**{ko}**"
            if en:
                line += f"  ·  *{en}*"
            extras = []
            if sc: extras.append(f"학명 _{sc}_")
            if part: extras.append(f"부위 {part}")
            if extras:
                line += f"  <span style='color:#888;'>· {' · '.join(extras)}</span>"
            st.markdown(line, unsafe_allow_html=True)
    else:
        st.caption("원재료 표준사전 매칭 없음")

    # ===== 3. 사용 시장 제품 =====
    st.markdown(f"##### 📦 이 원료를 쓰는 시장 건기식 (총 {len(products)}건, 상위 10개)")
    if products:
        df = pd.DataFrame([
            {
                "제품명": str(p.get("PRDUCT", "")).strip(),
                "제조사": p.get("ENTRPS", ""),
                "신고번호": p.get("STTEMNT_NO", ""),
            }
            for p in products[:10]
        ])
        st.dataframe(df, width="stretch", hide_index=True, height=320)
    else:
        st.caption("매칭 제품 없음")

    # 성분 탐색 deep-link
    if st.button("🧪 성분 탐색에서 5-bucket 판정 보기",
                 key=f"goto_ing_{grp_cd or name}"):
        st.session_state["_ing_prefill"] = name
        st.switch_page("pages/4_성분탐색.py")


# ===== 카탈로그 렌더러 =====
def render_catalog(rows: list[dict], key_prefix: str) -> None:
    if not rows:
        st.caption("—"); return
    df = pd.DataFrame([
        {
            "원료명": r.get("HELT_ITM_GRP_NM", ""),
            "세부분류": r.get("SCLAS_NM", ""),
            "코드": r.get("HELT_ITM_GRP_CD", ""),
        }
        for r in rows
    ]).sort_values("원료명").reset_index(drop=True)

    flt = st.text_input("이 목록에서 필터",
                        key=f"{key_prefix}_filter",
                        placeholder="예) 비타민 · 오메가 · 추출물")
    if flt:
        df = df[df["원료명"].str.contains(flt, case=False, na=False)].reset_index(drop=True)

    event = st.dataframe(
        df, width="stretch", hide_index=True, height=360,
        on_select="rerun", selection_mode="single-row",
        key=f"{key_prefix}_df",
    )
    if event.selection and event.selection.rows:
        picked = df.iloc[event.selection.rows[0]]["원료명"]
        source_row = next((r for r in rows if r.get("HELT_ITM_GRP_NM") == picked), {})
        render_detail(picked, source_row)
    else:
        st.caption("👆 위 표에서 원료를 선택하면 표준 효능·사용 제품·학명 매칭이 표시됩니다.")


# ===== 4 탭 =====
tabs = st.tabs([
    f"🥗 고시형 · 영양소 ({len(nutri_rows)})",
    f"🥣 고시형 · 복합/혼합 ({len(mixed_rows)})",
    f"🌿 고시형 · 기능성원료 ({len(func_rows)})",
    f"🟢 개별인정형 ({len(indiv_rows)})",
])

with tabs[0]: render_catalog(nutri_rows, "nutri")
with tabs[1]: render_catalog(mixed_rows, "mixed")
with tabs[2]: render_catalog(func_rows,  "func")
with tabs[3]: render_catalog(indiv_rows, "indiv")
