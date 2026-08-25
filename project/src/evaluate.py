# -*- coding: utf-8 -*-
"""학습된 모델의 test-set 성능 평가 -> 제안서용 성능표(JSON/Markdown) 생성"""
import sys, os, json, argparse, warnings, multiprocessing as mp

warnings.filterwarnings("ignore")
os.environ.setdefault("YOLO_VERBOSE", "false")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KO = {
    "person": "작업자", "helmet": "안전모 착용", "no_helmet": "안전모 미착용",
    "vest": "안전조끼 착용", "no_vest": "안전조끼 미착용",
    "goggles": "보안경 착용", "no_goggles": "보안경 미착용",
    "gloves": "안전장갑 착용", "no_gloves": "안전장갑 미착용",
    "cone": "안전콘", "smoke": "연기·화재",
    "corrosion": "부식", "crack": "균열", "cable_damage": "케이블 손상",
    "weld_bad": "용접 불량", "weld_good": "용접 양호", "weld_defect": "용접 결함부",
    "wall_damage": "벽체 손상", "gauge": "계기", "digit": "지침 숫자",
}


def find_weights(task):
    c = sorted(ROOT.glob("runs/" + task + "_*/weights/best.pt"),
               key=lambda p: p.stat().st_mtime, reverse=True)
    return c[0] if c else None


def eval_task(task, split="test", imgsz=416):
    import torch
    torch.set_num_threads(max(1, mp.cpu_count() - 2))
    from ultralytics import YOLO
    w = find_weights(task)
    if w is None:
        print(f"[skip] {task}: no weights")
        return None
    m = YOLO(str(w))
    r = m.val(data=str(ROOT / "data" / "processed" / task / "data.yaml"),
              split=split, imgsz=imgsz, device="cpu", verbose=False,
              project=str(ROOT / "runs"), name=f"eval_{task}", exist_ok=True, plots=True)
    b = r.box
    names = m.names
    per = []
    for i, ci in enumerate(b.ap_class_index):
        cn = names[int(ci)]
        per.append(dict(cls=cn, ko=KO.get(cn, cn),
                        precision=round(float(b.p[i]), 4),
                        recall=round(float(b.r[i]), 4),
                        map50=round(float(b.ap50[i]), 4),
                        map5095=round(float(b.ap[i]), 4)))
    # 실제 학습된 epoch 수 (results.csv 행 수)
    epochs = None
    csvp = Path(w).parent.parent / "results.csv"
    if csvp.exists():
        epochs = max(0, sum(1 for _ in open(csvp, encoding="utf-8")) - 1)
    out = dict(task=task, weights=str(w), split=split, imgsz=imgsz, epochs=epochs,
               overall=dict(precision=round(float(b.mp), 4), recall=round(float(b.mr), 4),
                            map50=round(float(b.map50), 4), map5095=round(float(b.map), 4)),
               per_class=per)
    return out


def to_markdown(reports):
    L = ["# 모델 성능 평가 결과 (test split)", ""]
    for rep in reports:
        if rep is None:
            continue
        o = rep["overall"]
        L.append(f"## {rep['task'].upper()} 모델")
        L.append("")
        L.append(f"- 가중치: `{Path(rep['weights']).parent.parent.name}`")
        L.append(f"- 입력 해상도: {rep['imgsz']}px / 평가 split: {rep['split']}"
                 + (f" / 학습 epoch: {rep['epochs']}" if rep.get("epochs") else ""))
        L.append("")
        L.append("| 지표 | 값 |")
        L.append("|---|---|")
        L.append(f"| mAP@50 | **{o['map50']*100:.1f}%** |")
        L.append(f"| mAP@50-95 | {o['map5095']*100:.1f}% |")
        L.append(f"| Precision | {o['precision']*100:.1f}% |")
        L.append(f"| Recall | {o['recall']*100:.1f}% |")
        L.append("")
        L.append("| 클래스 | Precision | Recall | mAP@50 | mAP@50-95 |")
        L.append("|---|---:|---:|---:|---:|")
        for p in sorted(rep["per_class"], key=lambda x: -x["map50"]):
            L.append(f"| {p['ko']} (`{p['cls']}`) | {p['precision']*100:.1f}% | "
                     f"{p['recall']*100:.1f}% | **{p['map50']*100:.1f}%** | {p['map5095']*100:.1f}% |")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    from datasets_config import TASKS as _T
    ap.add_argument("--tasks", nargs="*", default=list(_T.keys()))
    ap.add_argument("--split", default="test")
    ap.add_argument("--imgsz", type=int, default=416)
    a = ap.parse_args()
    reports = []
    for t in a.tasks:
        print(f"[eval] {t} ...")
        rep = eval_task(t, a.split, a.imgsz)
        if rep:
            o = rep["overall"]
            print(f"  mAP50={o['map50']*100:.1f}%  mAP50-95={o['map5095']*100:.1f}%  "
                  f"P={o['precision']*100:.1f}%  R={o['recall']*100:.1f}%")
        reports.append(rep)
    (ROOT / "reports").mkdir(exist_ok=True)
    with open(ROOT / "reports" / "performance.json", "w", encoding="utf-8") as f:
        json.dump([r for r in reports if r], f, ensure_ascii=False, indent=2)
    (ROOT / "reports" / "performance.md").write_text(to_markdown(reports), encoding="utf-8")
    print("saved: reports/performance.json, reports/performance.md")


if __name__ == "__main__":
    main()
