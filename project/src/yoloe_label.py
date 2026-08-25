# -*- coding: utf-8 -*-
"""
YOLOE 자동 라벨링 — 텍스트 프롬프트로 대량 라벨을 만든다

SAM 3 는 개념 이해가 뛰어나지만 CPU에서 40~80초/장이라 수백 장을 라벨링하기 어렵다.
YOLOE 는 같은 방식(텍스트 프롬프트 open-vocabulary)이면서 0.3초/장으로 100배 이상 빠르다.

그래서 둘의 역할이 갈린다.
  · SAM 3  : 소수 이미지의 정밀 라벨 · 어려운 개념 · 품질 기준선
  · YOLOE  : 대량 이미지의 초벌 라벨 · 실용 경로

둘 다 '사람이 박스를 치지 않는다'는 점은 같다.
"""
import sys, os, json, glob, time, argparse, warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("YOLO_VERBOSE", "false")
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompts", required=True,
                    help='JSON: {"클래스명": "텍스트 프롬프트", ...}')
    ap.add_argument("--split", default="train")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conf", type=float, default=0.20)
    ap.add_argument("--class-conf", default=None,
                    help='클래스별 임계값 JSON: {"safety vest":0.05}. '
                         '모델이 개념마다 다른 신뢰도로 답하기 때문에 하나의 값으로 묶으면 손해가 난다.')
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--model", default="yoloe-11s-seg.pt")
    a = ap.parse_args()

    import torch
    torch.set_num_threads(max(1, os.cpu_count() - 4))
    from ultralytics import YOLOE

    spec = json.loads(a.prompts)
    classes = list(spec.keys())
    texts = [spec[c] for c in classes]
    print("클래스:", classes)
    print("프롬프트:", texts)

    cconf = json.loads(a.class_conf) if a.class_conf else {}
    if cconf:
        print("클래스별 임계값:", cconf)
    base_conf = min([a.conf] + [v for v in cconf.values()])   # 가장 낮은 값으로 뽑고 뒤에서 거른다

    m = YOLOE(a.model)
    m.set_classes(texts, m.get_text_pe(texts))

    paths = sorted(glob.glob(a.images))
    if a.limit:
        paths = paths[: a.limit]
    print(f"대상 이미지 {len(paths)}장")

    out = Path(a.out)
    (out / a.split / "images").mkdir(parents=True, exist_ok=True)
    (out / a.split / "labels").mkdir(parents=True, exist_ok=True)

    from PIL import Image
    t0 = time.time()
    stats, n_img, n_box = {}, 0, 0
    for i, p in enumerate(paths, 1):
        try:
            r = m.predict(p, conf=base_conf, imgsz=a.imgsz, device="cpu", verbose=False)[0]
        except Exception as e:
            print(f"  [{i}] 실패 {str(e)[:50]}")
            continue
        im = Image.open(p).convert("RGB")
        W, H = im.size
        lines = []
        for b in r.boxes:
            cid = int(b.cls)
            thr = cconf.get(classes[cid], a.conf)
            if float(b.conf) < thr:
                continue
            x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
            bw, bh = x2 - x1, y2 - y1
            if bw < 4 or bh < 4 or bw * bh > 0.92 * W * H:
                continue
            cx, cy = (x1 + bw / 2) / W, (y1 + bh / 2) / H
            lines.append(f"{cid} {cx:.6f} {cy:.6f} {bw/W:.6f} {bh/H:.6f}")
            stats[classes[cid]] = stats.get(classes[cid], 0) + 1
        if lines:
            stem = Path(p).stem[:44]
            im.save(out / a.split / "images" / f"{stem}.jpg", quality=90)
            (out / a.split / "labels" / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
            n_img += 1
            n_box += len(lines)
        if i % 100 == 0 or i == len(paths):
            el = time.time() - t0
            print(f"  [{i}/{len(paths)}] 라벨 {n_box}개 / 이미지 {n_img}장 · {el/i:.2f}s/장")

    y = out / "data.yaml"
    body = [f"path: {out.resolve().as_posix()}", f"train: {a.split}/images",
            f"val: {a.split}/images", "", f"nc: {len(classes)}", "names:"]
    body += [f"  {i}: {c}" for i, c in enumerate(classes)]
    y.write_text("\n".join(body) + "\n", encoding="utf-8")
    print(f"\n완료: 이미지 {n_img}장 · 라벨 {n_box}개 · {(time.time()-t0)/60:.1f}분")
    print("클래스별:", stats)


if __name__ == "__main__":
    main()
