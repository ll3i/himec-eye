# -*- coding: utf-8 -*-
"""용접결함 데이터셋(rikkarth/welding-defect-object-detection) 수집.
snapshot_download 는 Windows 260자 경로 제한에 걸리므로 resolve URL로 직접 받는다."""
import sys, os, io, warnings, hashlib, urllib.request, json
warnings.filterwarnings("ignore"); sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
from huggingface_hub import list_repo_files
from datasets_config import TASKS

REPO = "rikkarth/welding-defect-object-detection"
MAP = TASKS["defect"]["yolo"][REPO]
CLASSES = TASKS["defect"]["classes"]
name2id = {c: i for i, c in enumerate(CLASSES)}
OUT = Path(__file__).resolve().parents[1] / "data" / "processed" / "defect"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main/"
SPLIT = {"train": "train", "valid": "val", "test": "test"}


def fetch(rel):
    for _ in range(3):
        try:
            with urllib.request.urlopen(BASE + urllib.parse.quote(rel), timeout=60) as r:
                return r.read()
        except Exception as e:
            err = e
    print("   fail", rel, err); return None


import urllib.parse
files = list_repo_files(REPO, repo_type="dataset")
imgs = [f for f in files if "/images/" in f and f.lower().endswith((".jpg", ".jpeg", ".png"))]
lbls = set(f for f in files if "/labels/" in f and f.endswith(".txt"))
print(f"repo files: {len(files)}, images: {len(imgs)}, labels: {len(lbls)}")

stats, done = {}, {"train": 0, "val": 0, "test": 0}
for i, ip in enumerate(imgs):
    src_split = ip.split("/")[0]
    if src_split not in SPLIT:
        continue
    split = SPLIT[src_split]
    stem = ip.split("/")[-1].rsplit(".", 1)[0]
    lp = f"{src_split}/labels/{stem}.txt"
    if lp not in lbls:
        continue
    lb = fetch(lp)
    if lb is None:
        continue
    lines = []
    for ln in lb.decode("utf-8", "ignore").strip().splitlines():
        p = ln.split()
        if len(p) < 5:
            continue
        tgt = MAP.get(int(float(p[0])))
        if tgt is None:
            continue
        lines.append(" ".join([str(name2id[tgt])] + p[1:5]))
        stats[tgt] = stats.get(tgt, 0) + 1
    if not lines:
        continue
    img = fetch(ip)
    if img is None:
        continue
    short = "weld_" + hashlib.md5(stem.encode()).hexdigest()[:12]
    (OUT / split / "images" / f"{short}.jpg").write_bytes(img)
    (OUT / split / "labels" / f"{short}.txt").write_text("\n".join(lines), encoding="utf-8")
    done[split] += 1
    if (i + 1) % 200 == 0:
        print(f"   {i+1}/{len(imgs)} -> {done}")

print("DONE", done)
print("class dist:", stats)
