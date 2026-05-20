"""기능성원료 가이드 — 식약처 I0760 분류 + 시장 표기 통합 카탈로그.

상단 통합 검색 1개 — 4 카테고리 + 시장 표기 변형까지 한 번에.
검색어 비어있을 때 4 탭 카탈로그 (영양소·복합혼합·기능성원료·개별인정형).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from config import DATA_DIR
from lib import (
    load_htfs_all,
    load_htfs_cat_all,
    norm,
    parse_functionality,
    search_htfs_by_ingredient,
    search_rwmatr,
)
from theme import info_pill, page

# 효능 종결어미 + 구두점(.,·/) 으로 결합된 다중 효능 분리
_TERM_PUNCT = re.compile(r'(필요|있음|줌|함|향상)\s*[,.·/]\s*')
_MIXED_SCLAS = {"혼합기능성원료", "복합영양소제품", "영양보충용제품"}


def split_combined_benefits(text: str) -> list[str]:
    """'A에 필요, B에 필요' 형태를 ['A에 필요', 'B에 필요'] 로 분리."""
    results = []
    last = 0
    for m in _TERM_PUNCT.finditer(text):
        results.append(text[last:m.start() + len(m.group(1))])
        last = m.end()
    if last < len(text):
        results.append(text[last:])
    if not results:
        results = [text]
    return [r.strip(" .,·/").strip() for r in results if r.strip()]


# ====== 캐시 데이터 ======
@st.cache_data(show_spinner=False)
def get_market_header_freq() -> Counter:
    """전체 시장 건기식의 [원료명] 헤더 빈도."""
    freq: Counter = Counter()
    for r in load_htfs_all():
        fn = r.get("MAIN_FNCTN", "") or ""
        for m in re.finditer(r'\[([^\]]+)\]', fn):
            h = m.group(1).strip()
            h = re.sub(r'\s*\(\s*제\d{4}-\d+호\s*\)', '', h).strip()
            h = re.sub(r'\s*\([^)]*[A-Za-z][^)]*\)', '', h).strip()
            if h:
                freq[h] += 1
    return freq


@st.cache_data(show_spinner=False)
def load_alias_map() -> dict[str, list[str]]:
    """수기 별칭 매핑 (카탈로그명 → 시장 표기 리스트)."""
    path = Path(DATA_DIR) / "ingredient_aliases.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def find_aliases(cat_name: str, header_freq: Counter,
                 manual_map: dict[str, list[str]]) -> list[tuple[str, int]]:
    """카탈로그명의 시장 표기 별칭 (수기 우선, 그 다음 norm 부분 매칭 자동)."""
    cn = norm(cat_name)
    if not cn:
        return []
    seen = {cat_name}
    result: list[tuple[str, int]] = []

    # 1. 수기 매핑
    for alias in manual_map.get(cat_name, []):
        if alias not in seen:
            result.append((alias, header_freq.get(alias, 0)))
            seen.add(alias)

    # 2. 자동: norm 부분 매칭 (양방향) — 최소 5건 이상만 (노이즈 제거)
    auto: list[tuple[str, int]] = []
    for h, n in header_freq.items():
        if h in seen or n < 5:
            continue
        hn = norm(h)
        if not hn or len(hn) < 2:
            continue
        if cn in hn or hn in cn:
            auto.append((h, n))
    auto.sort(key=lambda x: -x[1])
    for h, n in auto:
        if h not in seen:
            result.append((h, n))
            seen.add(h)

    return result[:4]


def official_name(cat_name: str, aliases: list[tuple[str, int]]) -> str:
    """공식 명칭 = 시장 빈도 가장 높은 표기 (없으면 카탈로그명)."""
    if aliases:
        top = max(aliases, key=lambda x: x[1])
        if top[1] >= 50:
            return top[0]
    return cat_name


def classify(row: dict) -> tuple[str, str]:
    """행 분류 → (라벨, tone)."""
    mlsfc = row.get("MLSFC_NM", "")
    sclas = row.get("SCLAS_NM", "")
    if mlsfc == "개별인정형 건강기능식품":
        return ("🟢 개별인정형", "success")
    if mlsfc == "기능성원료":
        return ("🌿 고시형 · 기능성원료", "info")
    if sclas in _MIXED_SCLAS:
        return ("🥣 고시형 · 복합/혼합", "info")
    return ("🥗 고시형 · 영양소", "info")


# ====== 상세 패널 ======
def render_detail(name: str, source_row: dict,
                  aliases: list[tuple[str, int]],
                  header_freq: Counter) -> None:
    st.divider()
    label, tone = classify(source_row)
    badge = info_pill(label, tone=tone)
    st.markdown(f"### 📋 {name}  {badge}", unsafe_allow_html=True)

    # 메타
    sclas = source_row.get("SCLAS_NM", "")
    grp_cd = source_row.get("HELT_ITM_GRP_CD", "")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**중분류**: {source_row.get('MLSFC_NM') or '—'}")
    c2.markdown(f"**세부분류**: {sclas or '—'}")
    c3.markdown(f"**식약처 코드**: `{grp_cd or '—'}`")

    # 별칭
    if aliases:
        st.markdown("**별칭(시장 표기)**: " +
                    "  ·  ".join(f"`{a}` <span style='color:#888;'>({n})</span>"
                                   for a, n in aliases),
                    unsafe_allow_html=True)

    # 효능 집계 (카탈로그명 + 별칭 모두로 검색)
    search_terms = [name] + [a for a, _ in aliases]
    seen_stmt = set()
    pool: list[dict] = []
    for term in search_terms:
        for p in search_htfs_by_ingredient(term, limit=200):
            stmt = p.get("STTEMNT_NO")
            if stmt and stmt not in seen_stmt:
                pool.append(p)
                seen_stmt.add(stmt)

    benefit_counter: Counter = Counter()
    name_norms = {norm(t) for t in search_terms if t}
    for p in pool:
        secs = parse_functionality(p.get("MAIN_FNCTN") or "")
        for sec in secs:
            ing = sec.get("ingredient") or ""
            ing_n = norm(ing)
            if any(nn and nn in ing_n for nn in name_norms):
                for b in sec.get("benefits", []):
                    for part in split_combined_benefits(b):
                        benefit_counter[part] += 1

    is_indiv = (source_row.get("MLSFC_NM") == "개별인정형 건강기능식품")
    st.markdown(f"##### {'🟢 인정 효능 문구 (KFDA 개별인정)' if is_indiv else '💪 식약처 공전 표준 기능성'}")
    st.caption("회사가 KFDA 개별인정 신청 시 등재한 효능 문구."
               if is_indiv
               else "식약처 「건강기능식품 공전」 등재 표준 기능성 문구. 모든 시장 제품 동일 표기 의무.")
    standard = [b for b, n in benefit_counter.most_common() if n >= 5][:3]
    if standard:
        for b in standard:
            st.markdown(f"- {b}")
    elif benefit_counter:
        st.markdown(f"- {benefit_counter.most_common(1)[0][0]}")
    else:
        st.caption("자동 추출 실패 — 아래 사용 제품의 기능성 문구 직접 확인.")

    # 원재료 표준사전 (정확 매칭)
    rw_hits = []
    for term in search_terms:
        for r in search_rwmatr(term, limit=10):
            if (norm(term) == norm(r.get("RPRSNT_RAWMTRL_NM", ""))
                or norm(term) == norm(r.get("RAWMTRL_NCKNM", ""))
                or norm(term) == norm(r.get("ENG_NM", ""))):
                rw_hits.append(r)
    if rw_hits:
        st.markdown("##### 🌱 원재료 표준사전 매칭")
        seen_ko = set()
        for rh in rw_hits:
            ko = rh.get("RPRSNT_RAWMTRL_NM", "")
            if ko in seen_ko:
                continue
            seen_ko.add(ko)
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

    # 사용 시장 제품
    st.markdown(f"##### 📦 이 원료를 쓰는 시장 건기식 (총 {len(pool)}건, 상위 10개)")
    if pool:
        df = pd.DataFrame([
            {
                "제품명": str(p.get("PRDUCT", "")).strip(),
                "제조사": p.get("ENTRPS", ""),
                "신고번호": p.get("STTEMNT_NO", ""),
            }
            for p in pool[:10]
        ])
        st.dataframe(df, width="stretch", hide_index=True, height=320)
    else:
        st.caption("매칭 제품 없음")

    if st.button("🧪 성분 탐색에서 5-bucket 판정 보기",
                 key=f"goto_ing_{grp_cd or name}"):
        st.session_state["_ing_prefill"] = official_name(name, aliases)
        st.switch_page("pages/4_성분탐색.py")


# ====== 페이지 ======
page(
    "기능성원료 가이드",
    caption="식약처 I0760 분류 585종 + 시장 표기 통합 · 표준 효능 · 사용 제품",
    icon="📚",
)

catalog = load_htfs_cat_all()
header_freq = get_market_header_freq()
alias_map = load_alias_map()

nutri_rows = [r for r in catalog
              if r.get("MLSFC_NM") == "영양소"
              and r.get("SCLAS_NM") not in _MIXED_SCLAS]
mixed_rows = [r for r in catalog
              if r.get("MLSFC_NM") == "영양소"
              and r.get("SCLAS_NM") in _MIXED_SCLAS]
func_rows  = [r for r in catalog if r.get("MLSFC_NM") == "기능성원료"]
indiv_rows = [r for r in catalog if r.get("MLSFC_NM") == "개별인정형 건강기능식품"]

# 카탈로그 행에 별칭·공식명 자동 매핑
def enrich(row: dict) -> dict:
    name = row.get("HELT_ITM_GRP_NM", "")
    aliases = find_aliases(name, header_freq, alias_map)
    return {
        "row": row,
        "name": name,
        "aliases": aliases,
        "official": official_name(name, aliases),
    }

enriched_all = [enrich(r) for r in catalog]
by_tab = {
    "nutri": [e for e in enriched_all
              if e["row"].get("MLSFC_NM") == "영양소"
              and e["row"].get("SCLAS_NM") not in _MIXED_SCLAS],
    "mixed": [e for e in enriched_all
              if e["row"].get("MLSFC_NM") == "영양소"
              and e["row"].get("SCLAS_NM") in _MIXED_SCLAS],
    "func":  [e for e in enriched_all if e["row"].get("MLSFC_NM") == "기능성원료"],
    "indiv": [e for e in enriched_all if e["row"].get("MLSFC_NM") == "개별인정형 건강기능식품"],
}

# ===== 상단 통합 검색 =====
query = st.text_input(
    "원료/성분 검색",
    placeholder="예) EPA · 비타민C · 셀레늄 · 오메가 · 모로신 · MSM",
    key="guide_q",
    label_visibility="collapsed",
)


def build_df(enriched: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "공식 명칭": e["official"],
            "별칭": ", ".join(a for a, _ in e["aliases"] if a != e["official"])[:60],
            "세부분류": e["row"].get("SCLAS_NM", ""),
            "분류": classify(e["row"])[0],
            "코드": e["row"].get("HELT_ITM_GRP_CD", ""),
            "_name": e["name"],
        }
        for e in enriched
    ])


def find_picked(df: pd.DataFrame, idx: int, enriched: list[dict]) -> dict | None:
    picked_name = df.iloc[idx]["_name"]
    return next((e for e in enriched if e["name"] == picked_name), None)


if query:
    nq = norm(query)

    # 매칭: 카탈로그 자체 이름·별칭·SCLAS_NM 모두 검사
    matches = []
    for e in enriched_all:
        hay_parts = [e["name"], e["row"].get("SCLAS_NM", "")] + [a for a, _ in e["aliases"]]
        hay = norm(" ".join(hay_parts))
        if nq in hay:
            matches.append(e)

    st.caption(f"매칭 **{len(matches)}건**")

    if matches:
        df = build_df(matches)
        display = df.drop(columns=["_name"])
        event = st.dataframe(
            display, width="stretch", hide_index=True, height=400,
            on_select="rerun", selection_mode="single-row",
            key="search_df",
        )
        if event.selection and event.selection.rows:
            e = find_picked(df, event.selection.rows[0], matches)
            if e:
                render_detail(e["name"], e["row"], e["aliases"], header_freq)
        else:
            st.caption("👆 위 표에서 원료를 선택하면 상세가 표시됩니다.")
    else:
        # 카탈로그 매칭 없음 → 시장 헤더에서 fallback
        market_hits = [(h, n) for h, n in header_freq.items() if nq in norm(h)]
        market_hits.sort(key=lambda x: -x[1])
        if market_hits:
            st.markdown("##### 카탈로그 미등재 · 시장 표기 매칭")
            st.caption("I0760 카탈로그에는 없지만 시장 제품에 표기된 원료. 식약처 자체 분류 누락이거나 신규 등재 케이스.")
            for h, n in market_hits[:15]:
                st.markdown(f"- **{h}**  ·  시장 {n}건")
        else:
            st.info("매칭 없음. 다른 키워드로 시도해보세요.")

else:
    # ===== 4 탭 카탈로그 =====
    tabs = st.tabs([
        f"🥗 고시형 · 영양소 ({len(by_tab['nutri'])})",
        f"🥣 고시형 · 복합/혼합 ({len(by_tab['mixed'])})",
        f"🌿 고시형 · 기능성원료 ({len(by_tab['func'])})",
        f"🟢 개별인정형 ({len(by_tab['indiv'])})",
    ])

    def render_tab(enriched: list[dict], key: str):
        if not enriched:
            st.caption("—"); return
        df = build_df(enriched).sort_values("공식 명칭").reset_index(drop=True)
        display = df.drop(columns=["_name", "분류"])  # 탭별이라 분류 컬럼 생략
        event = st.dataframe(
            display, width="stretch", hide_index=True, height=400,
            on_select="rerun", selection_mode="single-row",
            key=f"tab_{key}",
        )
        if event.selection and event.selection.rows:
            e = find_picked(df, event.selection.rows[0],
                            [enriched[i] for i in df.index])
            if e:
                render_detail(e["name"], e["row"], e["aliases"], header_freq)

    with tabs[0]: render_tab(by_tab["nutri"], "nutri")
    with tabs[1]: render_tab(by_tab["mixed"], "mixed")
    with tabs[2]: render_tab(by_tab["func"],  "func")
    with tabs[3]: render_tab(by_tab["indiv"], "indiv")
