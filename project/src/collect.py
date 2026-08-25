# -*- coding: utf-8 -*-
"""공개 데이터셋 -> 통합 YOLO 포맷 수집기 (HIMEC 현장사진 판독)"""
import sys, io, os, json, re, shutil, warnings, argparse
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from huggingface_hub import hf_hub_download, list_repo_files
import pyarrow.parquet as pq
from datasets_config import TASKS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"
SPLIT_MAP = {"train": "train", "validation": "val", "test": "test"}


def slug(repo: str) -> str:
    return repo.split("/")[-1].replace("-", "_")


def ensure_dirs(task: str):
    for sp in ["train", "val", "test"]:
        (OUT / task / sp / "images").mkdir(parents=True, exist_ok=True)
        (OUT / task / sp / "labels").mkdir(parents=True, exist_ok=True)


def convert_parquet(repo: str, mapping: dict, task: str, classes: list, stats: dict,
                    max_train: int = 0):
    """RF100 parquet(COCO bbox) -> YOLO txt"""
    name2id = {c: i for i, c in enumerate(classes)}
    files = [f for f in list_repo_files(repo, repo_type="dataset") if f.endswith(".parquet")]
    sg = slug(repo)
    for f in files:
        m = re.search(r"data/(train|validation|test)-", f)
        if not m:
            continue
        split = SPLIT_MAP[m.group(1)]
        p = hf_hub_download(repo, f, repo_type="dataset")
        tbl = pq.read_table(p)
        n_img = n_box = 0
        for row in tbl.to_pylist():
            if max_train and split == "train" and n_img >= max_train:
                break
            W, H = row["width"], row["height"]
            objs = row["objects"]
            lines = []
            for bbox, cat in zip(objs["bbox"], objs["category"]):
                tgt = mapping.get(int(cat))
                if tgt is None:
                    continue
                x, y, w, h = [float(v) for v in bbox]
                if w <= 1 or h <= 1:
                    continue
                cx, cy = (x + w / 2) / W, (y + h / 2) / H
                nw, nh = w / W, h / H
                if not (0 < cx < 1 and 0 < cy < 1):
                    continue
                nw, nh = min(nw, 1.0), min(nh, 1.0)
                lines.append(f"{name2id[tgt]} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
                stats[tgt] = stats.get(tgt, 0) + 1
                n_box += 1
            if not lines:                      # 라벨 없는 이미지는 스킵(배경 과다 방지)
                continue
            stem = f"{sg}_{row['image_id']}"
            img_b = row["image"]["bytes"]
            (OUT / task / split / "images" / f"{stem}.jpg").write_bytes(img_b)
            (OUT / task / split / "labels" / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
            n_img += 1
        print(f"    [{split:>5}] {sg:<28} images={n_img:>5} boxes={n_box:>6}")
        del tbl


def convert_yolo_repo(repo: str, mapping: dict, task: str, classes: list, stats: dict):
    """이미 YOLO 포맷으로 배포되는 repo 처리.

    snapshot_download 는 원본 파일명이 길 경우 Windows 260자 경로 제한에 걸리므로
    resolve URL 로 개별 파일을 받아 짧은 해시 이름으로 저장한다.
    """
    import hashlib, urllib.request, urllib.parse
    name2id = {c: i for i, c in enumerate(classes)}
    sg = slug(repo)
    base = f"https://huggingface.co/datasets/{repo}/resolve/main/"
    split_map = {"train": "train", "valid": "val", "test": "test"}

    def fetch(rel):
        for _ in range(3):
            try:
                with urllib.request.urlopen(base + urllib.parse.quote(rel), timeout=60) as r:
                    return r.read()
            except Exception:
                pass
        return None

    files = list_repo_files(repo, repo_type="dataset")
    imgs = [f for f in files if "/images/" in f and f.lower().endswith((".jpg", ".jpeg", ".png"))]
    lbls = set(f for f in files if "/labels/" in f and f.endswith(".txt"))
    done = {v: 0 for v in split_map.values()}
    boxes = {v: 0 for v in split_map.values()}

    for ip in imgs:
        src_split = ip.split("/")[0]
        if src_split not in split_map:
            continue
        split = split_map[src_split]
        stem = ip.split("/")[-1].rsplit(".", 1)[0]
        lp = f"{src_split}/labels/{stem}.txt"
        if lp not in lbls:
            continue
        lb = fetch(lp)
        if lb is None:
            continue
        lines = []
        for ln in lb.decode("utf-8", "ignore").strip().splitlines():
            parts = ln.split()
            if len(parts) < 5:
                continue
            tgt = mapping.get(int(float(parts[0])))
            if tgt is None:
                continue
            lines.append(" ".join([str(name2id[tgt])] + parts[1:5]))
            stats[tgt] = stats.get(tgt, 0) + 1
            boxes[split] += 1
        if not lines:
            continue
        img = fetch(ip)
        if img is None:
            continue
        short = f"{sg[:6]}_{hashlib.md5(stem.encode()).hexdigest()[:12]}"
        (OUT / task / split / "images" / f"{short}.jpg").write_bytes(img)
        (OUT / task / split / "labels" / f"{short}.txt").write_text("\n".join(lines), encoding="utf-8")
        done[split] += 1

    for split in ["train", "val", "test"]:
        print(f"    [{split:>5}] {sg:<28} images={done[split]:>5} boxes={boxes[split]:>6}")


def convert_coco_zip(repo: str, mapping: dict, task: str, classes: list, stats: dict,
                     max_train: int = 0):
    """Roboflow가 zip(COCO json + 이미지)으로 배포하는 데이터셋 처리."""
    import zipfile
    name2id = {c: i for i, c in enumerate(classes)}
    sg = slug(repo)
    split_map = {"train": "train", "valid": "val", "test": "test"}
    for src_split, split in split_map.items():
        try:
            zp = hf_hub_download(repo, f"data/{src_split}.zip", repo_type="dataset")
        except Exception:
            continue
        z = zipfile.ZipFile(zp)
        names = z.namelist()
        jf = [n for n in names if n.endswith(".json")]
        if not jf:
            continue
        coco = json.loads(z.read(jf[0]))
        cats = {c["id"]: c["name"] for c in coco.get("categories", [])}
        imgs = {im["id"]: im for im in coco.get("images", [])}
        by_img = {}
        for a in coco.get("annotations", []):
            by_img.setdefault(a["image_id"], []).append(a)
        n_img = n_box = 0
        for iid, anns in by_img.items():
            if max_train and split == "train" and n_img >= max_train:
                break
            im = imgs.get(iid)
            if not im:
                continue
            W, H = im["width"], im["height"]
            lines = []
            for a in anns:
                tgt = mapping.get(cats.get(a["category_id"], ""))
                if tgt is None:
                    continue
                x, y, w, h = [float(v) for v in a["bbox"]]
                if w <= 1 or h <= 1:
                    continue
                cx, cy = (x + w / 2) / W, (y + h / 2) / H
                if not (0 < cx < 1 and 0 < cy < 1):
                    continue
                lines.append(f"{name2id[tgt]} {cx:.6f} {cy:.6f} "
                             f"{min(w/W,1.0):.6f} {min(h/H,1.0):.6f}")
                stats[tgt] = stats.get(tgt, 0) + 1
                n_box += 1
            if not lines:
                continue
            fn = im["file_name"]
            if fn not in names:
                cand = [n for n in names if n.endswith(fn)]
                if not cand:
                    continue
                fn = cand[0]
            stem = f"{sg[:8]}_{iid}"
            (OUT / task / split / "images" / f"{stem}.jpg").write_bytes(z.read(fn))
            (OUT / task / split / "labels" / f"{stem}.txt").write_text("\n".join(lines),
                                                                      encoding="utf-8")
            n_img += 1
        print(f"    [{split:>5}] {sg:<28} images={n_img:>5} boxes={n_box:>6}")


def write_yaml(task: str, classes: list):
    y = OUT / task / "data.yaml"
    body = [f"path: {(OUT/task).as_posix()}", "train: train/images", "val: val/images",
            "test: test/images", "", f"nc: {len(classes)}", "names:"]
    body += [f"  {i}: {c}" for i, c in enumerate(classes)]
    y.write_text("\n".join(body) + "\n", encoding="utf-8")
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=list(TASKS.keys()))
    a = ap.parse_args()
    for task in a.tasks:
        cfg = TASKS[task]
        print(f"\n=== TASK: {task} ({len(cfg['classes'])} classes) ===")
        ensure_dirs(task)
        stats = {}
        cap = cfg.get("max_train", 0)
        for repo, mp in cfg["parquet"].items():
            print(f"  -> {repo}")
            convert_parquet(repo, mp, task, cfg["classes"], stats, cap)
        for repo, mp in cfg.get("yolo", {}).items():
            print(f"  -> {repo}")
            convert_yolo_repo(repo, mp, task, cfg["classes"], stats)
        for repo, mp in cfg.get("coco", {}).items():
            print(f"  -> {repo}  (COCO zip)")
            convert_coco_zip(repo, mp, task, cfg["classes"], stats, cap)
        if cfg.get("synthetic"):
            print("  -> 합성 데이터: python src/make_polarity_data.py 로 별도 생성")
            continue
        y = write_yaml(task, cfg["classes"])
        print(f"  data.yaml: {y}")
        print("  class distribution:")
        for c in cfg["classes"]:
            print(f"    {c:<14} {stats.get(c,0):>7}")


if __name__ == "__main__":
    main()
