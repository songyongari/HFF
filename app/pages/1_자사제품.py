"""자사 제품 — 바이오컴 11종 + 다빈치랩 21종 상세 뷰."""
from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from lib import (
    biocom_brand_list,
    find_brand,
    load_biocom_xlsx_ingredients,
    load_davinci_products,
    load_ingredient_master,
    lookup_rwmatr,
    norm,
    render_functionality,
    search_htfs_nutri,
    tag_functions,
)
from renderers import (
    foodhist_origin_table,
    material_table,
    nutri_metric_cards,
    product_header,
)
from theme import page

from fetchers.mfc_rpt import parse_raw_materials
from fetchers.nutri import CORE_NUTRIENTS
from fetchers.nutri_process import FIELD_LABELS as NP_LABELS

page(
    "자사 제품",
    caption="바이오컴 11종(건기식 8 + 일반식품 3) · 다빈치랩 구매대행 21종",
    icon="📦",
)

# 소스 선택
source = st.radio("브랜드",
                  ["바이오컴 (11종)", "다빈치랩 (21종)"],
                  horizontal=True)

if source.startswith("바이오컴"):
    brand = st.selectbox("제품 선택", biocom_brand_list())
    m = find_brand(brand)
    if not m:
        st.error("제품 데이터를 찾을 수 없습니다.")
        st.stop()
    is_davinci = False
else:
    davinci = load_davinci_products()
    brand = st.selectbox("제품 선택", [p["product"] for p in davinci])
    m = next((p for p in davinci if p["product"] == brand), None)
    if not m:
        st.error("제품 데이터를 찾을 수 없습니다.")
        st.stop()
    is_davinci = True

if is_davinci:
    st.markdown(f"### {brand}")
    st.caption("다빈치랩 · 미국 제조 · 현재 구매대행 판매")

    # 개요 메트릭
    ingredients = m.get("ingredients", [])
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("성분 수", len(ingredients))
    mc2.metric("섭취", m.get("usage", "—"))
    mc3.metric("식약처 기준 매핑", sum(1 for i in ingredients if isinstance(i.get("ratio"), (int, float))))

    tabs_dv = st.tabs([
        "🌿 성분 · 함량",
        "📏 식약처 기준 대비 배수",
        "🧪 내부 시드 매핑",
        "🇺🇸 미국 시장 대안",
    ])

    with tabs_dv[0]:
        df = pd.DataFrame([
            {
                "성분": ing["name"],
                "함량": ing.get("amount"),
                "단위": ing.get("unit"),
                "식약처 기준": str(ing["kfda_std"]) if ing.get("kfda_std") is not None else "—",
                "배수": (f"{ing.get('ratio'):.2f}"
                         if isinstance(ing.get("ratio"), (int, float)) else "—"),
            }
            for ing in ingredients
        ])
        st.dataframe(df, width="stretch", hide_index=True)

    with tabs_dv[1]:
        ratios = [(ing["name"], ing.get("ratio"))
                  for ing in ingredients
                  if isinstance(ing.get("ratio"), (int, float))]
        if ratios:
            df_r = pd.DataFrame(ratios, columns=["성분", "배수"]).set_index("성분").sort_values("배수", ascending=False)
            st.bar_chart(df_r)
            st.caption("식약처 1일 영양성분 기준치 대비 배수 (1 이상 = 기준치 초과)")
        else:
            st.caption("식약처 기준치 매핑된 성분이 없습니다.")

    with tabs_dv[2]:
        # 제품 성분을 내부 82 시드와 매핑 → 법적·검사·Phase 표 생성
        ings_master = load_ingredient_master()
        rows = []
        ingredient_names_raw = [i["name"] for i in ingredients]
        for ing_row in ingredients:
            raw_name = ing_row["name"]
            raw_norm = norm(raw_name)
            match = None
            for seed in ings_master:
                keys = [seed["name_ko"], seed["name_en"]] + (seed.get("aliases") or [])
                for k in keys:
                    if k and len(norm(k)) >= 3 and norm(k) in raw_norm:
                        match = seed
                        break
                if match: break
            rows.append({
                "라벨 성분": raw_name,
                "시드 매칭": match["name_ko"] if match else "—",
                "Bucket": match["legal"]["bucket"] if match else "",
                "국내 등재": match["legal"].get("korea_registered", "") if match else "",
                "OAT": "●" if match and match["tests"].get("oat") else "",
                "IgG": "●" if match and match["tests"].get("igg") else "",
                "호르몬": "●" if match and match["tests"].get("hormone") else "",
                "모발": "●" if match and match["tests"].get("hair") else "",
                "장내": "●" if match and match["tests"].get("microbiome") else "",
                "Phase": match["phase"]["phase"] if match else "",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption("라벨 성분 → 내부 82 시드 자동 매칭. 시드에 없으면 '—'로 표시.")

    with tabs_dv[3]:
        # 🇺🇸 수입 건기식 DB (4,380건)에서 이 다빈치 제품의 주성분 기반 대안 검색
        st.caption("이 다빈치 제품의 **주요 성분**을 키워드로 미국 시장 수입 건기식 DB(4,380건)에서 동일/유사 성분 제품을 찾습니다.")

        if not ingredients:
            st.info("이 제품의 성분 데이터가 비어있습니다.")
        else:
            # 상위 성분 (함량 큰 순서)
            sorted_ings = sorted(
                ingredients,
                key=lambda i: i.get("amount", 0) if isinstance(i.get("amount"), (int, float)) else 0,
                reverse=True,
            )
            candidate_keywords: list[str] = []
            for ing in sorted_ings:
                nm = str(ing.get("name", "")).strip()
                if nm and nm not in candidate_keywords:
                    candidate_keywords.append(nm)
                if len(candidate_keywords) >= 8:
                    break

            picked = st.multiselect(
                "검색할 성분 (함량 상위 자동 선택)",
                options=candidate_keywords,
                default=candidate_keywords[:3],
            )

            if picked:
                total_hits = []
                seen_rpt = set()
                for kw in picked:
                    hits = search_htfs_nutri(kw, mode="ingredient", limit=30)
                    for h in hits:
                        rpt = h.get("itemMnftrRptNo", "")
                        if rpt not in seen_rpt:
                            seen_rpt.add(rpt)
                            total_hits.append({**h, "_matched_kw": kw})

                if total_hits:
                    st.caption(f"✅ 매칭 {len(total_hits)}건 (중복 제거)")
                    df_alt = pd.DataFrame([
                        {
                            "매칭 성분": h["_matched_kw"],
                            "제품명": h.get("foodNm", ""),
                            "주성분(Lv4)": h.get("foodLv4Nm", ""),
                            "기준량": h.get("ntrtIgrdPvsnUnitAmnt", ""),
                            "제조사": h.get("mfrNm", ""),
                            "수입사": h.get("imptNm", ""),
                            "원산지": h.get("cooNm", ""),
                            "보고번호": h.get("itemMnftrRptNo", ""),
                        }
                        for h in total_hits
                    ])
                    st.dataframe(df_alt, width="stretch", hide_index=True, height=400)

                    from collections import Counter
                    origins = Counter(h.get("cooNm", "") for h in total_hits).most_common(5)
                    makers = Counter(h.get("mfrNm", "") for h in total_hits).most_common(5)
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**원산지 Top 5**")
                        for o, n in origins:
                            st.markdown(f"- {o or '—'}: {n}건")
                    with c2:
                        st.markdown("**제조사 Top 5**")
                        for mk, n in makers:
                            st.markdown(f"- {mk[:30] if mk else '—'}: {n}건")
                else:
                    st.info("선택한 성분 키워드로 수입 건기식 DB에서 매칭 없음.")
            else:
                st.caption("성분을 1개 이상 선택하세요.")
    st.stop()

cat = m.get("category")
st.markdown(f"### {brand}  \n<span style='color:gray'>분류: {cat}</span>", unsafe_allow_html=True)

tabs = st.tabs(["📋 개요", "💪 기능성", "🌿 원료", "🍎 영양", "⚠️ 안전성"])


def num(v) -> str:
    if v is None or v == "":
        return "—"
    return str(v).strip()


# ============ 탭 1: 개요 ============
with tabs[0]:
    if cat == "건기식":
        h = m.get("htfs", {})
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**정식 제품명**: {num(h.get('PRDUCT'))}")
            st.markdown(f"**제조사**: {num(h.get('ENTRPS'))}")
            st.markdown(f"**신고번호**: {num(h.get('STTEMNT_NO'))}")
            st.markdown(f"**등록일**: {num(h.get('REGIST_DT'))}")
        with col2:
            st.markdown(f"**유통기한**: {num(h.get('DISTB_PD'))}")
            st.markdown(f"**보관**: {num(h.get('PRSRV_PD'))}")
            st.markdown(f"**1일 섭취**: {num(h.get('SRV_USE'))}")
        st.markdown("**성상**")
        st.info(num(h.get("SUNGSANG")))
        hits = m.get("htfs_all_hits", [])
        if len(hits) > 1:
            with st.expander(f"⚠ 이 검색어로 식약처 DB에 여러 건 매칭됨 ({len(hits)}건) — 대체 후보"):
                for h2 in hits:
                    st.markdown(
                        f"- `{h2.get('STTEMNT_NO','')}` — {h2.get('PRDUCT','').strip()}  (제조: {h2.get('ENTRPS','')})"
                    )
    else:
        r = m.get("mfc_rpt", {}) or {}
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**정식 제품명**: {m.get('official_name', '—')}")
            st.markdown(f"**제조사**: {num(r.get('BSSH_NM'))}")
            st.markdown(f"**품목제조번호**: {num(m.get('report_no'))}")
            st.markdown(f"**품목유형**: {num(r.get('PRDLST_DCNM'))}")
        with col2:
            st.markdown(f"**보고일자**: {num(r.get('PRMS_DT'))}")
            st.markdown(f"**변경일자**: {num(r.get('CHNG_DT'))}")
            st.markdown(f"**인허가번호**: {num(r.get('LCNS_NO'))}")


# ============ 탭 2: 기능성 ============
with tabs[1]:
    if cat == "건기식":
        h = m.get("htfs", {})
        main_fn = h.get("MAIN_FNCTN") or ""
        st.markdown("##### 주된 기능성 (식약처 공식)")
        if main_fn.strip():
            render_functionality(main_fn)
            with st.expander("원문 보기"):
                st.code(main_fn, language=None)
        else:
            st.caption("—")
        tags = tag_functions(main_fn)
        if tags:
            st.markdown("##### 자동 태그")
            st.markdown("  ".join(f"`#{t}`" for t in tags))
        st.markdown("**기준·규격**")
        st.code(num(h.get("BASE_STANDARD")))
    else:
        st.markdown("일반식품은 '기능성 표시' 대신 **품목유형**과 **원재료 특성**으로 대표됩니다.")
        r = m.get("mfc_rpt", {}) or {}
        st.markdown(f"**품목유형**: `{r.get('PRDLST_DCNM','—')}`")
        raw = parse_raw_materials(r.get("RAWMTRL_NM", ""))
        # 원재료 중 기능성 원료 탐지
        fn_hits = []
        for rm in raw:
            entry = lookup_rwmatr(rm)
            if entry and "건강기능식품" in str(entry.get("LCLAS_NM", "")):
                fn_hits.append(rm)
        if fn_hits:
            st.markdown("**건강기능 원료 포함 (원재료 사전 매칭)**")
            st.write("• " + "  ·  ".join(fn_hits))


# ============ 탭 3: 원료 ============
with tabs[2]:
    # 바이오컴 제품 xlsx 성분·함량 (공통: 건기식·일반식품 모두)
    biocom_xlsx = load_biocom_xlsx_ingredients()
    matched_xlsx = None
    brand_keys = {brand.replace(" ", ""): brand}   # 엑셀과 검색어 공백 차이 대응
    for xlsx_brand, p in biocom_xlsx.items():
        if xlsx_brand.replace(" ", "") == brand.replace(" ", ""):
            matched_xlsx = p
            break
    if matched_xlsx:
        st.markdown(f"#### 📋 성분 함량표 (바이오컴 사내 DB · `최신_영양제 성분 DB.xlsx`)")
        if matched_xlsx.get("usage"):
            st.caption(f"섭취방법: {matched_xlsx['usage']}")
        df_amt = pd.DataFrame([
            {
                "성분": ing["name"],
                "함량": ing.get("amount"),
                "단위": ing.get("unit"),
                "식약처 기준": str(ing["kfda_std"]) if ing.get("kfda_std") is not None else "—",
                "배수": (f"{ing.get('ratio'):.2f}"
                         if isinstance(ing.get("ratio"), (int, float)) else str(ing.get("ratio") or "—")),
            }
            for ing in matched_xlsx.get("ingredients", [])
        ])
        st.dataframe(df_amt, width="stretch", hide_index=True)
        # 배수 차트
        ratios = [(ing["name"], ing.get("ratio"))
                  for ing in matched_xlsx.get("ingredients", [])
                  if isinstance(ing.get("ratio"), (int, float))]
        if ratios:
            with st.expander("식약처 1일 영양성분 기준치 대비 배수 차트"):
                df_r = pd.DataFrame(ratios, columns=["성분", "배수"]).set_index("성분").sort_values("배수", ascending=False)
                st.bar_chart(df_r)
        st.divider()

    if cat == "건기식":
        # 1차: C003 건기식 품목제조신고 (가장 완전)
        mfc = m.get("htfs_mfc") or {}
        if mfc.get("RAWMTRL_NM"):
            raws_c003 = [s.strip() for s in mfc["RAWMTRL_NM"].split(",") if s.strip()]
            material_table(raws_c003,
                           title=f"📋 원재료명 · 총 {len(raws_c003)}종 (C003 건기식 품목제조신고)")
            st.caption(f"제형: {mfc.get('PRDT_SHAP_CD_NM','—')}  |  성상: {mfc.get('DISPOS','—')}")
            st.divider()

        # 2차: 식품이력 — 원산지·GMO 보조
        rows = m.get("foodhist_rawmtrl", []) or []
        if rows:
            foodhist_origin_table(rows, title=f"🌏 원산지·GMO (식품이력 {len(rows)}건)")
        else:
            st.caption("식품이력(원산지·GMO) 등록 없음")
    else:
        # 일반식품 — C002 품목제조보고 원재료
        r = m.get("mfc_rpt", {}) or {}
        raw = parse_raw_materials(r.get("RAWMTRL_NM", ""))
        material_table(raw, title=f"📋 원재료명 · 총 {len(raw)}종 (C002 품목제조보고)")


# ============ 탭 4: 영양 ============
with tabs[3]:
    if cat == "건기식":
        # 건기식: xlsx 성분·함량 + 기준·규격 (BASE_STANDARD) 조합
        xlsx_ing = matched_xlsx.get("ingredients", []) if matched_xlsx else []
        h = m.get("htfs", {})

        if xlsx_ing:
            st.markdown("##### 🧾 제품 성분·함량 (사내 DB)")
            df_n = pd.DataFrame([
                {
                    "성분": ing["name"],
                    "함량": ing.get("amount"),
                    "단위": ing.get("unit"),
                    "식약처 기준": str(ing["kfda_std"]) if ing.get("kfda_std") is not None else "—",
                    "배수": (f"{ing.get('ratio'):.2f}"
                             if isinstance(ing.get("ratio"), (int, float)) else "—"),
                }
                for ing in xlsx_ing
            ])
            st.dataframe(df_n, width="stretch", hide_index=True)

            ratios = [(ing["name"], ing.get("ratio"))
                      for ing in xlsx_ing
                      if isinstance(ing.get("ratio"), (int, float))]
            if ratios:
                with st.expander("식약처 1일 영양성분 기준치 대비 배수 차트"):
                    df_r = pd.DataFrame(ratios, columns=["성분", "배수"]).set_index("성분").sort_values("배수", ascending=False)
                    st.bar_chart(df_r)
        else:
            st.caption("사내 성분 DB 매칭 없음")

        if h.get("BASE_STANDARD"):
            st.markdown("##### 📊 식약처 기준·규격 (건기식 신고)")
            st.code(h.get("BASE_STANDARD"), language=None)

        st.caption("참고: 국내 건기식은 공공 API에 영양성분표가 따로 없어 **사내 xlsx 성분·함량 + 식약처 신고 기준·규격**으로 구성합니다.")

    else:
        # 일반식품: 신규 API(nutri_process) 우선 → 기존 API(nutri) fallback → xlsx 보완
        nutri_new = m.get("nutri_process") or []
        nutri_old = m.get("nutri")

        from fetchers.nutri_process import FIELD_LABELS as NP_LABELS

        if nutri_new:
            st.markdown(f"##### 🍎 영양성분 (전국통합 가공식품 DB · {len(nutri_new)}건 중 대표)")
            n = nutri_new[0]
            c1, c2 = st.columns(2)
            c1.markdown(f"**1회 제공량**: {n.get('servSize','—')}")
            c1.markdown(f"**제품중량**: {n.get('foodSize','—')}")
            c2.markdown(f"**기준량**: {n.get('nutConSrtrQua','—')}")
            c2.markdown(f"**분류**: {n.get('foodLv3Nm','')} > {n.get('foodLv4Nm','')}")
            # 영양소 값이 있는 것만 메트릭 카드
            cols = st.columns(4)
            i = 0
            for code, label in NP_LABELS.items():
                v = n.get(code)
                if v not in (None, "", "0", 0, "0.00"):
                    cols[i % 4].metric(label, v)
                    i += 1
            if i == 0:
                st.caption("영양성분 값이 비어있습니다.")
            st.caption(f"제조: {n.get('mfrNm','—')}  |  기준일: {n.get('crtrYmd','—')}")

            if len(nutri_new) > 1:
                with st.expander(f"다른 등록 레코드 {len(nutri_new)-1}건"):
                    st.dataframe(pd.DataFrame(nutri_new[1:]), width="stretch", hide_index=True)

        elif nutri_old:
            # 기존 API 폴백
            n = nutri_old
            st.markdown(f"##### 🍎 영양성분 (식품영양성분DB)")
            st.markdown(f"**1회 섭취참고량**: {n.get('NUTRI_AMOUNT_SERVING', '—')}  |  "
                        f"**기준량**: {n.get('SERVING_SIZE', '—')}")
            st.markdown(f"**카테고리**: {n.get('FOOD_CAT1_NM','')} > {n.get('FOOD_CAT2_NM','')} > {n.get('FOOD_CAT3_NM','')}")
            rows = []
            for code, label in CORE_NUTRIENTS.items():
                v = n.get(code)
                if v not in (None, ""):
                    rows.append({"영양소": label, "값 (100g당)": str(v)})
            if rows:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption(f"최근 업데이트: {n.get('UPDATE_DATE', '—')}")
        else:
            st.warning("공공 영양성분 DB 두 곳 모두에 미등재 (최근 등록 제품은 DB 갱신 지연).")

        # 일반식품에도 xlsx 성분·함량 보완
        if matched_xlsx:
            st.markdown("##### 🧾 제품 성분·함량 (사내 DB)")
            df_n = pd.DataFrame([
                {
                    "성분": ing["name"],
                    "함량": ing.get("amount"),
                    "단위": ing.get("unit"),
                    "식약처 기준": str(ing["kfda_std"]) if ing.get("kfda_std") is not None else "—",
                    "배수": (f"{ing.get('ratio'):.2f}"
                             if isinstance(ing.get("ratio"), (int, float)) else "—"),
                }
                for ing in matched_xlsx.get("ingredients", [])
            ])
            st.dataframe(df_n, width="stretch", hide_index=True)


# ============ 탭 5: 안전성 ============
with tabs[4]:
    if cat == "건기식":
        h = m.get("htfs", {})
        st.markdown("**섭취 방법 / 일일섭취량**")
        st.info(num(h.get("SRV_USE")))
        st.markdown("**섭취 시 주의사항**")
        st.warning(num(h.get("INTAKE_HINT1")))
        st.markdown("**보관 방법**")
        st.code(num(h.get("PRSRV_PD")))
    else:
        st.info("일반식품은 식품안전나라 API에 섭취 주의사항이 별도 제공되지 않습니다. 포장 표기를 따라 주세요.")
        r = m.get("mfc_rpt", {}) or {}
        if r.get("ETQTY_XPORT_PRDLST_YN") == "O":
            st.caption("✈ 수출 가능 품목으로 등록됨")
