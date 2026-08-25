# -*- coding: utf-8 -*-
"""시연 페이지 빌드 — 템플릿에 데모 데이터·룰·시연영상을 인라인하여 자체완결 HTML 생성"""
import sys, os, json, base64, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]


def b64file(p, mime):
    return "data:" + mime + ";base64," + base64.b64encode(Path(p).read_bytes()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default=str(ROOT / "reports" / "demo_template.html"))
    ap.add_argument("--demo", default=str(ROOT / "reports" / "demo_data.json"))
    ap.add_argument("--rules", default=str(ROOT / "reports" / "rules.json"))
    ap.add_argument("--gif", default=str(ROOT / "reports" / "demo_판독과정.gif"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "demo_page.html"))
    a = ap.parse_args()

    html = Path(a.template).read_text(encoding="utf-8")
    demo = Path(a.demo).read_text(encoding="utf-8")
    rules = Path(a.rules).read_text(encoding="utf-8")
    gif = b64file(a.gif, "image/gif") if os.path.exists(a.gif) else ""

    for k, v in [("__DEMO__", demo), ("__RULES__", rules), ("__GIF__", gif)]:
        if k not in html:
            print(f"  [warn] 플레이스홀더 {k} 없음")
        html = html.replace(k, v)

    Path(a.out).write_text(html, encoding="utf-8")
    mb = os.path.getsize(a.out) / 1e6
    print(f"built: {a.out}  ({mb:.2f} MB)")
    if mb > 15:
        print("  [warn] 16MB 제한에 근접합니다. 데모 사진 수나 GIF 크기를 줄이세요.")
    n = json.loads(demo)["items"]
    print(f"  시연 사진 {len(n)}장 · 시연영상 {os.path.getsize(a.gif)/1e6:.2f} MB")


if __name__ == "__main__":
    main()
