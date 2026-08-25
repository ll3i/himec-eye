# -*- coding: utf-8 -*-
"""HIMEC 현장사진 판독 모델 학습 (CPU 최적화)"""
import sys, os, argparse, warnings, time, multiprocessing as mp
warnings.filterwarnings("ignore")
os.environ.setdefault("YOLO_VERBOSE", "true")
sys.stdout.reconfigure(encoding="utf-8")
import sys as _s, os as _o
_s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    from datasets_config import TASKS as _T
    ap.add_argument("--task", required=True, choices=list(_T.keys()))
    ap.add_argument("--model", default="yolo11n.pt")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=416)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--patience", type=int, default=15)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--name", default=None)
    ap.add_argument("--threads", type=int, default=0, help="0=자동(코어-2)")
    ap.add_argument("--cache", default="ram",
                    help="ram|disk|none — 병렬 학습 시 메모리 고갈을 피하려면 none")
    a = ap.parse_args()

    import torch
    nt = a.threads if a.threads > 0 else max(1, mp.cpu_count() - 2)
    torch.set_num_threads(nt)
    print(f"[cfg] torch threads={torch.get_num_threads()} cores={mp.cpu_count()}")

    from ultralytics import YOLO
    data = ROOT / "data" / "processed" / a.task / "data.yaml"
    if not data.exists():                      # 외부 데이터셋 (라벨 출처 비교 실험 등)
        alt = ROOT / "data" / a.task / "data.yaml"
        if alt.exists():
            data = alt
    name = a.name or f"{a.task}_{Path(a.model).stem}_{a.imgsz}"
    t0 = time.time()
    m = YOLO(a.model)
    m.train(
        data=str(data), epochs=a.epochs, imgsz=a.imgsz, batch=a.batch,
        device="cpu", workers=a.workers, project=str(ROOT / "runs"), name=name,
        exist_ok=True, patience=a.patience,
        cache=(False if a.cache == "none" else a.cache), seed=0,
        optimizer="AdamW", lr0=0.002, cos_lr=True, warmup_epochs=3,
        # 현장 사진 특성 반영: 조도/시점 변화 큼, 좌우반전 유효, 상하반전 무효
        hsv_h=0.015, hsv_s=0.7, hsv_v=0.5, degrees=8.0, translate=0.1,
        scale=0.5, fliplr=0.5, flipud=0.0, mosaic=1.0, close_mosaic=10,
        plots=True, val=True, verbose=True,
    )
    print(f"[done] {name} elapsed={(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
