# -*- coding: utf-8 -*-
"""제출 패키지(ZIP) 생성 — 공모전 파일명 규칙에 맞춰 압축"""
import sys, os, zipfile, argparse, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

# (원본경로, ZIP 내부경로) — 없으면 건너뜀
ITEMS = [
    # 한글 2010 으로 작성한 제출서류가 본본. docx 는 한글이 없는 심사자를 위한 동일 내용 사본.
    ("reports/HIMEC AI 활용 아이디어 공모전_출품작.hwp", "붙임1~4_제출서류.hwp"),
    ("reports/발표자료.pptx", "첨부/발표자료.pptx"),
    ("README.md", "첨부/README.md"),
    ("docs/제안서_붙임4.md", "첨부/제안서_전문.md"),
    ("docs/데이터셋_라이선스.md", "첨부/데이터셋_출처및라이선스.md"),
    ("reports/performance.md", "첨부/모델성능_리포트.md"),
    ("reports/performance.json", "첨부/모델성능_리포트.json"),
    ("reports/검측조서.html", "첨부/실행결과_검측조서.html"),
    ("reports/시정조치_이행확인서.html", "첨부/실행결과_시정조치이행확인서.html"),
    ("data/dataset_summary.json", "첨부/데이터셋_구성.json"),
    ("reports/demo_판독과정.gif", "첨부/시연영상_판독과정.gif"),
    ("../site/index.html", "첨부/주시연페이지/index.html"),
    ("../site/watch.html", "첨부/주시연페이지/watch.html"),
    ("../site/linesim.html", "첨부/주시연페이지/linesim.html"),
    ("../site/main.html", "첨부/주시연페이지/main.html"),
    ("../site/rules.html", "첨부/주시연페이지/rules.html"),
    ("../site/report.html", "첨부/주시연페이지/report.html"),
]
SRC_FILES = ["datasets_config.py", "collect.py", "collect_welding.py", "train.py",
             "train_schedule.sh", "rules.py", "inspect_engine.py", "report.py",
             "evaluate.py", "make_submission_docx.py", "make_package.py", "run_demo.sh",
             "followup.py", "build_artifact.py", "run_all.sh",
             "make_demo_data.py", "make_demo_video.py", "build_demo_page.py", "build_web.py"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, help="팀명 (파일명에 들어감)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-annotated", type=int, default=12, help="포함할 판독결과 이미지 수")
    a = ap.parse_args()

    name = f"HIMEC AI 활용 아이디어 공모전_{a.team}"
    out = Path(a.out) if a.out else ROOT / "reports" / f"{name}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, dst in ITEMS:
            p = ROOT / src
            if p.exists():
                z.write(p, f"{name}/{dst}")
                n += 1
            else:
                print(f"  [skip] {src} (없음)")
        for f in SRC_FILES:
            p = ROOT / "src" / f
            if p.exists():
                z.write(p, f"{name}/첨부/소스코드/src/{f}")
                n += 1
        # 주 시연 페이지의 자산 (해시 파일명 + 사진 23장)
        site = ROOT.parent / "site"
        for q in list(site.glob("data.*.js")) + list(site.glob("dc-runtime.*.js")):
            z.write(q, f"{name}/첨부/주시연페이지/{q.name}")
            n += 1
        for q in sorted((site / "assets").glob("*.jpg")):
            z.write(q, f"{name}/첨부/주시연페이지/assets/{q.name}")
            n += 1

        # 시연 화면 스크린샷 (붙임4 에도 실려 있고, 원본 해상도로 한 벌 더 넣는다)
        for q in sorted((ROOT / "reports" / "시연화면").glob("*.png")):
            z.write(q, f"{name}/첨부/시연화면/{q.name}")
            n += 1

        # 판독 결과 이미지
        ann = ROOT / "reports" / "out" / "annotated"
        if ann.exists():
            # 공개 데이터셋 원본 중 제3자 화면녹화 워터마크가 남은 파일은 제외한다
            SKIP = {"defect__cable_damage__cable_damage_125.jpg"}
            imgs = sorted([q for q in ann.glob("*.jpg")
                           if not q.name.startswith("_") and q.name not in SKIP])
            for q in imgs[: a.max_annotated]:
                z.write(q, f"{name}/첨부/판독결과이미지/{q.name}")
                n += 1
        # 학습 결과 그래프
        for run in ROOT.glob("runs/*/results.png"):
            z.write(run, f"{name}/첨부/학습결과/{run.parent.name}_results.png")
            n += 1
        for run in ROOT.glob("runs/*/confusion_matrix_normalized.png"):
            z.write(run, f"{name}/첨부/학습결과/{run.parent.name}_confusion.png")
            n += 1
        for run in ROOT.glob("runs/*/labels.jpg"):        # 클래스 분포·박스 통계
            if run.parent.name.startswith(("safety_", "defect_", "gauge_")):
                z.write(run, f"{name}/첨부/학습결과/{run.parent.name}_라벨분포.jpg")
                n += 1
        for run in ROOT.glob("runs/*/results.csv"):
            if run.parent.name.startswith(("safety_", "defect_", "gauge_")):
                z.write(run, f"{name}/첨부/학습결과/{run.parent.name}_학습로그.csv")
                n += 1

    print(f"\n패키지 생성 완료: {out}")
    print(f"  파일 {n}개 / {out.stat().st_size/1e6:.1f} MB")
    print("\n[남은 작업] 시연영상 유튜브 업로드 후 링크 반영:")
    print('  python src/add_youtube.py --url https://youtu.be/XXXX --team "%s"' % a.team)
    print("  제출: contest@himec.co.kr / 마감 2026-09-30")


if __name__ == "__main__":
    main()
