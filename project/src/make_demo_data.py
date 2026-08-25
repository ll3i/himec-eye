# -*- coding: utf-8 -*-
"""
시연 웹페이지용 데이터 생성

브라우저에서는 YOLO 추론을 돌릴 수 없으므로(모델·런타임을 페이지에 실을 수 없음),
낮은 임계값으로 미리 추론한 '원시 탐지 결과'를 페이지에 담는다.
룰엔진은 JS로 포팅하여, 임계값·라우팅·관계추론을 브라우저에서 실시간으로 바꿔볼 수 있게 한다.
즉 탐지는 고정이고, 그 위의 판정 로직은 진짜로 다시 돈다.
"""
import sys, os, io, json, glob, base64, argparse, warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("YOLO_VERBOSE", "false")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
from datasets_config import TASKS as _TC
TASKS = list(_TC.keys())


def thumb_b64(path, max_side=560, q=76):
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", type=float, default=0.05, help="원시 추론 임계값(낮게)")
    ap.add_argument("--max-side", type=int, default=560)
    ap.add_argument("--out", default=str(ROOT / "reports" / "demo_data.json"))
    a = ap.parse_args()

    from inspect_engine import InspectionEngine, _find_weights
    from ultralytics import YOLO
    from agents import AGENTS

    models, names = {}, {}
    for t in TASKS:
        w = _find_weights(t)
        if w:
            m = YOLO(str(w))
            models[t], names[t] = m, m.names
    print("모델:", list(models.keys()))

    paths = sorted(glob.glob(str(ROOT / "data" / "demo" / "*.jpg")))
    print(f"데모 사진 {len(paths)}장 · conf={a.conf} 로 전 모델 추론")

    items = []
    for i, p in enumerate(paths, 1):
        base = os.path.basename(p)
        parts = base.split("__")
        src_task = parts[0] if parts[0] in TASKS else "safety"
        expected = parts[1] if len(parts) > 2 else ""
        im = Image.open(p)
        W, H = im.size
        det = {}
        for t, m in models.items():
            r = m.predict(p, conf=a.conf, iou=0.5, imgsz=416, device="cpu", verbose=False)[0]
            dl = []
            for b in r.boxes:
                x1, y1, x2, y2 = [float(v) for v in b.xyxy[0].tolist()]
                dl.append(dict(c=names[t][int(b.cls)], p=round(float(b.conf), 3),
                               b=[round(x1 / W, 4), round(y1 / H, 4),
                                  round(x2 / W, 4), round(y2 / H, 4)]))
            det[t] = sorted(dl, key=lambda d: -d["p"])
        exif = InspectionEngine.read_exif(p)
        items.append(dict(id=f"img{i:02d}", name=base, task=src_task, expected=expected,
                          task_ko=AGENTS.get(src_task, {}).get("ko", src_task),
                          w=W, h=H, img=thumb_b64(p, a.max_side), det=det,
                          exif={k: v for k, v in exif.items() if v}))
        n = sum(len(v) for v in det.values())
        print(f"  [{i:>2}/{len(paths)}] {base[:48]:<50} raw={n}")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(dict(conf=a.conf, tasks=list(models.keys()),
                       trained={k: True for k in models.keys()}, items=items),
                  f, ensure_ascii=False, separators=(",", ":"))
    mb = os.path.getsize(a.out) / 1e6
    print(f"\nsaved: {a.out}  ({mb:.2f} MB, {len(items)}장)")


if __name__ == "__main__":
    main()


def export_rules(out):
    """룰엔진 정의를 JS에서 쓸 수 있도록 JSON으로 내보낸다."""
    from rules import RULES, CONF_POLICY, PPE_PAIRS, DERIVED_RULES
    from datasets_config import NONCONFORMITY, TASKS as DS_TASKS
    from agents import AGENTS
    data = dict(
        rules={t: {c: dict(rule_id=r["rule_id"], category=r["category"], title=r["title"],
                           risk=r["risk"], basis=r["basis"], action=r["action"])
                   for c, r in rs.items()} for t, rs in RULES.items()},
        conf={c: v[0] for c, v in CONF_POLICY.items()},
        conf_reason={c: v[1] for c, v in CONF_POLICY.items()},
        ppe_pairs=[list(x) for x in PPE_PAIRS],
        nonconformity=NONCONFORMITY,
        classes={t: v["classes"] for t, v in DS_TASKS.items()},
        derived=DERIVED_RULES,
        agents=AGENTS,
    )
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return out
