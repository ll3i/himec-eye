# -*- coding: utf-8 -*-
"""
역극(逆極) 검사용 합성 데이터 생성

배터리 셀 선별 공정에서 가장 치명적인 불량은 '역극' — 셀이 뒤집힌 채 배열되는 것이다.
실제 고객사의 셀 이미지는 자산이므로 공개 학습에 쓸 수 없다.
그래서 각형 셀의 구조적 단서(양극 단자 / 음극 단자 / 라벨 방향)를 모사한 합성 트레이를
생성하여 '극성 방향 판정'이라는 방법론 자체를 실증한다.

실제 도입 시에는 이 합성 데이터 대신 고객사 양품 셀 이미지로 재학습하면 된다.
학습 코드도, 판정 로직도 그대로 쓴다.

각형 셀 모사 요소
  · 셀 몸체    : 은색 메탈 케이스
  · 양극(+)    : 밝은 알루미늄 단자 (한쪽 끝)
  · 음극(-)    : 어두운 구리색 단자 (반대쪽 끝)
  · 라벨       : 한쪽에 치우친 스티커 (방향 단서)
  · 역극 셀    : 위 요소가 180도 회전
"""
import sys, os, random, argparse, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "polarity"
CLASSES = ["cell_ok", "cell_reversed"]


def jitter(c, d):
    """밝기만 흔든다 — 채널별로 흔들면 금속이 파스텔로 변색된다."""
    k = random.uniform(-d, d)
    return tuple(max(0, min(255, int(v + k))) for v in c)


def draw_cell(d, x, y, w, h, reversed_, rng):
    """각형 셀 하나. reversed_ 이면 극성 배치가 뒤집힌다."""
    body = jitter((176, 180, 186), 14)
    edge = jitter((120, 126, 133), 12)
    d.rounded_rectangle([x, y, x + w, y + h], radius=max(2, int(w * 0.06)),
                        fill=body, outline=edge, width=max(1, int(w * 0.03)))

    # 케이스 상면 하이라이트
    d.rounded_rectangle([x + w * .08, y + h * .06, x + w * .92, y + h * .30],
                        radius=max(1, int(w * .04)), fill=jitter((198, 202, 208), 10))

    pos_c = jitter((228, 230, 234), 10)   # 양극: 밝은 알루미늄
    neg_c = jitter((150, 106, 68), 12)    # 음극: 어두운 구리
    tw, th = w * 0.26, h * 0.16
    top_y = y + h * 0.36
    bot_y = y + h - h * 0.20 - th

    # 정상: 좌측 상단 양극 / 우측 하단 음극,  역극: 좌우 반전
    px = x + w * (0.14 if not reversed_ else 0.60)
    nx = x + w * (0.60 if not reversed_ else 0.14)
    d.rounded_rectangle([px, top_y, px + tw, top_y + th], radius=2,
                        fill=pos_c, outline=jitter((160, 164, 170), 10))
    d.rounded_rectangle([nx, top_y, nx + tw, top_y + th], radius=2,
                        fill=neg_c, outline=jitter((110, 78, 50), 10))
    # 단자 극성 각인 (+ / -)
    cy = top_y + th / 2
    d.line([px + tw / 2 - tw * .18, cy, px + tw / 2 + tw * .18, cy], fill=(90, 94, 100), width=1)
    d.line([px + tw / 2, cy - th * .22, px + tw / 2, cy + th * .22], fill=(90, 94, 100), width=1)
    d.line([nx + tw / 2 - tw * .18, cy, nx + tw / 2 + tw * .18, cy], fill=(60, 42, 28), width=1)

    # 라벨 스티커 — 방향 단서 (정상은 아래쪽, 역극은 위쪽에 붙는 셈)
    ly = bot_y if not reversed_ else y + h * 0.16
    d.rectangle([x + w * .16, ly, x + w * .84, ly + h * .16], fill=jitter((238, 238, 232), 8))
    for i in range(rng.randint(4, 7)):     # 바코드 느낌
        bx = x + w * .20 + i * (w * .60 / 7)
        d.line([bx, ly + h * .03, bx, ly + h * .13], fill=(70, 70, 74), width=1)


def make_image(rng, W=640, H=640):
    bg = jitter((58, 62, 70), 10)
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)

    # 트레이 판
    m = rng.randint(18, 42)
    d.rounded_rectangle([m, m, W - m, H - m], radius=10,
                        fill=jitter((78, 84, 94), 10), outline=jitter((46, 50, 58), 8), width=3)

    cols = rng.choice([3, 4, 5])
    rows = rng.choice([3, 4, 5])
    pad = rng.randint(8, 16)
    gw = (W - 2 * m - pad * (cols + 1)) / cols
    gh = (H - 2 * m - pad * (rows + 1)) / rows
    cw, ch = gw * rng.uniform(.82, .96), gh * rng.uniform(.82, .96)

    # 이 트레이에 섞을 역극 셀 수.
    #
    # 실제 라인의 역극 발생률은 1%도 되지 않는다. 그 비율을 그대로 학습 데이터에 쓰면
    # 모델이 "전부 정상"이라고 답하는 쪽으로 편향된다(실제로 9.2%로 만들었더니
    # 검증 mAP는 높은데 운영 임계값에서 역극을 거의 잡지 못했다).
    # 학습 데이터의 비율은 현실 분포가 아니라 '무엇을 배우게 할 것인가'로 정해야 한다.
    total = cols * rows
    n_rev = 0
    r = rng.random()
    if r < 0.30:
        n_rev = rng.randint(1, max(1, total // 5))          # 소수 혼입
    elif r < 0.70:
        n_rev = rng.randint(max(1, total // 4), max(2, total // 2))   # 다수 혼입
    elif r < 0.85:
        n_rev = rng.randint(max(1, total // 2), total)       # 대량 (트레이 방향 전체 오류)
    rev_idx = set(rng.sample(range(total), n_rev)) if n_rev else set()

    labels = []
    for i in range(total):
        cx, cy = i % cols, i // cols
        x = m + pad + cx * (gw + pad) + (gw - cw) / 2 + rng.uniform(-2, 2)
        y = m + pad + cy * (gh + pad) + (gh - ch) / 2 + rng.uniform(-2, 2)
        rv = i in rev_idx
        draw_cell(d, x, y, cw, ch, rv, rng)
        labels.append((1 if rv else 0, x, y, cw, ch))

    # 조명 그라디언트
    grad = Image.new("L", (W, H))
    gd = ImageDraw.Draw(grad)
    ox, oy = rng.uniform(0, W), rng.uniform(0, H)
    for i in range(0, max(W, H), 8):
        gd.ellipse([ox - i, oy - i, ox + i, oy + i], outline=max(0, 170 - i // 5))
    grad = grad.filter(ImageFilter.GaussianBlur(40))
    light = Image.new("RGB", (W, H), (255, 255, 240))
    im = Image.composite(Image.blend(im, light, 0.11), im, grad)

    if rng.random() < 0.5:
        im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.9)))
    # 센서 노이즈
    if rng.random() < 0.7:
        px = im.load()
        for _ in range(int(W * H * 0.02)):
            xx, yy = rng.randrange(W), rng.randrange(H)
            v = rng.randint(-18, 18)
            p = px[xx, yy]
            px[xx, yy] = tuple(max(0, min(255, c + v)) for c in p)
    return im, labels


def build(split, n, seed, W=640, H=640):
    rng = random.Random(seed)
    idir = OUT / split / "images"
    ldir = OUT / split / "labels"
    idir.mkdir(parents=True, exist_ok=True)
    ldir.mkdir(parents=True, exist_ok=True)
    n_ok = n_rev = 0
    for i in range(n):
        im, labels = make_image(rng, W, H)
        stem = f"tray_{split}_{i:04d}"
        im.save(idir / f"{stem}.jpg", quality=88)
        lines = []
        for cls, x, y, w, h in labels:
            cx, cy = (x + w / 2) / W, (y + h / 2) / H
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {w/W:.6f} {h/H:.6f}")
            if cls:
                n_rev += 1
            else:
                n_ok += 1
        (ldir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
    return n_ok, n_rev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=420)
    ap.add_argument("--val", type=int, default=60)
    ap.add_argument("--test", type=int, default=110)
    a = ap.parse_args()
    tot_ok = tot_rev = 0
    for split, n, seed in [("train", a.train, 11), ("val", a.val, 22), ("test", a.test, 33)]:
        ok, rev = build(split, n, seed)
        tot_ok += ok
        tot_rev += rev
        print(f"  {split:<6} images={n:>4}  cell_ok={ok:>6}  cell_reversed={rev:>5}")
    # data.yaml
    y = OUT / "data.yaml"
    body = [f"path: {OUT.as_posix()}", "train: train/images", "val: val/images",
            "test: test/images", "", f"nc: {len(CLASSES)}", "names:"]
    body += [f"  {i}: {c}" for i, c in enumerate(CLASSES)]
    y.write_text("\n".join(body) + "\n", encoding="utf-8")
    print(f"\n합계 cell_ok={tot_ok} cell_reversed={tot_rev} "
          f"(역극 비율 {tot_rev/max(1,tot_ok+tot_rev)*100:.1f}%)")
    print("data.yaml:", y)


if __name__ == "__main__":
    main()
