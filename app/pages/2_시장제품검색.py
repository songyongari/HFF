"""시장 제품 검색 — 건기식 44K + 일반식품 1M 통합 조회.

탭 1: 건기식 (HtfsInfoService03 캐시 44,296건)
탭 2: 일반식품 (C002 품목제조보고 on-demand)

선택 시 상세 카드 (여러 API 조합).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import (
    load_htfs_all,
    load_htfs_nutri_all,
    lookup_rwmatr,
    norm,
    render_functionality,
    search_htfs_by_ingredient,
    search_htfs_by_product_name,
    search_htfs_nutri,
    tag_functions,
)
from renderers import (
    foodhist_origin_table,
    material_table,
    nutri_metric_cards,
)

from fetchers.htfs_nutri import FIELD_LABELS as NUTRI_LABELS

from fetchers.foodhist import fetch_by_product_name as foodhist_by_name
from fetchers.htfs_mfc import (
    fetch_by_report_no as htfs_mfc_by_rpt,
    parse_raw_materials as htfs_mfc_parse,
)
from fetchers.mfc_rpt import (
    fetch_by_report_no as mfc_by_report_no,
    parse_raw_materials,
    search_by_company as mfc_by_company,
    search_by_product_name as mfc_by_name,
)
from fetchers.nutri import CORE_NUTRIENTS, search as nutri_search
from fetchers.nutri_process import (
    FIELD_LABELS as NP_LABELS,
    search_by_report_no as nutri_process_by_rpt,
)
from theme import page

_nutri_count = len(load_htfs_nutri_all())
page(
    "시장 제품 검색",
    caption=f"건기식 44,296 · 일반식품 1M+ · 수입 건기식 {_nutri_count:,} 통합",
    icon="🏷️",
)

main_tabs = st.tabs([
    "🟢 건기식 (44,296건)",
    "🟡 일반식품 (1M+)",
    f"🇺🇸 수입 건기식 ({_nutri_count:,}건)",
])


# ==============================================================
# 탭 1: 건기식
# ==============================================================
with main_tabs[0]:
    st.markdown("##### 건강기능식품 DB")
    col1, col2 = st.columns([3, 2])
    with col1:
        mode = st.radio("검색 축", ["제품명", "원료/기능성/키워드", "제조사"],
                        horizontal=True, key="htfs_mode")
    with col2:
        q = st.text_input("검색어", placeholder="예) 바이오밸런스 / 은행잎 / 엔피케이",
                          key="htfs_q")

    if q:
        if mode == "제품명":
            results = search_htfs_by_product_name(q, limit=300)
        elif mode == "원료/기능성/키워드":
            results = search_htfs_by_ingredient(q, limit=300)
        else:  # 제조사
            qn = norm(q)
            results = [it for it in load_htfs_all() if qn in norm(it.get("ENTRPS", ""))][:300]

        st.caption(f"매칭 **{len(results)}건** (상위 300 표시)")

        if results:
            # 테이블 요약
            df = pd.DataFrame([
                {
                    "선택": False,
                    "제품명": str(it.get("PRDUCT", "")).strip(),
                    "제조사": it.get("ENTRPS", ""),
                    "신고번호": it.get("STTEMNT_NO", ""),
                    "등록일": it.get("REGIST_DT", ""),
                    "기능성 요약": (it.get("MAIN_FNCTN") or "").replace("\n", " ")[:80],
                }
                for it in results
            ])
            edited = st.data_editor(df, width="stretch", hide_index=True,
                                    height=400, disabled=["제품명", "제조사", "신고번호", "등록일", "기능성 요약"])

            # 선택된 행의 인덱스 찾기
            picked_idx = [i for i, row in edited.iterrows() if row["선택"]]
            if not picked_idx:
                st.info("👆 위 표에서 '선택' 체크박스를 눌러 상세 보기")
            else:
                st.divider()
                idx = picked_idx[0]
                item = results[idx]
                # --- 건기식 상세 카드 ---
                st.markdown(f"### 📋 {str(item.get('PRDUCT','')).strip()}")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**제조사**: {item.get('ENTRPS','—')}")
                    st.markdown(f"**신고번호**: {item.get('STTEMNT_NO','—')}")
                    st.markdown(f"**등록일**: {item.get('REGIST_DT','—')}")
                with c2:
                    st.markdown(f"**유통기한**: {item.get('DISTB_PD','—')}")
                    st.markdown(f"**보관**: {item.get('PRSRV_PD','—')}")
                    st.markdown(f"**1일 섭취**: {item.get('SRV_USE','—')}")

                sub_tabs = st.tabs(["💪 기능성", "🌿 원재료", "📊 기준·규격", "⚠️ 주의사항"])
                with sub_tabs[0]:
                    main_fn = item.get("MAIN_FNCTN") or ""
                    if main_fn.strip():
                        render_functionality(main_fn)
                        with st.expander("원문 보기"):
                            st.code(main_fn, language=None)
                    else:
                        st.caption("—")
                    tags = tag_functions(main_fn)
                    if tags:
                        st.markdown("**태그**: " + "  ·  ".join(f"`#{t}`" for t in tags))

                with sub_tabs[1]:
                    # 1차: C003 품목제조신고
                    sttemnt = str(item.get("STTEMNT_NO", "")).strip()
                    mfc = None
                    if sttemnt:
                        with st.spinner("C003 조회..."):
                            mfc = htfs_mfc_by_rpt(sttemnt)
                    if mfc and mfc.get("RAWMTRL_NM"):
                        raws = htfs_mfc_parse(mfc["RAWMTRL_NM"])
                        material_table(raws, title=f"📋 원재료 · 총 {len(raws)}종 (C003 품목제조신고)")
                        st.caption(f"제형: {mfc.get('PRDT_SHAP_CD_NM','—')}  |  성상: {mfc.get('DISPOS','—')}")
                    else:
                        st.caption("C003에서 이 신고번호 데이터 없음")

                    # 2차: 식품이력 보조
                    with st.spinner("식품이력 조회..."):
                        raw_rows = foodhist_by_name(str(item.get("PRDUCT", "")).strip())
                    if raw_rows:
                        foodhist_origin_table(raw_rows, title=f"🌏 원산지·GMO (식품이력 {len(raw_rows)}건)")
                    else:
                        st.caption("식품이력(원산지·GMO) 등록 없음")

                    st.caption("ℹ️ 건기식 '함량'은 공공 API 비공개 — 라벨 기준")

                with sub_tabs[2]:
                    st.code(item.get("BASE_STANDARD") or "—", language=None)

                with sub_tabs[3]:
                    st.warning(item.get("INTAKE_HINT1") or "—")
        else:
            st.info("검색 결과 없음")
    else:
        st.caption("좌측에 검색어를 입력하세요.")

# ==============================================================
# 탭 2: 일반식품
# ==============================================================
with main_tabs[1]:
    st.markdown("##### 일반식품 (식품·첨가물 품목제조보고)")
    col1, col2 = st.columns([3, 2])
    with col1:
        mode = st.radio("검색 축", ["품목명", "업소명", "보고번호", "원재료명"],
                        horizontal=True, key="c002_mode")
    with col2:
        q = st.text_input("검색어",
                          placeholder="예) 영데이즈 / 엔피케이 / 20100515088653 / 난소화성말토덱스트린",
                          key="c002_q")
        limit = st.slider("결과 수", 10, 200, 50, step=10, key="c002_limit")

    if q:
        with st.spinner("식품안전나라 C002 호출 중..."):
            try:
                if mode == "품목명":
                    rows = mfc_by_name(q, limit=limit)
                elif mode == "업소명":
                    rows = mfc_by_company(q, limit=limit)
                elif mode == "보고번호":
                    one = mfc_by_report_no(q.strip())
                    rows = [one] if one else []
                else:
                    from fetchers.mfc_rpt import search_by_raw_material
                    rows = search_by_raw_material(q, limit=limit)
            except Exception as e:
                st.error(f"API 호출 실패: {e}")
                rows = []

        st.caption(f"매칭 **{len(rows)}건**")

        if rows:
            df = pd.DataFrame([
                {
                    "선택": False,
                    "품목명": r.get("PRDLST_NM", ""),
                    "업소": r.get("BSSH_NM", ""),
                    "품목유형": r.get("PRDLST_DCNM", ""),
                    "보고번호": r.get("PRDLST_REPORT_NO", ""),
                    "보고일자": r.get("PRMS_DT", ""),
                }
                for r in rows
            ])
            edited = st.data_editor(df, width="stretch", hide_index=True,
                                    height=400,
                                    disabled=["품목명", "업소", "품목유형", "보고번호", "보고일자"])
            picked_idx = [i for i, row in edited.iterrows() if row["선택"]]
            if not picked_idx:
                st.info("👆 위 표에서 '선택' 체크박스를 눌러 상세 보기")
            else:
                idx = picked_idx[0]
                item = rows[idx]
                st.divider()
                st.markdown(f"### 📋 {item.get('PRDLST_NM','')}")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**업소**: {item.get('BSSH_NM','—')}")
                    st.markdown(f"**품목유형**: {item.get('PRDLST_DCNM','—')}")
                    st.markdown(f"**보고번호**: {item.get('PRDLST_REPORT_NO','—')}")
                with c2:
                    st.markdown(f"**보고일자**: {item.get('PRMS_DT','—')}")
                    st.markdown(f"**변경일자**: {item.get('CHNG_DT','—')}")
                    st.markdown(f"**수출가능**: "
                                f"{'✈ 가능' if item.get('ETQTY_XPORT_PRDLST_YN')=='O' else '—'}")

                sub_tabs = st.tabs(["🌿 원재료", "🍎 영양성분 (조회)"])
                with sub_tabs[0]:
                    raw_list = parse_raw_materials(item.get("RAWMTRL_NM", ""))
                    material_table(raw_list, title=f"원재료 · 총 {len(raw_list)}종")
                    st.caption("ℹ️ 일반식품 '함량'은 공공 API 없음 — 라벨 기준")
                with sub_tabs[1]:
                    rno = item.get("PRDLST_REPORT_NO", "").strip()
                    if not rno:
                        st.caption("보고번호 없음")
                    else:
                        # 1차: 신규 API (tn_pubr_public_nutri_process_info_api) 보고번호 정확매칭
                        with st.spinner("가공식품 영양 통합 DB 조회..."):
                            np_rows = nutri_process_by_rpt(rno)
                        if np_rows:
                            n = np_rows[0]
                            st.success(f"✓ 가공식품 통합 DB 매칭 ({len(np_rows)}건 중 대표)")
                            c1, c2 = st.columns(2)
                            c1.markdown(f"**1회 제공량**: {n.get('servSize','—')}  |  **제품중량**: {n.get('foodSize','—')}")
                            c2.markdown(f"**기준량**: {n.get('nutConSrtrQua','—')}  |  **분류**: {n.get('foodLv3Nm','')}>{n.get('foodLv4Nm','')}")
                            cols_n = st.columns(4)
                            i = 0
                            for code, label in NP_LABELS.items():
                                v = n.get(code)
                                if v not in (None, "", "0", 0, "0.00"):
                                    cols_n[i % 4].metric(label, v)
                                    i += 1
                            if i == 0:
                                st.caption("등록된 영양성분 값 없음")
                        else:
                            # 2차 fallback: 기존 FoodNtrCpntDbInfo02
                            with st.spinner("기존 식품영양성분DB fallback..."):
                                nutri_rows = nutri_search(
                                    food_nm_kr=item.get("PRDLST_NM", "")[:20],
                                    page_size=5,
                                )
                                match = next(
                                    (n for n in nutri_rows
                                     if str(n.get("ITEM_REPORT_NO", "")).strip() == rno),
                                    None,
                                )
                            if match:
                                st.info("기존 식품영양성분DB 매칭")
                                cols = st.columns(3)
                                for i, (code, label) in enumerate(CORE_NUTRIENTS.items()):
                                    v = match.get(code)
                                    if v not in (None, ""):
                                        cols[i % 3].metric(label, v)
                                st.caption(f"기준량: {match.get('SERVING_SIZE','—')} / "
                                           f"1회 섭취참고량: {match.get('NUTRI_AMOUNT_SERVING','—')}")
                            else:
                                st.warning("두 영양성분 DB 모두에 미등재")
        else:
            st.info("검색 결과 없음")
    else:
        st.caption("좌측에 검색어를 입력하세요.")


# ==============================================================
# 탭 3: 수입 건기식 (전국건강기능식품영양성분 표준데이터)
# ==============================================================
with main_tabs[2]:
    st.markdown("##### 수입 건기식 (전국건강기능식품영양성분 표준데이터)")
    st.caption("수입 건기식만 포함 · imptYn=Y · 영양성분·원산지국 등")
    col1, col2 = st.columns([3, 2])
    with col1:
        mode_n = st.radio("검색 축",
                          ["제품명", "제조사·수입사·유통사", "원료·성분", "보고번호"],
                          horizontal=True, key="nutri_mode")
    with col2:
        q_n = st.text_input("검색어",
                            placeholder="예) 마그네슘 / US PHARMATECH / 엠에스엠 / 22US32581G6",
                            key="nutri_q")

    if q_n:
        mode_map = {"제품명": "foodNm", "제조사·수입사·유통사": "mfrNm",
                    "원료·성분": "ingredient", "보고번호": "reportNo"}
        results = search_htfs_nutri(q_n, mode=mode_map[mode_n], limit=200)
        st.caption(f"매칭 **{len(results)}건**")

        if results:
            df = pd.DataFrame([
                {
                    "선택": False,
                    "제품명": r.get("foodNm", ""),
                    "대분류": r.get("foodLv3Nm", ""),
                    "세분류": r.get("foodLv4Nm", ""),
                    "기준량": r.get("ntrtIgrdPvsnUnitAmnt", ""),
                    "제조사": r.get("mfrNm", ""),
                    "수입사": r.get("imptNm", ""),
                    "원산지": r.get("cooNm", ""),
                    "보고번호": r.get("itemMnftrRptNo", ""),
                }
                for r in results
            ])
            edited = st.data_editor(df, width="stretch", hide_index=True, height=400,
                                    disabled=[c for c in df.columns if c != "선택"])
            picked_idx = [i for i, row in edited.iterrows() if row["선택"]]
            if not picked_idx:
                st.info("👆 위 표에서 '선택' 체크박스를 눌러 상세 보기")
            else:
                idx = picked_idx[0]
                item = results[idx]
                st.divider()
                st.markdown(f"### 📋 {item.get('foodNm', '')}")

                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**제조사**: {item.get('mfrNm', '—')}")
                    st.markdown(f"**수입사**: {item.get('imptNm', '—')}")
                    st.markdown(f"**유통사**: {item.get('distNm', '—')}")
                with c2:
                    st.markdown(f"**원산지**: {item.get('cooNm', '—')}")
                    st.markdown(f"**보고번호**: {item.get('itemMnftrRptNo', '—')}")
                    st.markdown(f"**작성일**: {item.get('crtYmd', '—')}")
                with c3:
                    st.markdown(f"**1회 섭취**: {item.get('onetmQnt', '—')} "
                                f"({item.get('onetmQntWghtVolm', '')})")
                    st.markdown(f"**1일 섭취 횟수**: {item.get('onetmIntkNmtm', '—')}")
                    st.markdown(f"**총 제품중량**: {item.get('foodWght', '—')}")

                # 대표 성분 블록 (수입 건기식은 foodLv4/5Nm 이 핵심 성분명)
                st.markdown("##### 🧬 대표 성분 · 기준량")
                sc1, sc2, sc3 = st.columns(3)
                sc1.metric("주요 성분", item.get("foodLv4Nm") or item.get("foodLv5Nm") or "—")
                sc2.metric("분류 (대)", item.get("foodLv3Nm") or "—")
                sc3.metric("기준량", item.get("ntrtIgrdPvsnUnitAmnt") or "—")
                st.caption("ℹ️ 수입 건기식은 개별 원재료 리스트가 공공 API에 없습니다. "
                           "대표 성분은 식약처 분류 체계의 세분류 기준이며, 기준량이 해당 성분의 함량을 의미합니다.")

                tabs_n = st.tabs(["🍎 영양성분", "📊 분류 체계"])
                with tabs_n[0]:
                    st.caption(f"기준량: {item.get('ntrtIgrdPvsnUnitAmnt', '—')} 기준")
                    nutri_metric_cards(item, NUTRI_LABELS, per_row=3)

                with tabs_n[1]:
                    st.markdown(f"- **대분류(Lv3)**: {item.get('foodLv3Nm', '—')}")
                    st.markdown(f"- **중분류(Lv4)**: {item.get('foodLv4Nm', '—')} ← 일반적으로 대표 성분")
                    st.markdown(f"- **소분류(Lv5)**: {item.get('foodLv5Nm', '—')}")
                    st.markdown(f"- **세분류(Lv6)**: {item.get('foodLv6Nm', '—')}")
                    st.markdown(f"- **식품코드**: {item.get('foodCd', '—')}")
        else:
            st.info("검색 결과 없음")
    else:
        st.caption("검색어를 입력하세요.")
