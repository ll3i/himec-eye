# -*- coding: utf-8 -*-
"""
SAM 3 자동 라벨링 — 텍스트 프롬프트로 YOLO 학습 라벨을 만든다

지금 구조의 병목은 모델이 아니라 라벨링이다.
새 검사 항목이 생기면 사진을 모으고 박스를 치는 일부터 시작해야 하고,
불량·미착용처럼 드문 사례는 늘 모자란다.

SAM 3는 고정된 클래스 목록 없이 텍스트로 개념을 지시하면 해당하는 것을 모두 찾아 마스크를 낸다.
그 마스크의 바운딩 박스를 YOLO 라벨로 바꾸면, 사람이 박스를 치지 않고도 학습 데이터가 생긴다.

  텍스트 프롬프트  ──▶  SAM 3  ──▶  마스크  ──▶  YOLO 박스 라벨  ──▶  YOLO 학습
     "forklift"                                                        (현장 엣지 배포)

여기서 쓰는 가중치는 SAM3-LiteText (Apache-2.0).
SAM3의 ViT-H 이미지 인코더는 그대로 두고 텍스트 인코더만 MobileCLIP으로 경량화한 변형이라
원본 SAM3와 같은 프롬프트 인터페이스를 쓴다.
"""
import sys, os, io, json, glob, time, argparse, warnings

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "vil-uob/sam3-litetext-l"


class Sam3Labeler:
    """텍스트 프롬프트 -> 박스 라벨"""

    def __init__(self, model_id: str = MODEL_ID, threshold: float = 0.30,
                 mask_threshold: float = 0.5, imgsz: int = 0):
        import torch
        from transformers import AutoModel, AutoProcessor
        torch.set_num_threads(max(1, os.cpu_count() - 2))
        self.torch = torch
        print(f"[sam3] loading {model_id} ...")
        t = time.time()
        self.model = AutoModel.from_pretrained(model_id).eval()
        self.proc = AutoProcessor.from_pretrained(model_id)
        print(f"[sam3] loaded in {time.time()-t:.1f}s "
              f"({sum(p.numel() for p in self.model.parameters())/1e6:.0f}M params)")
        self.threshold = threshold
        self.mask_threshold = mask_threshold
        self.imgsz = imgsz

    def label_one(self, path: str, prompts: dict):
        """
        prompts: {"forklift": 0, "person": 1, ...}  텍스트 -> YOLO 클래스 인덱스
        반환: (라벨 줄 목록, 원본 크기, 프롬프트별 검출수)
        """
        im = Image.open(path).convert("RGB")
        if self.imgsz and max(im.size) > self.imgsz:
            s = self.imgsz / max(im.size)
            im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
        W, H = im.size
        lines, found = [], {}
        for text, cid in prompts.items():
            inputs = self.proc(images=im, text=text, return_tensors="pt")
            with self.torch.no_grad():
                out = self.model(**inputs)
            # post_process 는 검출이 0일 때 예외를 내므로 직접 디코딩한다.
            # pred_logits: (1, Q) 쿼리별 점수 / pred_boxes: (1, Q, 4) 정규화 xyxy
            score = out.pred_logits[0].sigmoid()
            keep = (score >= self.threshold).nonzero().flatten()
            n = 0
            if len(keep):
                bx = out.pred_boxes[0][keep]
                for b in bx:
                    x1, y1, x2, y2 = [float(v) * s for v, s in zip(b, (W, H, W, H))]
                    x1, y1 = max(0.0, x1), max(0.0, y1)
                    x2, y2 = min(float(W), x2), min(float(H), y2)
                    bw, bh = x2 - x1, y2 - y1
                    if bw < 4 or bh < 4:
                        continue
                    # 화면 전체를 덮는 마스크는 개념 오인 — 버린다
                    if bw * bh > 0.92 * W * H:
                        continue
                    cx, cy = (x1 + bw / 2) / W, (y1 + bh / 2) / H
                    lines.append(f"{cid} {cx:.6f} {cy:.6f} {bw/W:.6f} {bh/H:.6f}")
                    n += 1
            found[text] = n
        return lines, (W, H), found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="glob 패턴")
    ap.add_argument("--out", required=True, help="출력 데이터셋 루트 (YOLO 구조)")
    ap.add_argument("--prompts", required=True,
                    help='JSON: {"클래스명": "텍스트 프롬프트", ...} 순서가 클래스 인덱스')
    ap.add_argument("--split", default="train")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threshold", type=float, default=0.30)
    ap.add_argument("--imgsz", type=int, default=768, help="추론 전 축소 (0=원본)")
    a = ap.parse_args()

    spec = json.loads(a.prompts)               # {"forklift": "forklift", ...}
    classes = list(spec.keys())
    prompts = {spec[c]: i for i, c in enumerate(classes)}
    print("클래스:", classes)
    print("프롬프트:", list(prompts.keys()))

    paths = sorted(glob.glob(a.images))
    if a.limit:
        paths = paths[: a.limit]
    print(f"대상 이미지 {len(paths)}장")

    out = Path(a.out)
    (out / a.split / "images").mkdir(parents=True, exist_ok=True)
    (out / a.split / "labels").mkdir(parents=True, exist_ok=True)

    lab = Sam3Labeler(threshold=a.threshold, imgsz=a.imgsz)
    t0 = time.time()
    stats, n_img, n_box = {}, 0, 0
    for i, p in enumerate(paths, 1):
        try:
            lines, (W, H), found = lab.label_one(p, prompts)
        except Exception as e:
            print(f"  [{i}] {os.path.basename(p)[:40]} 실패: {str(e)[:60]}")
            continue
        for k, v in found.items():
            stats[k] = stats.get(k, 0) + v
        if lines:
            stem = Path(p).stem[:44]
            Image.open(p).convert("RGB").save(out / a.split / "images" / f"{stem}.jpg", quality=90)
            (out / a.split / "labels" / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
            n_img += 1
            n_box += len(lines)
        if i % 10 == 0 or i == len(paths):
            el = time.time() - t0
            print(f"  [{i}/{len(paths)}] 라벨 {n_box}개 / 이미지 {n_img}장 "
                  f"· {el/i:.1f}s/장 · 남은 {(len(paths)-i)*el/i/60:.1f}분")

    y = out / "data.yaml"
    body = [f"path: {out.resolve().as_posix()}", f"train: {a.split}/images",
            f"val: {a.split}/images", "", f"nc: {len(classes)}", "names:"]
    body += [f"  {i}: {c}" for i, c in enumerate(classes)]
    y.write_text("\n".join(body) + "\n", encoding="utf-8")

    print(f"\n완료: 이미지 {n_img}장 · 라벨 {n_box}개 · {(time.time()-t0)/60:.1f}분")
    print("프롬프트별 검출:", stats)
    print("data.yaml:", y)


if __name__ == "__main__":
    main()
