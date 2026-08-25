# -*- coding: utf-8 -*-
"""
시정조치 이행 확인 (Follow-up)

감리 실무에서 지적사항은 '발견'으로 끝나지 않는다. 시정요구 → 재시공 → 재촬영 → 확인의
루프가 닫혀야 검측이 완료된다. 이 모듈은 같은 위치를 찍은 이전/이후 사진의 판독 결과를
비교하여 지적사항이 해소되었는지 자동 판정한다.

  · 해소(closed)  : 이전에 있었고 이후에 없음      -> 시정 완료
  · 잔존(open)    : 이전에도 있고 이후에도 있음    -> 재시정 요구
  · 신규(new)     : 이전에 없었고 이후에 생김      -> 신규 지적

같은 위치 사진의 짝은 EXIF GPS·촬영일시로 자동 매칭하거나, 파일명 규칙으로 지정한다.
"""
import sys, os, json, argparse, math, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = Path(__file__).resolve().parents[1]


def _findings_map(result: Dict) -> Dict[str, Dict]:
    return {f["rule_id"]: f for f in result.get("findings", [])}


def compare(before: Dict, after: Dict) -> Dict:
    """이전/이후 판독 결과 비교 -> 시정 이행 판정"""
    b, a = _findings_map(before), _findings_map(after)
    closed, still_open, new = [], [], []
    for rid, f in b.items():
        if rid not in a:
            closed.append(dict(rule_id=rid, title=f["title"], risk=f["risk"],
                               before_count=f["count"]))
        else:
            still_open.append(dict(rule_id=rid, title=f["title"], risk=f["risk"],
                                   before_count=f["count"], after_count=a[rid]["count"],
                                   action=f["action"]))
    for rid, f in a.items():
        if rid not in b:
            new.append(dict(rule_id=rid, title=f["title"], risk=f["risk"],
                            after_count=f["count"], action=f["action"]))

    total_prev = len(b)
    rate = (len(closed) / total_prev * 100) if total_prev else None
    if still_open:
        verdict = "재시정 요구"
    elif new:
        verdict = "신규 지적 발생"
    elif total_prev:
        verdict = "시정 완료"
    else:
        verdict = "지적사항 없음"

    return dict(
        before_image=before.get("image"), after_image=after.get("image"),
        before_at=(before.get("exif") or {}).get("datetime") or before.get("inspected_at"),
        after_at=(after.get("exif") or {}).get("datetime") or after.get("inspected_at"),
        closed=closed, still_open=still_open, new=new,
        closure_rate=(round(rate, 1) if rate is not None else None),
        verdict=verdict,
    )


def _gps_dist_m(p: List[float], q: List[float]) -> float:
    """두 GPS 좌표 간 거리(m) — 하버사인"""
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, [p[0], p[1], q[0], q[1]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _parse_dt(s: Optional[str]) -> Optional[datetime.datetime]:
    if not s:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def auto_pair(results: List[Dict], radius_m: float = 15.0) -> List[Tuple[Dict, Dict]]:
    """EXIF GPS·촬영일시로 같은 위치의 이전/이후 사진 짝을 찾는다."""
    items = []
    for r in results:
        ex = r.get("exif") or {}
        gps, dt = ex.get("gps"), _parse_dt(ex.get("datetime"))
        if gps and dt:
            items.append((gps, dt, r))
    items.sort(key=lambda x: x[1])
    used, pairs = set(), []
    for i in range(len(items)):
        if i in used:
            continue
        gi, ti, ri = items[i]
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            gj, tj, rj = items[j]
            if _gps_dist_m(gi, gj) <= radius_m and tj > ti:
                pairs.append((ri, rj))
                used.add(i); used.add(j)
                break
    return pairs


def render_html(cmps: List[Dict], out_html: str) -> str:
    from report import CSS, _esc, RISK_BADGE
    P = ["<style>" + CSS + "</style>", "<div class=wrap>",
         "<h1>시정조치 이행 확인서</h1>",
         "<div class=sub>지적 → 시정요구 → 재촬영 → 확인 루프 자동 판정 · 생성 "
         + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + "</div>"]
    for i, c in enumerate(cmps, 1):
        vc = {"시정 완료": "#00af64", "재시정 요구": "#dc1428",
              "신규 지적 발생": "#f5a500", "지적사항 없음": "#0096dc"}[c["verdict"]]
        P.append("<div class=card>")
        P.append(f"<h3>No.{i}. {_esc(c['before_image'])} → {_esc(c['after_image'])} "
                 f"&nbsp;<span class=verdict style='background:{vc}'>{c['verdict']}</span></h3>")
        rate = f"{c['closure_rate']}%" if c["closure_rate"] is not None else "—"
        P.append(f"<div class=sub style='margin:0 0 10px'>이전 {_esc(c['before_at'])} · "
                 f"이후 {_esc(c['after_at'])} · 시정 완료율 <b>{rate}</b></div>")
        P.append("<div class=scroll><table>")
        P.append("<tr><th>구분</th><th>규정No</th><th>지적사항</th><th>위험도</th><th>비고</th></tr>")
        for k, label, extra in [("closed", "해소", lambda x: f"이전 {x['before_count']}건 → 0건"),
                                ("still_open", "잔존", lambda x: f"{x['before_count']}건 → {x['after_count']}건 · {x['action']}"),
                                ("new", "신규", lambda x: f"{x['after_count']}건 · {x['action']}")]:
            for f in c[k]:
                lbl, col = RISK_BADGE[f["risk"]]
                P.append(f"<tr><td><b>{label}</b></td><td>{_esc(f['rule_id'])}</td>"
                         f"<td>{_esc(f['title'])}</td>"
                         f"<td><span class=badge style='background:{col}'>{lbl}</span></td>"
                         f"<td class=basis>{_esc(extra(f))}</td></tr>")
        P.append("</table></div></div>")
    P.append("<div class=foot>본 확인서는 AI 자동 판독 기반 초안이며, 시정 완료 확정은 "
             "감리원(책임기술자) 확인 후 이루어집니다.</div></div>")
    Path(out_html).parent.mkdir(parents=True, exist_ok=True)
    Path(out_html).write_text("\n".join(P), encoding="utf-8")
    return out_html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "reports" / "out" / "results.json"))
    ap.add_argument("--before", help="이전 사진 파일명 (지정 시 --after 와 1:1 비교)")
    ap.add_argument("--after", help="이후 사진 파일명")
    ap.add_argument("--out", default=str(ROOT / "reports" / "시정조치_이행확인서.html"))
    a = ap.parse_args()

    results = json.load(open(a.results, encoding="utf-8"))
    by_name = {r["image"]: r for r in results}

    if a.before and a.after:
        if a.before not in by_name or a.after not in by_name:
            print("해당 파일의 판독 결과가 없습니다.")
            return
        pairs = [(by_name[a.before], by_name[a.after])]
    else:
        pairs = auto_pair(results)
        if not pairs:
            print("EXIF GPS·촬영일시로 짝지을 수 있는 사진이 없습니다.")
            print("  → --before/--after 로 직접 지정하거나, GPS가 기록된 현장 사진을 사용하세요.")
            return

    cmps = [compare(b, af) for b, af in pairs]
    out = render_html(cmps, a.out)
    for c in cmps:
        print(f"{c['before_image']} → {c['after_image']}: {c['verdict']} "
              f"(해소 {len(c['closed'])} / 잔존 {len(c['still_open'])} / 신규 {len(c['new'])})")
    print("saved:", out)


if __name__ == "__main__":
    main()
