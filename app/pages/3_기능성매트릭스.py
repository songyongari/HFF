"""기능성 탐색 — 11개 태그 중 하나를 선택하면, 그에 연결된 모든 것을 한 화면에."""
from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from lib import (
    FUNCTION_TAGS,
    load_htfs_all,
    load_ingredient_master,
    load_master,
    load_davinci_products,
    tag_functions,
)
from theme import section

from theme import page

page(
    "기능성 탐색",
    caption="태그를 선택하면 연결된 바이오컴·시장 제품·성분을 한 화면에",
    icon="🧮",
)

# ============ 태그 선택 ============
tag = st.radio("기능성 선택", list(FUNCTION_TAGS.keys()), horizontal=True)
keywords = FUNCTION_TAGS[tag]

st.markdown(f"### `#{tag}`")
st.caption("분류 키워드: " + " · ".join(f"`{k}`" for k in keywords))

# ============ 데이터 ============
biocom = load_master()
davinci = load_davinci_products()
htfs = load_htfs_all()
ings = load_ingredient_master()

# 이 태그에 해당하는지 판정
def has_tag(text: str) -> bool:
    return tag in tag_functions(text)


# 바이오컴 건기식 매칭
biocom_hits = []
for m in biocom:
    if m.get("category") != "건기식":
        continue
    main_fn = m.get("htfs", {}).get("MAIN_FNCTN", "")
    if has_tag(main_fn):
        biocom_hits.append(m)

# 건기식 DB 매칭
market_hits = [it for it in htfs if has_tag(it.get("MAIN_FNCTN", ""))]

# 성분 매칭 — 태그에 해당하는 카테고리 가진 내부 시드
# (엄격한 매핑은 어렵지만 간이로: 성분 카테고리 문자열에 태그 키워드가 포함되는지)
ingredient_hits = []
for ing in ings:
    cat = (ing.get("category") or "").lower()
    if any(k.lower() in cat for k in keywords + [tag]):
        ingredient_hits.append(ing)

# ============ 메트릭 ============
m1, m2, m3, m4 = st.columns(4)
m1.metric("바이오컴 제품", len(biocom_hits))
m2.metric("시장 전체 건기식", f"{len(market_hits):,}")
m3.metric("연관 성분 (시드)", len(ingredient_hits))
m4.metric("관련 제조사 수", len(set(str(h.get("ENTRPS", "")) for h in market_hits)))

st.divider()

section("🏷️ 바이오컴 제품")
if not biocom_hits:
    st.caption("매칭되는 바이오컴 건기식 없음")
else:
    df = pd.DataFrame([
        {
            "제품": m["brand"],
            "정식명": str(m.get("htfs", {}).get("PRDUCT", "")).strip(),
            "제조사": m.get("htfs", {}).get("ENTRPS", ""),
            "기능성 요약": (m.get("htfs", {}).get("MAIN_FNCTN") or "").replace("\n", " ")[:120],
        }
        for m in biocom_hits
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

section("🏭 시장 TOP 제조사")
if market_hits:
    top_makers = Counter(str(it.get("ENTRPS", "")) for it in market_hits).most_common(10)
    df_m = pd.DataFrame(top_makers, columns=["제조사", "제품 수"])
    c1, c2 = st.columns([1, 1])
    with c1:
        st.dataframe(df_m, use_container_width=True, hide_index=True, height=340)
    with c2:
        st.markdown("**대표 제품 (상위 10)**")
        for it in market_hits[:10]:
            st.markdown(f"- {str(it.get('PRDUCT','')).strip()} "
                        f"<span style='color:gray; font-size:0.85em'>({it.get('ENTRPS','')})</span>",
                        unsafe_allow_html=True)

section("🧪 연관 성분", caption="내부 시드 82개 기준")
if ingredient_hits:
    df_i = pd.DataFrame([
        {
            "성분": i["name_ko"],
            "영문": i["name_en"],
            "카테고리": i.get("category", ""),
            "Bucket": i.get("legal", {}).get("bucket", ""),
            "다빈치": i.get("supplier", {}).get("davinci_status", ""),
            "Phase": i.get("phase", {}).get("phase", ""),
        }
        for i in ingredient_hits
    ])
    st.dataframe(df_i, use_container_width=True, hide_index=True)
else:
    st.caption("해당 태그와 직접 매칭되는 성분 시드가 아직 없습니다. (시드 사전에 태깅 추가 여지)")

st.divider()

section("📊 11개 태그 전체 분포", caption="시장 44K+ 건기식 기준")
counter: Counter[str] = Counter()
total = 0
for it in htfs:
    text = it.get("MAIN_FNCTN", "")
    if not text:
        continue
    total += 1
    for t in tag_functions(text):
        counter[t] += 1
dist = pd.DataFrame(
    [{"태그": t, "건수": counter.get(t, 0),
      "비율(%)": round(counter.get(t, 0) / max(total, 1) * 100, 1)}
     for t in FUNCTION_TAGS]
).sort_values("건수", ascending=False)
cA, cB = st.columns([1, 2])
cA.dataframe(dist, use_container_width=True, hide_index=True)
cB.bar_chart(dist.set_index("태그")["건수"])

# ============ 바이오컴+다빈치 × 11 태그 매트릭스 ============
with st.expander("🗺 바이오컴+다빈치 × 11태그 매트릭스"):
    rows = []
    for m in biocom:
        main = m.get("htfs", {}).get("MAIN_FNCTN") if m.get("category") == "건기식" else ""
        tags_here = set(tag_functions(main or ""))
        rows.append({
            "브랜드": m["brand"],
            "소스": "바이오컴",
            **{t: "●" if t in tags_here else "" for t in FUNCTION_TAGS},
        })
    # 다빈치는 MAIN_FNCTN이 없어서 태그 추정 생략 (제품 이름 기반 태깅은 별도 로직 필요)
    # 현재는 포함하지 않음 — 향후 v0.4에서 내부 매핑 확장 시 구현.
    df_mtx = pd.DataFrame(rows)
    st.dataframe(df_mtx, use_container_width=True, hide_index=True)
