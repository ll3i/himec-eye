#!/usr/bin/env bash
# 멀티에이전트 시연 사이트 빌드 & 배포 (HIMEC 사이트와 완전 분리된 별도 Vercel 프로젝트)
set -e
cd "$(dirname "$0")/.."
echo "[1/5] 시연 데이터 생성 (전 에이전트, 낮은 임계값 추론)"
python -u src/make_demo_data.py --conf 0.05
echo "[2/5] 룰 export"
python - <<'PY'
import sys; sys.path.insert(0,'src'); sys.argv=['x']
from make_demo_data import export_rules
print(' ', export_rules('reports/rules.json'))
PY
echo "[3/5] 성능 평가"
python -u src/evaluate.py --tasks safety product polarity logistics semiconductor parking || true
echo "[4/5] 페이지 빌드"
python -u src/build_agents_page.py
python -u src/build_web.py --site agents
echo "[5/5] 배포"
cd web-agents && vercel deploy --prod --yes 2>&1 | grep -E "Production|ready" | head -3
