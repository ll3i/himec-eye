# -*- coding: utf-8 -*-
"""
시연 영상 생성 — 현장사진이 검측조서가 되는 과정

좌측에 사진, 우측에 검측조서 패널을 두고
  스캔 → 탐지 박스 등장 → 지적사항 판정 → 근거조항·조치사항 기재
순서로 애니메이션한다. 실제 판독 결과(results.json)를 그대로 사용한다.
"""
import sys, os, io, json, argparse, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"

W, H = 940, 500
PAD = 18
IMG_BOX = 464                      # 좌측 사진 영역 한 변
PANEL_X = PAD + IMG_BOX + PAD      # 우측 패널 시작 x

BG = (14, 18, 24)
PANEL = (23, 30, 39)
LINE = (44, 55, 68)
INK = (232, 238, 245)
MUT = (150, 165, 180)
BRAND = (92, 163, 221)
RISK = {4: (255, 107, 127), 3: (255, 145, 82), 2: (232, 184, 74), 1: (92, 184, 232)}
OK = (76, 199, 154)
VERD = {"부적합": (255, 107, 127), "조건부적합": (232, 184, 74), "적합": (76, 199, 154)}


def F(sz, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT, sz)
    except Exception:
        return ImageFont.load_default()


def fit(im, box):
    """정사각 box 안에 레터박스로 맞춤"""
    s = min(box / im.width, box / im.height)
    nw, nh = int(im.width * s), int(im.height * s)
    im2 = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (box, box), (8, 11, 15))
    canvas.paste(im2, ((box - nw) // 2, (box - nh) // 2))
    return canvas, s, (box - nw) // 2, (box - nh) // 2


def base_frame():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([PANEL_X - 8, PAD, W - PAD, H - PAD], fill=PANEL, outline=LINE)
    return im, d


def draw_header(d, title, sub):
    d.text((PANEL_X + 6, PAD + 10), title, font=F(15, True), fill=INK)
    d.text((PANEL_X + 6, PAD + 32), sub, font=F(11), fill=MUT)
    d.line([PANEL_X + 6, PAD + 52, W - PAD - 10, PAD + 52], fill=LINE, width=1)


def wrap(d, text, font, maxw):
    out, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=font) > maxw:
            out.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def render(img_path, result, phase, prog):
    """phase: scan | detect | judge | write / prog: 0~1"""
    im, d = base_frame()
    src = Image.open(img_path).convert("RGB")
    canvas, s, ox, oy = fit(src, IMG_BOX)
    findings = result["findings"]

    # ---- 탐지 박스
    cd = ImageDraw.Draw(canvas, "RGBA")
    if phase in ("detect", "judge", "write"):
        boxes = [(f, b) for f in findings for b in f["boxes"]]
        n = len(boxes) if phase != "detect" else max(1, int(len(boxes) * prog + 0.001))
        for f, b in boxes[:n]:
            x1 = b[0] * s + ox; y1 = b[1] * s + oy
            x2 = b[2] * s + ox; y2 = b[3] * s + oy
            c = RISK[f["risk"]]
            cd.rectangle([x1, y1, x2, y2], outline=c, width=3)
            if phase in ("judge", "write"):
                lab = f["rule_id"]
                fs = F(12, True)
                tw = cd.textlength(lab, font=fs)
                ty = max(0, y1 - 18)
                cd.rectangle([x1, ty, x1 + tw + 10, ty + 17], fill=c + (240,))
                cd.text((x1 + 5, ty + 2), lab, font=fs, fill=(15, 20, 26))

    # ---- 스캔 라인
    if phase == "scan":
        y = int(IMG_BOX * prog)
        cd.rectangle([0, max(0, y - 46), IMG_BOX, y], fill=BRAND + (46,))
        cd.line([0, y, IMG_BOX, y], fill=BRAND + (235,), width=3)

    im.paste(canvas, (PAD, PAD))
    d.rectangle([PAD, PAD, PAD + IMG_BOX, PAD + IMG_BOX], outline=LINE)

    # ---- 사진 캡션
    cap = result["image"]
    if len(cap) > 44:
        cap = cap[:41] + "..."
    d.text((PAD + 2, PAD + IMG_BOX + 7), cap, font=F(11), fill=MUT)

    # ---- 우측 패널
    phase_txt = {"scan": "현장사진 판독 중...", "detect": "객체 탐지",
                 "judge": "규정 대조 · 위험도 판정", "write": "검측조서 자동 작성"}[phase]
    draw_header(d, "HIMEC EYE  현장 검측조서", phase_txt)

    y = PAD + 64
    pw = W - PAD - 10 - (PANEL_X + 6)

    if phase == "scan":
        d.text((PANEL_X + 6, y), "안전 · 하자 · 계기 3축 동시 판독", font=F(12), fill=MUT)
        bw = int(pw * prog)
        d.rectangle([PANEL_X + 6, y + 26, PANEL_X + 6 + pw, y + 32], fill=LINE)
        d.rectangle([PANEL_X + 6, y + 26, PANEL_X + 6 + bw, y + 32], fill=BRAND)
        return im

    if phase == "detect":
        nb = sum(len(f["boxes"]) for f in findings)
        shown = max(1, int(nb * prog + 0.001))
        d.text((PANEL_X + 6, y), f"객체 검출  {shown} / {nb}", font=F(13, True), fill=INK)
        d.text((PANEL_X + 6, y + 22), "위치 · 종류 · 신뢰도", font=F(11), fill=MUT)
        return im

    # judge / write : 지적사항 카드
    vc = VERD[result["verdict"]]
    d.rectangle([PANEL_X + 6, y, PANEL_X + 6 + 86, y + 24], fill=vc)
    d.text((PANEL_X + 14, y + 4), result["verdict"], font=F(13, True), fill=(15, 20, 26))
    d.text((PANEL_X + 102, y + 5), f"지적사항 {len(findings)}건", font=F(12), fill=MUT)
    y += 38

    show_detail = (phase == "write")
    for i, f in enumerate(findings[:3]):
        c = RISK[f["risk"]]
        d.rectangle([PANEL_X + 6, y, PANEL_X + 9, y + (76 if show_detail else 34)], fill=c)
        d.text((PANEL_X + 16, y), f["rule_id"], font=F(12, True), fill=c)
        d.text((PANEL_X + 52, y), f["risk_label"], font=F(10), fill=MUT)
        for k, ln in enumerate(wrap(d, f["title"], F(12), pw - 20)[:1]):
            d.text((PANEL_X + 16, y + 16), ln, font=F(12), fill=INK)
        y += 34
        if show_detail:
            # 타이핑 효과: 근거조항이 점진적으로 채워짐
            basis = "근거 " + f["basis"].split("-")[0].strip()
            act = "조치 " + f["action"]
            lines = wrap(d, basis, F(10), pw - 20)[:2] + wrap(d, act, F(10), pw - 20)[:2]
            total = sum(len(x) for x in lines)
            budget = int(total * min(1.0, max(0.0, prog * 3 - i)))
            used = 0
            for ln in lines:
                if used >= budget:
                    break
                take = min(len(ln), budget - used)
                d.text((PANEL_X + 16, y), ln[:take], font=F(10), fill=MUT)
                used += len(ln)
                y += 13
            y += 6
        y += 4
        if y > H - PAD - 40:
            break

    if phase == "write" and prog > 0.85:
        d.line([PANEL_X + 6, H - PAD - 30, W - PAD - 10, H - PAD - 30], fill=LINE)
        d.text((PANEL_X + 6, H - PAD - 24), "감리원 확인 후 확정", font=F(10), fill=MUT)
    return im


def pick_diverse(results, n):
    """지적 유형이 겹치지 않도록 골라 시연의 다양성을 확보한다."""
    pool = [r for r in results if r["findings"]]
    pool.sort(key=lambda r: (-r.get("risk_max", 0), -len(r["findings"])))
    seen, out = set(), []
    for r in pool:
        key = r["findings"][0]["rule_id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= n:
            break
    for r in pool:                      # 부족하면 채운다
        if len(out) >= n:
            break
        if r not in out:
            out.append(r)
    return out


def build(results, out_gif, n_photos=4, scale=1.0, fps=12, colors=72):
    frames, durs = [], []
    seq = pick_diverse(results, n_photos)
    for r in seq:
        p = r.get("annotated") or r.get("path")
        src = r.get("path")
        if not (src and os.path.exists(src)):
            continue
        for ph, steps, hold in [("scan", 8, 0), ("detect", 6, 0),
                                ("judge", 1, 4), ("write", 10, 6)]:
            for i in range(steps):
                fr = render(src, r, ph, (i + 1) / steps)
                frames.append(fr); durs.append(int(1000 / fps))
            for _ in range(hold):
                frames.append(frames[-1].copy()); durs.append(int(1000 / fps))
    if scale != 1.0:
        frames = [f.resize((int(W * scale), int(H * scale)), Image.LANCZOS) for f in frames]
    frames = [f.convert("P", palette=Image.ADAPTIVE, colors=colors) for f in frames]
    frames[0].save(out_gif, save_all=True, append_images=frames[1:],
                   duration=durs, loop=0, optimize=True, disposal=2)
    return out_gif, len(frames)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "reports" / "out" / "results.json"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "demo_판독과정.gif"))
    ap.add_argument("--photos", type=int, default=4)
    ap.add_argument("--scale", type=float, default=0.78)
    ap.add_argument("--colors", type=int, default=72)
    a = ap.parse_args()
    results = json.load(open(a.results, encoding="utf-8"))
    out, n = build(results, a.out, a.photos, a.scale, colors=a.colors)
    print(f"saved: {out}  ({os.path.getsize(out)/1e6:.2f} MB, {n} frames)")


if __name__ == "__main__":
    main()
