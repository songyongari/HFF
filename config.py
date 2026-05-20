"""바이오컴 건기식/일반식품 통합 조회 프로젝트 설정"""
from __future__ import annotations

import os
from pathlib import Path

# .env 간단 파싱 (python-dotenv 의존성 제거)
_ROOT = Path(__file__).parent
_env_path = _ROOT / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


# === API 키 ===
def _get_key(name: str) -> str:
    """환경변수 → Streamlit secrets 순으로 조회. 둘 다 없으면 빈 문자열.

    배포 환경(Streamlit Cloud)에서 secrets 누락 시 import 단계에서 죽지 않도록
    빈 문자열 fallback. 앱 대부분은 사전 수집된 data/*.json 만 사용하므로
    키 없이도 동작. 라이브 API 호출(C002, FoodHist on-demand) 만 실패함.
    """
    val = os.environ.get(name)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets[name]
    except Exception:
        return ""

KEY_DATAGO = _get_key("KEY_DATAGO")   # 공공데이터포털 (Decoding)
KEY_FSKR = _get_key("KEY_FSKR")       # 식품안전나라


# === data.go.kr 엔드포인트 ===
DG_BASE = "http://apis.data.go.kr/1471000"
URL_HTFS = f"{DG_BASE}/HtfsInfoService03/getHtfsItem01"             # 건강기능식품정보
URL_FOODHIST = f"{DG_BASE}/FoodHistInfoService03/getPrductRawmtrlList03"  # 식품이력 원재료
URL_RWMATR = f"{DG_BASE}/FoodRwmatrInfoService01/getFoodRwmatrList01"     # 식품원재료 사전
URL_NUTRI = f"{DG_BASE}/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02"        # 식품영양성분DB


# === 식품안전나라 엔드포인트 ===
FSKR_BASE = "http://openapi.foodsafetykorea.go.kr/api"
SID_HTFS_CAT = "I0760"   # 건강기능식품 영양DB (실제: 원료/기능성 분류)
SID_MFC_RPT = "C002"     # 식품(첨가물)품목제조보고(원재료)
SID_HTFS_MFC = "C003"    # 건강기능식품 품목제조신고(원재료)


# === 바이오컴 제품 마스터 ===
# 건기식 8종 — HtfsInfoService03 검색용
BIOCOM_HTFS_PRODUCTS = [
    "바이오 밸런스",
    "클린밸런스",
    "당당케어",
    "썬화이버",
    "방탄젤리",
    "풍성밸런스",
    "뉴로마스터",
    "다래케어",
]

# 일반식품 3종 — 품목제조보고번호로 직접 조회
BIOCOM_GENERAL_PRODUCTS = [
    {"brand": "영데이즈", "report_no": "20100515088653",
     "official_name": "슈퍼슬로우 & 화이트샷 영데이즈 SOD 효소 리포좀 글루타치온"},
    {"brand": "리셋데이", "report_no": "20100515088718",
     "official_name": "리셋데이 글루텐분해효소 알파CD 차전자피 K-낙산균"},
    {"brand": "메타드림", "report_no": "20060445110961",
     "official_name": "메타드림 식물성 멜라토닌 함유"},
]

COMPANY_NAME = "바이오컴"

# === 경로 ===
DATA_DIR = _ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
