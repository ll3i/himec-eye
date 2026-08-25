#!/usr/bin/env bash
# 학습 스케줄러: safety를 지정 epoch까지 돌린 뒤 중단하고, defect -> gauge 를 순차 학습.
# CPU 학습 환경에서 3개 모델을 제한된 시간 안에 확보하기 위한 스크립트.
set -u
cd "$(dirname "$0")/.."
SAFETY_EPOCHS=${1:-5}     # safety 를 몇 epoch 까지 돌리고 끊을지
DEFECT_EPOCHS=${2:-8}
GAUGE_EPOCHS=${3:-12}
CSV=runs/safety_yolo11n_416/results.csv

echo "[sched] safety 를 ${SAFETY_EPOCHS} epoch 까지 대기"
while :; do
  n=$(wc -l < "$CSV" 2>/dev/null || echo 0)
  # results.csv 는 헤더 1줄 + epoch 당 1줄
  if [ "$n" -ge $((SAFETY_EPOCHS + 1)) ]; then break; fi
  sleep 30
done
echo "[sched] safety ${SAFETY_EPOCHS} epoch 도달 -> 학습 중단"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*--task safety*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }"
sleep 10

echo "[sched] defect 학습 시작 (${DEFECT_EPOCHS} epoch)"
python -u src/train.py --task defect --epochs "$DEFECT_EPOCHS" --imgsz 416 \
       --batch 32 --workers 8 --patience 4 > runs/train_defect.log 2>&1
echo "[sched] defect 완료 rc=$?"

echo "[sched] gauge 학습 시작 (${GAUGE_EPOCHS} epoch)"
python -u src/train.py --task gauge --epochs "$GAUGE_EPOCHS" --imgsz 416 \
       --batch 16 --workers 4 --patience 6 > runs/train_gauge.log 2>&1
echo "[sched] gauge 완료 rc=$?"

echo "[sched] ALL DONE"
ls -la runs/*/weights/best.pt 2>/dev/null
