# -*- coding: utf-8 -*-
"""멀티에이전트 시연 페이지 빌드 — 템플릿에 데모 데이터·룰 인라인"""
import sys, os, json, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = Path(__file__).resolve().parents[1]


def perf_block(perf_path):
    """성능표 — 에이전트별 성능을 한 표로."""
    if not os.path.exists(perf_path):
        return ""
    reps = json.load(open(perf_path, encoding="utf-8"))
    if not reps:
        return ""
    from agents import AGENTS
    P = ['<section><h2>Evidence</h2>',
         '<p class="h2t">에이전트별 실증 성능</p>',
         '<p>모두 <strong>GPU 없이 CPU에서</strong> 제한된 epoch만 학습한 프로토타입 수치입니다. '
         '분야별 데이터 양이 그대로 성능 차이로 나타납니다.</p>',
         '<div class="scroll"><table><thead><tr><th>에이전트</th><th>분야</th>'
         '<th class="num">학습 epoch</th><th class="num">mAP@50</th>'
         '<th class="num">Precision</th><th class="num">Recall</th></tr></thead><tbody>']
    for r in sorted(reps, key=lambda x: -x["overall"]["map50"]):
        t = r["task"]
        ko = AGENTS.get(t, {}).get("ko", t)
        o = r["overall"]
        P.append(f'<tr><td class="mono">{t}</td><td><strong>{ko}</strong></td>'
                 f'<td class="num">{r.get("epochs","—")}</td>'
                 f'<td class="num"><b>{o["map50"]*100:.1f}%</b></td>'
                 f'<td class="num">{o["precision"]*100:.1f}%</td>'
                 f'<td class="num">{o["recall"]*100:.1f}%</td></tr>')
    P.append('</tbody></table></div>')

    P.append('<h3>분야별 주요 판독 항목 성능</h3><div class="scroll"><table>'
             '<thead><tr><th>에이전트</th><th>판독 항목</th><th class="num">mAP@50</th>'
             '<th class="num">Precision</th><th class="num">Recall</th></tr></thead><tbody>')
    for r in reps:
        ko = AGENTS.get(r["task"], {}).get("ko", r["task"])
        for c in sorted(r["per_class"], key=lambda x: -x["map50"])[:4]:
            P.append(f'<tr><td>{ko}</td><td>{c["ko"]} <span class="mono" '
                     f'style="font-size:11px;color:var(--ink-3)">{c["cls"]}</span></td>'
                     f'<td class="num"><b>{c["map50"]*100:.1f}%</b></td>'
                     f'<td class="num">{c["precision"]*100:.1f}%</td>'
                     f'<td class="num">{c["recall"]*100:.1f}%</td></tr>')
    P.append('</tbody></table></div>')
    P.append('<p class="note">수렴까지 학습하고 현장 실제 이미지로 파인튜닝하면 크게 향상됩니다. '
             '역극 에이전트는 합성 데이터로 방법론을 실증한 것이며, 도입 시에는 양품 셀 이미지로 재학습합니다.</p>')
    P.append('</section>')
    return "\n".join(P)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default=str(ROOT / "reports" / "agents_template.html"))
    ap.add_argument("--demo", default=str(ROOT / "reports" / "demo_data.json"))
    ap.add_argument("--rules", default=str(ROOT / "reports" / "rules.json"))
    ap.add_argument("--perf", default=str(ROOT / "reports" / "performance.json"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "agents_page.html"))
    a = ap.parse_args()

    html = Path(a.template).read_text(encoding="utf-8")
    html = html.replace("__DEMO__", Path(a.demo).read_text(encoding="utf-8"))
    html = html.replace("__RULES__", Path(a.rules).read_text(encoding="utf-8"))
    html = html.replace('<div id="perf-slot"></div>', perf_block(a.perf))
    Path(a.out).write_text(html, encoding="utf-8")
    mb = os.path.getsize(a.out) / 1e6
    print(f"built: {a.out}  ({mb:.2f} MB)")
    n = json.loads(Path(a.demo).read_text(encoding="utf-8"))
    print(f"  시연 사진 {len(n['items'])}장 · 학습 에이전트 {len(n.get('trained',{}))}개")


if __name__ == "__main__":
    main()
