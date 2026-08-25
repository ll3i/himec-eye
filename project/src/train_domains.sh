#!/usr/bin/env bash
# 삼구아이앤씨 도메인별 YOLO 모델 순차 학습
set -u
cd "$(dirname "$0")/.."
EP=${1:-6}
for t in polarity product semiconductor logistics parking; do
  echo "════ $t (${EP} epoch) ════"
  python -u src/train.py --task "$t" --epochs "$EP" --imgsz 416 \
      --batch 32 --workers 8 --patience 3 > "runs/train_${t}.log" 2>&1
  echo "  rc=$? $(tail -c 300 runs/train_${t}.log | tr '\r' '\n' | grep -oE 'all .*' | tail -1)"
done
echo "════ ALL DONE ════"
ls -la runs/*/weights/best.pt 2>/dev/null
