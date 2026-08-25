#!/usr/bin/env bash
# E2E 데모: 데모 사진 판독 -> 검측조서 생성
set -e
cd "$(dirname "$0")/.."
echo "[1/3] 현장사진 판독"
python -u src/inspect_engine.py "data/demo/*.jpg" --out reports/out --conf "${CONF:-0.25}"
echo "[2/3] 검측조서 생성"
python -u src/report.py --results reports/out/results.json \
    --out "reports/검측조서.html" \
    --site "${SITE:-○○ 데이터센터 신축공사}" --area "${AREA:-지하1층 기계실}"
echo "[3/3] 완료"
ls -la reports/검측조서.html reports/out/results.json
