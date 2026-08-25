# -*- coding: utf-8 -*-
"""
HIMEC 현장사진 AI 판독 - 데이터셋 수집 설정

HIMEC 사업영역(기계설비/전기·정보통신/소방방재/PM·CM/토탈커미셔닝) 기준으로
공개 데이터셋을 3개 판독 태스크에 매핑한다.

  [SAFETY] 현장 전경 사진  -> 안전 판독 (PPE 미착용, 화재/연기)
  [DEFECT] 근접 검측 사진  -> 하자 판독 (부식, 균열, 케이블 손상, 용접 결함)
  [GAUGE ] 계기 사진       -> 커미셔닝 검침 판독

RF100(Francesco/*) 데이터셋은 category index 0 이 supercategory 더미 클래스라
실제 어노테이션에 쓰이지 않는다 -> 매핑에서 제외(None) 처리.
"""

# ---------------------------------------------------------------- SAFETY
SAFETY_CLASSES = [
    "person",        # 0 작업자
    "helmet",        # 1 안전모 착용
    "no_helmet",     # 2 안전모 미착용   [지적]
    "vest",          # 3 안전조끼 착용
    "no_vest",       # 4 안전조끼 미착용 [지적]
    "goggles",       # 5 보안경 착용
    "no_goggles",    # 6 보안경 미착용   [지적]
    "gloves",        # 7 안전장갑 착용
    "no_gloves",     # 8 안전장갑 미착용 [지적]
    "cone",          # 9 안전콘/구획
    "smoke",         # 10 연기·화재     [지적]
]

SAFETY_SOURCES = {
    "Francesco/construction-safety-gsnvb": {
        # src classes: ['construction-safety','helmet','no-helmet','no-vest','person','vest']
        0: None, 1: "helmet", 2: "no_helmet", 3: "no_vest", 4: "person", 5: "vest",
    },
    "Francesco/street-work": {
        # ['street-work-items','Cone','Face_Shield','Gloves','Goggles','Head','Helmet','No glasses','No gloves']
        0: None, 1: "cone", 2: "goggles", 3: "gloves", 4: "goggles",
        5: "no_helmet",      # 'Head' = 맨머리 = 안전모 미착용
        6: "helmet", 7: "no_goggles", 8: "no_gloves",
    },
    "Francesco/smoke-uvylj": {
        # ['smoke-0','smoke']
        0: None, 1: "smoke",
    },
}

# ---------------------------------------------------------------- DEFECT
DEFECT_CLASSES = [
    "corrosion",      # 0 부식(배관/덕트/철물)      [지적]
    "crack",          # 1 균열                      [지적]
    "cable_damage",   # 2 케이블 피복손상/단선      [지적]
    "weld_bad",       # 3 용접 불량                 [지적]
    "weld_good",      # 4 용접 양호
    "weld_defect",    # 5 용접 결함부(기공/언더컷)  [지적]
    "wall_damage",    # 6 벽체/구조 손상            [지적]
]

DEFECT_SOURCES = {
    "Francesco/corrosion-bi3q3": {
        # ['corrosion-0','Slippage','corrosion','crack']
        0: None, 1: "corrosion", 2: "corrosion", 3: "crack",
    },
    "Francesco/cable-damage": {
        # ['cable-damage','break','thunderbolt']
        0: None, 1: "cable_damage", 2: "cable_damage",
    },
    "Francesco/wall-damage": {
        # ['wall-damage','Minorrotation','Moderaterotation','Severerotation']
        0: None, 1: "wall_damage", 2: "wall_damage", 3: "wall_damage",
    },
}

# YOLO 포맷으로 이미 배포되는 데이터셋 (parquet 아님)
DEFECT_YOLO_SOURCES = {
    "rikkarth/welding-defect-object-detection": {
        # data.yaml names: ['Bad Weld','Good Weld','Defect']
        0: "weld_bad", 1: "weld_good", 2: "weld_defect",
    },
}

# ---------------------------------------------------------------- GAUGE
GAUGE_CLASSES = ["gauge", "digit"]

GAUGE_SOURCES = {
    "Francesco/gauge-u2lwv": {
        # ['gauge','gauges','numbers']
        0: None, 1: "gauge", 2: "digit",
    },
}


# ---------------------------------------------------------------- PRODUCT
# 제조 공정 라인 검사 (양품/불량 선별)
#   영남사업부 AI VISION INSPECTOR 사례(SK온 양산 선별창고 배터리 셀 선별)와 같은
#   '라인 위 제품을 찍어 양품/불량을 가르는' 검사 축.
PRODUCT_CLASSES = [
    "ok",                 # 0 양품 (정상)
    "dry_joint",          # 1 접합 불량(냉납)        [불량]
    "incorrect_install",  # 2 조립·삽입 불량         [불량]
    "board_damage",       # 3 기판·부품 손상         [불량]
    "short_circuit",      # 4 단락                   [불량]
    "surface_defect",     # 5 표면 결함(접힘·스크래치) [불량]
    "cell_anomaly",       # 6 셀 이상(결함·음영)      [불량]
]

PRODUCT_SOURCES = {
    "Francesco/4-fold-defect": {
        # ['4-fold-defect','4-fold defect']
        0: None, 1: "surface_defect",
    },
    "Francesco/solar-panels-taxvb": {
        # ['solar-panels','Cell','Cell-Multi','No-Anomaly','Shadowing','Unclassified']
        0: None, 1: "cell_anomaly", 2: "cell_anomaly", 3: "ok",
        4: "cell_anomaly", 5: None,
    },
}

# COCO(zip) 포맷으로 배포되는 데이터셋
PRODUCT_COCO_SOURCES = {
    "keremberke/pcb-defect-segmentation": {
        # categories: dry_joint, incorrect_installation, pcb_damage, short_circuit
        "dry_joint": "dry_joint",
        "incorrect_installation": "incorrect_install",
        "pcb_damage": "board_damage",
        "short_circuit": "short_circuit",
    },
}

# ---------------------------------------------------------------- POLARITY
# 역극(逆極) 검사 - 배터리 셀 트레이의 극성 방향 판정
#   실제 고객사 셀 이미지는 자산이므로, 동일 구조의 합성 데이터로 방법론을 실증한다.
POLARITY_CLASSES = [
    "cell_ok",        # 0 정상 배열 셀
    "cell_reversed",  # 1 역극 셀 [불량]
]


# ---------------------------------------------------------------- LOGISTICS
# 물류 - 자재 입고 / 적재 / 출고 운송 현장
LOGISTICS_CLASSES = [
    "forklift",          # 0 지게차
    "worker",            # 1 작업자 (지게차 동선 내 보행자)
    "chassis_loaded",    # 2 적재 완료 섀시
    "chassis_empty",     # 3 공차 섀시
    "chassis_working",   # 4 상하차 작업 중
    "stacker",           # 5 스태커/적재장비
]

LOGISTICS_SOURCES = {
    "Francesco/truck-movement": {
        # ['truck-movement','otr_chassis_loaded','otr_chassis_unloaded','otr_chassis_working','person','stacker']
        0: None, 1: "chassis_loaded", 2: "chassis_empty", 3: "chassis_working",
        4: "worker", 5: "stacker",
    },
}

LOGISTICS_COCO_SOURCES = {
    "keremberke/forklift-object-detection": {
        "forklift": "forklift", "person": "worker",
    },
}

# ---------------------------------------------------------------- SEMICONDUCTOR
# 반도체·전자 - 부품 실장 검사 (생산도급/임가공 라인)
SEMICON_CLASSES = [
    "ic",            # 0 IC / 칩
    "capacitor",     # 1 커패시터
    "resistor",      # 2 저항
    "connector",     # 3 커넥터
    "diode",         # 4 다이오드 (극성 부품)
    "transistor",    # 5 트랜지스터
    "led",           # 6 LED (극성 부품)
    "pads",          # 7 패드/핀
    "misc_part",     # 8 기타 부품
]

SEMICON_SOURCES = {
    "Francesco/printed-circuit-board": {
        0: None, 1: "misc_part", 2: "capacitor", 3: "capacitor", 4: "misc_part",
        5: "connector", 6: "diode", 7: "misc_part", 8: "capacitor", 9: "misc_part",
        10: "ic", 11: "misc_part", 12: "misc_part", 13: "led", 14: "pads",
        15: "pads", 16: "resistor", 17: "resistor", 18: "resistor", 19: "misc_part",
        20: "pads", 21: "transistor", 22: None, 23: "ic",
    },
}

# ---------------------------------------------------------------- PARKING
# 주차 - 주차장 운영 관리 (차종 판별 / 점유 현황)
PARKING_CLASSES = [
    "car",          # 0 승용차
    "bus",          # 1 버스
    "truck",        # 2 화물차
]

PARKING_SOURCES = {
    "Francesco/vehicles-q0x2v": {
        # ['vehicles','big bus','big truck','bus-l-','bus-s-','car','mid truck',
        #  'small bus','small truck','truck-l-','truck-m-','truck-s-','truck-xl-']
        0: None, 1: "bus", 2: "truck", 3: "bus", 4: "bus", 5: "car", 6: "truck",
        7: "bus", 8: "truck", 9: "truck", 10: "truck", 11: "truck", 12: "truck",
    },
}


# ---------------------------------------------------------------- 라벨 출처 비교 실험
# 같은 이미지에 대해 라벨을 누가 만들었는지만 다르게 하고 성능을 비교한다.
#   human_safety : 사람이 친 박스
#   yoloe_safety : YOLOE 가 텍스트 프롬프트로 만든 박스
#   sam3_safety  : SAM 3 가 텍스트 프롬프트로 만든 박스
# 평가는 셋 다 '사람 라벨' val/test 로 한다.
LABELSRC_CLASSES = ["person", "helmet", "safety vest"]


# ---------------------------------------------------------------- SAFETY2 (안전·위생)
# 삼구아이앤씨 사업영역 기준으로 재구성한 안전·위생 판독 축.
#
# 기존 safety 는 건설현장 PPE 중심이라 '미착용' 데이터가 늘 모자랐다(no_helmet 561개).
# 여기서는 미착용 클래스가 완비된 데이터셋을 쓴다.
# 또한 마스크·위생화는 급식(F&B)과 반도체 클린룸에서 그대로 쓰이는 항목이라
# 건설 안전이 아니라 '사업장 안전·위생'으로 축을 넓혔다.
SAFETY2_CLASSES = [
    "helmet",       # 0 안전모 착용
    "no_helmet",    # 1 안전모 미착용   [지적]
    "mask",         # 2 마스크 착용     (급식·클린룸 위생)
    "no_mask",      # 3 마스크 미착용   [지적]
    "gloves",       # 4 장갑 착용       (급식·생산 위생)
    "no_gloves",    # 5 장갑 미착용     [지적]
    "goggles",      # 6 보안경 착용
    "no_goggles",   # 7 보안경 미착용   [지적]
    "shoes",        # 8 안전화·위생화 착용
    "no_shoes",     # 9 안전화·위생화 미착용 [지적]
]

SAFETY2_COCO_SOURCES = {
    "keremberke/protective-equipment-detection": {
        "helmet": "helmet", "no_helmet": "no_helmet",
        "mask": "mask", "no_mask": "no_mask",
        "glove": "gloves", "no_glove": "no_gloves",
        "goggles": "goggles", "no_goggles": "no_goggles",
        "shoes": "shoes", "no_shoes": "no_shoes",
    },
    "keremberke/hard-hat-detection": {
        "hardhat": "helmet", "no-hardhat": "no_helmet",
    },
}

# ---------------------------------------------------------------- CLEANING (미화)
# 시설관리 사업의 미화 — 분리수거 상태 판독
CLEANING_CLASSES = ["cardboard", "plastic", "glass", "metal", "paper", "biodegradable"]

CLEANING_COCO_SOURCES = {
    "keremberke/garbage-object-detection": {
        "cardboard": "cardboard", "plastic": "plastic", "glass": "glass",
        "metal": "metal", "paper": "paper", "biodegradable": "biodegradable",
    },
}

TASKS = {
    "safety": dict(classes=SAFETY_CLASSES, parquet=SAFETY_SOURCES, yolo={}),
    "defect": dict(classes=DEFECT_CLASSES, parquet=DEFECT_SOURCES, yolo=DEFECT_YOLO_SOURCES),
    "gauge":  dict(classes=GAUGE_CLASSES,  parquet=GAUGE_SOURCES,  yolo={}),
    "product": dict(classes=PRODUCT_CLASSES, parquet=PRODUCT_SOURCES, yolo={},
                    coco=PRODUCT_COCO_SOURCES),
    "polarity": dict(classes=POLARITY_CLASSES, parquet={}, yolo={}, synthetic=True),
    "logistics": dict(classes=LOGISTICS_CLASSES, parquet=LOGISTICS_SOURCES, yolo={},
                      coco=LOGISTICS_COCO_SOURCES),
    "semiconductor": dict(classes=SEMICON_CLASSES, parquet=SEMICON_SOURCES, yolo={}),
    "parking": dict(classes=PARKING_CLASSES, parquet=PARKING_SOURCES, yolo={}, max_train=1600),
    "human_safety": dict(classes=LABELSRC_CLASSES, parquet={}, yolo={}, external=True),
    "yoloe_safety": dict(classes=LABELSRC_CLASSES, parquet={}, yolo={}, external=True),
    "sam3_safety":  dict(classes=LABELSRC_CLASSES, parquet={}, yolo={}, external=True),
    "yoloe2_safety": dict(classes=LABELSRC_CLASSES, parquet={}, yolo={}, external=True),
    "safety2": dict(classes=SAFETY2_CLASSES, parquet={}, yolo={},
                    coco=SAFETY2_COCO_SOURCES, max_train=3200),
    "cleaning": dict(classes=CLEANING_CLASSES, parquet={}, yolo={},
                     coco=CLEANING_COCO_SOURCES, max_train=1400),
    # 반도체 재설계: 9클래스(불균형 203배) -> 3클래스(13배). 실무 1차 검사는 부품 종류가 아니라 위치다.
    "semicon2": dict(classes=["passive","chip","pads"], parquet={}, yolo={}, external=True),
}

# 지적사항(부적합) 판정 대상 클래스 - 리포트 생성 시 사용
NONCONFORMITY = {
    "safety": ["no_helmet", "no_vest", "no_goggles", "no_gloves", "smoke"],
    "defect": ["corrosion", "crack", "cable_damage", "weld_bad", "weld_defect", "wall_damage"],
    "gauge":  [],
    "product": ["dry_joint", "incorrect_install", "board_damage", "short_circuit",
                "surface_defect", "cell_anomaly"],
    "polarity": ["cell_reversed"],
    "safety2": ["no_helmet", "no_mask", "no_gloves", "no_goggles", "no_shoes"],
    "cleaning": [],
    # 물류·반도체·주차는 '불량'이 아니라 상태/객체 판정이므로 지적 대상은 룰엔진에서 조합으로 정의
    "logistics": [],
    "semiconductor": [],
    "parking": [],
}
