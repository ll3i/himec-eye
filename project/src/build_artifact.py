# -*- coding: utf-8 -*-
"""
artifact.html 의 실증 섹션(#perf-slot)에 모델 성능표와 실제 판독 결과 이미지를 채워
배포용 최종 HTML(artifact_final.html)을 만든다.
"""
import sys, os, io, json, base64, html, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
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
TASK_KO = {"safety": "SAFETY 안전", "defect": "DEFECT 하자", "gauge": "GAUGE 계기"}
RISK_CLS = {4: "rk4", 3: "rk3", 2: "rk2", 1: "rk1"}


def b64(path, max_side=760, q=78):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=q)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def esc(s):
    return html.escape(str(s if s is not None else ""))


def perf_html(perf_path):
    if not os.path.exists(perf_path):
        return ""
    reps = json.load(open(perf_path, encoding="utf-8"))
    if not reps:
        return ""
    P = ['<h3>모델 성능 &mdash; 자체 test split 평가</h3>',
         '<div class="scroll"><table>',
         '<thead><tr><th>모델</th><th class="num">mAP@50</th><th class="num">mAP@50-95</th>'
         '<th class="num">Precision</th><th class="num">Recall</th><th class="num">학습 epoch</th></tr></thead><tbody>']
    for r in reps:
        o = r["overall"]
        ep = r.get("epochs", "—")
        P.append(f'<tr><td>{esc(TASK_KO.get(r["task"], r["task"]))}</td>'
                 f'<td class="num"><b>{o["map50"]*100:.1f}%</b></td>'
                 f'<td class="num">{o["map5095"]*100:.1f}%</td>'
                 f'<td class="num">{o["precision"]*100:.1f}%</td>'
                 f'<td class="num">{o["recall"]*100:.1f}%</td>'
                 f'<td class="num">{ep}</td></tr>')
    P.append("</tbody></table></div>")

    # 클래스별 상위 성능
    P.append('<h3>지적사항 클래스별 탐지 성능</h3>')
    P.append('<div class="scroll"><table>')
    P.append('<thead><tr><th>모델</th><th>클래스</th><th class="num">mAP@50</th>'
             '<th class="num">Precision</th><th class="num">Recall</th></tr></thead><tbody>')
    for r in reps:
        for p in sorted(r["per_class"], key=lambda x: -x["map50"]):
            P.append(f'<tr><td class="mono">{esc(r["task"])}</td>'
                     f'<td>{esc(p["ko"])} <span class="basis mono">{esc(p["cls"])}</span></td>'
                     f'<td class="num"><b>{p["map50"]*100:.1f}%</b></td>'
                     f'<td class="num">{p["precision"]*100:.1f}%</td>'
                     f'<td class="num">{p["recall"]*100:.1f}%</td></tr>')
    P.append("</tbody></table></div>")
    P.append('<p class="note">CPU 환경(GPU 없음)에서 제한된 epoch만 학습한 프로토타입 수치입니다. '
             '수렴까지 학습하고 사내 데이터로 파인튜닝하면 크게 향상됩니다.</p>')
    return "\n".join(P)


def samples_html(results_path, max_n=4):
    if not os.path.exists(results_path):
        return ""
    res = json.load(open(results_path, encoding="utf-8"))
    # 지적사항이 검출된 것 우선
    res = sorted(res, key=lambda r: (-len(r["findings"]), -r.get("risk_max", 0)))
    res = [r for r in res if r["findings"]][:max_n]
    if not res:
        return ""
    P = ['<h3>실제 판독 결과</h3>',
         '<p>아래는 학습된 모델이 시험 사진을 판독하고 룰엔진이 지적사항으로 승격시킨 실제 출력입니다.</p>',
         '<div class="samples">']
    for r in res:
        img = r.get("annotated") or r.get("path")
        if not img or not os.path.exists(img):
            continue
        vcls = {"부적합": "rk4", "조건부적합": "rk2", "적합": "rkok"}[r["verdict"]]
        P.append('<figure class="sample">')
        P.append(f'<img src="{b64(img)}" alt="판독 결과">')
        P.append('<figcaption>')
        P.append(f'<span class="rk {vcls}">{esc(r["verdict"])}</span> ')
        for f in r["findings"][:4]:
            P.append(f'<span class="rk {RISK_CLS[f["risk"]]}">{esc(f["rule_id"])} '
                     f'{esc(f["title"].split("(")[0].strip())} &times;{f["count"]}</span> ')
        P.append('</figcaption></figure>')
    P.append("</div>")
    return "\n".join(P)


SAMPLE_CSS = """
<style>
.samples{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin:18px 0 6px}
.sample{margin:0;border:1px solid var(--line);background:var(--surface)}
.sample img{width:100%;display:block}
.sample figcaption{padding:11px 12px;margin:0;display:flex;flex-wrap:wrap;gap:5px;font-size:11.5px;line-height:1.9}
</style>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "reports" / "artifact.html"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "artifact_final.html"))
    ap.add_argument("--perf", default=str(ROOT / "reports" / "performance.json"))
    ap.add_argument("--results", default=str(ROOT / "reports" / "out" / "results.json"))
    a = ap.parse_args()

    src = Path(a.src).read_text(encoding="utf-8")
    block = perf_html(a.perf) + "\n" + samples_html(a.results)
    if block.strip():
        block = SAMPLE_CSS + block
    out = src.replace('<div id="perf-slot"></div>', block if block.strip()
                      else '<p class="note">모델 학습이 진행 중입니다.</p>')
    Path(a.out).write_text(out, encoding="utf-8")
    print("built:", a.out, f"{os.path.getsize(a.out)/1e6:.2f} MB")
    print("  perf table:", "yes" if "mAP@50" in out else "no")
    print("  samples   :", out.count('class="sample"'))


if __name__ == "__main__":
    main()
