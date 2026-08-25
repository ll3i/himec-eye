# -*- coding: utf-8 -*-
"""
HIMEC 현장 검측조서 자동 생성기

판독 결과(JSON) -> 감리 실무에서 그대로 쓰는 '검측조서 / 시정요구서' HTML.
이미지를 base64로 인라인하여 파일 하나로 공유 가능하게 만든다.
"""
import sys, os, io, json, base64, datetime, html
from pathlib import Path
from typing import List, Dict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

RISK_BADGE = {
    4: ("긴급", "#dc1428"),
    3: ("높음", "#ff5a00"),
    2: ("보통", "#f5b400"),
    1: ("낮음", "#0096dc"),
}
VERDICT_COLOR = {"부적합": "#dc1428", "조건부적합": "#f5a500", "적합": "#00af64"}


def _b64(path: str, max_side: int = 900) -> str:
    from PIL import Image
    try:
        im = Image.open(path).convert("RGB")
        if max(im.size) > max_side:
            s = max_side / max(im.size)
            im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


CSS = """
:root{--bg:#ffffff;--fg:#14181f;--mut:#5b6472;--line:#e2e6ec;--card:#f7f9fb;--brand:#0b3d70;}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1319;--fg:#e8ecf2;--mut:#95a0b0;--line:#252c37;--card:#161c25;--brand:#5b9bd5;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:'Malgun Gothic','맑은 고딕',system-ui,sans-serif;line-height:1.6}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
h2{font-size:18px;margin:34px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--brand)}
h3{font-size:15px;margin:0 0 8px}
.sub{color:var(--mut);font-size:13px;margin-bottom:22px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0 18px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--card);font-weight:600;white-space:nowrap}
.kv th{width:150px}
.badge{display:inline-block;padding:2px 9px;border-radius:11px;color:#fff;font-size:11.5px;font-weight:700;white-space:nowrap}
.verdict{display:inline-block;padding:5px 16px;border-radius:5px;color:#fff;font-weight:700;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:12px 0 20px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:14px 16px}
.stat .n{font-size:26px;font-weight:700;letter-spacing:-.02em}
.stat .l{font-size:12px;color:var(--mut)}
.photo{border:1px solid var(--line);border-radius:9px;overflow:hidden;margin:10px 0 6px}
.photo img{width:100%;display:block}
.card{border:1px solid var(--line);border-radius:11px;padding:18px;margin:16px 0;background:var(--card)}
.basis{font-size:12px;color:var(--mut);line-height:1.5}
.act{font-size:12.5px}
.tag{display:inline-block;background:var(--brand);color:#fff;font-size:11px;padding:1px 7px;border-radius:4px;margin-right:6px}
.bar{height:9px;background:var(--line);border-radius:5px;overflow:hidden;min-width:80px}
.bar>div{height:100%;background:#00af64}
.foot{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);color:var(--mut);font-size:11.5px}
.scroll{overflow-x:auto}
"""


def render(results: List[Dict], site: Dict, out_html: str) -> str:
    n_img = len(results)
    all_f = [f for r in results for f in r["findings"]]
    n_ng = sum(1 for r in results if r["verdict"] == "부적합")
    n_cond = sum(1 for r in results if r["verdict"] == "조건부적합")
    urgent = [f for f in all_f if f["risk"] >= 3]

    P = []
    P.append("<!-- HIMEC 현장 검측조서 -->")
    P.append("<style>" + CSS + "</style>")
    P.append("<div class=wrap>")
    P.append("<h1>현장 검측조서 (AI 판독)</h1>")
    P.append("<div class=sub>사진 기반 하자·안전 자동 판독 결과 | 생성 "
             + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + "</div>")

    # 현장 정보
    P.append("<table class=kv>")
    for k, v in site.items():
        P.append("<tr><th>" + _esc(k) + "</th><td>" + _esc(v) + "</td></tr>")
    P.append("</table>")

    # 요약 통계
    P.append("<h2>1. 판독 요약</h2>")
    P.append("<div class=grid>")
    for n, l in [(n_img, "판독 사진"), (len(all_f), "지적사항 총계"),
                 (len(urgent), "긴급·높음 위험"), (n_ng, "부적합 판정"),
                 (n_cond, "조건부적합")]:
        P.append("<div class=stat><div class=n>" + str(n) + "</div><div class=l>" + l + "</div></div>")
    P.append("</div>")

    # 지적사항 집계
    agg = {}
    for f in all_f:
        k = (f["rule_id"], f["title"], f["risk"], f["category"])
        agg[k] = agg.get(k, 0) + f["count"]
    if agg:
        P.append("<div class=scroll><table>")
        P.append("<tr><th>규정No</th><th>분류</th><th>지적사항</th><th>위험도</th><th>검출건수</th></tr>")
        for (rid, title, risk, cat), c in sorted(agg.items(), key=lambda x: (-x[0][2], -x[1])):
            lbl, col = RISK_BADGE[risk]
            P.append("<tr><td><b>" + _esc(rid) + "</b></td><td>" + _esc(cat) + "</td><td>"
                     + _esc(title) + "</td><td><span class=badge style='background:" + col + "'>"
                     + lbl + "</span></td><td>" + str(c) + "</td></tr>")
        P.append("</table></div>")
    else:
        P.append("<p>검출된 지적사항이 없습니다.</p>")

    # PPE 준수율
    ppe_all = {}
    for r in results:
        for p in r["ppe_compliance"]:
            a, b = ppe_all.get(p["item"], (0, 0))
            ppe_all[p["item"]] = (a + p["worn"], b + p["not_worn"])
    if ppe_all:
        P.append("<h2>2. 개인보호구(PPE) 착용 준수율</h2>")
        P.append("<div class=scroll><table>")
        P.append("<tr><th>보호구</th><th>착용</th><th>미착용</th><th>준수율</th><th style='width:180px'></th></tr>")
        for item, (a, b) in ppe_all.items():
            rate = a / max(1, a + b) * 100
            P.append("<tr><td>" + _esc(item) + "</td><td>" + str(a) + "</td><td>" + str(b)
                     + "</td><td><b>" + f"{rate:.1f}" + "%</b></td>"
                     + "<td><div class=bar><div style='width:" + f"{rate:.0f}" + "%'></div></div></td></tr>")
        P.append("</table></div>")

    # 사진별 상세
    P.append("<h2>3. 사진별 판독 상세</h2>")
    for i, r in enumerate(results, 1):
        vc = VERDICT_COLOR[r["verdict"]]
        P.append("<div class=card>")
        P.append("<h3>No." + str(i) + ". " + _esc(r["image"])
                 + " &nbsp; <span class=verdict style='background:" + vc + "'>"
                 + r["verdict"] + "</span></h3>")
        ex = r.get("exif") or {}
        meta = []
        if ex.get("datetime"):
            meta.append("촬영 " + _esc(ex["datetime"]))
        if ex.get("gps"):
            meta.append("GPS " + _esc(ex["gps"]))
        if ex.get("camera"):
            meta.append(_esc(ex["camera"]))
        meta.append("판독 " + _esc(r["inspected_at"]))
        P.append("<div class=sub style='margin:0 0 10px'>" + " · ".join(meta) + "</div>")

        img = r.get("annotated") or r.get("path")
        b = _b64(img) if img and os.path.exists(img) else ""
        if b:
            P.append("<div class=photo><img src='" + b + "' alt='판독결과'></div>")

        if r["findings"]:
            P.append("<div class=scroll><table>")
            P.append("<tr><th>No</th><th>지적사항</th><th>위험도</th><th>건수</th>"
                     "<th>근거 법규·기준</th><th>요구 조치사항</th></tr>")
            for j, f in enumerate(r["findings"], 1):
                lbl, col = RISK_BADGE[f["risk"]]
                det = (" <br><span class=basis>" + _esc(f["detail"]) + "</span>") if f.get("detail") else ""
                P.append("<tr><td>" + str(j) + "</td>"
                         + "<td><span class=tag>" + _esc(f["rule_id"]) + "</span>"
                         + _esc(f["title"]) + det + "</td>"
                         + "<td><span class=badge style='background:" + col + "'>" + lbl + "</span></td>"
                         + "<td>" + str(f["count"]) + "</td>"
                         + "<td class=basis>" + _esc(f["basis"]) + "</td>"
                         + "<td class=act>" + _esc(f["action"]) + "</td></tr>")
            P.append("</table></div>")
        else:
            P.append("<p style='font-size:13px'>지적사항 없음 — 적합.</p>")
        P.append("</div>")

    P.append("<div class=foot>본 조서는 AI 자동 판독 결과 초안이며, 최종 판정은 감리원(책임기술자) 확인 후 확정됩니다. "
             "· 제1회 HIMEC AI 활용 아이디어 공모전 출품작 프로토타입</div>")
    P.append("</div>")

    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    Path(out_html).write_text("\n".join(P), encoding="utf-8")
    return out_html


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "reports" / "out" / "results.json"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "검측조서.html"))
    ap.add_argument("--site", default="○○ 데이터센터 신축공사")
    ap.add_argument("--area", default="지하1층 기계실")
    a = ap.parse_args()
    results = json.load(open(a.results, encoding="utf-8"))
    site = {
        "현장명": a.site,
        "검측구역": a.area,
        "검측구분": "기계설비 / 전기설비 / 안전관리",
        "판독방식": "현장사진 AI 자동판독 (YOLO 객체탐지 + 규정 룰엔진)",
        "작성": "HIMEC AX/IT (프로토타입)",
    }
    out = render(results, site, a.out)
    print("report:", out)


if __name__ == "__main__":
    main()
