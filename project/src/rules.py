# -*- coding: utf-8 -*-
"""
HIMEC 현장 검측 룰 엔진

YOLO 탐지 결과(객체)를 감리/검측 실무의 '지적사항(부적합)'으로 승격시킨다.
각 룰은 근거 법규·기준을 함께 반환하여 검측조서에 그대로 인용 가능하도록 한다.

위험도(RISK): 4=긴급(즉시중지) 3=높음 2=보통 1=낮음
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional


@dataclass
class Finding:
    rule_id: str
    task: str                 # safety | defect | gauge
    category: str             # 지적 분류
    title: str                # 지적사항 요약
    risk: int                 # 1~4
    basis: str                # 근거 법규/기준
    action: str               # 요구 조치사항
    count: int = 0
    max_conf: float = 0.0
    boxes: List[List[float]] = field(default_factory=list)
    detail: str = ""

    def risk_label(self) -> str:
        return {4: "긴급", 3: "높음", 2: "보통", 1: "낮음"}[self.risk]

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["risk_label"] = self.risk_label()
        return d


# ----------------------------------------------------------------- 룰 정의
# key = 탐지 클래스명, value = 지적사항 템플릿
SAFETY_RULES = {
    "no_helmet": dict(
        rule_id="S-01", category="개인보호구",
        title="안전모 미착용 작업자 발견",
        risk=3,
        basis="산업안전보건기준에 관한 규칙 제32조(보호구의 지급 등) 제1항 제1호 "
              "- 물체가 떨어지거나 날아올 위험 또는 근로자가 추락할 위험이 있는 작업: 안전모",
        action="해당 작업자 즉시 작업중지 후 안전모 착용 조치, 작업 전 TBM 시 보호구 점검 강화",
    ),
    "no_vest": dict(
        rule_id="S-02", category="개인보호구",
        title="안전조끼(형광조끼) 미착용 작업자 발견",
        risk=2,
        basis="산업안전보건기준에 관한 규칙 제32조 제1항 제10호 "
              "- 차량계 하역운반기계 등이 운행되는 장소: 안전조끼(형광 반사재 부착)",
        action="안전조끼 착용 후 작업 재개, 중장비 동선 구간 출입 시 착용 상시 확인",
    ),
    "no_goggles": dict(
        rule_id="S-03", category="개인보호구",
        title="보안경 미착용 작업자 발견",
        risk=2,
        basis="산업안전보건기준에 관한 규칙 제32조 제1항 제4호 "
              "- 물체가 흩날릴 위험이 있는 작업: 보안경",
        action="용접·절단·연마 작업 구간 보안경 착용 의무화, 보호구 비치 상태 점검",
    ),
    "no_gloves": dict(
        rule_id="S-04", category="개인보호구",
        title="안전장갑 미착용 작업자 발견",
        risk=2,
        basis="산업안전보건기준에 관한 규칙 제32조 제1항 제5호 "
              "- 감전의 위험이 있는 작업: 절연용 보호구",
        action="작업 특성에 맞는 보호장갑 지급·착용 확인",
    ),
    "smoke": dict(
        rule_id="S-05", category="화재·소방",
        title="연기 발생 감지 (화재 의심)",
        risk=4,
        basis="화재의 예방 및 안전관리에 관한 법률 제17조(화재예방강화지구 등) 및 "
              "산업안전보건기준에 관한 규칙 제241조(화재위험작업 시의 준수사항)",
        action="즉시 작업중지·화기감시자 확인·소화기 조치, 화재감시자 배치 및 소방서 신고 여부 판단",
    ),
}

DEFECT_RULES = {
    "corrosion": dict(
        rule_id="D-01", category="기계설비-부식",
        title="배관·철물 부식 발생",
        risk=2,
        basis="기계설비법 제17조 및 「기계설비 유지관리기준」(국토교통부 고시) 별표 점검항목 "
              "- 배관 및 부속기기의 부식·누수 상태 점검",
        action="부식부 케레이징 후 방청도장 재시공, 진행성 부식 시 해당 구간 배관 교체 검토",
    ),
    "crack": dict(
        rule_id="D-02", category="구조-균열",
        title="균열 발생",
        risk=3,
        basis="건축물관리법 시행령 제9조 및 「시설물의 안전 및 유지관리 실시 세부지침」 "
              "- 콘크리트 균열폭 0.3mm 이상 시 보수 대상(내구성 기준)",
        action="균열폭 실측(크랙게이지) 후 0.3mm 이상 시 에폭시 주입 보수, 진행성 여부 정기 계측",
    ),
    "cable_damage": dict(
        rule_id="D-03", category="전기설비-절연",
        title="전선·케이블 피복 손상",
        risk=3,
        basis="전기설비기술기준의 판단기준 제52조(저압전로의 절연성능) 및 "
              "한국전기설비규정(KEC) 132 - 절연저항 확보",
        action="손상 케이블 즉시 교체 또는 절연처리, 절연저항 측정(1MΩ 이상) 후 성적서 제출",
    ),
    "weld_bad": dict(
        rule_id="D-04", category="기계설비-용접",
        title="배관 용접부 불량",
        risk=3,
        basis="기계설비공사 표준시방서 및 KS B 0845(강용접 이음부의 방사선 투과시험) "
              "- 용접부 외관검사 및 비파괴검사 기준",
        action="해당 용접부 그라인딩 후 재용접, 재시공 부위 비파괴검사(RT/PT) 실시 및 성적서 제출",
    ),
    "weld_defect": dict(
        rule_id="D-05", category="기계설비-용접",
        title="용접 결함부(기공·언더컷 등) 발견",
        risk=2,
        basis="KS B 0845 / KS B 0896(강용접부의 초음파탐상시험) 결함 등급 판정 기준",
        action="결함 유형·크기 판정 후 보수용접, 동일 시공자 용접부 전수 외관검사 확대",
    ),
    "wall_damage": dict(
        rule_id="D-06", category="구조-손상",
        title="벽체·구조체 손상",
        risk=2,
        basis="「시설물의 안전 및 유지관리 실시 세부지침」 상태평가 기준 "
              "- 부재 손상 및 변형 상태",
        action="손상 범위 실측·사진대지 작성, 구조 안전성 검토 후 보수공법 결정",
    ),
}

GAUGE_RULES = {
    "gauge": dict(
        rule_id="G-01", category="커미셔닝-검침",
        title="계기(게이지) 검침 대상 식별",
        risk=1,
        basis="기계설비법 시행규칙 별표1 「기계설비 성능점검」 및 "
              "토탈커미셔닝(TAB) 성능검증 절차 - 운전데이터 계측·기록",
        action="검침값 자동 기록 및 설계값 대비 편차 확인, 허용범위 초과 시 원인 분석",
    ),
}

RULES = {"safety": SAFETY_RULES, "defect": DEFECT_RULES, "gauge": GAUGE_RULES}

# ---------------------------------------------------------------- 임계값 정책
# 감리 실무에서 오탐(false alarm)과 미탐(miss)의 비용은 항목마다 다르다.
#   · 안전모 미착용을 놓치면 사고로 이어진다      -> 재현율 우선 (임계값 낮춤)
#   · 화재 경보를 남발하면 현장이 경보를 무시한다 -> 정밀도 우선 (임계값 높임)
# 단일 conf 값을 전 클래스에 쓰지 않고 항목별로 다르게 두는 이유다.
CONF_POLICY = {
    # class      : (임계값, 정책 근거)
    "no_helmet":    (0.25, "미탐 비용이 큼 - 재현율 우선"),
    "no_vest":      (0.30, "표준"),
    "no_goggles":   (0.30, "표준"),
    "no_gloves":    (0.30, "표준"),
    "smoke":        (0.55, "오경보 시 현장 신뢰 상실 - 정밀도 우선"),
    "crack":        (0.30, "구조 안전 관련 - 재현율 우선"),
    "cable_damage": (0.35, "표준"),
    "corrosion":    (0.35, "표준"),
    "weld_bad":     (0.35, "재시공 요구 - 오탐 시 분쟁 소지"),
    "weld_defect":  (0.35, "표준"),
    "wall_damage":  (0.35, "표준"),
    "gauge":        (0.30, "표준"),
}


def conf_threshold(cls: str, default: float = 0.25) -> float:
    return CONF_POLICY.get(cls, (default, ""))[0]

# 착용/미착용 쌍 - PPE 준수율 산출용
PPE_PAIRS = [("helmet", "no_helmet", "안전모"),
             ("vest", "no_vest", "안전조끼"),
             ("goggles", "no_goggles", "보안경"),
             ("gloves", "no_gloves", "안전장갑")]


def build_findings(task: str, dets: List[Dict], min_conf: float = 0.25) -> List[Finding]:
    """탐지 결과 -> 지적사항 목록 (클래스별 임계값 정책 적용)"""
    rules = RULES.get(task, {})
    agg: Dict[str, Finding] = {}
    for d in dets:
        cls, conf = d["cls"], d["conf"]
        if cls not in rules:
            continue
        if conf < max(min_conf, conf_threshold(cls, min_conf)):
            continue
        if cls not in agg:
            agg[cls] = Finding(task=task, **rules[cls])
        f = agg[cls]
        f.count += 1
        f.max_conf = max(f.max_conf, conf)
        f.boxes.append(d["xyxy"])
    return sorted(agg.values(), key=lambda f: (-f.risk, -f.count))


def _overlap_ratio(inner: List[float], outer: List[float]) -> float:
    """inner 박스가 outer 영역과 겹치는 비율 (inner 면적 대비)"""
    x1, y1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    x2, y2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    a_in = max(1e-6, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return (x2 - x1) * (y2 - y1) / a_in


def derive_ppe_findings(dets: List[Dict], img_w: int, img_h: int,
                        person_conf: float = 0.35,
                        min_person_ratio: float = 0.04) -> List[Finding]:
    """
    미착용 클래스를 '직접 탐지'가 아니라 '관계 추론'으로 보완한다.

    미착용(no_helmet 등)은 착용(helmet)보다 학습 데이터가 훨씬 적어 탐지 성능이 낮다.
    반면 작업자(person)와 착용 보호구(helmet/vest)는 데이터가 많아 잘 탐지된다.
    그래서 '작업자는 있는데 그 머리 위치에 안전모가 없다'는 관계로 미착용을 추론한다.
    데이터 불균형을 모델이 아니라 규칙으로 우회하는 것이다.

    오탐을 막기 위해 다음 조건을 만족하는 작업자만 판정 대상으로 삼는다.
      · person 신뢰도가 충분히 높을 것
      · 화면에서 일정 크기 이상일 것 (멀리 있는 작업자는 보호구 판별 불가)
    """
    persons = [d for d in dets if d["cls"] == "person" and d["conf"] >= person_conf]
    if not persons:
        return []
    worn = {"helmet": [d["xyxy"] for d in dets if d["cls"] == "helmet"],
            "vest": [d["xyxy"] for d in dets if d["cls"] == "vest"]}
    # 이미 '지적사항으로 채택될 만큼' 확실히 직접 탐지된 미착용만 중복 판정에서 제외.
    # 임계값 미만의 약한 탐지까지 제외하면 관계 추론이 통째로 막힌다.
    direct = {d["cls"] for d in dets if d["conf"] >= conf_threshold(d["cls"])}

    zones = {  # (착용클래스, 미착용클래스, person 박스 내 세로 구간, 라벨)
        "helmet": ("no_helmet", 0.00, 0.35, "안전모"),
        "vest":   ("no_vest",   0.20, 0.75, "안전조끼"),
    }
    out: Dict[str, Finding] = {}
    for d in persons:
        x1, y1, x2, y2 = d["xyxy"]
        pw, ph = x2 - x1, y2 - y1
        if (pw * ph) / max(1, img_w * img_h) < min_person_ratio:
            continue
        for ok_cls, (ng_cls, t0, t1, label) in zones.items():
            if ng_cls in direct:          # 직접 탐지가 있으면 그쪽을 신뢰
                continue
            zone = [x1, y1 + ph * t0, x2, y1 + ph * t1]
            if any(_overlap_ratio(b, zone) >= 0.3 for b in worn[ok_cls]):
                continue                  # 해당 구간에 보호구가 있음 -> 착용
            rule = SAFETY_RULES[ng_cls]
            if ng_cls not in out:
                f = Finding(task="safety", **rule)
                f.detail = f"작업자 탐지 영역에 {label}가 확인되지 않아 미착용으로 추정 (관계 추론)"
                out[ng_cls] = f
            f = out[ng_cls]
            f.count += 1
            f.max_conf = max(f.max_conf, d["conf"])
            f.boxes.append([x1, y1 + ph * t0, x2, y1 + ph * t1])
    return list(out.values())


def ppe_compliance(dets: List[Dict], min_conf: float = 0.25) -> List[Dict]:
    """PPE 착용률(준수율) 산출"""
    cnt: Dict[str, int] = {}
    for d in dets:
        if d["conf"] >= min_conf:
            cnt[d["cls"]] = cnt.get(d["cls"], 0) + 1
    out = []
    for ok, ng, label in PPE_PAIRS:
        a, b = cnt.get(ok, 0), cnt.get(ng, 0)
        if a + b == 0:
            continue
        out.append(dict(item=label, worn=a, not_worn=b,
                        rate=round(a / (a + b) * 100, 1)))
    return out


def severity_by_area(f: Finding, img_w: int, img_h: int) -> str:
    """탐지 면적 비율로 하자 등급 판정 (D-01 부식 등)"""
    area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in f.boxes)
    ratio = area / max(1, img_w * img_h) * 100
    if ratio >= 5.0:
        return f"중대 (검출면적 {ratio:.1f}%)"
    if ratio >= 1.0:
        return f"보통 (검출면적 {ratio:.1f}%)"
    return f"경미 (검출면적 {ratio:.2f}%)"


# ================================================================
# 삼구아이앤씨 사업분야별 도메인 룰
#   생산 / 역극 / 물류 / 반도체 / 주차
#   각 도메인은 독립 에이전트로 동작하며, 자체 규정·위험도·조치를 갖는다.
# ================================================================

PRODUCT_RULES = {
    "dry_joint": dict(
        rule_id="P-01", category="생산-접합",
        title="접합 불량(냉납) 검출",
        risk=3,
        basis="IPC-A-610 전자조립 허용성 기준 Class 2 - 솔더 접합부 젖음성 불량 / "
              "사내 공정검사 기준서",
        action="해당 접합부 재작업 후 재검사, 동일 로트 전수검사 확대 여부 판단",
    ),
    "incorrect_install": dict(
        rule_id="P-02", category="생산-조립",
        title="조립·삽입 불량 (부품 오삽입·방향 오류)",
        risk=3,
        basis="IPC-A-610 부품 실장 방향·위치 기준 / 제조물 책임법 제3조(결함의 정의)",
        action="해당 부품 재실장, 작업표준서(WI) 재교육 및 초·중·종물 검사 강화",
    ),
    "board_damage": dict(
        rule_id="P-03", category="생산-손상",
        title="기판·부품 손상",
        risk=2,
        basis="IPC-A-610 기판 손상 허용 한계 / 사내 외관검사 기준",
        action="손상 정도 판정 후 폐기 또는 수리, 취급·이송 공정 원인 조사",
    ),
    "short_circuit": dict(
        rule_id="P-04", category="생산-전기",
        title="단락(쇼트) 검출",
        risk=4,
        basis="IPC-A-610 / 전기용품 및 생활용품 안전관리법 - 절연·단락 결함",
        action="즉시 격리, 절연저항 측정 및 원인 공정 추적, 동일 로트 홀드",
    ),
    "surface_defect": dict(
        rule_id="P-05", category="생산-외관",
        title="표면 결함(접힘·스크래치·이물)",
        risk=2,
        basis="사내 외관검사 기준 / KS A ISO 2859-1 계수형 샘플링 검사",
        action="외관 등급 판정 후 선별, 발생 공정 및 취급 방법 개선",
    ),
    "cell_anomaly": dict(
        rule_id="P-06", category="생산-셀",
        title="셀 이상(결함·음영) 검출",
        risk=3,
        basis="셀 외관·EL 검사 기준 / KS C IEC 61215 계열 결함 판정",
        action="이상 셀 격리 후 정밀검사, 동일 트레이 전수 재검",
    ),
}

POLARITY_RULES = {
    "cell_reversed": dict(
        rule_id="X-01", category="선별-역극",
        title="역극(逆極) 셀 검출 — 극성 반전 배열",
        risk=4,
        basis="배터리 셀 선별 작업표준 - 극성 방향 정렬 / "
              "KS C IEC 62133 이차전지 안전요구사항 (역접속 방지)",
        action="해당 셀 즉시 격리·교체, 트레이 전수 재검, 라인 조장 최종 확인 후 출고",
    ),
}

LOGISTICS_RULES = {
    "chassis_working": dict(
        rule_id="L-02", category="물류-작업",
        title="상하차 작업 진행 중 — 작업구역 통제 확인 필요",
        risk=1,
        basis="산업안전보건기준에 관한 규칙 제39조(하역운반기계등에 의한 위험 방지)",
        action="작업구역 통제선·유도자 배치 상태 확인",
    ),
}

SEMICON_RULES = {}

PARKING_RULES = {}

RULES.update({
    "product": PRODUCT_RULES,
    "polarity": POLARITY_RULES,
    "logistics": LOGISTICS_RULES,
    "semiconductor": SEMICON_RULES,
    "parking": PARKING_RULES,
})

CONF_POLICY.update({
    # 생산 - 라인 정지·재작업 비용이 크므로 표준~보수적
    "dry_joint":         (0.35, "재작업 유발 - 오탐 시 생산성 저하"),
    "incorrect_install": (0.30, "치명 불량 - 재현율 우선"),
    "board_damage":      (0.35, "표준"),
    "short_circuit":     (0.30, "안전 직결 - 재현율 우선"),
    "surface_defect":    (0.35, "표준"),
    "cell_anomaly":      (0.35, "표준"),
    # 역극 - 유출 시 고객 클레임·안전사고. 놓치는 비용이 압도적으로 크다
    "cell_reversed":     (0.25, "유출 시 클레임·안전사고 - 재현율 최우선"),
    "cell_ok":           (0.40, "양품 판정은 보수적으로"),
    # 물류
    "forklift":          (0.35, "표준"),
    "worker":            (0.30, "협착 위험 판정 입력 - 재현율 우선"),
    "chassis_working":   (0.45, "상태 판정 - 정밀도 우선"),
    # 주차
    "car": (0.35, "표준"), "bus": (0.35, "표준"), "truck": (0.35, "표준"),
})


# ---------------------------------------------------------------- 파생 룰
# 단일 객체가 아니라 '객체 사이의 관계'에서 나오는 지적사항.
# 물류 현장 재해의 상당수는 장비 자체가 아니라 장비와 사람의 거리에서 발생한다.

DERIVED_RULES = {
    "L-01": dict(
        rule_id="L-01", category="물류-협착위험",
        title="지게차 작업반경 내 보행 작업자 감지",
        risk=4,
        basis="산업안전보건기준에 관한 규칙 제172조(운전위치 이탈 시의 조치) 및 "
              "제39조(하역운반기계등에 의한 위험 방지) - 차량계 하역운반기계 작업반경 내 "
              "근로자 출입 금지",
        action="즉시 작업중지 및 작업자 대피, 유도자 배치·통제선 설치 후 작업 재개, "
               "지게차 동선과 보행자 통로 분리 여부 점검",
    ),
    "E-01": dict(
        rule_id="E-01", category="반도체-극성부품",
        title="극성 부품 실장 방향 확인 대상",
        risk=2,
        basis="IPC-A-610 극성 부품(다이오드·LED·전해커패시터) 방향 표시 정합 기준",
        action="극성 마크와 기판 실크 대조 확인, 오방향 시 재실장",
    ),
    "K-01": dict(
        rule_id="K-01", category="주차-운영",
        title="주차 점유 현황 집계",
        risk=1,
        basis="주차장법 시행규칙 제6조(주차장의 구조·설비기준) - 주차구획 운영관리",
        action="차종별 점유 현황 기록, 대형차 전용구획 초과 시 배치 조정",
    ),
}


def derive_logistics_findings(dets: List[Dict], img_w: int, img_h: int,
                              margin: float = 0.35) -> List[Finding]:
    """
    지게차 작업반경 내 보행 작업자 감지.

    지게차 박스를 좌우로 margin 비율만큼 확장한 영역을 '작업반경'으로 보고,
    그 안에 작업자 박스가 일정 비율 이상 들어오면 협착 위험으로 판정한다.
    (단안 카메라라 실제 거리는 알 수 없으므로, 화면상 근접을 위험 신호로 쓴다.)
    """
    forks = [d for d in dets if d["cls"] == "forklift"
             and d["conf"] >= conf_threshold("forklift")]
    workers = [d for d in dets if d["cls"] == "worker"
               and d["conf"] >= conf_threshold("worker")]
    if not forks or not workers:
        return []
    f = None
    for fk in forks:
        x1, y1, x2, y2 = fk["xyxy"]
        w, h = x2 - x1, y2 - y1
        zone = [x1 - w * margin, y1 - h * margin * 0.5,
                x2 + w * margin, y2 + h * margin * 0.5]
        for wk in workers:
            if _overlap_ratio(wk["xyxy"], zone) < 0.35:
                continue
            if f is None:
                f = Finding(task="logistics", **DERIVED_RULES["L-01"])
                f.detail = "지게차 작업반경(박스 확장 영역) 내 보행자 검출 - 화면상 근접 기준"
            f.count += 1
            f.max_conf = max(f.max_conf, min(fk["conf"], wk["conf"]))
            f.boxes.append(wk["xyxy"])
    return [f] if f else []


def derive_semicon_findings(dets: List[Dict], img_w: int, img_h: int) -> List[Finding]:
    """극성이 있는 부품(다이오드·LED)을 방향 확인 대상으로 올린다."""
    polar = [d for d in dets if d["cls"] in ("diode", "led")
             and d["conf"] >= conf_threshold(d["cls"], 0.30)]
    if not polar:
        return []
    f = Finding(task="semiconductor", **DERIVED_RULES["E-01"])
    f.count = len(polar)
    f.max_conf = max(d["conf"] for d in polar)
    f.boxes = [d["xyxy"] for d in polar]
    f.detail = f"극성 부품 {len(polar)}점 검출 - 실장 방향 대조 필요"
    return [f]


def derive_parking_findings(dets: List[Dict], img_w: int, img_h: int) -> List[Finding]:
    """차종별 점유 현황을 집계 항목으로 만든다(지적이 아니라 운영 기록)."""
    ko = {"car": "승용", "bus": "버스", "truck": "화물"}
    cnt = {}
    for d in dets:
        if d["cls"] in ko and d["conf"] >= conf_threshold(d["cls"], 0.35):
            cnt[d["cls"]] = cnt.get(d["cls"], 0) + 1
    if not cnt:
        return []
    f = Finding(task="parking", **DERIVED_RULES["K-01"])
    f.count = sum(cnt.values())
    f.max_conf = max(d["conf"] for d in dets if d["cls"] in ko)
    f.boxes = [d["xyxy"] for d in dets
               if d["cls"] in ko and d["conf"] >= conf_threshold(d["cls"], 0.35)]
    f.detail = "총 " + str(f.count) + "대 — " + " · ".join(
        f"{ko[k]} {v}대" for k, v in sorted(cnt.items()))
    return [f]


DERIVERS = {
    "logistics": derive_logistics_findings,
    "semiconductor": derive_semicon_findings,
    "parking": derive_parking_findings,
}


# ================================================================
# 삼구아이앤씨 사업영역 확장 — 안전·위생 / 미화
#   기존 SAFETY 는 건설현장 PPE 기준이었다.
#   여기서는 급식(F&B)·반도체 클린룸·생산라인까지 포함하도록 위생 항목을 넣는다.
#   마스크·위생장갑·위생화는 '안전'이 아니라 '위생' 규정을 근거로 삼는다.
# ================================================================

SAFETY2_RULES = {
    "no_helmet": dict(
        rule_id="H-01", category="안전-보호구",
        title="안전모 미착용 발견",
        risk=3,
        basis="산업안전보건기준에 관한 규칙 제32조 제1항 제1호 "
              "- 물체가 떨어지거나 날아올 위험이 있는 작업: 안전모",
        action="즉시 착용 조치 후 작업 재개, 작업 전 TBM 시 보호구 점검",
    ),
    "no_mask": dict(
        rule_id="H-02", category="위생-마스크",
        title="마스크 미착용 발견",
        risk=3,
        basis="식품위생법 시행규칙 별표17 「식품접객업 영업자 준수사항」 - 위생모·마스크 착용 / "
              "반도체 클린룸 작업표준 - 방진마스크 착용",
        action="급식·식품취급 구역 및 클린룸 출입 전 마스크 착용 확인, 미착용자 출입 제한",
    ),
    "no_gloves": dict(
        rule_id="H-03", category="위생-장갑",
        title="위생장갑·보호장갑 미착용 발견",
        risk=2,
        basis="식품위생법 시행규칙 별표17 - 식품 직접 취급 시 위생장갑 착용 / "
              "산업안전보건기준에 관한 규칙 제32조 제1항 제5호",
        action="작업 특성에 맞는 장갑 지급·착용 확인, 교체 주기 관리",
    ),
    "no_goggles": dict(
        rule_id="H-04", category="안전-보호구",
        title="보안경 미착용 발견",
        risk=2,
        basis="산업안전보건기준에 관한 규칙 제32조 제1항 제4호 "
              "- 물체가 흩날릴 위험이 있는 작업: 보안경",
        action="해당 공정 보안경 착용 의무화, 보호구 비치 상태 점검",
    ),
    "no_shoes": dict(
        rule_id="H-05", category="위생-복장",
        title="안전화·위생화 미착용 발견",
        risk=2,
        basis="산업안전보건기준에 관한 규칙 제32조 제1항 제2호(안전화) / "
              "클린룸 작업표준 - 방진화 착용 및 교차오염 방지",
        action="지정 신발 착용 확인, 클린룸·조리구역 신발 교체 구역 운영 상태 점검",
    ),
}

CLEANING_RULES = {}

RULES.update({"safety2": SAFETY2_RULES, "cleaning": CLEANING_RULES})

CONF_POLICY.update({
    # 위생 항목은 급식·클린룸에서 유출 시 회수·클레임 비용이 크다 -> 재현율 우선
    "no_mask":   (0.25, "위생 유출 비용이 큼 - 재현율 우선"),
    "no_gloves": (0.25, "위생 유출 비용이 큼 - 재현율 우선"),
    "no_shoes":  (0.30, "표준"),
    "mask": (0.35, "착용 판정은 보수적으로"),
    "shoes": (0.35, "착용 판정은 보수적으로"),
    # 미화 - 분리수거 상태는 지적이 아니라 집계
    "cardboard": (0.35, "표준"), "plastic": (0.35, "표준"), "glass": (0.35, "표준"),
    "metal": (0.35, "표준"), "paper": (0.35, "표준"), "biodegradable": (0.40, "과탐지 억제"),
})

DERIVED_RULES["C-01"] = dict(
    rule_id="C-01", category="미화-분리수거",
    title="분리수거 대상물 집계",
    risk=1,
    basis="폐기물관리법 제13조(폐기물의 처리기준) 및 사업장 폐기물 분리배출 지침",
    action="재질별 분리 상태 기록, 혼합 배출 구간 확인 및 수거 주기 조정",
)


def derive_cleaning_findings(dets, img_w: int, img_h: int):
    """분리수거 대상물을 재질별로 집계한다(지적이 아니라 운영 기록)."""
    ko = {"cardboard": "종이박스", "plastic": "플라스틱", "glass": "유리",
          "metal": "금속", "paper": "종이", "biodegradable": "일반·음식물"}
    sel = [d for d in dets if d["cls"] in ko and d["conf"] >= conf_threshold(d["cls"], 0.35)]
    if not sel:
        return []
    cnt = {}
    for d in sel:
        cnt[d["cls"]] = cnt.get(d["cls"], 0) + 1
    f = Finding(task="cleaning", **DERIVED_RULES["C-01"])
    f.count = len(sel)
    f.max_conf = max(d["conf"] for d in sel)
    f.boxes = [d["xyxy"] for d in sel]
    f.detail = "총 " + str(f.count) + "점 — " + " · ".join(
        f"{ko[k]} {v}" for k, v in sorted(cnt.items(), key=lambda x: -x[1]))
    return [f]


DERIVERS["cleaning"] = derive_cleaning_findings
