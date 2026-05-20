"""
바이오컴 건기식 11종 공공데이터 수집 스크립트
================================================

식품의약품안전처 공공데이터 API를 통해 바이오컴 건강기능식품 11종의
공식 정보(기능성, 원재료, 섭취방법, 주의사항 등)를 수집합니다.

[사용하는 API]
1) 건강기능식품정보 (https://www.data.go.kr/data/15056760/openapi.do)
   - 입력: 제품명 또는 업체명
   - 출력: 품목제조관리번호, 업소명, 제품명, 유통기한, 섭취량 등 기본정보

2) 건강기능식품 품목제조신고 (선택)
   - 입력: 품목제조관리번호(1번 API에서 받아온 값)
   - 출력: "주된 기능성", "섭취 시 주의사항", "원재료" 등 상세정보
   - ※ 사용자가 이 API도 신청했을 경우에만 활성화됨 (아래 USE_DETAIL_API 참고)

[사전 준비]
- pip install requests pandas openpyxl
- 공공데이터포털(data.go.kr)에서 API 신청 및 승인 완료
- 마이페이지 > 개발계정 > 서비스키(Encoding) 복사

[실행 방법]
1) 아래 SERVICE_KEY 에 본인 키 붙여넣기
2) python biocom_htfs_collector.py
3) ./output/ 폴더에 결과 파일이 생성됨
   - biocom_htfs_basic.json      : 1차 수집 원본
   - biocom_htfs_detail.json     : 2차 수집 원본(상세 API 사용 시)
   - biocom_htfs_summary.xlsx    : 정리된 엑셀 (수작업 채움용 템플릿 포함)
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

# ==============================================================
# 1. 설정
# ==============================================================

# 공공데이터포털에서 발급받은 서비스키(Encoding 버전)를 붙여넣으세요.
# 예: "abcd1234%2Befgh5678%3D%3D"
SERVICE_KEY = "s8fwjSgEXE3TSTH1yJ6NVhRTyRzA/CSdiH4Q4OkFPV1y2Y9qra1gDeTVSmvcKAbAqY2G9HXLBlDhs97sSx0Yow=="

# 상세 API(건강기능식품 품목제조신고) 승인 여부
# True: 품목제조관리번호로 상세(기능성 등) 까지 조회
# False: 기본 정보만 수집 (기능성/주의사항 등은 수기 입력용 템플릿으로 제공)
USE_DETAIL_API = False

# 바이오컴 제조/판매 제품 11종
# ⚠️ 실제 식약처 등록 제품명과 정확히 일치해야 매칭됨.
#    제품 라벨/패키지 기준으로 미세 표기 차이(띄어쓰기, 특수문자)를 맞춰주세요.
BIOCOM_PRODUCTS = [
    "바이오 밸런스",
    "영데이즈",
    "클린 밸런스",
    "당당케어",
    "썬화이버",
    "방탄젤리",
    "리셋데이",
    "메타드림",
    "풍성 밸런스",
    "뉴로 마스터",
    "다래케어",
]

# 업체명으로 한 번에 검색해보고 싶을 때 사용(정확한 법인명 입력 필요)
# 예: "바이오컴" 으로 나오는지 혹은 제조업체가 OEM이라 다른 이름인지 확인해야 함
COMPANY_NAME = "바이오컴"

# 출력 경로
OUTPUT_DIR = Path("./output")
OUTPUT_DIR.mkdir(exist_ok=True)

# API 엔드포인트
# ※ 공공데이터포털 마이페이지의 "요청주소"와 반드시 일치시키세요.
#   승인 후 발급되는 상세 페이지의 요청 URL을 복사하는 것이 가장 정확합니다.
BASE_URL_BASIC = "http://apis.data.go.kr/1471000/HtfsInfoService03/getHtfsItem01"
BASE_URL_DETAIL = "http://apis.data.go.kr/1471000/HtfsMftcInfoService/getHtfsMftcItem"

# 공공데이터 API는 호출당 1초 내외 간격을 두는 것이 안전
REQUEST_INTERVAL = 0.5


# ==============================================================
# 2. API 호출 함수
# ==============================================================

def call_api(url: str, params: dict) -> dict:
    """
    공공데이터 API 공통 호출 함수.
    JSON으로 받아 dict 반환. 실패 시 에러 메시지 포함해 반환.
    """
    params = {**params, "ServiceKey": SERVICE_KEY, "type": "json"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        # 공공데이터는 XML로 응답하는 경우도 있으니 확인
        try:
            return resp.json()
        except ValueError:
            return {"_raw_text": resp.text, "_error": "JSON 파싱 실패 (XML일 가능성)"}
    except requests.RequestException as e:
        return {"_error": str(e)}


def search_by_product_name(product_name: str) -> dict:
    """건강기능식품정보 API: 제품명으로 검색"""
    params = {
        "pageNo": "1",
        "numOfRows": "20",
        # 파라미터명은 API 문서의 "요청변수"에 맞춰주세요.
        # 자주 쓰는 변수명: prduct(제품명), bssh_nm(업소명)
        "prduct": product_name,
    }
    return call_api(BASE_URL_BASIC, params)


def search_by_company(company_name: str, page: int = 1) -> dict:
    """건강기능식품정보 API: 업체명으로 검색 (페이지네이션)"""
    params = {
        "pageNo": str(page),
        "numOfRows": "100",
        "bssh_nm": company_name,
    }
    return call_api(BASE_URL_BASIC, params)


def fetch_detail_by_report_no(prdlst_report_no: str) -> dict:
    """건강기능식품 품목제조신고 API: 품목제조관리번호로 상세 조회"""
    params = {
        "PRDLST_REPORT_NO": prdlst_report_no,
    }
    return call_api(BASE_URL_DETAIL, params)


# ==============================================================
# 3. 응답 파싱 헬퍼
# ==============================================================

def extract_items(api_response: dict) -> list[dict]:
    """
    공공데이터 표준 응답 구조에서 items 리스트만 꺼내는 함수.
    구조: response > body > items (또는 items > item)
    실제 구조는 API 문서/실제 응답으로 한번 더 확인 필요.
    """
    if "_error" in api_response:
        return []

    try:
        # 이 API 응답: {"header":..., "body": {"items":[{"item":{...}}, ...]}}
        # (일부 공공데이터 API는 response > body 로 한 단계 더 감싸기도 함)
        body = api_response.get("body") or api_response.get("response", {}).get("body", {})
        items = body.get("items", [])
        # 어떤 API는 items: [{item: {...}}, ...], 어떤 API는 items: [{...}, ...]
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, list):
            # item 래핑 해제
            if items and isinstance(items[0], dict) and "item" in items[0] and len(items[0]) == 1:
                return [x["item"] for x in items]
            return items
        return []
    except (AttributeError, TypeError):
        return []


# ==============================================================
# 4. 수집 루프
# ==============================================================

def _norm(s: str) -> str:
    """제품명 매칭용 정규화: 공백/특수문자 제거"""
    return "".join(ch for ch in str(s) if not ch.isspace()).lower()


def collect_basic_info() -> list[dict]:
    """
    HtfsInfoService03/getHtfsItem01 은 검색 파라미터를 받지 않고 전체 목록만 반환하므로,
    전체 페이지를 순회 다운로드한 뒤 로컬에서 ENTRPS(업체) / PRDUCT(제품명)로 필터링.
    """
    print("=" * 60)
    print("[1단계] 건강기능식품정보 API 전체 페이지 다운로드 후 로컬 필터")
    print("=" * 60)

    # 첫 페이지로 totalCount 확인
    page_size = 500  # API 상한
    first = call_api(BASE_URL_BASIC, {"pageNo": "1", "numOfRows": str(page_size)})
    body = first.get("body") or first.get("response", {}).get("body", {})
    total = int(body.get("totalCount", 0))
    if total == 0:
        print(f"❌ totalCount=0 — 응답: {first}")
        return []
    total_pages = (total + page_size - 1) // page_size
    print(f"   전체 {total:,}건, 페이지당 {page_size}건 → {total_pages} 페이지")

    all_items: list[dict] = extract_items(first)
    for page in range(2, total_pages + 1):
        raw = call_api(BASE_URL_BASIC, {"pageNo": str(page), "numOfRows": str(page_size)})
        items = extract_items(raw)
        all_items.extend(items)
        print(f"   페이지 {page}/{total_pages} ({len(items)}건) 누적 {len(all_items):,}")
        time.sleep(REQUEST_INTERVAL)

    print(f"\n   ✅ 총 {len(all_items):,}건 수신 완료. 로컬 필터링 시작")

    # 1) 업체명 "바이오컴" 포함
    biocom_items = [it for it in all_items if COMPANY_NAME in str(it.get("ENTRPS", ""))]
    print(f"   업체명 '{COMPANY_NAME}' 매칭: {len(biocom_items)}건")

    # 2) 제품명 매칭 (업체명 무관 — 위탁제조/OEM 대비)
    product_keys = [_norm(n) for n in BIOCOM_PRODUCTS]
    product_hits: dict[str, list[dict]] = {n: [] for n in BIOCOM_PRODUCTS}
    for it in all_items:
        prod_norm = _norm(it.get("PRDUCT", ""))
        for orig, key in zip(BIOCOM_PRODUCTS, product_keys):
            if key and key in prod_norm:
                product_hits[orig].append(it)

    # 결과 조립: 검색어 라벨 붙이기
    results: list[dict] = []
    for name in BIOCOM_PRODUCTS:
        hits = product_hits[name]
        # 중복 제거를 위해 바이오컴 업체 매치 여부 플래그
        if hits:
            for it in hits:
                results.append({
                    "검색어": name,
                    "is_biocom_match": COMPANY_NAME in str(it.get("ENTRPS", "")),
                    **it,
                })
            print(f"   '{name}': 제품명 매칭 {len(hits)}건")
        else:
            results.append({
                "검색어": name,
                "_note": "전체 DB에서 해당 제품명 미발견 — 정확한 등록명 확인 필요",
            })
            print(f"   '{name}': 매칭 없음")

    # 바이오컴 업체 매치지만 제품명 리스트와 안 겹치는 것도 별도로 보존
    product_hit_ids = {id(h) for hits in product_hits.values() for h in hits}
    extras = [it for it in biocom_items if id(it) not in product_hit_ids]
    for it in extras:
        results.append({
            "검색어": f"(업체매치만) {it.get('PRDUCT','')}",
            "is_biocom_match": True,
            **it,
        })
    if extras:
        print(f"   + 업체 '{COMPANY_NAME}' 매칭이지만 제품명 외인 항목 {len(extras)}건")

    return results


def collect_detail_info(basic_results: list[dict]) -> list[dict]:
    """
    1단계 결과에서 품목제조관리번호를 뽑아 상세 API 호출.
    USE_DETAIL_API가 True일 때만 실행.
    """
    if not USE_DETAIL_API:
        print("\n⏭️  상세 API 호출 skip (USE_DETAIL_API=False)")
        return []

    print("\n" + "=" * 60)
    print("[2단계] 건강기능식품 품목제조신고 API로 상세 조회")
    print("=" * 60)

    details = []
    for row in basic_results:
        # 품목제조관리번호 필드명: PRDLST_REPORT_NO / prdlst_report_no / 품목제조관리번호 등
        report_no = (
            row.get("PRDLST_REPORT_NO")
            or row.get("prdlst_report_no")
            or row.get("품목제조관리번호")
        )
        if not report_no:
            continue

        print(f"\n📄 상세조회: {row.get('검색어')} / {report_no}")
        raw = fetch_detail_by_report_no(str(report_no))
        items = extract_items(raw)

        if items:
            for it in items:
                details.append({
                    "검색어": row.get("검색어"),
                    "품목제조관리번호": report_no,
                    **it,
                })
        else:
            details.append({
                "검색어": row.get("검색어"),
                "품목제조관리번호": report_no,
                "_note": "상세 조회 결과 없음",
                "_raw": raw,
            })

        time.sleep(REQUEST_INTERVAL)

    return details


# ==============================================================
# 5. 엑셀 출력 (수작업 보완용 템플릿 포함)
# ==============================================================

def save_summary_excel(basic: list[dict], detail: list[dict]) -> None:
    """
    수집 결과를 한 눈에 볼 엑셀로 저장.
    시트 구성:
      - 01_기본정보: 1단계 API 결과
      - 02_상세정보: 2단계 API 결과 (있을 경우)
      - 03_정리템플릿: 11종 × 필요 컬럼 매트릭스 (수기 보완용)
    """
    out_path = OUTPUT_DIR / "biocom_htfs_summary.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:

        # 시트 1: 기본정보
        if basic:
            df_basic = pd.DataFrame(basic)
            df_basic.to_excel(writer, sheet_name="01_기본정보", index=False)

        # 시트 2: 상세정보
        if detail:
            df_detail = pd.DataFrame(detail)
            df_detail.to_excel(writer, sheet_name="02_상세정보", index=False)

        # 시트 3: 11종 정리 템플릿
        template_cols = [
            "제품명",
            "업소명(정식 법인명)",
            "품목제조관리번호",
            "식품유형",
            "주된 기능성(공식문구)",
            "기능성 원료",
            "일일섭취량",
            "섭취방법",
            "섭취 시 주의사항",
            "보관방법",
            "원재료명",
            "유통기한",
            "데이터 출처",  # API / 제품라벨 / 수기 등
            "비고",
        ]
        df_template = pd.DataFrame(
            {col: ["" for _ in BIOCOM_PRODUCTS] for col in template_cols}
        )
        df_template["제품명"] = BIOCOM_PRODUCTS
        df_template.to_excel(writer, sheet_name="03_정리템플릿", index=False)

    print(f"\n💾 엑셀 저장 완료: {out_path}")


# ==============================================================
# 6. 메인
# ==============================================================

def main() -> None:
    if SERVICE_KEY == "여기에_본인_서비스키_붙여넣기":
        print("❌ SERVICE_KEY 를 본인의 공공데이터 서비스키로 바꿔주세요.")
        return

    # 1단계: 제품명 기반 검색
    basic = collect_basic_info()
    with open(OUTPUT_DIR / "biocom_htfs_basic.json", "w", encoding="utf-8") as f:
        json.dump(basic, f, ensure_ascii=False, indent=2)
    print(f"\n💾 1단계 저장: {OUTPUT_DIR / 'biocom_htfs_basic.json'}")

    # 2단계: 상세 조회 (선택)
    detail = collect_detail_info(basic)
    if detail:
        with open(OUTPUT_DIR / "biocom_htfs_detail.json", "w", encoding="utf-8") as f:
            json.dump(detail, f, ensure_ascii=False, indent=2)
        print(f"💾 2단계 저장: {OUTPUT_DIR / 'biocom_htfs_detail.json'}")

    # 3단계: 엑셀로 통합
    save_summary_excel(basic, detail)

    # 요약 출력
    print("\n" + "=" * 60)
    print("📊 수집 요약")
    print("=" * 60)
    found = sum(1 for r in basic if "_note" not in r and "_api_error" not in r)
    print(f"  전체 검색 제품: {len(BIOCOM_PRODUCTS)}개")
    print(f"  API 조회 성공(건수 기준): {found}건")
    print(f"  상세 API 호출: {'ON' if USE_DETAIL_API else 'OFF'}")
    print(f"\n📁 결과 위치: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
