"""바이오컴 11종 제품 마스터 데이터 1회 수집 → data/*.json 캐시 생성.

실행: `python collect_master.py`
출력:
  data/htfs_all.json          — 건기식 전체 (44K+건)
  data/rwmatr_all.json        — 원재료 사전 전체 (18K+건)
  data/htfs_cat_all.json      — 건기식 원료 분류 (I0760, 585건)
  data/biocom_master.json     — 바이오컴 11종 통합 카드 데이터
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from config import (
    BIOCOM_GENERAL_PRODUCTS,
    BIOCOM_HTFS_PRODUCTS,
    COMPANY_NAME,
    DATA_DIR,
)
from fetchers import blockraw, foodhist, htfs, htfs_cat, htfs_mfc, htfs_nutri, mfc_rpt, nutri, nutri_process, rwmatr


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  💾 {path.name}  ({path.stat().st_size//1024} KB)")


def step_htfs_all() -> list[dict]:
    path = DATA_DIR / "htfs_all.json"
    if path.exists():
        print("[1] htfs_all.json 캐시 존재 → 재사용")
        return json.loads(path.read_text(encoding="utf-8"))
    print("[1] 건기식 전체 페이지 다운로드 중...")
    items = htfs.fetch_all_htfs()
    save(path, items)
    return items


def step_rwmatr_all() -> list[dict]:
    path = DATA_DIR / "rwmatr_all.json"
    if path.exists():
        print("[2] rwmatr_all.json 캐시 존재 → 재사용")
        return json.loads(path.read_text(encoding="utf-8"))
    print("[2] 원재료 사전 전체 다운로드 중...")
    items = rwmatr.fetch_all()
    save(path, items)
    return items


def step_htfs_cat_all() -> list[dict]:
    path = DATA_DIR / "htfs_cat_all.json"
    if path.exists():
        print("[3] htfs_cat_all.json 캐시 존재 → 재사용")
        return json.loads(path.read_text(encoding="utf-8"))
    print("[3] 건기식 원료분류(I0760) 다운로드 중...")
    rows = htfs_cat.fetch_all()
    save(path, rows)
    return rows


def step_htfs_nutri_all() -> list[dict]:
    path = DATA_DIR / "htfs_nutri_all.json"
    if path.exists():
        print("[3.5] htfs_nutri_all.json 캐시 존재 → 재사용")
        return json.loads(path.read_text(encoding="utf-8"))
    print("[3.5] 건기식 영양성분(표준데이터) 다운로드 중...")
    rows = htfs_nutri.fetch_all()
    save(path, rows)
    return rows


def step_blocklist() -> list[dict]:
    path = DATA_DIR / "blocklist_282.json"
    if path.exists():
        print("[3.7] blocklist_282.json 캐시 존재 → 재사용")
        return json.loads(path.read_text(encoding="utf-8"))
    print("[3.7] 반입차단 원료·성분 다운로드 중...")
    rows = blockraw.fetch_all()
    save(path, rows)
    return rows


def build_biocom_master(htfs_all: list[dict], htfs_nutri_all: list[dict]) -> list[dict]:
    """바이오컴 11종 각각에 대해 여러 API 결과를 한 객체로 합침."""
    print("[4] 바이오컴 11종 통합 데이터 빌드 중...")
    master: list[dict] = []

    # 건기식 8종
    hits_by_name = htfs.filter_by_product_name(htfs_all, BIOCOM_HTFS_PRODUCTS)
    for brand in BIOCOM_HTFS_PRODUCTS:
        hits = hits_by_name.get(brand, [])
        # 복수 매칭 중 검색어에 가장 가까운 것 우선 (이름이 짧은 것)
        hits = sorted(hits, key=lambda it: len(str(it.get("PRDUCT", ""))))
        if not hits:
            master.append({"brand": brand, "category": "건기식", "_note": "미매칭"})
            continue
        htfs_row = hits[0]
        product_name = str(htfs_row.get("PRDUCT", "")).strip()
        sttemnt_no = str(htfs_row.get("STTEMNT_NO", "")).strip()

        # 식품이력 원재료 — 풀네임 먼저, 0건이면 brand 짧은 이름으로 fallback
        print(f"   - {brand}: 이력 원재료 조회 (풀네임)...")
        foodhist_rows = foodhist.fetch_by_product_name(product_name)
        time.sleep(0.4)
        if not foodhist_rows:
            short = brand.replace(" ", "")  # "바이오 밸런스" → "바이오밸런스"
            print(f"     풀네임 0건 → 브랜드명 '{brand}' 재시도")
            foodhist_rows = foodhist.fetch_by_product_name(brand)
            time.sleep(0.4)
            if not foodhist_rows and short != brand:
                print(f"     → 공백제거 '{short}' 재시도")
                foodhist_rows = foodhist.fetch_by_product_name(short)
                time.sleep(0.4)
        print(f"     이력 원재료: {len(foodhist_rows)}건")

        # 건기식 영양성분 — STTEMNT_NO ↔ itemMnftrRptNo
        nutri_row = htfs_nutri.find_by_report_no(htfs_nutri_all, sttemnt_no)
        if not nutri_row:
            # 제품명 fallback
            alt = htfs_nutri.filter_by_product_name(htfs_nutri_all, brand)
            if alt:
                nutri_row = alt[0]
        print(f"     영양성분: {'✓' if nutri_row else '—'}")

        # C003 건기식 품목제조신고 — 원재료 전체 텍스트 확보
        htfs_mfc_row = htfs_mfc.fetch_by_report_no(sttemnt_no) if sttemnt_no else None
        print(f"     C003 품목제조신고: {'✓' if htfs_mfc_row else '—'}")

        master.append({
            "brand": brand,
            "category": "건기식",
            "htfs": htfs_row,
            "htfs_all_hits": hits,       # 동명 다중 매칭 참고용
            "foodhist_rawmtrl": foodhist_rows,
            "htfs_nutri": nutri_row,
            "htfs_mfc": htfs_mfc_row,
        })

    # 일반식품 3종
    for gp in BIOCOM_GENERAL_PRODUCTS:
        brand, rno = gp["brand"], gp["report_no"]
        print(f"   - {brand} (일반식품, 보고번호 {rno})")
        # C002: 품목제조보고(원재료)
        mfc_row = mfc_rpt.fetch_by_report_no(rno)

        # 가공식품 영양성분 통합 (tn_pubr_public_nutri_process_info_api) — 보고번호 정확매칭
        nutri_rows_new = nutri_process.search_by_report_no(rno)
        print(f"     가공식품 영양 통합(신규 API): {len(nutri_rows_new)}건")

        # 기존 식품영양성분DB 도 항상 fallback으로 시도 (스키마 다름, 병합 저장)
        nutri_row_old = None
        if brand == "메타드림":
            nutri_row_old = nutri.search_by_report_no(rno, maker_hint="콜마비앤에이치")
        else:
            nutri_row_old = nutri.search_by_report_no(rno, maker_hint="엔피케이")
        print(f"     기존 식품영양성분DB: {'✓' if nutri_row_old else '—'}")

        master.append({
            "brand": brand,
            "category": "일반식품",
            "official_name": gp["official_name"],
            "report_no": rno,
            "mfc_rpt": mfc_row,
            "nutri": nutri_row_old,               # 기존 스키마 (FOOD_NM_KR, AMT_NUM1..)
            "nutri_process": nutri_rows_new,      # 신규 스키마 (foodNm, enerc..) 리스트
        })

    save(DATA_DIR / "biocom_master.json", master)
    return master


def main() -> None:
    print("=" * 60)
    print("바이오컴 11종 마스터 수집")
    print("=" * 60)
    htfs_all = step_htfs_all()
    step_rwmatr_all()
    step_htfs_cat_all()
    htfs_nutri_all = step_htfs_nutri_all()
    step_blocklist()
    master = build_biocom_master(htfs_all, htfs_nutri_all)

    print("\n요약:")
    for m in master:
        tag = "✅" if not m.get("_note") else "⚠️"
        print(f"  {tag} {m['brand']} [{m['category']}]")


if __name__ == "__main__":
    main()
