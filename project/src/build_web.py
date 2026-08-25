# -*- coding: utf-8 -*-
"""
배포용 정적 사이트 빌드 (Vercel)

아티팩트는 head를 자동으로 감싸주지만 일반 호스팅은 그렇지 않다.
완전한 HTML 문서(doctype/meta charset/viewport)로 감싸고,
페이지 간 이동을 위한 네비게이션을 삽입한다.
"""
import sys, os, re, json, shutil, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

NAV_CSS = """
<style id="sitenav-css">
.sitenav{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:2px;
  padding:0 18px;background:var(--surface,#fff);border-bottom:1px solid var(--line,#d3dce4);
  font-family:'IBM Plex Sans KR','Malgun Gothic',system-ui,sans-serif;overflow-x:auto}
.sitenav .brand{font-weight:700;font-size:13.5px;letter-spacing:-.02em;
  margin-right:16px;white-space:nowrap;color:var(--ink,#0f1720)}
.sitenav .brand span{color:var(--brand,#0b4f87)}
.sitenav .brand{letter-spacing:-.01em}
.sitenav a{display:inline-block;padding:11px 13px;font-size:13px;text-decoration:none;
  color:var(--ink-2,#41505f);border-bottom:2px solid transparent;white-space:nowrap}
.sitenav a:hover{color:var(--brand,#0b4f87)}
.sitenav a.on{color:var(--brand,#0b4f87);font-weight:600;border-bottom-color:var(--brand,#0b4f87)}
.sitenav .sp{flex:1}
.sitenav .meta{font-family:'IBM Plex Mono',monospace;font-size:10.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-3,#6d7d8d);white-space:nowrap;padding-right:4px}
@media (max-width:640px){.sitenav .meta{display:none}.sitenav{padding:0 10px}}
</style>
"""

SITES = {
    "himec": dict(
        brand=("HIMEC", "EYE"),
        meta="제1회 HIMEC AI 활용 아이디어 공모전 · 시공·품질관리",
        out="web",
        pages=[("index.html", "시연"), ("proposal.html", "제안서"), ("report.html", "검측조서")],
    ),
    "agents": dict(
        brand=("AI", "VISION"),
        meta="분야별 전용 AI 비전 검사",
        out="web-agents",
        pages=[("index.html", "멀티에이전트 시연")],
    ),
}
PAGES = []


def nav_html(current, site):
    a = []
    for href, label in site["pages"]:
        on = " class=\"on\"" if href == current else ""
        url = "/" if href == "index.html" else "/" + href[:-5]  # cleanUrls
        a.append(f'<a href="{url}"{on}>{label}</a>')
    b0, b1 = site["brand"]
    if len(site["pages"]) < 2:
        a = []
    return ('<nav class="sitenav"><span class="brand">' + b0 + ' <span>' + b1 + '</span></span>'
            + "".join(a)
            + '<span class="sp"></span>'
            + '<span class="meta">' + site["meta"] + '</span></nav>')


def wrap(body_html, title, desc, current, site):
    """조각 HTML -> 완전한 문서. 기존 title/link(폰트)는 head로 승격."""
    head_extra = []
    for m in re.finditer(r'<link[^>]+>', body_html):
        head_extra.append(m.group(0))
    body_html = re.sub(r'<link[^>]+>\s*', '', body_html)

    m = re.search(r'<title>(.*?)</title>', body_html, re.S)
    if m:
        title = m.group(1).strip() or title
        body_html = re.sub(r'<title>.*?</title>\s*', '', body_html, flags=re.S)

    # 폰트 링크가 없는 페이지(검측조서)에도 동일 서체를 적용
    if not any("fonts.googleapis" in h for h in head_extra):
        head_extra.append('<link rel="preconnect" href="https://fonts.googleapis.com">')
        head_extra.append('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
        head_extra.append('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
                          'family=IBM+Plex+Sans+KR:wght@300;400;500;600;700&'
                          'family=IBM+Plex+Mono:wght@400;500;600&display=swap">')

    return (
        "<!doctype html>\n<html lang=\"ko\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        f"<meta name=\"description\" content=\"{desc}\">\n"
        "<meta name=\"robots\" content=\"noindex\">\n"
        f"<title>{title}</title>\n"
        + "\n".join(head_extra) + "\n"
        + NAV_CSS +
        "</head>\n<body>\n"
        + nav_html(current, site) + "\n"
        + body_html +
        "\n</body>\n</html>\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="himec", choices=list(SITES.keys()))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    site = SITES[a.site]
    out = Path(a.out) if a.out else ROOT / site["out"]
    out.mkdir(parents=True, exist_ok=True)

    JOBS = {
        "himec": [
            (ROOT / "reports" / "demo_page.html", "index.html", "HIMEC EYE 시연",
             "현장사진 판독을 직접 조작해 보는 시연 — 임계값·검측유형·관계추론을 바꾸면 판정이 실시간으로 달라집니다."),
            (ROOT / "reports" / "artifact_final.html", "proposal.html", "HIMEC EYE 제안",
             "현장사진 1장으로 MEP 하자·안전을 판독하고 검측조서를 자동 생성하는 제안과 실증 결과."),
            (ROOT / "reports" / "검측조서.html", "report.html", "현장 검측조서",
             "AI 판독으로 자동 생성한 현장 검측조서 실행 결과."),
        ],
        "agents": [
            (ROOT / "reports" / "agents_page.html", "index.html", "AI 비전 검사 플랫폼",
             "분야별 전용 AI 에이전트가 각자 판독하고 결과를 하나로 합치는 멀티에이전트 비전 검사 시연."),
        ],
    }
    jobs = JOBS[a.site]
    total = 0
    for src, dst, title, desc in jobs:
        if not src.exists():
            print(f"  [skip] {src.name} 없음")
            continue
        html = wrap(src.read_text(encoding="utf-8"), title, desc, dst, site)
        (out / dst).write_text(html, encoding="utf-8")
        mb = (out / dst).stat().st_size / 1e6
        total += mb
        print(f"  {dst:<16} {mb:6.2f} MB   ({src.name})")

    # Vercel 설정 — 정적 사이트, UTF-8 명시
    vercel = {
        "cleanUrls": True,
        "headers": [{
            "source": "/(.*)",
            "headers": [
                {"key": "Content-Type", "value": "text/html; charset=utf-8"},
                {"key": "X-Content-Type-Options", "value": "nosniff"},
            ],
        }],
    }
    (out / "vercel.json").write_text(json.dumps(vercel, indent=2), encoding="utf-8")
    print(f"\n총 {total:.2f} MB -> {out}")
    print("배포:  vercel deploy --prod --yes   (web 디렉터리에서)")


if __name__ == "__main__":
    main()
