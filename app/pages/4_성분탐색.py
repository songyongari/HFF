"""성분 탐색 — 5개 소스 동시 검색.

어떤 성분명을 입력해도 다음에서 찾는다:
  1. 원재료 표준사전 (18,542건) — 영문명·학명·부위·사용조건
  2. 건기식 제품 (44,296건) — 이 성분이 쓰인 제품 리스트
  3. 일반식품 (C002 API on-demand) — 품목제조보고 원재료 검색
  4. 수입 건기식 (4,380건) — 영양성분·원산지국
  5. 내부 심층 시드 (82개) — 법적·검사·Phase·대체 등 (매칭시만)
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import (
    BUCKET_COLOR,
    BUCKET_LABEL,
    check_blocked,
    classify_bucket,
    load_htfs_cat_all,
    load_htfs_nutri_all,
    load_ingredient_master,
    load_marketing_rules,
    load_substitutes,
    norm,
    search_htfs_by_ingredient,
    search_htfs_nutri,
    search_rwmatr,
)
from renderers import bucket_badge, render_bucket_block
from theme import section

from fetchers.mfc_rpt_live import search_by_raw_material

from theme import page

page(
    "성분 탐색",
    caption="5 소스 동시 검색 · 5-bucket 자동 판정 · 반입차단 실시간 체크",
    icon="🧪",
)

# ============ 검색 ============
# 카탈로그·다른 페이지에서 넘어온 prefill 처리 (1회 소비)
_prefill = st.session_state.pop("_ing_prefill", None)
if _prefill:
    st.session_state["ing_query"] = _prefill

col_q, col_go = st.columns([5, 1])
with col_q:
    query = st.text_input(
        "성분명",
        placeholder="예) 마그네슘 · NMN · 비타민C · 콜라겐 · 프로바이오틱스 · 커큐민 · Ashwagandha",
        label_visibility="collapsed",
        key="ing_query",
    )
with col_go:
    search_c002 = st.checkbox("C002 조회", value=True,
                               help="일반식품 품목제조보고 API를 실시간 호출 (3~10초 소요)")

if not query:
    st.info("위에 성분명을 입력하거나, 아래 카탈로그에서 선택하세요.")

    # ============ 기능성 원료 카탈로그 (I0760) ============
    section("📚 기능성 원료 카탈로그", caption="식약처 I0760 분류 · 행 클릭 시 자동 검색")
    catalog = load_htfs_cat_all()
    # 영양소(MLSFC_NM)를 SCLAS_NM 기준으로 단일/복합 분리
    _MIXED_SCLAS = {"혼합기능성원료", "복합영양소제품", "영양보충용제품"}
    nutri_rows = [r for r in catalog
                  if r.get("MLSFC_NM") == "영양소"
                  and r.get("SCLAS_NM") not in _MIXED_SCLAS]
    mixed_rows = [r for r in catalog
                  if r.get("MLSFC_NM") == "영양소"
                  and r.get("SCLAS_NM") in _MIXED_SCLAS]
    func_rows  = [r for r in catalog if r.get("MLSFC_NM") == "기능성원료"]
    indiv_rows = [r for r in catalog if r.get("MLSFC_NM") == "개별인정형 건강기능식품"]

    cat_tabs = st.tabs([
        f"🥗 고시형 · 영양소 ({len(nutri_rows)})",
        f"🥣 고시형 · 복합/혼합 ({len(mixed_rows)})",
        f"🌿 고시형 · 기능성원료 ({len(func_rows)})",
        f"🟢 개별인정형 ({len(indiv_rows)})",
    ])

    def _render_catalog(rows, key_prefix):
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
        flt = st.text_input("이 목록에서 필터", key=f"{key_prefix}_filter",
                            placeholder="예) 비타민 · 오메가 · 추출물")
        if flt:
            df = df[df["원료명"].str.contains(flt, case=False, na=False)].reset_index(drop=True)
        event = st.dataframe(
            df, width="stretch", hide_index=True, height=420,
            on_select="rerun", selection_mode="single-row",
            key=f"{key_prefix}_df",
        )
        if event.selection and event.selection.rows:
            picked = df.iloc[event.selection.rows[0]]["원료명"]
            st.session_state["_ing_prefill"] = picked
            st.rerun()

    with cat_tabs[0]: _render_catalog(nutri_rows, "cat_nutri")
    with cat_tabs[1]: _render_catalog(mixed_rows, "cat_mixed")
    with cat_tabs[2]: _render_catalog(func_rows, "cat_func")
    with cat_tabs[3]: _render_catalog(indiv_rows, "cat_indiv")
    st.stop()

# ============ 최우선: 5-bucket 종합 판정 ============
verdict = classify_bucket(query)
vb = verdict["bucket"]
color = BUCKET_COLOR.get(vb, "#757575")
src_label = {
    "official_api": "✓ 식약처 공식 API 기반",
    "internal_seed": "✓ 내부 시드 수기 검증",
    "inferred": "⚠ 추정 — 표기 차이로 인한 미매칭 가능",
}.get(verdict.get("source"), "")

st.markdown(
    f"<div style='padding:14px 18px; background:{color}; color:white; border-radius:8px; "
    f"margin-bottom:12px;'>"
    f"<div style='font-size:1.4em; font-weight:bold;'>{vb} — {verdict['label']}</div>"
    f"<div style='font-size:0.9em; margin-top:6px;'>{src_label}</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# 판정 근거
with st.expander("판정 근거 자세히", expanded=(not verdict["confident"])):
    for r in verdict["reasons"]:
        st.markdown(f"- {r}")
    if verdict.get("blocked_entry"):
        be = verdict["blocked_entry"]
        st.markdown("---")
        st.markdown(f"**반입차단 상세**: {be.get('RAW_IRDNT_NM','')} / {be.get('RAW_IRDNT_ENG_NM','') or '—'}")
        st.caption(f"지정일: {be.get('APPN_DT','')} · 근거: {(be.get('APPN_RSN') or '')[:200]}")
    if verdict.get("registered_entry"):
        re_ = verdict["registered_entry"]
        st.markdown("---")
        st.markdown(f"**원재료 사전 등재**: {re_.get('RPRSNT_RAWMTRL_NM','')}")
        st.caption(f"분류: {re_.get('LCLAS_NM','')} > {re_.get('MLSFC_NM','')}"
                   f" · 영문: {re_.get('ENG_NM','')} · 학명: {(re_.get('SCNM') or '')[:60]}")

# ============ 4개 소스 동시 검색 ============
ings = load_ingredient_master()
rules = load_marketing_rules()
subs = load_substitutes()

# Source 1: 원재료 사전
rwmatr_hits = search_rwmatr(query, limit=30)

# Source 2: 건기식 DB
htfs_hits = search_htfs_by_ingredient(query, limit=100)

# Source 3: 일반식품 C002 (on-demand, toggle)
c002_hits: list[dict] = []
if search_c002:
    with st.spinner("일반식품 품목제조보고 API 호출 중..."):
        try:
            c002_hits = search_by_raw_material(query, limit=100) or []
        except Exception as e:
            st.caption(f"⚠️ C002 호출 실패: {e}")

# Source 4: 수입 건기식
imp_hits = search_htfs_nutri(query, mode="ingredient", limit=100)

# Source 5: 내부 시드 (정확 매칭)
qn = norm(query)
seed_hits = [
    i for i in ings
    if any(qn in norm(f) for f in
           [i.get("name_ko"), i.get("name_en")] + (i.get("aliases") or []))
]

# ============ 5 소스 검색 결과 요약 ============
section(f"'{query}' 검색 결과")
sc1, sc2, sc3, sc4, sc5 = st.columns(5)
sc1.metric("📗 원재료 사전", len(rwmatr_hits))
sc2.metric("🟢 건기식", len(htfs_hits))
sc3.metric("🟡 일반식품", len(c002_hits) if search_c002 else "—")
sc4.metric("🇺🇸 수입 건기식", len(imp_hits))
sc5.metric("📋 내부 시드", len(seed_hits))

# ============ 탭 구성 ============
tabs = st.tabs([
    f"📋 내부 심층 ({len(seed_hits)})",
    f"📗 원재료 사전 ({len(rwmatr_hits)})",
    f"🟢 건기식 제품 ({len(htfs_hits)})",
    f"🟡 일반식품 ({len(c002_hits)})",
    f"🇺🇸 수입 건기식 ({len(imp_hits)})",
])

# ---------- 탭 1: 내부 심층 시드 ----------
with tabs[0]:
    if not seed_hits:
        st.info("내부 시드(82개 성분)에서 매칭되는 항목이 없습니다. "
                "다른 탭(건기식·일반식품·원재료사전)에서 확인하세요.")
    else:
        # 매칭된 시드 선택
        if len(seed_hits) > 1:
            picked = st.radio("선택",
                              [f"{i['name_ko']} ({i['name_en']})" for i in seed_hits],
                              horizontal=True)
            idx = [f"{i['name_ko']} ({i['name_en']})" for i in seed_hits].index(picked)
            ing = seed_hits[idx]
        else:
            ing = seed_hits[0]

        # 헤더
        ch1, ch2, ch3 = st.columns([2, 1, 1])
        with ch1:
            st.markdown(f"### {ing['name_ko']}")
            st.caption(f"{ing['name_en']}")
            if ing.get("aliases"):
                st.caption("이명: " + " · ".join(ing["aliases"]))
        with ch2:
            render_bucket_block(ing.get("legal", {}).get("bucket", "?"))
        with ch3:
            status = ing.get("supplier", {}).get("davinci_status", "—")
            st.markdown(
                f"<div style='padding:8px 12px; border:1px solid #ddd; border-radius:6px; "
                f"text-align:center;'><div style='font-size:1.8em'>{status}</div>"
                f"<div style='font-size:0.85em'>다빈치랩</div></div>",
                unsafe_allow_html=True,
            )

        if ing.get("legal", {}).get("hormone_sensitive"):
            st.warning("⚠️ 표시광고 민감 — 호르몬/성 관련 표현 주의")

        # 상세 표
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("##### 📋 기본")
            st.markdown(f"- **카테고리**: {ing.get('category','—')}")
            st.markdown(f"- **국내 등재**: {ing['legal'].get('korea_registered','—')}")
            st.markdown(f"- **Phase**: {ing['phase'].get('phase', '—')} / 긴급도 {ing['phase'].get('urgency','—')}")
            if ing.get("note"):
                st.markdown(f"- **비고**: {ing['note']}")
        with cc2:
            st.markdown("##### 🧬 5종 검사 연결")
            test_labels = {"oat": "OAT", "igg": "IgG", "hormone": "호르몬",
                           "hair": "모발", "microbiome": "장내세균"}
            for k, label in test_labels.items():
                v = ing.get("tests", {}).get(k)
                icon = "✅" if v else "—"
                desc = v if v else ""
                st.markdown(f"- {icon} **{label}** {desc}")

        # 다빈치 제품
        dav_products = ing.get("supplier", {}).get("davinci_products", [])
        biocom_in = ing.get("products", {}).get("biocom_used_in", [])
        davinci_in = ing.get("products", {}).get("davinci_used_in", [])
        if dav_products or biocom_in or davinci_in:
            st.markdown("##### 📦 자사·다빈치 보유 제품")
            if dav_products:
                st.markdown("**다빈치 단독/대표**: " + " · ".join(dav_products))
            if biocom_in:
                st.markdown("**바이오컴 제품에 포함**: " + " · ".join(biocom_in))
            if davinci_in:
                st.markdown("**다빈치 제품에 포함**: " + " · ".join(davinci_in))

        # 대체 성분
        alt = ing.get("substitutes", {}).get("alternatives_for_blocked", [])
        is_sub = ing.get("substitutes", {}).get("is_substitute_of", [])
        if alt or is_sub:
            st.markdown("##### 🔄 대체 성분")
            if alt:
                st.markdown(f"- 이 성분이 제약될 때 대안: {' · '.join(alt)}")
            for s in is_sub:
                st.markdown(f"- **{s['for']}** 의 한국 합법 대체로 사용 _({s['reason']})_")

# ---------- 탭 2: 원재료 표준 사전 ----------
with tabs[1]:
    if not rwmatr_hits:
        st.info("원재료 표준 사전(18,542건)에서 매칭 없음.")
    else:
        st.caption(f"식약처 식품원재료 표준사전에서 {len(rwmatr_hits)}건 매칭")
        df = pd.DataFrame([
            {
                "표준명": r.get("RPRSNT_RAWMTRL_NM", ""),
                "이명": r.get("RAWMTRL_NCKNM") or "—",
                "영문명": r.get("ENG_NM", "") or "—",
                "학명": (r.get("SCNM") or "")[:60],
                "분류": r.get("LCLAS_NM", ""),
                "세분류": r.get("MLSFC_NM", ""),
                "부위": r.get("REGN_CD_NM") or "—",
                "사용조건": (r.get("USE_CND_NM") or "")[:60],
            }
            for r in rwmatr_hits
        ])
        st.dataframe(df, width="stretch", hide_index=True, height=400)

# ---------- 탭 3: 건기식 제품 ----------
with tabs[2]:
    if not htfs_hits:
        st.info("건기식 DB(44,296건)에서 매칭 없음.")
    else:
        st.caption(f"이 성분/키워드가 **제품명·기능성·성상 기준**에 등장하는 건기식 {len(htfs_hits)}건 "
                   "(상위 100건 표시)")
        df = pd.DataFrame([
            {
                "제품명": str(it.get("PRDUCT", "")).strip(),
                "제조사": it.get("ENTRPS", ""),
                "신고번호": it.get("STTEMNT_NO", ""),
                "등록일": it.get("REGIST_DT", ""),
                "기능성 요약": (it.get("MAIN_FNCTN") or "").replace("\n", " ")[:120],
            }
            for it in htfs_hits
        ])
        st.dataframe(df, width="stretch", hide_index=True, height=400)

        # 제조사 Top
        from collections import Counter
        makers = Counter(str(it.get("ENTRPS", "")) for it in htfs_hits).most_common(10)
        with st.expander(f"제조사 Top 10 (매칭 제품 수)"):
            for m, c in makers:
                st.markdown(f"- **{m}**: {c}건")

# ---------- 탭 4: 일반식품 C002 ----------
with tabs[3]:
    if not search_c002:
        st.caption("상단의 'C002 조회' 체크를 켜면 일반식품 1M+건 API 호출.")
    elif not c002_hits:
        st.info("일반식품 품목제조보고에서 이 원재료명 매칭 없음.")
    else:
        st.caption(f"식품안전나라 C002에서 원재료명에 이 성분이 포함된 일반식품 {len(c002_hits)}건")
        df = pd.DataFrame([
            {
                "품목명": r.get("PRDLST_NM", ""),
                "업소": r.get("BSSH_NM", ""),
                "품목유형": r.get("PRDLST_DCNM", ""),
                "보고번호": r.get("PRDLST_REPORT_NO", ""),
                "보고일자": r.get("PRMS_DT", ""),
                "원재료(앞 100자)": (r.get("RAWMTRL_NM") or "")[:100],
            }
            for r in c002_hits
        ])
        st.dataframe(df, width="stretch", hide_index=True, height=400)
        from collections import Counter
        cats = Counter(str(r.get("PRDLST_DCNM", "")) for r in c002_hits).most_common(10)
        with st.expander(f"품목유형 Top 10"):
            for c, n in cats:
                st.markdown(f"- **{c}**: {n}건")

# ---------- 탭 5: 수입 건기식 ----------
with tabs[4]:
    if not imp_hits:
        st.info("수입 건기식 DB(4,380건)에서 매칭 없음.")
    else:
        st.caption(f"제품명/분류에 이 성분이 포함된 수입 건기식 {len(imp_hits)}건")
        df = pd.DataFrame([
            {
                "제품명": r.get("foodNm", ""),
                "세분류": r.get("foodLv4Nm") or r.get("foodLv5Nm", ""),
                "기준량": r.get("ntrtIgrdPvsnUnitAmnt", ""),
                "제조사": r.get("mfrNm", ""),
                "수입사": r.get("imptNm", ""),
                "원산지": r.get("cooNm", ""),
                "보고번호": r.get("itemMnftrRptNo", ""),
            }
            for r in imp_hits
        ])
        st.dataframe(df, width="stretch", hide_index=True, height=400)
        from collections import Counter
        origins = Counter(str(r.get("cooNm", "")) for r in imp_hits).most_common(5)
        with st.expander("원산지 Top 5"):
            for o, n in origins:
                st.markdown(f"- **{o}**: {n}건")
