"""3개 연구 문서(.md)와 다빈치랩 성분 DB(.xlsx)에서 성분 마스터 시드를 생성.

출력:
  data/ingredient_master.json   — 56 롱리스트 통합 성분 (+ 다빈치 성분 역매핑)
  data/davinci_products.json    — 다빈치랩 21종 제품 구성
  data/substitutes.json         — 반입차단 → 대체 성분 매핑
  data/supplier_coverage.json   — 다빈치 38 쇼트리스트 🟢🟡🔴

실행: python seed_ingredients.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent
RESEARCH_DIR = Path("C:/Users/바이오컴/Desktop/davinchi rab")
XLSX_PATH = Path("C:/Users/바이오컴/Desktop/기획/건강기능식품/원본/최신_영양제 성분 DB_251103.xlsx")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


# ========================================================
# 1. 56 성분 롱리스트 — 검사 매핑 (수기 시드, 원본: 01_ §4.1)
# ========================================================
# 5종 검사 연결: oat / igg / hormone / hair / microbiome
# 주석에 카테고리도 병기 — ingredient_master 의 category 필드로 사용

RAW_56 = [
    # (한글명, 영문/학명, aliases, 카테고리, {oat,igg,hormone,hair,microbiome 태그문자열 or None}, note)
    ("메틸B12", "Methylcobalamin", ["메틸코발라민"], "메틸화", {"oat": "메틸화"}, ""),
    ("5-MTHF", "L-Methylfolate", ["L-메틸폴레이트", "Quatrefolic"], "메틸화", {"oat": "메틸화"}, ""),
    ("P5P", "Pyridoxal-5-Phosphate", ["활성형 B6"], "메틸화", {"oat": "메틸화"}, ""),
    ("TMG", "Trimethylglycine", ["베타인"], "메틸화", {"oat": "메틸화"}, ""),
    ("SAM-e", "S-Adenosyl Methionine", [], "메틸화", {"oat": "메틸화"}, "의약품 분류"),
    ("CoQ10 (유비퀴놀)", "Ubiquinol", ["코큐텐"], "미토콘드리아", {"oat": "에너지"}, ""),
    ("PQQ", "Pyrroloquinoline Quinone", [], "미토콘드리아", {"oat": "에너지"}, ""),
    ("L-카르니틴", "L-Carnitine", ["L-카르니틴 타르트레이트"], "미토콘드리아", {"oat": "에너지"}, ""),
    ("ALCAR", "Acetyl-L-Carnitine", ["아세틸-L-카르니틴"], "미토콘드리아", {"oat": "에너지·인지"}, ""),
    ("D-리보스", "D-Ribose", [], "미토콘드리아", {"oat": "에너지"}, ""),
    ("NMN", "Nicotinamide Mononucleotide", [], "미토콘드리아/Longevity", {"oat": "NAD+"}, "최대 트렌드"),
    ("NR", "Nicotinamide Riboside", ["Tru Niagen"], "미토콘드리아/Longevity", {"oat": "NAD+"}, ""),
    ("NAC", "N-Acetyl Cysteine", [], "해독", {"oat": "해독/항산화"}, "반입차단 확정"),
    ("글루타티온 (리포좀)", "Liposomal Glutathione", ["S-아세틸 글루타티온"], "해독", {"oat": "해독", "hair": "해독"}, ""),
    ("ALA", "Alpha Lipoic Acid", ["R-ALA", "알파리포산"], "해독/중금속", {"oat": "해독", "hair": "해독"}, ""),
    ("글리신", "Glycine", [], "해독/신경", {"oat": "해독·신경"}, ""),
    ("타우린", "Taurine", [], "해독/신경", {"oat": "해독·신경"}, ""),
    ("Urolithin A", "Urolithin A", ["Mitopure"], "Longevity", {"oat": "미토파지"}, "Timeline 독점"),
    ("Spermidine", "Spermidine", [], "Longevity", {"oat": "자가포식"}, ""),
    ("Fisetin", "Fisetin", [], "Longevity", {"oat": "세노리틱"}, "신규"),
    ("베르베린", "Berberine", [], "5R/대사", {"igg": "항균", "microbiome": "항균"}, "대사·혈당·장 공통"),
    ("오레가노 오일", "Oregano Oil", [], "5R/항균", {"igg": "항균", "microbiome": "항균"}, ""),
    ("카프릴산", "Caprylic Acid", [], "5R/항균", {"igg": "Candida", "microbiome": "Candida"}, ""),
    ("파우다르코/올리브잎", "Pau d'Arco / Olive Leaf", [], "5R/항균", {"igg": "항균", "microbiome": "항균"}, ""),
    ("광범위 소화효소", "Digestive Enzyme Complex", ["프로테아제+리파아제+아밀라아제"], "5R/소화", {"igg": "소화 지원"}, ""),
    ("DPP-IV 효소", "DPP-IV Enzyme", [], "5R/소화", {"igg": "글루텐·카제인 분해"}, ""),
    ("HCL+펩신", "HCL + Pepsin", [], "5R/소화", {"igg": "위산"}, ""),
    ("담즙산염", "Ox Bile", [], "5R/소화", {"igg": "지방 소화"}, "수입 회색"),
    ("콜로스트럼", "Bovine Colostrum", [], "5R/면역", {"igg": "장벽·면역"}, "2026 최대 트렌드"),
    ("SBI", "Serum Bovine Immunoglobulin", ["2000 IgG 복합"], "5R/장벽", {"igg": "장벽"}, "회색 성분"),
    ("아연-카르노신", "Zinc Carnosine", ["PepZin GI"], "5R/장벽", {"igg": "장벽", "hair": "아연"}, ""),
    ("L-글루타민", "L-Glutamine", [], "장벽", {"igg": "장벽"}, ""),
    ("쿼르세틴", "Quercetin", [], "항염", {"igg": "마스트세포"}, ""),
    ("슬리퍼리엘름/DGL", "Slippery Elm / DGL", [], "장벽", {"igg": "장벽"}, ""),
    ("알로에베라", "Aloe Vera Inner Leaf", [], "장벽", {"igg": "장벽"}, ""),
    ("커큐민", "Curcumin", ["Meriva", "고흡수형"], "항염", {"igg": "항염"}, ""),
    ("아슈와간다 Shoden", "Ashwagandha (Shoden)", ["Withania somnifera"], "어댑토젠", {"hormone": "HPA 수면"}, "개별인정 '수면질'"),
    ("홍경천", "Rhodiola rosea", [], "어댑토젠", {"hormone": "HPA 피로"}, "개별인정 '피로개선'"),
    ("홀리바질", "Holy Basil (Tulsi)", [], "어댑토젠", {"hormone": "HPA"}, ""),
    ("엘류테로", "Eleuthero", ["Siberian Ginseng"], "어댑토젠", {"hormone": "HPA"}, ""),
    ("마카", "Maca", ["Lepidium meyenii"], "어댑토젠/성호르몬", {"hormone": "성호르몬 보조"}, "성기능 표방 주의"),
    ("인삼", "Panax Ginseng", [], "어댑토젠", {"hormone": "HPA"}, ""),
    ("감초", "Licorice", [], "어댑토젠", {"hormone": "HPA", "igg": "장벽"}, "고혈압 주의"),
    ("코디세프스", "Cordyceps", ["동충하초"], "어댑토젠", {"hormone": "HPA"}, ""),
    ("Mg L-트레오네이트", "Magnesium L-Threonate", [], "수면/뇌", {"hormone": "수면", "hair": "미네랄"}, "뇌 침투"),
    ("L-테아닌", "L-Theanine", ["Suntheanine"], "수면/이완", {"hormone": "수면"}, "개별인정"),
    ("GABA", "Gamma-Aminobutyric Acid", [], "수면", {"hormone": "수면"}, "개별인정 '수면'"),
    ("포스파티딜세린", "Phosphatidylserine", ["PS"], "수면/뇌", {"hormone": "코르티솔"}, "개별인정 '기억력'"),
    ("타트체리", "Tart Cherry Extract", [], "수면", {"hormone": "수면"}, "멜라토닌 미량"),
    ("DIM", "Diindolylmethane", [], "여성호르몬", {"hormone": "에스트로겐 대사"}, "갱년기 표방 주의"),
    ("I3C", "Indole-3-Carbinol", [], "여성호르몬", {"hormone": "에스트로겐 대사"}, ""),
    ("Calcium-D-Glucarate", "Calcium-D-Glucarate", [], "여성호르몬", {"hormone": "에스트로겐 대사"}, ""),
    ("호로파/Tongkat/Tribulus", "Fenugreek / Tongkat Ali / Tribulus", [], "성호르몬", {"hormone": "성호르몬"}, "성 표방 금지"),
    ("Mg 글리시네이트", "Magnesium Glycinate", [], "미네랄", {"hormone": "수면·근이완", "hair": "미네랄"}, ""),
    ("아연 피콜리네이트", "Zinc Picolinate", [], "미네랄", {"hair": "미네랄", "hormone": "호르몬"}, ""),
    ("셀레늄 메티오닌", "Selenomethionine", [], "미네랄/해독", {"hair": "수은 억제·갑상선", "hormone": "갑상선"}, ""),
    ("요오드", "Iodine", ["Lugol's", "Potassium Iodide"], "미네랄/갑상선", {"hair": "갑상선", "hormone": "갑상선"}, ""),
    ("구리 비스글리시네이트", "Copper Bisglycinate", [], "미네랄", {"hair": "미네랄"}, ""),
    ("크로뮴 피콜리네이트", "Chromium Picolinate", [], "미네랄/대사", {"hair": "혈당"}, "혈당 표방 주의"),
    ("몰리브덴", "Molybdenum", [], "미네랄", {"hair": "미네랄"}, ""),
    ("붕소", "Boron", [], "미네랄", {"hair": "뼈·호르몬", "hormone": "뼈 지원"}, ""),
    ("클로렐라", "Chlorella", ["CGF"], "중금속 해독", {"hair": "중금속 흡착"}, ""),
    ("MCP", "Modified Citrus Pectin", ["PectaSol-C"], "중금속 해독", {"hair": "중금속 흡착"}, ""),
    ("제올라이트", "Zeolite (Clinoptilolite)", [], "중금속 해독", {"hair": "중금속 흡착"}, "회색"),
    ("활성탄", "Activated Charcoal", [], "해독", {"hair": "흡착"}, ""),
    ("실란트로", "Cilantro Extract", [], "중금속 해독", {"hair": "킬레이션"}, ""),
    ("밀크씨슬", "Milk Thistle (Silymarin)", [], "간 지원", {"hair": "간 지원"}, "개별인정 '간건강'"),
    ("L. rhamnosus GG", "Lactobacillus rhamnosus GG", [], "프로바이오틱스", {"microbiome": "면역·설사"}, "고시 균주"),
    ("L. plantarum", "Lactobacillus plantarum", ["Probio 65"], "프로바이오틱스", {"microbiome": "장벽·SIBO"}, ""),
    ("Bifido 3종", "Bifidobacterium longum/lactis/infantis", [], "프로바이오틱스", {"microbiome": "노화·어린이·염증"}, "고시"),
    ("S. boulardii", "Saccharomyces boulardii", [], "프로바이오틱스", {"microbiome": "효모형·항생제 후", "igg": "5R"}, ""),
    ("Akkermansia", "Akkermansia muciniphila", ["Pendulum"], "차세대 균주", {"microbiome": "장점막·대사"}, "Pendulum 독점, 최대 트렌드"),
    ("Faecalibacterium", "Faecalibacterium prausnitzii", [], "차세대 균주", {"microbiome": "항염"}, "초기 시장"),
    ("포자형 균주", "Spore-forming Probiotic", ["Megasporebiotic"], "프로바이오틱스", {"microbiome": "포자형"}, ""),
    ("PHGG", "Partially Hydrolyzed Guar Gum", [], "프리바이오틱스", {"microbiome": "식이섬유"}, "고시 식이섬유"),
    ("아카시아 섬유/이눌린/FOS/GOS", "Acacia Fiber / Inulin / FOS / GOS", [], "프리바이오틱스", {"microbiome": "식이섬유"}, "고시"),
    ("부티레이트", "Butyrate (Ca/Mg)", [], "포스트바이오틱스", {"oat": "장 대사", "microbiome": "SCFA"}, "OAT+장 공통"),
    ("락토페린", "Lactoferrin", [], "면역/포스트바이오틱스", {"igg": "면역", "microbiome": "면역"}, "개별인정"),
    ("오메가-3 EPA", "Omega-3 High-EPA", [], "범용/항염", {"oat": "항염", "igg": "항염", "hormone": "항염"}, ""),
    ("D3+K2", "Vitamin D3 + K2", [], "범용/뼈·면역", {"hormone": "호르몬 지원", "hair": "뼈"}, ""),
    ("Inositol", "Inositol (Myo/D-chiro)", [], "대사/여성", {"hormone": "PCOS·대사"}, "여성 시장 핵심"),
    ("Berberine", "Berberine", [], "대사/GLP-1", {"hormone": "혈당·대사", "microbiome": "항균"}, "중복 플래그"),
]


# ========================================================
# 2. 5-bucket 분류 (원본: 02_규제_필터링.md §2 전체 + §3.2 요약)
# ========================================================
# 버킷: "①" | "②" | "③" | "③-H" | "④"
BUCKET_MAP = {
    # ① 건기식 + 자유 (29개)
    "메틸B12": "①", "CoQ10 (유비퀴놀)": "①", "L-카르니틴": "①", "ALA": "①",
    "글리신": "①", "타우린": "①", "콜로스트럼": "①", "알로에베라": "①",
    "커큐민": "①", "아슈와간다 Shoden": "①", "홍경천": "①", "엘류테로": "①",
    "인삼": "①", "감초": "①", "코디세프스": "①", "L-테아닌": "①",
    "GABA": "①", "포스파티딜세린": "①", "Mg 글리시네이트": "①",
    "아연 피콜리네이트": "①", "셀레늄 메티오닌": "①", "요오드": "①",
    "구리 비스글리시네이트": "①", "크로뮴 피콜리네이트": "①", "몰리브덴": "①",
    "클로렐라": "①", "밀크씨슬": "①", "L. rhamnosus GG": "①",
    "Bifido 3종": "①", "PHGG": "①", "아카시아 섬유/이눌린/FOS/GOS": "①",
    "락토페린": "①", "오메가-3 EPA": "①", "D3+K2": "①",
    # ② 건기식 아님 + 직구 자유
    "TMG": "②", "PQQ": "②", "D-리보스": "②", "L-글루타민": "②",
    "쿼르세틴": "②", "슬리퍼리엘름/DGL": "②", "홀리바질": "②",
    "Mg L-트레오네이트": "②", "MCP": "②", "실란트로": "②", "붕소": "②",
    "L. plantarum": "②",
    # ③ 구매대행 금지 + 개인직구 가능 (미국법인 핵심)
    "NMN": "③", "NR": "③", "Urolithin A": "③", "Spermidine": "③",
    "5-MTHF": "③", "P5P": "③", "ALCAR": "③", "부티레이트": "③",
    "Berberine": "③", "베르베린": "③", "Inositol": "③",
    # 추가 회색지대
    "타트체리": "②", "Calcium-D-Glucarate": "②",
    # ③-H 호르몬/성 제약
    "DIM": "③-H", "I3C": "③-H", "호로파/Tongkat/Tribulus": "③-H",
    "마카": "③-H",
    # ④ 반입차단
    "NAC": "④", "SAM-e": "④",
    # 회색지대 기본값 ②~③
    "Fisetin": "③", "글루타티온 (리포좀)": "②", "오레가노 오일": "③",
    "카프릴산": "②", "파우다르코/올리브잎": "②", "광범위 소화효소": "②",
    "DPP-IV 효소": "②", "HCL+펩신": "②", "담즙산염": "③",
    "SBI": "③", "아연-카르노신": "②", "제올라이트": "③", "활성탄": "②",
    "S. boulardii": "②", "Akkermansia": "②", "Faecalibacterium": "②",
    "포자형 균주": "②",
}

# 국내 건기식 등재 상태 (02_ 개별 표에서 추출)
KOREA_REG = {
    "메틸B12": "고시 (B12)", "CoQ10 (유비퀴놀)": "개별인정", "L-카르니틴": "고시",
    "ALA": "개별인정", "글리신": "고시", "타우린": "고시",
    "콜로스트럼": "일반식품", "알로에베라": "개별인정 다수",
    "커큐민": "개별인정 (강황)", "아슈와간다 Shoden": "개별인정 (수면질)",
    "홍경천": "개별인정 (피로개선)", "엘류테로": "식품공전",
    "인삼": "고시", "감초": "식품공전", "코디세프스": "고시/개별인정",
    "L-테아닌": "개별인정", "GABA": "개별인정 (수면)",
    "포스파티딜세린": "개별인정 (기억력)", "Mg 글리시네이트": "고시 (Mg)",
    "아연 피콜리네이트": "고시 (Zn)", "셀레늄 메티오닌": "고시 (Se)",
    "요오드": "고시", "구리 비스글리시네이트": "고시 (Cu)",
    "크로뮴 피콜리네이트": "고시 (Cr)", "몰리브덴": "고시 (Mo)",
    "클로렐라": "일반식품", "밀크씨슬": "개별인정 (간건강)",
    "L. rhamnosus GG": "고시 균주", "Bifido 3종": "고시 균주",
    "PHGG": "고시 (식이섬유)", "아카시아 섬유/이눌린/FOS/GOS": "고시 (식이섬유)",
    "락토페린": "개별인정", "오메가-3 EPA": "고시", "D3+K2": "고시 (각각)",
    "마카": "일반식품",
}


# ========================================================
# 3. 대체 성분 매핑 (원본: 02_규제_필터링.md §3.5)
# ========================================================
SUBSTITUTES = [
    {"blocked": "NAC",
     "reason": "반입차단 (의약품 분류)",
     "alternatives": ["글루타티온 (리포좀)", "ALA", "셀레늄 메티오닌"]},
    {"blocked": "DHEA 저하 권고",
     "reason": "DHEA 반입차단",
     "alternatives": ["아슈와간다 Shoden", "홍경천", "포스파티딜세린", "판토텐산(B5)", "비타민C"]},
    {"blocked": "멜라토닌 권고",
     "reason": "멜라토닌 반입차단",
     "alternatives": ["아슈와간다 Shoden", "GABA", "L-테아닌", "Mg L-트레오네이트", "타트체리"]},
    {"blocked": "5-HTP 권고",
     "reason": "5-HTP 반입차단",
     "alternatives": ["사프란 추출물", "Mg 글리시네이트", "P5P", "아연 피콜리네이트"]},
    {"blocked": "에스트로겐 우세 (③-H 영역)",
     "reason": "③-H 마케팅 제약",
     "alternatives": ["DIM", "I3C", "Calcium-D-Glucarate"]},
    {"blocked": "테스토스테론 저하 권고",
     "reason": "성호르몬 표방 불가",
     "alternatives": ["아슈와간다 Shoden", "아연 피콜리네이트", "D3+K2", "호로파/Tongkat/Tribulus (③-H)"]},
    {"blocked": "SAM-e",
     "reason": "반입차단 (의약품)",
     "alternatives": ["TMG", "메틸B12", "5-MTHF"]},
]


# ========================================================
# 4. 다빈치랩 38 쇼트리스트 커버리지 (원본: 03_공급처_매트릭스.md §2)
# ========================================================
# 🟢 풀보유 | 🟡 부분(복합) | 🔴 미보유
DAVINCI_COVERAGE = {
    # 🟢 풀 보유 12
    "NMN": ("🟢", ["NMN 단독"]),
    "Berberine": ("🟢", ["Berberine Force (Berberine + 5-MTHF + R-ALA 복합)"]),
    "DIM": ("🟢", ["BioDIM Complex"]),
    "아슈와간다 Shoden": ("🟢", ["Amyloid Complete (Shoden 포함)", "멜라토닌-free Sleep (Ashwagandha + L-Theanine)"]),
    "글루타티온 (리포좀)": ("🟢", ["Glutathione Bright (Provail Whey, 2.5x 흡수)"]),
    "L-테아닌": ("🟢", ["L-Theanine 200mg 단독"]),
    "CoQ10 (유비퀴놀)": ("🟢", ["Phospholipids 카테고리 포함"]),
    "L-카르니틴": ("🟢", ["L-Carnitine 카테고리"]),
    "Mg 글리시네이트": ("🟢", ["Magnesium 카테고리"]),
    "아연 피콜리네이트": ("🟢", ["Zinc 카테고리"]),
    "오메가-3 EPA": ("🟢", ["Krill Oil + Fish Oil"]),
    "D3+K2": ("🟢", ["D3/K2 Liquid"]),
    # 🟡 부분
    "5-MTHF": ("🟡", ["Methyl Benefits (복합)", "Berberine Force (복합)"]),
    "P5P": ("🟡", ["복합 제품 포함"]),
    "ALCAR": ("🟡", ["L-카르니틴 카테고리 내 확인 필요"]),
    "TMG": ("🟡", ["Methyl Benefits 내 포함"]),
    "ALA": ("🟡", ["Berberine Force 내 R-ALA"]),
    "콜로스트럼": ("🟡", ["Amyloid Complete 내 Immulox Colostrum"]),
    # 🔴 미보유 (20)
    "NR": ("🔴", []),
    "Urolithin A": ("🔴", []),
    "Spermidine": ("🔴", []),
    "Inositol": ("🔴", []),
    "부티레이트": ("🔴", []),
    "I3C": ("🔴", []),
    "호로파/Tongkat/Tribulus": ("🔴", []),
    "마카": ("🔴", []),
    "홍경천": ("🔴", []),
    "GABA": ("🔴", []),
    "포스파티딜세린": ("🔴", []),
    "코디세프스": ("🔴", []),
    "락토페린": ("🔴", []),
    "Akkermansia": ("🔴", []),
    "Faecalibacterium": ("🔴", []),
    "포자형 균주": ("🔴", []),
    "S. boulardii": ("🔴", []),
    "PQQ": ("🔴", []),
    "커큐민": ("🔴", []),  # 고흡수형 확인 필요
}


# ========================================================
# 5. Phase 편성 + 긴급도 (원본: 03_ §5)
# ========================================================
PHASE_URGENCY = {
    # Phase 1 (0~6개월) — OAT + 장내세균 + 미네랄 블록
    "NMN": (1, "★★★"), "NR": (1, "★★"), "Urolithin A": (1, "★★★"),
    "Spermidine": (1, "★★"), "Inositol": (1, "★★★"), "부티레이트": (1, "★★"),
    "CoQ10 (유비퀴놀)": (1, "★★"), "L-카르니틴": (1, "★★"), "ALA": (1, "★★"),
    "글리신": (1, "★"), "타우린": (1, "★"), "메틸B12": (1, "★"),
    "5-MTHF": (1, "★★"), "P5P": (1, "★★"), "ALCAR": (1, "★★"), "TMG": (1, "★"),
    "Berberine": (1, "★★"), "베르베린": (1, "★★"), "L. rhamnosus GG": (1, "★"),
    "Bifido 3종": (1, "★"), "PHGG": (1, "★"),
    "아카시아 섬유/이눌린/FOS/GOS": (1, "★"),
    "Mg 글리시네이트": (1, "★★"), "아연 피콜리네이트": (1, "★★"),
    "셀레늄 메티오닌": (1, "★"), "요오드": (1, "★"), "오메가-3 EPA": (1, "★★"),
    "D3+K2": (1, "★★"), "글루타티온 (리포좀)": (1, "★★"),
    # Phase 2 (6~12M) — IgG 5R + 호르몬 ①
    "콜로스트럼": (2, "★★★"), "SBI": (2, "★★"), "락토페린": (2, "★★"),
    "L-글루타민": (2, "★★"), "쿼르세틴": (2, "★★"), "카프릴산": (2, "★"),
    "광범위 소화효소": (2, "★★"), "DPP-IV 효소": (2, "★"),
    "아연-카르노신": (2, "★★"), "오레가노 오일": (2, "★"),
    "파우다르코/올리브잎": (2, "★"), "슬리퍼리엘름/DGL": (2, "★"),
    "알로에베라": (2, "★"), "커큐민": (2, "★★"),
    "아슈와간다 Shoden": (2, "★★★"), "홍경천": (2, "★★★"),
    "GABA": (2, "★★★"), "L-테아닌": (2, "★★★"),
    "포스파티딜세린": (2, "★★"), "코디세프스": (2, "★"),
    "홀리바질": (2, "★"), "엘류테로": (2, "★"), "인삼": (2, "★"),
    "감초": (2, "★"), "Mg L-트레오네이트": (2, "★★"),
    # Phase 3 (12~18M) — ③-H + 차세대 균주
    "DIM": (3, "★★"), "I3C": (3, "★★"),
    "호로파/Tongkat/Tribulus": (3, "★"), "마카": (3, "★"),
    "Akkermansia": (3, "★★★★"), "Faecalibacterium": (3, "★"),
    "포자형 균주": (3, "★★"), "S. boulardii": (3, "★★"),
    # Phase 4 — 보류/관망
    "Fisetin": (4, "★"), "타트체리": (4, "★"),
    "HCL+펩신": (4, "★"), "담즙산염": (4, "★"),
    "PQQ": (4, "★"), "D-리보스": (4, "★"),
    "클로렐라": (4, "★"), "MCP": (4, "★"),
    "제올라이트": (4, "★"), "활성탄": (4, "★"),
    "실란트로": (4, "★"), "밀크씨슬": (4, "★"),
    "구리 비스글리시네이트": (4, "★"), "크로뮴 피콜리네이트": (4, "★"),
    "몰리브덴": (4, "★"), "붕소": (4, "★"),
    "L. plantarum": (4, "★"), "Calcium-D-Glucarate": (4, "★"),
    "NAC": (0, ""),  # 반입차단 제외
    "SAM-e": (0, ""),
}


# ========================================================
# 6. 표시광고 금지어 힌트 (호르몬 영역)
# ========================================================
FORBIDDEN_KEYWORDS_BASE = [
    "정력", "남성 활력", "성기능", "발기", "성능력", "갱년기 치료",
    "호르몬 치료", "에스트로겐 증가", "테스토스테론 증가",
    "질병 치료", "질병 예방", "우울증 치료", "불면증 치료",
    "당뇨 치료", "고혈압 치료", "암 치료"
]
HORMONE_SENSITIVE = {
    "DIM", "I3C", "Calcium-D-Glucarate", "호로파/Tongkat/Tribulus",
    "마카", "아슈와간다 Shoden", "홍경천", "GABA",
    "L-테아닌", "포스파티딜세린"
}


# ========================================================
# 7. 제품 엑셀 파싱 — 바이오컴 11 + 다빈치 21 통합
# ========================================================
def parse_xlsx_products() -> tuple[list[dict], dict[str, dict]]:
    """xlsx 읽기 — 바이오컴 + 다빈치 분리 반환.

    Returns:
        (davinci_list, biocom_by_brand)
        biocom_by_brand 는 바이오컴 브랜드명으로 key된 dict.
    """
    try:
        import openpyxl
    except ImportError:
        print("[경고] openpyxl 미설치 — 엑셀 스킵")
        return [], {}
    if not XLSX_PATH.exists():
        print(f"[경고] xlsx 없음: {XLSX_PATH}")
        return [], {}
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb["영양제 성분 리스트"]
    rows = list(ws.iter_rows(values_only=True))
    # R1: 헤더(제품명|성분|함량|단위|식약처기준|함량배수|섭취방법)
    current = None
    products: dict[str, dict] = {}
    for row in rows[2:]:
        if not row or len(row) < 8:
            continue
        name, ing, amt, unit, std, ratio, usage = row[1], row[2], row[3], row[4], row[5], row[6], row[7]
        if name:
            current = str(name).strip()
        if not current or current in ("None", ""):
            continue
        if not ing:
            continue
        p = products.setdefault(current, {"product": current, "ingredients": [], "usage": ""})
        if usage and not p["usage"]:
            p["usage"] = str(usage).strip()
        p["ingredients"].append({
            "name": str(ing).strip(),
            "amount": amt, "unit": str(unit).strip() if unit else "",
            "kfda_std": std, "ratio": ratio,
        })

    davinci = [p for p in products.values() if "다빈치랩" in p["product"]]
    biocom = {p["product"]: p for p in products.values() if "다빈치랩" not in p["product"]}
    return davinci, biocom


# ========================================================
# 8. 최종 시드 생성
# ========================================================
def build_ingredient_master(davinci_products: list[dict],
                            biocom_xlsx: dict[str, dict]) -> list[dict]:
    master = []
    for idx, (ko, en, aliases, cat, tests_raw, note) in enumerate(RAW_56, start=1):
        bucket = BUCKET_MAP.get(ko, "?")
        tests = {k: tests_raw.get(k) for k in ("oat", "igg", "hormone", "hair", "microbiome")}
        phase, urgency = PHASE_URGENCY.get(ko, (0, ""))
        davinci = DAVINCI_COVERAGE.get(ko, ("—", []))
        substitutes_for = [s["alternatives"] for s in SUBSTITUTES if s["blocked"] == ko]
        substitute_of = []
        for s in SUBSTITUTES:
            if ko in s["alternatives"]:
                substitute_of.append({"for": s["blocked"], "reason": s["reason"]})
        hormone_sensitive = ko in HORMONE_SENSITIVE

        # 다빈치 제품 역매핑
        used_in_davinci = []
        for p in davinci_products:
            names_here = " ".join(i["name"] for i in p["ingredients"])
            if _ingredient_in_text(ko, en, aliases, names_here):
                used_in_davinci.append(p["product"])

        # 바이오컴 제품 역매핑
        used_in_biocom = []
        for brand, p in biocom_xlsx.items():
            names_here = " ".join(i["name"] for i in p["ingredients"])
            if _ingredient_in_text(ko, en, aliases, names_here):
                used_in_biocom.append(brand)

        master.append({
            "id": f"ing_{idx:03d}",
            "name_ko": ko,
            "name_en": en,
            "aliases": aliases,
            "category": cat,
            "note": note,
            "legal": {
                "bucket": bucket,
                "korea_registered": KOREA_REG.get(ko, "미등재"),
                "hormone_sensitive": hormone_sensitive,
            },
            "tests": tests,
            "phase": {
                "phase": phase,
                "urgency": urgency,
            },
            "supplier": {
                "davinci_status": davinci[0],
                "davinci_products": davinci[1],
            },
            "products": {
                "biocom_used_in": used_in_biocom,
                "davinci_used_in": used_in_davinci,
            },
            "substitutes": {
                "alternatives_for_blocked": substitutes_for[0] if substitutes_for else [],
                "is_substitute_of": substitute_of,
            },
        })
    return master


def _ingredient_in_text(ko: str, en: str, aliases: list[str], text: str) -> bool:
    """단순 문자열 매칭으로 성분이 제품 성분 리스트에 포함되는지.

    오탐 줄이기 위해 최소 4자 이상 토큰만 사용.
    """
    keys = [ko, en] + aliases
    txt_norm = text.lower().replace(" ", "")
    for k in keys:
        if not k: continue
        core = k.lower().replace(" ", "")
        # 4자 이상 연속 매칭만 인정
        if len(core) >= 4 and core in txt_norm:
            return True
        # 영문 첫 단어도 4자 이상
        first = k.split()[0].lower() if " " in k else k.lower()
        if len(first) >= 4 and first in text.lower():
            return True
    return False


def main() -> None:
    print("=" * 60)
    print("성분 마스터 시드 생성")
    print("=" * 60)

    # xlsx 파싱 — 바이오컴 + 다빈치 동시
    print("\n[1/4] xlsx 파싱 (바이오컴 + 다빈치랩)...")
    davinci_products, biocom_xlsx = parse_xlsx_products()
    print(f"   ✅ 다빈치 {len(davinci_products)}개, 바이오컴 {len(biocom_xlsx)}개 제품 파싱")
    (DATA_DIR / "davinci_products.json").write_text(
        json.dumps(davinci_products, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "biocom_xlsx_ingredients.json").write_text(
        json.dumps(biocom_xlsx, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ingredient master
    print("\n[2/4] 성분 마스터 조립 (56개 × 여러 레이어)...")
    master = build_ingredient_master(davinci_products, biocom_xlsx)
    (DATA_DIR / "ingredient_master.json").write_text(
        json.dumps(master, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   ✅ {len(master)}개 성분 레코드")

    # 대체 성분
    print("\n[3/4] substitutes.json...")
    (DATA_DIR / "substitutes.json").write_text(
        json.dumps(SUBSTITUTES, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   ✅ {len(SUBSTITUTES)}개 매핑")

    # 표시광고 힌트 + 기타 메타
    print("\n[4/4] 규제·표시광고 사전...")
    (DATA_DIR / "marketing_rules.json").write_text(
        json.dumps({
            "forbidden_keywords": FORBIDDEN_KEYWORDS_BASE,
            "hormone_sensitive_ingredients": sorted(HORMONE_SENSITIVE),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   ✅ 금지어 {len(FORBIDDEN_KEYWORDS_BASE)}개, 호르몬 민감 성분 {len(HORMONE_SENSITIVE)}개")

    # 요약
    bucket_counts = {}
    phase_counts = {}
    test_counts = {"oat": 0, "igg": 0, "hormone": 0, "hair": 0, "microbiome": 0}
    davinci_status_counts = {"🟢": 0, "🟡": 0, "🔴": 0, "—": 0}
    for m in master:
        bucket_counts[m["legal"]["bucket"]] = bucket_counts.get(m["legal"]["bucket"], 0) + 1
        phase_counts[m["phase"]["phase"]] = phase_counts.get(m["phase"]["phase"], 0) + 1
        for t, v in m["tests"].items():
            if v: test_counts[t] += 1
        s = m["supplier"]["davinci_status"]
        davinci_status_counts[s] = davinci_status_counts.get(s, 0) + 1
    print("\n" + "=" * 60)
    print("요약")
    print("=" * 60)
    print(f"5-bucket 분포: {dict(sorted(bucket_counts.items()))}")
    print(f"Phase 분포:    {dict(sorted(phase_counts.items()))}")
    print(f"검사 매핑:     {test_counts}")
    print(f"다빈치 상태:   {davinci_status_counts}")
    print(f"\n📁 저장 위치: {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
