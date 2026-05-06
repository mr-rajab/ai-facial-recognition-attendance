"""Week 4 Day 1: closed-set evaluation on folder-per-identity dataset; masked vs unmasked split."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

import cv2
import numpy as np

from augmentation import synthesize_lower_face_mask
from face_engine import FaceEngine, GalleryStore, cosine_topk


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _list_labeled_images(root: str) -> List[Tuple[str, str]]:
    """Returns (absolute_path, label_student_id) from root/<label>/*."""
    out: List[Tuple[str, str]] = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        sub = os.path.join(root, name)
        if not os.path.isdir(sub):
            continue
        label = name
        for fn in sorted(os.listdir(sub)):
            ext = os.path.splitext(fn.lower())[1]
            if ext not in IMAGE_EXTS:
                continue
            out.append((os.path.join(sub, fn), label))
    return out


@dataclass
class EvalSummary:
    condition: str
    total: int
    detected: int
    top1_correct: int
    accuracy_on_detected: float
    accuracy_overall: float


def _eval_condition(
    engine: FaceEngine,
    pairs: List[Tuple[str, str]],
    gmat: np.ndarray,
    gids: List[str],
    min_sim: float,
    transform,
) -> EvalSummary:
    detected = 0
    correct = 0
    for path, true_label in pairs:
        img = cv2.imread(path)
        if img is None:
            continue
        img = transform(img)
        face = engine.largest_face(img)
        if face is None or face.embedding is None:
            continue
        detected += 1
        top = cosine_topk(face.embedding, gmat, gids, k=1)
        pred, sim = top[0]
        if sim < min_sim:
            pred = "unknown"
        if pred == true_label:
            correct += 1
    total = len(pairs)
    acc_det = (correct / detected) if detected else 0.0
    acc_all = (correct / total) if total else 0.0
    return EvalSummary(
        condition=transform.__name__ if hasattr(transform, "__name__") else "custom",
        total=total,
        detected=detected,
        top1_correct=correct,
        accuracy_on_detected=acc_det,
        accuracy_overall=acc_all,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate top-1 recognition vs gallery.")
    parser.add_argument("--dataset", default="data/eval", help="Root with one subfolder per identity label.")
    parser.add_argument("--gallery-root", default="data/embeddings", help="Gallery path.")
    parser.add_argument("--min-sim", type=float, default=0.30, help="Similarity threshold for accepting match.")
    parser.add_argument("--out-json", default="data/reports/evaluation_metrics.json", help="Write metrics JSON.")
    args = parser.parse_args()

    store = GalleryStore(args.gallery_root)
    gmat, gids, _ = store.load_matrix()
    if gmat.shape[0] == 0:
        raise SystemExit("Gallery is empty. Run enroll.py first.")

    pairs = _list_labeled_images(args.dataset)
    if not pairs:
        raise SystemExit(
            f"No labeled images under {args.dataset}. Expected layout:\n"
            f"  {args.dataset}/<student_id>/img1.jpg\n"
            "Create folders matching enrolled student_id strings."
        )

    engine = FaceEngine()

    def id_transform(im: np.ndarray) -> np.ndarray:
        return im

    def mask_transform(im: np.ndarray) -> np.ndarray:
        return synthesize_lower_face_mask(im, cover_frac=0.42)

    s_clean = _eval_condition(engine, pairs, gmat, gids, args.min_sim, id_transform)
    s_clean.condition = "unmasked"
    s_mask = _eval_condition(engine, pairs, gmat, gids, args.min_sim, mask_transform)
    s_mask.condition = "synthetic_lower_mask"

    payload: Dict[str, object] = {
        "dataset": os.path.abspath(args.dataset),
        "gallery": os.path.abspath(args.gallery_root),
        "min_sim": args.min_sim,
        "unmasked": asdict(s_clean),
        "masked": asdict(s_mask),
    }

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(json.dumps(payload, indent=2))
    print(f"\nWrote {args.out_json}")


if __name__ == "__main__":
    main()
