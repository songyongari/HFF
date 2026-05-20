"""바이오컴 건기식 통합 정보 탐색기 — 홈."""
from __future__ import annotations

import streamlit as st

from lib import (
    check_blocked,
    load_blocklist,
    load_davinci_products,
    load_htfs_all,
    load_htfs_nutri_all,
    load_ingredient_master,
    load_master,
    load_rwmatr_all,
    norm,
    search_htfs_by_ingredient,
    search_htfs_by_product_name,
    search_htfs_nutri,
    search_rwmatr,
)
from theme import COLOR, bucket_badge, nav_card, page, section

page(
    "바이오컴 건기식 탐색기",
    caption="식약처 공공 API · 연구 문서 · 브랜드 DB를 한 곳에서 조회 — 탐색 전용",
    icon="🧬",
)

# 데이터 로드
ings = load_ingredient_master()
biocom = load_master()
davinci = load_davinci_products()
htfs = load_htfs_all()
rwmatr = load_rwmatr_all()
htfs_nutri = load_htfs_nutri_all()
blocklist = load_blocklist()

# ============ Hero: 빠른 검색 (성분 + 제품) ============
section("🔎 빠른 검색",
        caption="성분명이든 제품명이든 · 반입차단 자동 체크")

q = st.text_input(
    "검색",
    placeholder="예) NMN · 비타민C · 바이오 밸런스 · 엔피케이 · Ashwagandha",
    label_visibility="collapsed",
)

if q:
    qn = norm(q)

    # ---- 반입차단 알림 (최우선) ----
    blk = check_blocked(q)
    if blk:
        st.error(
            f"🚫 **반입차단 지정** — "
            f"{blk.get('RAW_IRDNT_NM','')} / {blk.get('RAW_IRDNT_ENG_NM','') or '—'} "
            f"(지정일 {blk.get('APPN_DT','')})"
        )

    # ---- 성분 매칭 ----
    seed_hits = [
        i for i in ings
        if any(qn in norm(f or "")
               for f in [i.get("name_ko"), i.get("name_en")] + (i.get("aliases") or []))
    ]
    rw_hits = search_rwmatr(q, limit=30)
    ingr_mkt_hits = search_htfs_by_ingredient(q, limit=200)
    ingr_imp_hits = search_htfs_nutri(q, mode="ingredient", limit=30)

    # ---- 제품 매칭 ----
    biocom_hits = [m for m in biocom if qn in norm(m.get("brand", ""))]
    davinci_hits = [p for p in davinci if qn in norm(p.get("product", ""))]
    prod_mkt_hits = search_htfs_by_product_name(q, limit=100)
    prod_imp_hits = search_htfs_nutri(q, mode="foodNm", limit=30)

    # ---- 성분 섹션 ----
    st.markdown("##### 🧪 성분")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("내부 시드", len(seed_hits))
    c2.metric("원재료 사전", len(rw_hits))
    c3.metric("건기식 기능성", f"{len(ingr_mkt_hits):,}")
    c4.metric("수입 건기식", len(ingr_imp_hits))

    if seed_hits:
        for h in seed_hits[:4]:
            b = h.get("legal", {}).get("bucket", "?")
            dav = h.get("supplier", {}).get("davinci_status", "—")
            st.markdown(
                f"- {bucket_badge(b, small=True)} "
                f"**{h['name_ko']}** <span style='color:{COLOR['muted']};'>"
                f"({h['name_en']}) · {dav} · {h.get('category', '')}</span>",
                unsafe_allow_html=True,
            )

    # ---- 제품 섹션 ----
    st.markdown("##### 📦 제품")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("바이오컴 자사", len(biocom_hits))
    p2.metric("다빈치랩", len(davinci_hits))
    p3.metric("건기식 제품명", f"{len(prod_mkt_hits):,}")
    p4.metric("수입 건기식 제품", len(prod_imp_hits))

    prod_previews = []
    for m in biocom_hits[:3]:
        prod_previews.append(
            f"- 🏷 **{m['brand']}** "
            f"<span style='color:{COLOR['muted']};'>· 바이오컴 · {m.get('category','')}</span>"
        )
    for p in davinci_hits[:3]:
        prod_previews.append(
            f"- 🇺🇸 **{p['product']}** "
            f"<span style='color:{COLOR['muted']};'>· 다빈치랩</span>"
        )
    for h in prod_mkt_hits[:4]:
        prod_previews.append(
            f"- 🟢 **{str(h.get('PRDUCT','')).strip()}** "
            f"<span style='color:{COLOR['muted']};'>· {h.get('ENTRPS','')}</span>"
        )
    for h in prod_imp_hits[:3]:
        prod_previews.append(
            f"- 🇺🇸 **{h.get('foodNm','')}** "
            f"<span style='color:{COLOR['muted']};'>· {h.get('mfrNm','')[:30]}</span>"
        )
    for line in prod_previews[:8]:
        st.markdown(line, unsafe_allow_html=True)

    # ---- 상세 페이지 링크 ----
    total_ing = len(seed_hits) + len(rw_hits) + len(ingr_mkt_hits) + len(ingr_imp_hits)
    total_prod = len(biocom_hits) + len(davinci_hits) + len(prod_mkt_hits) + len(prod_imp_hits)
    if total_ing or total_prod:
        link1, link2 = st.columns(2)
        with link1:
            st.page_link("pages/4_성분탐색.py",
                         label="🧪 성분 탐색에서 상세", use_container_width=True)
        with link2:
            st.page_link("pages/2_시장제품검색.py",
                         label="🏷️ 시장 제품 검색에서 상세", use_container_width=True)
    else:
        st.caption(f"'{q}' — 모든 소스에서 매칭 없음")

st.divider()

# ============ Navigation ============
section("🗂 탐색 영역")

nc1, nc2 = st.columns(2)
with nc1:
    nav_card(
        "📦 자사 제품",
        f"바이오컴 {len(biocom)}종 · 다빈치랩 {len(davinci)}종 · "
        "기능성·원료·영양·안전성 통합",
        "pages/1_자사제품.py",
    )
    nav_card(
        "🧪 성분 탐색",
        "5-bucket 자동 판정 · 18K 원재료 사전 · 44K 건기식 · 1M 일반식품 · 4.4K 수입 건기식",
        "pages/4_성분탐색.py",
    )
with nc2:
    nav_card(
        "🏷️ 시장 제품 검색",
        f"건기식 {len(htfs):,} · 일반식품 1M+ · 수입 건기식 {len(htfs_nutri):,} 통합 검색",
        "pages/2_시장제품검색.py",
    )
    nav_card(
        "🧮 기능성 탐색",
        "11개 기능성 태그 × 바이오컴·시장·성분 매트릭스",
        "pages/3_기능성매트릭스.py",
    )

st.divider()

# ============ 현황 메트릭 ============
section("📊 데이터 현황")

m1, m2, m3, m4 = st.columns(4)
m1.metric("자사 제품", f"{len(biocom) + len(davinci)}종")
m2.metric("성분 시드", f"{len(ings)}")
m3.metric("반입차단", f"{len(blocklist)}")
m4.metric("연결 API", "10")

# ============ 데이터 출처 ============
with st.expander("연결된 공공 API 10종"):
    st.markdown("""
| API | 건수 | 용도 |
|---|---:|---|
| HtfsInfoService03 | 44,296 | 건기식 제품 정보·기능성 |
| FoodHistInfoService03 | 8.3M | 식품이력 원재료·원산지·GMO |
| FoodRwmatrInfoService01 | 18,542 | 원재료 표준 사전 |
| FoodNtrCpntDbInfo02 | 275,856 | 일반식품 영양성분 |
| tn_pubr_health_functional_food_nutrition | 4,380 | 수입 건기식 영양 |
| tn_pubr_nutri_process_info | 753,215 | 가공식품 영양 통합 |
| BlockRawIrdntInfoService | 314 | 반입차단 원료·성분 |
| I0760 (식품안전나라) | 585 | 건기식 원료 분류 |
| C002 (식품안전나라) | 1M+ | 품목제조보고 원재료 |
| C003 (식품안전나라) | 44K+ | 건기식 품목제조신고 |
""")
