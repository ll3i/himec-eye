# -*- coding: utf-8 -*-
"""
멀티에이전트 판독 오케스트레이터

삼구아이앤씨의 사업분야는 하나의 모델로 덮이지 않는다.
배터리 셀 역극과 지게차 협착 위험은 찍는 대상도, 판정 기준도, 근거 법규도 다르다.
그래서 분야마다 전용 모델과 전용 룰을 가진 '에이전트'를 두고,
오케스트레이터가 어떤 에이전트를 부를지 정하고 결과를 하나의 리포트로 합친다.

  [현장 이미지]
        │
   ┌────▼────────────────────────────────┐
   │ 오케스트레이터                       │
   │  · 라우팅   : 어떤 에이전트를 부를까 │
   │  · 병렬 실행                          │
   │  · 통합     : 위험도 순 단일 리포트  │
   └────┬────────────────────────────────┘
   ┌────┼────┬────┬────┬────┬────┐
   ▼    ▼    ▼    ▼    ▼    ▼    ▼
  안전  생산 역극 물류 반도체 주차 설비
         (각각 YOLO 모델 + 도메인 룰)

라우팅은 두 가지 모드를 쓴다.
  · 지정(explicit) : 사용자가 분야를 안다. 현장에서는 대부분 이쪽이다.
  · 자동(auto)     : 전 에이전트를 낮은 임계값으로 훑어 도메인 점수를 매기고 상위만 채택.
                     오탐(학습 분포 밖 이미지를 엉뚱한 에이전트가 잡는 것)을 막는 장치다.
"""
import sys, os, json, glob, warnings, datetime
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore")
os.environ.setdefault("YOLO_VERBOSE", "false")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image

from rules import (build_findings, ppe_compliance, severity_by_area,
                   derive_ppe_findings, DERIVERS, Finding)
from inspect_engine import InspectionEngine, _find_weights

ROOT = Path(__file__).resolve().parents[1]

# 에이전트 정의 — 삼구아이앤씨 사업분야 기준
AGENTS = {
    "safety2": dict(ko="안전·위생", desc="보호구·마스크·위생화 착용 판정",
                    scope="생산도급 · 급식(F&B) · 클린룸 공통"),
    "safety": dict(ko="안전", desc="개인보호구·화재 감시",
                   scope="전 사업장 공통 (생산·물류·시설)"),
    "product": dict(ko="생산", desc="제품 양품/불량 선별",
                    scope="생산도급·임가공 라인 검사"),
    "polarity": dict(ko="역극", desc="배터리 셀 극성 방향 판정",
                     scope="2차전지 셀 선별 공정"),
    "logistics": dict(ko="물류", desc="지게차·섀시·적재 상태",
                      scope="입고·적재·출고 운송"),
    "semiconductor": dict(ko="반도체", desc="부품 실장 검사",
                          scope="반도체·전자 생산기술 지원"),
    "parking": dict(ko="주차", desc="차종별 점유 현황",
                    scope="주차장 운영관리"),
    "defect": dict(ko="설비", desc="부식·균열·용접·케이블",
                   scope="시설관리·설비 유지보수"),
    "cleaning": dict(ko="미화", desc="분리수거 대상물 재질별 집계",
                     scope="시설관리 — 미화·폐기물 관리"),
    "gauge": dict(ko="계기", desc="계기 검침 자동 기록",
                  scope="설비 성능점검·커미셔닝"),
}


class DomainAgent:
    """도메인 하나를 책임지는 에이전트: 전용 YOLO 모델 + 전용 룰."""

    def __init__(self, task: str, imgsz: int = 416, iou: float = 0.5):
        self.task = task
        self.meta = AGENTS.get(task, {"ko": task, "desc": "", "scope": ""})
        self.imgsz, self.iou = imgsz, iou
        self.weights = _find_weights(task)
        self.model = None
        self.names: Dict[int, str] = {}
        if self.weights:
            from ultralytics import YOLO
            self.model = YOLO(str(self.weights))
            self.names = self.model.names

    @property
    def ready(self) -> bool:
        return self.model is not None

    def detect(self, path: str, conf: float) -> List[Dict]:
        if not self.ready:
            return []
        r = self.model.predict(path, conf=conf, iou=self.iou, imgsz=self.imgsz,
                               device="cpu", verbose=False)[0]
        return [dict(cls=self.names[int(b.cls)], conf=float(b.conf),
                     xyxy=[round(float(v), 1) for v in b.xyxy[0].tolist()])
                for b in r.boxes]

    def run(self, path: str, W: int, H: int, conf: float = 0.20,
            derive: bool = True) -> Dict:
        """탐지 -> 도메인 룰 적용 -> 이 에이전트의 판정"""
        dets = self.detect(path, conf)
        findings: List[Finding] = []
        for f in build_findings(self.task, dets, min_conf=conf):
            if f.rule_id in ("D-01", "D-02", "D-06"):
                f.detail = severity_by_area(f, W, H)
            findings.append(f)

        if derive:
            have = {f.rule_id for f in findings}
            extra: List[Finding] = []
            if self.task == "safety":
                extra = derive_ppe_findings(dets, W, H)
            elif self.task in DERIVERS:
                extra = DERIVERS[self.task](dets, W, H)
            for f in extra:
                if f.rule_id not in have:
                    findings.append(f)

        findings.sort(key=lambda f: (-f.risk, -f.count))
        risk = max([f.risk for f in findings], default=0)
        # 도메인 점수: 이 이미지가 이 도메인에 속할 가능성 (자동 라우팅에 사용)
        score = round(sum(d["conf"] for d in dets), 2)
        return dict(
            agent=self.task, ko=self.meta["ko"], desc=self.meta["desc"],
            detections=len(dets), raw=dets, score=score,
            findings=[f.to_dict() for f in findings],
            risk=risk,
            verdict=("부적합" if risk >= 3 else "조건부적합" if risk == 2 else "적합"),
            ppe=(ppe_compliance(dets, conf) if self.task == "safety" else []),
        )


class Orchestrator:
    """에이전트들을 부르고, 결과를 하나의 리포트로 합친다."""

    def __init__(self, tasks: Optional[List[str]] = None, imgsz: int = 416,
                 max_workers: int = 3):
        want = tasks or list(AGENTS.keys())
        self.agents: Dict[str, DomainAgent] = {}
        for t in want:
            a = DomainAgent(t, imgsz=imgsz)
            if a.ready:
                self.agents[t] = a
        self.max_workers = max_workers

    @property
    def ready_agents(self) -> List[str]:
        return list(self.agents.keys())

    def route(self, path: str, W: int, H: int, top: int = 2,
              min_score: float = 1.0) -> List[str]:
        """
        자동 라우팅 — 전 에이전트를 낮은 임계값으로 훑어 도메인 점수를 매긴다.
        점수가 낮은 도메인은 애초에 그 이미지의 분야가 아니므로 부르지 않는다.
        """
        scores = {}
        for t, a in self.agents.items():
            dets = a.detect(path, conf=0.25)
            scores[t] = round(sum(d["conf"] for d in dets), 2)
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        picked = [t for t, s in ranked[:top] if s >= min_score]
        return picked or ([ranked[0][0]] if ranked else []), scores

    def inspect(self, path: str, tasks: Optional[List[str]] = None,
                conf: float = 0.20, derive: bool = True,
                auto_route: bool = False) -> Dict:
        img = Image.open(path).convert("RGB")
        W, H = img.size
        routing = None
        if tasks:
            use = [t for t in tasks if t in self.agents]
        elif auto_route:
            use, routing = self.route(path, W, H)
        else:
            use = list(self.agents.keys())

        def _run(t):
            return self.agents[t].run(path, W, H, conf=conf, derive=derive)

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            results = list(ex.map(_run, use))

        all_f = [dict(f, agent=r["agent"], agent_ko=r["ko"])
                 for r in results for f in r["findings"]]
        all_f.sort(key=lambda f: (-f["risk"], -f["count"]))
        risk = max([f["risk"] for f in all_f], default=0)
        exif = InspectionEngine.read_exif(path)
        return dict(
            image=os.path.basename(path), path=str(path), width=W, height=H,
            inspected_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            exif=exif,
            agents_run=use, routing_scores=routing,
            per_agent=results,
            findings=all_f,
            ppe_compliance=[p for r in results for p in r["ppe"]],
            risk_max=risk,
            verdict=("부적합" if risk >= 3 else "조건부적합" if risk == 2 else "적합"),
            raw_detections={r["agent"]: r["raw"] for r in results},
            detections={r["agent"]: r["detections"] for r in results},
        )


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--agents", nargs="*", default=None, help="부를 에이전트 (미지정 시 전체)")
    ap.add_argument("--auto", action="store_true", help="자동 라우팅")
    ap.add_argument("--conf", type=float, default=0.20)
    ap.add_argument("--out", default=str(ROOT / "reports" / "agents_out"))
    a = ap.parse_args()

    orc = Orchestrator(tasks=a.agents)
    print("가동 에이전트:", [f"{t}({AGENTS[t]['ko']})" for t in orc.ready_agents])
    paths = []
    for pat in a.images:
        paths += sorted(glob.glob(pat))

    eng = InspectionEngine.__new__(InspectionEngine)
    eng.conf = a.conf
    results = []
    for p in paths:
        r = orc.inspect(p, tasks=a.agents, conf=a.conf, auto_route=a.auto)
        out = os.path.join(a.out, "annotated", os.path.basename(p))
        eng.annotate(p, r, out)
        r["annotated"] = out
        results.append(r)
        ids = [f"{f['rule_id']}" for f in r["findings"]]
        print(f"{os.path.basename(p)[:44]:<46} {r['verdict']:<6} "
              f"agents={','.join(r['agents_run']):<28} {ids}")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("saved:", os.path.join(a.out, "results.json"))


if __name__ == "__main__":
    main()
