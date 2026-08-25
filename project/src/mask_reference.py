# -*- coding: utf-8 -*-
"""
참고자료 이미지 익명화

내부 자료의 판정화면을 공개 페이지에 쓰기 전에 식별정보를 지운다.
  · 로트번호 / 제품 시리얼번호 : 고객사 자산 데이터
  · 좌측 스프레드시트의 일련번호 목록
지우는 것은 '가려서 안 보이게'가 아니라 '픽셀을 덮어써서 복원 불가하게' 처리한다.
"""
import sys, os, argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "_pdf_images"
OUT = ROOT / "data" / "reference"

# (파일, [(x0,y0,x1,y1,라벨)]) — 비율(0~1) 좌표
MASKS = {
    "p6_151.png": [
        (0.00, 0.26, 0.22, 1.00, "스프레드시트 일련번호"),
        (0.18, 0.255, 0.80, 0.30, "창 제목 (시스템명)"),
        (0.18, 0.30, 0.80, 0.365, "로트번호 · 진행 카운트"),
    ],
    "p6_138.png": [],   # 셀 라벨은 축소 시 판독 불가 — 전체 약한 블러만
}


def mask(fn, boxes, blur_all=0.0, max_side=760):
    p = SRC / fn
    if not p.exists():
        return None
    im = Image.open(p).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    for x0, y0, x1, y1, _ in boxes:
        box = [x0 * W, y0 * H, x1 * W, y1 * H]
        # 해당 영역을 강하게 블러 처리한 뒤 덮어써 원본 픽셀을 남기지 않는다
        region = im.crop([int(v) for v in box]).filter(ImageFilter.GaussianBlur(18))
        im.paste(region, (int(box[0]), int(box[1])))
        d.rectangle(box, outline=(120, 130, 140), width=1)
    if blur_all:
        im = im.filter(ImageFilter.GaussianBlur(blur_all))
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    OUT.mkdir(parents=True, exist_ok=True)
    o = OUT / fn.replace(".png", ".jpg")
    im.save(o, quality=84)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-side", type=int, default=760)
    a = ap.parse_args()
    for fn, boxes in MASKS.items():
        blur = 0.6 if not boxes else 0.0
        o = mask(fn, boxes, blur_all=blur, max_side=a.max_side)
        print(f"  {fn:<14} -> {o}  (마스킹 {len(boxes)}곳)" if o else f"  {fn}: 원본 없음")


if __name__ == "__main__":
    main()
