# -*- coding: utf-8 -*-
"""시연 영상(MP4) 생성 — 유튜브 업로드용.

사이트의 「관제 화면」과 같은 데이터·같은 판정 로직으로 프레임을 직접 그린다.
브라우저 화면 녹화가 아니라 렌더링이므로 프레임 수가 일정하고 화질이 균일하다.

  python src/make_demo_movie.py --fps 24 --out reports/시연영상.mp4
"""
import sys, re, json, math, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent / "site"

W, H = 1280, 720
FONTS = Path(r"C:\Windows\Fonts")

# 사이트(Watch 아트보드)와 같은 값
THRESH = {"no_helmet": .25, "no_vest": .30, "no_goggles": .30, "no_gloves": .30, "smoke": .55,
          "corrosion": .35, "crack": .30, "cable_damage": .35, "weld_bad": .35, "weld_defect": .35,
          "wall_damage": .35, "dry_joint": .35, "incorrect_install": .30, "board_damage": .35,
          "short_circuit": .30, "surface_defect": .35, "cell_anomaly": .35, "cell_ok": .40,
          "cell_reversed": .25, "forklift": .35, "worker": .30, "chassis_working": .45,
          "car": .35, "bus": .35, "truck": .35}
KO = {"person": "작업자", "helmet": "안전모 착용", "vest": "안전조끼 착용", "no_vest": "안전조끼 미착용",
      "cone": "안전콘", "smoke": "연기", "crack": "균열", "cell_ok": "정렬 정상 셀",
      "cell_reversed": "역극 셀", "forklift": "지게차", "worker": "작업자",
      "chassis_loaded": "적재 섀시", "chassis_empty": "공차 섀시", "chassis_working": "상하차 진행"}
CLS2RULE = {"no_helmet": "S-01", "no_vest": "S-02", "smoke": "S-05", "crack": "D-02",
            "cell_reversed": "X-01", "chassis_working": "L-02"}
RULE = {"S-01": (3, "안전모 미착용", "산업안전보건기준규칙 제32조①1 · 작업중지 후 착용 조치"),
        "S-02": (2, "안전조끼 미착용", "동 규칙 제32조①10 · 착용 후 작업 재개"),
        "S-05": (4, "연기 감지 · 화재 의심", "화재예방법 제17조 · 즉시 작업중지 · 화기감시자 확인"),
        "D-02": (3, "균열 검출", "시설물 안전·유지관리 세부지침 · 크랙게이지 실측 후 보수"),
        "X-01": (4, "역극 셀 검출", "KS C IEC 62133 · 즉시 격리 · 트레이 전수 재검"),
        "L-01": (4, "지게차 협착 위험", "산업안전보건기준규칙 제172조 · 즉시 작업중지 · 유도자 배치"),
        "L-02": (1, "상하차 작업 진행 중", "동 규칙 제39조 · 작업구역 통제선 확인")}
HUE = {4: (255, 45, 63), 3: (255, 138, 0), 2: (245, 166, 35), 1: (49, 130, 246)}
TAG = {4: "긴급", 3: "부적합", 2: "조건부", 1: "참고"}
OKC = (21, 181, 123)
HOT = {"L-01": {"forklift", "worker"}, "S-01": {"person"}, "S-02": {"person"}}

SCENES = [("img24", "CAM 03", "실내 하역 구역", "오전 09:20", "09:20"),
          ("img52", "CAM 07", "옥외 작업구역", "오후 14:35", "14:35"),
          ("img34", "CAM 11", "2차전지 셀 선별 라인", "오후 16:10", "16:10"),
          ("img08", "CAM 02", "구조물 점검 구간", "오전 11:05", "11:05")]
DUR = 9.0
T_SCAN, T_BOX, T_ALERT, PER_BOX = 1.0, 2.4, 3.6, 0.16


def font(px, bold=False):
    f = FONTS / ("malgunbd.ttf" if bold else "malgun.ttf")
    return ImageFont.truetype(str(f), px)


def th(c):
    return THRESH.get(c, 0.25)


def overlap(inner, outer):
    x1, y1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    x2, y2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    a = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return 0.0 if a <= 0 else (x2 - x1) * (y2 - y1) / a


def finding_of(it):
    """사이트와 같은 규칙으로 대표 지적사항 하나를 고른다."""
    counts = {}
    for d in it["det"]:
        if d["p"] >= th(d["c"]):
            counts[d["c"]] = counts.get(d["c"], 0) + 1
    found = [(CLS2RULE[c], n, False) for c, n in counts.items() if c in CLS2RULE]
    if it["task"] == "logistics":
        forks = [d for d in it["det"] if d["c"] == "forklift" and d["p"] >= th("forklift")]
        wks = [d for d in it["det"] if d["c"] == "worker" and d["p"] >= th("worker")]
        n = 0
        for f in forks:
            w, hh = f["b"][2] - f["b"][0], f["b"][3] - f["b"][1]
            zone = [f["b"][0] - w * .35, f["b"][1] - hh * .175, f["b"][2] + w * .35, f["b"][3] + hh * .175]
            n += sum(1 for k in wks if overlap(k["b"], zone) >= .35)
        if n:
            found.append(("L-01", n, True))
    if not found:
        return None
    found.sort(key=lambda x: (-RULE[x[0]][0], -x[1]))
    return found[0]


def rounded(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def draw_frame(local, scene, it, img, kept, fnd):
    """한 프레임을 그린다. 좌표는 스테이지(사진 영역) 기준."""
    frame = Image.new("RGB", (W, H), (5, 7, 10))
    ar = it["w"] / it["h"]
    sw = min(W, int(H * ar))
    sh = int(sw / ar)
    ox, oy = (W - sw) // 2, (H - sh) // 2
    frame.paste(img.resize((sw, sh), Image.LANCZOS), (ox, oy))
    d = ImageDraw.Draw(frame, "RGBA")

    risk = RULE[fnd[0]][0] if fnd else 0
    col = HUE.get(risk, OKC)
    hot = HOT.get(fnd[0], set()) if (fnd and fnd[2]) else set()

    shown = 0 if local < T_BOX else min(len(kept), int((local - T_BOX) / PER_BOX) + 1)
    for b in kept[:shown]:
        bc = col if b["c"] in hot else (
            HUE[RULE[CLS2RULE[b["c"]]][0]] if b["c"] in CLS2RULE else OKC)
        x1, y1 = ox + b["b"][0] * sw, oy + b["b"][1] * sh
        x2, y2 = ox + b["b"][2] * sw, oy + b["b"][3] * sh
        d.rectangle([x1, y1, x2, y2], outline=bc, width=3)
        lab = f"{KO.get(b['c'], b['c'])} {round(b['p']*100)}%"
        fnt = font(15, True)
        tw = d.textlength(lab, font=fnt)
        ly = y1 - 22 if y1 - 22 > oy else y1 + 2
        d.rectangle([x1 - 1, ly, x1 + tw + 12, ly + 21], fill=bc)
        d.text((x1 + 5, ly + 2), lab, font=fnt, fill=(255, 255, 255))

    # 스캔 띠
    if T_SCAN <= local < T_BOX:
        prog = (local - T_SCAN) / (T_BOX - T_SCAN)
        band = int(sh * 0.14)
        top = int(oy + (sh + band) * prog) - band
        for i in range(band):
            y = top + i
            if oy <= y < oy + sh:
                d.line([(ox, y), (ox + sw, y)], fill=(49, 130, 246, int(200 * (i / band) ** 2)))

    # 경보
    if local >= T_ALERT and fnd:
        pulse = 0.6 + 0.4 * abs(math.sin(local * 4))
        d.rectangle([ox, oy, ox + sw - 1, oy + sh - 1], outline=col + (int(255 * pulse),), width=7)
        head = RULE[fnd[0]][1] + (" !!" if risk >= 4 else "")
        hf = font(60, True)
        hw = d.textlength(head, font=hf)
        cx, cy = ox + sw // 2, oy + sh // 2
        # 경광등
        r = 22
        d.ellipse([cx - r, cy - 96 - r, cx + r, cy - 96 + r], fill=col + (int(255 * pulse),))
        d.rectangle([cx - r - 6, cy - 82, cx + r + 6, cy - 72], fill=col)
        for dx, dy in ((-40, -18), (40, -18), (-46, 6), (46, 6)):
            d.line([cx + dx // 2, cy - 96 + dy // 2, cx + dx, cy - 96 + dy], fill=col, width=4)
        for off in ((-2, -2), (2, 2), (-2, 2), (2, -2)):
            d.text((cx - hw / 2 + off[0], cy - 46 + off[1]), head, font=hf, fill=(5, 7, 10))
        d.text((cx - hw / 2, cy - 46), head, font=hf, fill=col)
        sub = f"{TAG[risk]} · {RULE[fnd[0]][2]}"
        sf = font(19, True)
        sw2 = d.textlength(sub, font=sf)
        rounded(d, [cx - sw2 / 2 - 18, cy + 26, cx + sw2 / 2 + 18, cy + 68], 12, (5, 7, 10, 210))
        d.text((cx - sw2 / 2, cy + 36), sub, font=sf, fill=(255, 255, 255))

    # 화면 정보
    tf = font(24, True)
    tw = d.textlength(scene[3], font=tf)
    rounded(d, [ox + 18, oy + 16, ox + 18 + tw + 34, oy + 16 + 40], 20, (255, 255, 255))
    d.text((ox + 35, oy + 24), scene[3], font=tf, fill=(25, 31, 40))
    if int(local * 1.4) % 2 == 0:
        d.ellipse([ox + 40 + tw + 30, oy + 30, ox + 52 + tw + 30, oy + 42], fill=(255, 45, 63))
    d.text((ox + 68 + tw + 30, oy + 26), "REC", font=font(17, True), fill=(255, 45, 63))
    stamp = f"2026-08-25  {scene[4]}:{int(local)%60:02d}"
    mf = font(18)
    d.text((ox + sw - 18 - d.textlength(stamp, font=mf), oy + 26), stamp, font=mf, fill=(255, 255, 255))
    cf = font(17, True)
    cw = d.textlength(scene[1], font=cf)
    rounded(d, [ox + 18, oy + sh - 52, ox + 18 + cw + 22, oy + sh - 20], 7, (5, 7, 10, 200))
    d.text((ox + 29, oy + sh - 47), scene[1], font=cf, fill=(255, 255, 255))
    d.text((ox + 50 + cw, oy + sh - 47), scene[2], font=font(17), fill=(233, 237, 242))
    nf = font(15)
    note = "재현 영상 · 실제 판독 데이터"
    d.text((ox + sw - 18 - d.textlength(note, font=nf), oy + sh - 45), note, font=nf, fill=(176, 184, 193))
    return frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--out", default=str(ROOT / "reports" / "시연영상.mp4"))
    a = ap.parse_args()

    js = next(SITE.glob("data.*.js")).read_text(encoding="utf-8")
    DET = json.loads(re.search(r"window\.DET = (\{.*?\});\n", js, re.S).group(1))
    IMG = json.loads(re.search(r"window\.IMG = (\{.*?\});\n", js, re.S).group(1))

    vw = cv2.VideoWriter(a.out, cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (W, H))
    if not vw.isOpened():
        raise SystemExit("VideoWriter 열기 실패")

    total = 0
    for scene in SCENES:
        sid = scene[0]
        it = DET[sid]
        img = Image.open(SITE / IMG[sid]).convert("RGB")
        kept = sorted([x for x in it["det"] if x["p"] >= th(x["c"])], key=lambda x: -x["p"])[:12]
        fnd = finding_of(it)
        print(f"  {sid}  {scene[2]:16s} 채택 {len(kept):2d}  "
              f"경보 {RULE[fnd[0]][1] if fnd else '없음'}")
        for f in range(int(DUR * a.fps)):
            frame = draw_frame(f / a.fps, scene, it, img, kept, fnd)
            vw.write(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
            total += 1
    vw.release()
    mb = Path(a.out).stat().st_size / 1e6
    print(f"\n{a.out}\n  {total} 프레임 · {total/a.fps:.0f}초 · {W}x{H} · {mb:.1f} MB")


if __name__ == "__main__":
    main()
