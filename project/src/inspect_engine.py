# -*- coding: utf-8 -*-
"""
HIMEC 현장사진 판독 엔진
사진 1장 -> [안전 / 하자 / 계기] 3축 동시 판독 -> 지적사항(Finding) + 시각화

설계 의도:
  - 감리원이 현장에서 찍은 사진을 그대로 넣으면 검측조서 초안이 나오는 것이 목표.
  - 모델이 아직 학습되지 않은 태스크는 자동으로 건너뛰어(graceful degrade) 항상 동작한다.
"""
import sys, os, io, json, glob, warnings, datetime

warnings.filterwarnings("ignore")
os.environ.setdefault("YOLO_VERBOSE", "false")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont, ExifTags
from rules import (build_findings, ppe_compliance, severity_by_area,
                   derive_ppe_findings, Finding)

ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = "C:/Windows/Fonts/malgun.ttf"
from datasets_config import TASKS as _TASKCFG
TASKS = list(_TASKCFG.keys())

RISK_COLOR = {4: (220, 20, 40), 3: (255, 90, 0), 2: (245, 180, 0), 1: (0, 150, 220)}
OK_COLOR = (0, 175, 100)


def _find_weights(task: str) -> Optional[Path]:
    """runs/ 에서 해당 태스크의 최신 best.pt 탐색"""
    cands = sorted(ROOT.glob("runs/" + task + "_*/weights/best.pt"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


class InspectionEngine:
    """
    tasks 를 지정하면 해당 판독축만 적용한다(검측 유형 라우팅).

    감리원은 사진을 찍는 시점에 이미 무엇을 검측하는지 알고 있다.
    '안전점검'으로 찍은 사진에 하자 모델까지 돌릴 필요는 없고, 반대도 마찬가지다.
    특히 하자 검측용 근접 촬영 사진(부식·용접부 클로즈업)은 안전 모델의 학습 분포
    밖이라 오탐(예: 텍스처를 연기로 오인)을 일으킨다. 유형을 지정하면 이를 차단한다.
    """

    def __init__(self, conf: float = 0.25, iou: float = 0.5, imgsz: int = 416,
                 tasks: Optional[List[str]] = None, derive: bool = True):
        from ultralytics import YOLO
        self.conf, self.iou, self.imgsz = conf, iou, imgsz
        self.derive = derive
        self.models: Dict[str, object] = {}
        self.names: Dict[str, Dict[int, str]] = {}
        for t in (tasks or TASKS):
            if t not in TASKS:
                continue
            w = _find_weights(t)
            if w is None:
                continue
            m = YOLO(str(w))
            self.models[t] = m
            self.names[t] = m.names
        self.loaded = list(self.models.keys())

    # ------------------------------------------------------------ EXIF
    @staticmethod
    def read_exif(path: str) -> Dict:
        out = {"datetime": None, "gps": None, "camera": None}
        try:
            img = Image.open(path)
            ex = img._getexif() or {}
            tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
            out["datetime"] = tags.get("DateTimeOriginal") or tags.get("DateTime")
            mk, md = tags.get("Make"), tags.get("Model")
            cam = " ".join(str(x).strip() for x in [mk, md] if x)
            out["camera"] = cam or None
            gps = tags.get("GPSInfo")
            if gps:
                g = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps.items()}

                def dms(v, ref):
                    deg = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
                    return -deg if ref in ("S", "W") else deg

                if "GPSLatitude" in g and "GPSLongitude" in g:
                    out["gps"] = [round(dms(g["GPSLatitude"], g.get("GPSLatitudeRef", "N")), 6),
                                  round(dms(g["GPSLongitude"], g.get("GPSLongitudeRef", "E")), 6)]
        except Exception:
            pass
        return out

    # ------------------------------------------------------------ 추론
    def detect(self, path: str) -> Dict[str, List[Dict]]:
        res = {}
        for t, m in self.models.items():
            r = m.predict(path, conf=self.conf, iou=self.iou, imgsz=self.imgsz,
                          device="cpu", verbose=False)[0]
            dets = []
            for b in r.boxes:
                dets.append(dict(cls=self.names[t][int(b.cls)],
                                 conf=float(b.conf),
                                 xyxy=[round(float(v), 1) for v in b.xyxy[0].tolist()]))
            res[t] = dets
        return res

    # ------------------------------------------------------------ 판독
    def inspect(self, path: str) -> Dict:
        img = Image.open(path).convert("RGB")
        W, H = img.size
        dets = self.detect(path)
        findings: List[Finding] = []
        for t, ds in dets.items():
            for f in build_findings(t, ds, min_conf=self.conf):
                if f.rule_id in ("D-01", "D-02", "D-06"):
                    f.detail = severity_by_area(f, W, H)
                findings.append(f)
        # 미착용 클래스는 직접 탐지가 약하므로 작업자-보호구 관계로 보완
        if "safety" in dets and self.derive:
            found = {f.rule_id for f in findings}
            for f in derive_ppe_findings(dets["safety"], W, H):
                if f.rule_id not in found:
                    findings.append(f)
        findings.sort(key=lambda f: (-f.risk, -f.count))

        ppe = ppe_compliance(dets.get("safety", []), self.conf)
        exif = self.read_exif(path)
        risk_max = max([f.risk for f in findings], default=0)
        verdict = "부적합" if risk_max >= 3 else ("조건부적합" if risk_max == 2 else "적합")
        return dict(
            image=os.path.basename(path), path=str(path), width=W, height=H,
            inspected_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            exif=exif,
            detections={t: len(d) for t, d in dets.items()},
            raw_detections=dets,
            findings=[f.to_dict() for f in findings],
            ppe_compliance=ppe,
            risk_max=risk_max,
            verdict=verdict,
        )

    # ------------------------------------------------------------ 시각화
    def annotate(self, path: str, result: Dict, out_path: str, max_side: int = 1100) -> str:
        img = Image.open(path).convert("RGB")
        if max(img.size) > max_side:
            s = max_side / max(img.size)
            img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
        else:
            s = 1.0
        d = ImageDraw.Draw(img, "RGBA")
        fs = max(14, int(img.width / 55))
        try:
            font = ImageFont.truetype(FONT_PATH, fs)
            font_s = ImageFont.truetype(FONT_PATH, int(fs * 0.8))
        except Exception:
            font = font_s = ImageFont.load_default()

        v = result["verdict"]
        bc = {"부적합": (220, 20, 40), "조건부적합": (245, 165, 0), "적합": OK_COLOR}[v]
        bh = int(fs * 1.9)

        for f in result["findings"]:
            c = RISK_COLOR[f["risk"]]
            for b in f["boxes"]:
                x1, y1, x2, y2 = [v_ * s for v_ in b]
                d.rectangle([x1, y1, x2, y2], outline=c, width=max(2, int(fs / 6)))
                lab = f["rule_id"] + " " + f["title"].split("(")[0].strip()[:16]
                tw = d.textlength(lab, font=font_s)
                ty = y1 - fs * 1.25
                if ty < bh + 2:          # 상단 판정 배너와 겹치면 박스 안쪽으로
                    ty = y1 + 2
                x1 = min(x1, img.width - tw - 10)
                d.rectangle([x1, ty, x1 + tw + 8, ty + fs * 1.2], fill=c + (235,))
                d.text((x1 + 4, ty + 1), lab, fill=(255, 255, 255), font=font_s)

        d.rectangle([0, 0, img.width, bh], fill=bc + (225,))
        n = len(result["findings"])
        txt = "판정: " + v + "   |   지적사항 " + str(n) + "건   |   " + result["inspected_at"][:16]
        d.text((10, int(bh * 0.22)), txt, fill=(255, 255, 255), font=font)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, quality=90)
        return out_path


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default=str(ROOT / "reports" / "out"))
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--tasks", nargs="*", default=None,
                    help="검측 유형 지정 (safety/defect/gauge). 미지정 시 학습된 전 축 적용")
    ap.add_argument("--no-derive", action="store_true",
                    help="작업자-보호구 관계 추론 비활성화 (직접 탐지만 사용)")
    a = ap.parse_args()
    eng = InspectionEngine(conf=a.conf, tasks=a.tasks, derive=not a.no_derive)
    print("loaded models:", eng.loaded)
    paths = []
    for pat in a.images:
        paths += sorted(glob.glob(pat))
    results = []
    for p in paths:
        r = eng.inspect(p)
        out = os.path.join(a.out, "annotated", os.path.basename(p))
        eng.annotate(p, r, out)
        r["annotated"] = out
        results.append(r)
        ids = [f["rule_id"] for f in r["findings"]]
        print(f"{os.path.basename(p):<34} {r['verdict']:<6} findings={len(r['findings'])} {ids}")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(a.out, "results.json"), "w", encoding="utf-8") as fp:
        json.dump(results, fp, ensure_ascii=False, indent=2)
    print("saved:", os.path.join(a.out, "results.json"))


if __name__ == "__main__":
    main()
