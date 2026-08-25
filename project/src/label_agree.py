# -*- coding: utf-8 -*-
"""
자동 라벨 vs 사람 라벨 일치도 측정

학습을 돌리지 않고도 라벨 품질을 볼 수 있다.
같은 이미지에 대해 사람이 친 박스와 자동으로 만든 박스를 클래스별로 매칭해
  · Recall     사람이 친 것 중 자동이 찾아낸 비율   (놓친 것)
  · Precision  자동이 친 것 중 사람 것과 맞는 비율  (헛것)
  · mean IoU   매칭된 쌍의 겹침 정도                 (위치 정확도)
를 낸다.

라벨링 도구를 고를 때 필요한 건 '모델이 얼마나 똑똑한가'가 아니라
'사람이 칠 박스를 얼마나 대신 쳐 주는가'다.
"""
import sys, os, json, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def load(p):
    out = []
    if not os.path.exists(p):
        return out
    for l in open(p, encoding="utf-8").read().split("\n"):
        f = l.split()
        if len(f) < 5:
            continue
        c = int(float(f[0]))
        cx, cy, w, h = [float(x) for x in f[1:5]]
        out.append((c, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


def iou(a, b):
    x1, y1 = max(a[1], b[1]), max(a[2], b[2])
    x2, y2 = min(a[3], b[3]), min(a[4], b[4])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    aa = (a[3] - a[1]) * (a[4] - a[2])
    bb = (b[3] - b[1]) * (b[4] - b[2])
    return inter / max(1e-9, aa + bb - inter)


def match(gt, pred, thr=0.5):
    """탐욕적 매칭 — IoU 큰 쌍부터 짝지운다."""
    pairs = []
    for i, g in enumerate(gt):
        for j, p in enumerate(pred):
            if g[0] != p[0]:
                continue
            v = iou(g, p)
            if v >= thr:
                pairs.append((v, i, j))
    pairs.sort(reverse=True)
    ug, up, matched = set(), set(), []
    for v, i, j in pairs:
        if i in ug or j in up:
            continue
        ug.add(i); up.add(j); matched.append((v, i, j))
    return matched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--human", required=True, help="사람 라벨 디렉터리 (labels)")
    ap.add_argument("--auto", nargs="+", required=True, help="자동 라벨 디렉터리들 (이름=경로)")
    ap.add_argument("--classes", nargs="*", default=["person", "helmet", "safety vest"])
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--out", default=str(ROOT / "reports" / "label_agreement.json"))
    a = ap.parse_args()

    report = {}
    for spec in a.auto:
        name, path = spec.split("=", 1)
        files = [f for f in os.listdir(path) if f.endswith(".txt")]
        tot_gt = tot_pd = tot_tp = 0
        ious, per = [], {}
        n_img = 0
        for fn in files:
            hp = os.path.join(a.human, fn)
            if not os.path.exists(hp):
                continue
            gt, pd = load(hp), load(os.path.join(path, fn))
            m = match(gt, pd, a.iou)
            n_img += 1
            tot_gt += len(gt); tot_pd += len(pd); tot_tp += len(m)
            ious += [v for v, _, _ in m]
            for ci, cname in enumerate(a.classes):
                g = sum(1 for x in gt if x[0] == ci)
                p = sum(1 for x in pd if x[0] == ci)
                t = sum(1 for v, i, j in m if gt[i][0] == ci)
                d = per.setdefault(cname, [0, 0, 0])
                d[0] += g; d[1] += p; d[2] += t
        rec = tot_tp / max(1, tot_gt)
        prec = tot_tp / max(1, tot_pd)
        f1 = 2 * rec * prec / max(1e-9, rec + prec)
        mi = sum(ious) / max(1, len(ious))
        report[name] = dict(images=n_img, human_boxes=tot_gt, auto_boxes=tot_pd,
                            matched=tot_tp, recall=round(rec, 4), precision=round(prec, 4),
                            f1=round(f1, 4), mean_iou=round(mi, 4),
                            per_class={k: dict(human=v[0], auto=v[1], matched=v[2],
                                               recall=round(v[2] / max(1, v[0]), 4),
                                               precision=round(v[2] / max(1, v[1]), 4))
                                       for k, v in per.items()})
        print(f"\n=== {name} (비교 {n_img}장, IoU>={a.iou}) ===")
        print(f"  사람 박스 {tot_gt} / 자동 박스 {tot_pd} / 일치 {tot_tp}")
        print(f"  Recall {rec*100:.1f}%  Precision {prec*100:.1f}%  F1 {f1*100:.1f}%  "
              f"mean IoU {mi:.3f}")
        for k, v in report[name]["per_class"].items():
            print(f"    {k:<14} 사람 {v['human']:>4} 자동 {v['auto']:>4} "
                  f"일치 {v['matched']:>4}  R={v['recall']*100:5.1f}% P={v['precision']*100:5.1f}%")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\nsaved:", a.out)


if __name__ == "__main__":
    main()
