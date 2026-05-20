"""Streamlit 페이지 공용 유틸."""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import streamlit as st

# app/ 밑에서 import 할 수 있도록 프로젝트 루트 경로 추가
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import DATA_DIR  # noqa: E402


@st.cache_data(show_spinner=False)
def load_json(name: str) -> list | dict:
    path = DATA_DIR / name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_master() -> list[dict]:
    return load_json("biocom_master.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_htfs_all() -> list[dict]:
    return load_json("htfs_all.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_rwmatr_all() -> list[dict]:
    return load_json("rwmatr_all.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_htfs_cat_all() -> list[dict]:
    return load_json("htfs_cat_all.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_ingredient_master() -> list[dict]:
    return load_json("ingredient_master.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_davinci_products() -> list[dict]:
    return load_json("davinci_products.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_biocom_xlsx_ingredients() -> dict:
    """바이오컴 11종 × 성분·함량 (xlsx 파싱)."""
    return load_json("biocom_xlsx_ingredients.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_htfs_nutri_all() -> list[dict]:
    """전국건강기능식품영양성분 표준데이터 — 수입 건기식 4,380건."""
    return load_json("htfs_nutri_all.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_blocklist() -> list[dict]:
    """해외직구식품 반입차단 원료·성분 (314건, 지정+해제 포함)."""
    return load_json("blocklist_282.json")  # type: ignore[return-value]


def check_blocked(name: str) -> dict | None:
    """성분명이 반입차단 리스트에 있는지 확인 (지정된 것만). Wrapper for fetchers.blockraw.is_blocked."""
    from fetchers.blockraw import is_blocked
    return is_blocked(name, load_blocklist())


def _norm_strict(s) -> str:
    """공백·하이픈·콤마·괄호·슬래시·언더스코어 제거 후 소문자."""
    import re
    return re.sub(r"[\s\-_,.·()\[\]/]+", "", str(s or "")).lower()


def check_food_registered(name: str) -> dict | None:
    """국내 식품원재료 사전에 A코드(식품원료) 또는 C코드(건기식원료)로 등재됐는지.

    반환: 해당 row (매칭 시), None (미매칭).
    판정 우선순위: 정확매칭 → 포함매칭(4자 이상).
    """
    if not name:
        return None
    q = _norm_strict(name)
    if len(q) < 2:
        return None
    rw = load_rwmatr_all()
    # 1차: 정확 매칭
    for row in rw:
        lc = str(row.get("LCLAS_NM", ""))
        if "A코드" not in lc and "C코드" not in lc:
            continue
        for key in ("RPRSNT_RAWMTRL_NM", "RAWMTRL_NCKNM", "ENG_NM"):
            c = _norm_strict(row.get(key))
            if c and c == q:
                return row
    # 2차: 포함 (4자 이상, 노이즈 감소)
    if len(q) >= 4:
        for row in rw:
            lc = str(row.get("LCLAS_NM", ""))
            if "A코드" not in lc and "C코드" not in lc:
                continue
            for key in ("RPRSNT_RAWMTRL_NM", "RAWMTRL_NCKNM", "ENG_NM"):
                c = _norm_strict(row.get(key))
                if c and len(c) >= 4 and (q in c or c in q):
                    return row
    return None


def _find_seed_by_name(name: str) -> dict | None:
    """내부 82 시드에서 name_ko/name_en/aliases 매칭."""
    if not name:
        return None
    qn = _norm_strict(name)
    for ing in load_ingredient_master():
        keys = [ing.get("name_ko"), ing.get("name_en")] + (ing.get("aliases") or [])
        for k in keys:
            kn = _norm_strict(k)
            if kn and (kn == qn or (len(kn) >= 4 and kn in qn) or (len(qn) >= 4 and qn in kn)):
                return ing
    return None


def _check_all_names(name: str, check_fn) -> tuple[dict | None, str | None]:
    """시드 매칭되면 name_ko/name_en/aliases 전부 시도해서 check_fn 결과 얻음.

    반환: (결과, 매칭에 성공한 이름)
    """
    seed = _find_seed_by_name(name)
    candidates = [name]
    if seed:
        candidates += [seed.get("name_ko"), seed.get("name_en")] + (seed.get("aliases") or [])
    for c in candidates:
        if not c:
            continue
        result = check_fn(c)
        if result:
            return result, c
    return None, None


def classify_bucket(name: str) -> dict:
    """5-bucket 판정 — 시드 우선 + 공식 데이터 보강.

    우선순위:
      1) 시드에 명시된 bucket (수기 검증)
      2) 반입차단 리스트 매칭 → ④
      3) 원재료 사전 A/C코드 매칭 → ②/①
      4) 어디에도 없음 → ③ (확실도 낮음)
    """
    seed = _find_seed_by_name(name)

    # 반입차단은 항상 최우선 체크 (시드보다 실시간 데이터가 권위)
    blk_entry, blk_name = _check_all_names(name, check_blocked)
    if blk_entry:
        return {
            "bucket": "④",
            "label": "반입차단",
            "reasons": [f"식약처 반입차단 지정 — {blk_entry.get('RAW_IRDNT_NM','')}"
                        + (f" (매칭 이름: {blk_name})" if blk_name != name else "")],
            "blocked_entry": blk_entry,
            "registered_entry": None,
            "source": "official_api",
            "confident": True,
        }

    # 시드에 명시된 값 우선 (수기 검증된 것)
    if seed:
        b = seed["legal"]["bucket"]
        return {
            "bucket": b,
            "label": {
                "①": "현재 판매 가능 (건기식 등재)",
                "②": "직구 대행 가능 (건기식 아님)",
                "③": "미국 법인 기회 (구매대행 금지)",
                "③-H": "호르몬/성 마케팅 제약",
                "④": "반입차단",
            }.get(b, "?"),
            "reasons": [
                f"내부 시드 수기 분류 기준 ({seed.get('name_ko')})",
                f"국내 등재: {seed['legal'].get('korea_registered','—')}",
            ],
            "blocked_entry": None,
            "registered_entry": None,
            "source": "internal_seed",
            "confident": True,
        }

    # 시드에 없으면 원재료 사전 매칭
    reg_entry, reg_name = _check_all_names(name, check_food_registered)
    if reg_entry:
        lc = str(reg_entry.get("LCLAS_NM", ""))
        if "C코드" in lc:
            return {
                "bucket": "①",
                "label": "건기식 등재 + 유통 가능",
                "reasons": [
                    f"원재료 사전 C코드 (건기식 원료) 매칭: {reg_entry.get('RPRSNT_RAWMTRL_NM','')}",
                    f"분류: {reg_entry.get('MLSFC_NM','')}",
                ],
                "blocked_entry": None,
                "registered_entry": reg_entry,
                "source": "official_api",
                "confident": True,
            }
        return {
            "bucket": "②",
            "label": "식품원료 등재 + 구매대행 가능",
            "reasons": [
                f"원재료 사전 A코드 (식품원료) 매칭: {reg_entry.get('RPRSNT_RAWMTRL_NM','')}",
                f"분류: {reg_entry.get('MLSFC_NM','')}",
            ],
            "blocked_entry": None,
            "registered_entry": reg_entry,
            "source": "official_api",
            "confident": True,
        }

    # 어디에도 없음 — ③ 추정 (확실도 낮음)
    return {
        "bucket": "③",
        "label": "미등재 추정 — 구매대행 불가, 개인직구 가능 (미국 법인 기회)",
        "reasons": [
            "반입차단 미지정",
            "국내 식품원재료 사전 A·C코드 미매칭",
            "내부 시드에도 없음",
            "⚠ 이름 표기 차이로 인한 미매칭 가능성 있음 — 식약처 문의 권장",
        ],
        "blocked_entry": None,
        "registered_entry": None,
        "source": "inferred",
        "confident": False,
    }


def search_htfs_nutri(query: str, *, mode: str = "foodNm", limit: int = 100) -> list[dict]:
    """수입 건기식 DB 검색.

    mode:
      - 'foodNm': 제품명 부분 매칭
      - 'mfrNm': 제조사 부분 매칭
      - 'ingredient': foodLv4Nm/foodLv5Nm/foodNm 에 포함 (성분 단위)
      - 'reportNo': itemMnftrRptNo 정확 매칭
    """
    if not query:
        return []
    q = norm(query)
    data = load_htfs_nutri_all()
    hits = []
    for d in data:
        if mode == "foodNm":
            if q in norm(d.get("foodNm", "")):
                hits.append(d)
        elif mode == "mfrNm":
            text = " ".join(str(d.get(k, "")) for k in ("mfrNm", "imptNm", "distNm"))
            if q in norm(text):
                hits.append(d)
        elif mode == "ingredient":
            text = " ".join(str(d.get(k, "")) for k in
                            ("foodNm", "foodLv3Nm", "foodLv4Nm", "foodLv5Nm"))
            if q in norm(text):
                hits.append(d)
        elif mode == "reportNo":
            if str(d.get("itemMnftrRptNo", "")).strip() == query.strip():
                hits.append(d)
        if len(hits) >= limit:
            break
    return hits


@st.cache_data(show_spinner=False)
def load_substitutes() -> list[dict]:
    return load_json("substitutes.json")  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def load_marketing_rules() -> dict:
    return load_json("marketing_rules.json")  # type: ignore[return-value]


def norm(s) -> str:
    """검색용 정규화 — 공백 제거 + 소문자."""
    return "".join(str(s).split()).lower() if s else ""


# ================================================================
# 기능성 텍스트 파서 — [성분] ①②③ / (가)(나) / · 구분자 처리
# ================================================================
import re as _re

_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_KR_LETTER = "가나다라마바사아자차카타파하"


def _split_bullets(text: str) -> list[str]:
    """한 섹션 텍스트를 번호/불릿 단위로 분할."""
    if not text:
        return []
    text = text.strip()

    # 1) ① 원번호
    if _re.search(rf'[{_CIRCLED}]', text):
        parts = _re.split(rf'[{_CIRCLED}]', text)
        prefix = parts[0].strip().rstrip(":·,.")
        result = [prefix] if prefix else []
        for p in parts[1:]:
            p = p.strip().rstrip(":·,.")
            if p:
                result.append(p)
        return result

    # 2) (가) 한글 번호
    if _re.search(rf'\([{_KR_LETTER}]\)', text):
        parts = _re.split(rf'\([{_KR_LETTER}]\)', text)
        prefix = parts[0].strip().rstrip(":·,.")
        result = [prefix] if prefix else []
        for p in parts[1:]:
            p = p.strip().rstrip(":·,.")
            if p:
                result.append(p)
        return result

    # 3) 중점(·) 구분 — 최소 2개 항목일 때만 분할
    if "·" in text or "･" in text:
        parts = [p.strip() for p in _re.split(r'[·･]', text) if p.strip()]
        if len(parts) >= 2:
            return parts

    # 4) 줄바꿈
    if "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        if len(parts) >= 2:
            return parts

    # 5) 콤마 구분 (3개 이상일 때만 — 설명형 쉼표 회피)
    if text.count(",") >= 2:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if all(len(p) <= 40 for p in parts):
            return parts

    return [text]


_RECOGNITION_NO = _re.compile(r'제\d{4}-\d+호')
_KO_MARKER = _re.compile(r'\(국문\)\s*')
_EN_MARKER = _re.compile(r'\(영문\)\s*')


def _bullet_split(text: str, *, allow_comma: bool = False) -> list[str]:
    """단일 텍스트 블록을 불릿 리스트로. 우선순위: ①②③ > (가) > \\n > ', '

    allow_comma=True: `, ` 분리 활성화 ((국문)/(영문) 마커 안에서만 안전).
    """
    text = text.strip().strip(",").strip()
    if not text:
        return []
    if _re.search(rf'[{_CIRCLED}]', text):
        parts = _re.split(rf'[{_CIRCLED}]', text)
        return [p.strip().rstrip(":·,.") for p in parts if p.strip()]
    if _re.search(rf'\([{_KR_LETTER}]\)', text):
        parts = _re.split(rf'\([{_KR_LETTER}]\)', text)
        return [p.strip().rstrip(":·,.") for p in parts if p.strip()]
    if "\n" in text:
        return [line.strip() for line in text.split("\n") if line.strip()]
    if allow_comma and ", " in text:
        return [s.strip() for s in text.split(", ") if s.strip()]
    return [text]


def _split_section_body(body: str) -> tuple[list[str], list[str]]:
    """섹션 본문을 (한글 불릿, 영문 불릿) 으로 분리.

    (국문)/(영문) 마커가 있으면 명시적 분리 — 마커 내부는 `, ` 분리도 허용.
    없으면 본문 전체를 한국어로 간주, 합성 문장은 그대로 보존.
    """
    body = body.strip()
    if not body:
        return [], []

    ko_m = _KO_MARKER.search(body)
    en_m = _EN_MARKER.search(body)

    if ko_m or en_m:
        if ko_m and en_m:
            ko_text = body[ko_m.end():en_m.start()]
            en_text = body[en_m.end():]
        elif ko_m:
            ko_text, en_text = body[ko_m.end():], ""
        else:
            ko_text, en_text = "", body[en_m.end():]
        return _bullet_split(ko_text, allow_comma=True), _bullet_split(en_text, allow_comma=True)

    return _bullet_split(body), []


def parse_functionality(text: str) -> list[dict]:
    """MAIN_FNCTN 원문을 {ingredient, recognition_no, benefits[...], english} 구조 리스트로.

    recognition_no: '제YYYY-NN호' 매칭 시 개별인정형, None 이면 고시형.
    english: (영문) 라벨이 있을 때 영문 효능 한 줄 텍스트.
    """
    if not text or not text.strip():
        return []
    text = text.strip()

    pattern = _re.compile(r'\[([^\]]+)\]')
    matches = list(pattern.finditer(text))
    sections: list[dict] = []

    def _make(ing: str | None, body: str) -> dict:
        rno = None
        if ing:
            m = _RECOGNITION_NO.search(ing)
            if m:
                rno = m.group(0)
        ko_bullets, en_bullets = _split_section_body(body)
        return {"ingredient": ing, "recognition_no": rno,
                "benefits": ko_bullets, "english": en_bullets}

    if not matches:
        return [_make(None, text)]

    # 첫 [ 앞에 prefix 텍스트가 있으면 no-ingredient 섹션으로
    first_start = matches[0].start()
    if first_start > 0:
        pre = text[:first_start].strip()
        if pre:
            sections.append(_make(None, pre))

    for i, m in enumerate(matches):
        ing = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        sections.append(_make(ing, body))

    return sections


def render_functionality(text: str, *, st_mod=None) -> None:
    """Streamlit 렌더러 — 정리된 기능성 뷰. 개별인정/고시형 뱃지 포함."""
    import streamlit as _st
    from theme import info_pill
    st_mod = st_mod or _st
    sections = parse_functionality(text)
    if not sections:
        st_mod.caption("—")
        return
    for sec in sections:
        if sec["ingredient"]:
            if sec["recognition_no"]:
                badge = info_pill(f"개별인정 · {sec['recognition_no']}", tone="success")
            else:
                badge = info_pill("고시형", tone="info")
            st_mod.markdown(f"**🔹 {sec['ingredient']}**  {badge}",
                            unsafe_allow_html=True)
        ko = sec["benefits"]
        en = sec.get("english") or []
        # 1:1 매핑 가능하면 영문을 각 한국어 불릿 밑에 caption 으로
        if en and len(en) == len(ko):
            for k, e in zip(ko, en):
                st_mod.markdown(f"- {k}")
                st_mod.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;🇬🇧 {e}",
                               unsafe_allow_html=True)
        else:
            for b in ko:
                st_mod.markdown(f"- {b}")
            if en:
                st_mod.caption("🇬🇧  \n" + "  \n".join(f"• {e}" for e in en))
        st_mod.write("")


def search_rwmatr(query: str, limit: int = 20) -> list[dict]:
    """원재료 표준사전(18,542건)에서 성분명 매칭."""
    if not query:
        return []
    q = norm(query)
    hits = []
    for row in load_rwmatr_all():
        target = " ".join(str(row.get(k, "")) for k in
                          ("RPRSNT_RAWMTRL_NM", "RAWMTRL_NCKNM", "ENG_NM", "SCNM"))
        if q in norm(target):
            hits.append(row)
            if len(hits) >= limit:
                break
    return hits


def search_htfs_by_ingredient(query: str, limit: int = 50) -> list[dict]:
    """건기식 DB(44K)에서 원재료/기능성/제품명에 성분 포함 제품 찾기."""
    if not query:
        return []
    q = query.strip()
    hits = []
    for it in load_htfs_all():
        hay = " ".join(str(it.get(k, "")) for k in
                       ("PRDUCT", "MAIN_FNCTN", "BASE_STANDARD"))
        if q in hay:
            hits.append(it)
            if len(hits) >= limit:
                break
    return hits


def search_htfs_by_product_name(query: str, limit: int = 50) -> list[dict]:
    """건기식 DB 제품명으로 검색."""
    if not query:
        return []
    q = norm(query)
    hits = []
    for it in load_htfs_all():
        if q in norm(it.get("PRDUCT", "")):
            hits.append(it)
            if len(hits) >= limit:
                break
    return hits


# 5-bucket 배지 색상
BUCKET_COLOR = {
    "①": "#2E7D32",    # 녹색 (판매 가능)
    "②": "#1976D2",    # 파랑 (대행 가능)
    "③": "#F57C00",    # 주황 (기회)
    "③-H": "#E64A19",  # 진주황 (호르몬 제약)
    "④": "#C62828",    # 빨강 (차단)
    "?": "#757575",    # 회색 (미분류)
}
BUCKET_LABEL = {
    "①": "현재 판매 가능",
    "②": "직구 대행 가능",
    "③": "미국 법인 기회",
    "③-H": "호르몬/성 제약",
    "④": "반입차단",
    "?": "미분류",
}


@lru_cache(maxsize=1)
def rwmatr_index() -> dict[str, list[dict]]:
    """원재료 사전 인덱스 (원재료명→엔트리들). 검색 성능용."""
    idx: dict[str, list[dict]] = {}
    for row in load_rwmatr_all():
        k = str(row.get("RPRSNT_RAWMTRL_NM", "")).strip()
        if not k:
            continue
        idx.setdefault(k, []).append(row)
        # 이명도 색인
        nk = str(row.get("RAWMTRL_NCKNM") or "").strip()
        if nk:
            idx.setdefault(nk, []).append(row)
    return idx


def lookup_rwmatr(name: str) -> dict | None:
    """원재료명(대충) → 가장 그럴듯한 사전 엔트리 1건. 미스 시 None."""
    if not name:
        return None
    idx = rwmatr_index()
    # 1) 완전 일치
    if name in idx:
        return idx[name][0]
    # 2) 포함 매칭 (이름 길이로 정렬)
    candidates: list[tuple[int, dict]] = []
    for key, rows in idx.items():
        if key and (key in name or name in key):
            candidates.append((abs(len(key) - len(name)), rows[0]))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    return None


# 기능성 키워드 → 범주 매핑 (간이 분류기)
FUNCTION_TAGS: dict[str, list[str]] = {
    "면역": ["면역", "면역력", "면역증진", "면역 과민"],
    "장건강": ["배변활동", "장 건강", "유산균", "유해균", "프로바이오틱스"],
    "혈당": ["혈당", "식후 혈당", "당대사"],
    "콜레스테롤": ["콜레스테롤"],
    "혈행": ["혈행", "혈소판", "혈액흐름"],
    "항산화": ["항산화", "유해산소"],
    "피로개선": ["피로"],
    "기억력": ["기억력"],
    "체지방": ["체지방", "다이어트"],
    "피부": ["피부", "피부건강"],
    "뼈/치아": ["뼈의 형성", "골다공증", "치아"],
    "간건강": ["간 건강"],
}


def tag_functions(text: str) -> list[str]:
    """기능성 원문에서 태그 추출."""
    tags: list[str] = []
    t = str(text or "")
    for tag, kws in FUNCTION_TAGS.items():
        if any(k in t for k in kws):
            tags.append(tag)
    return tags


def biocom_brand_list() -> list[str]:
    return [m["brand"] for m in load_master()]


def find_brand(brand: str) -> dict | None:
    for m in load_master():
        if m["brand"] == brand:
            return m
    return None
