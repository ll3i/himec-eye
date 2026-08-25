#!/usr/bin/env bash
# HIMEC EYE 전체 재현 스크립트
#   데이터 수집 → 학습 → 판독 → 검측조서 → 성능평가 → 제출물 생성
# 사용:  bash src/run_all.sh [팀명] [safety_ep] [defect_ep] [gauge_ep]
set -e
cd "$(dirname "$0")/.."
TEAM=${1:-팀명}
SEP=${2:-5}; DEP=${3:-8}; GEP=${4:-12}

echo "════ 1. 데이터 수집 ════"
python -u src/collect.py --tasks safety defect gauge

echo "════ 2. 모델 학습 (safety ${SEP}ep / defect ${DEP}ep / gauge ${GEP}ep) ════"
python -u src/train.py --task safety --epochs "$SEP" --imgsz 416 --batch 32 --workers 8
python -u src/train.py --task defect --epochs "$DEP" --imgsz 416 --batch 32 --workers 8
python -u src/train.py --task gauge  --epochs "$GEP" --imgsz 416 --batch 16 --workers 4

echo "════ 3. 현장사진 판독 ════"
python -u src/inspect_engine.py "data/demo/*.jpg" --out reports/out

echo "════ 4. 검측조서 생성 ════"
python -u src/report.py --results reports/out/results.json \
    --out "reports/검측조서.html" \
    --site "○○ 데이터센터 신축공사" --area "지하1층 기계실"

echo "════ 5. 성능 평가 ════"
python -u src/evaluate.py --tasks safety defect gauge

echo "════ 6. 제출물 생성 ════"
python -u src/make_submission_docx.py
python -u src/build_artifact.py
python -u src/make_package.py --team "$TEAM"

echo "════ 완료 ════"
ls -la reports/*.zip reports/*.docx reports/*.html 2>/dev/null
