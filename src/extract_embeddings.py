"""Batch-save embeddings for images under a label folder (Week 2 extension / debugging)."""

from __future__ import annotations

import argparse
import os

import cv2
import numpy as np

from face_engine import FaceEngine


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract embeddings to a single .npz file.")
    parser.add_argument("--input-dir", required=True, help="Folder of images.")
    parser.add_argument("--out", default="data/embeddings/batch.npz", help="Output .npz path.")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    engine = FaceEngine()
    paths: list[str] = []
    for name in sorted(os.listdir(args.input_dir)):
        ext = os.path.splitext(name.lower())[1]
        if ext not in IMAGE_EXTS:
            continue
        paths.append(os.path.join(args.input_dir, name))

    embs: list[np.ndarray] = []
    used: list[str] = []
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            continue
        f = engine.largest_face(img)
        if f is None or f.embedding is None:
            continue
        embs.append(f.embedding.astype(np.float32))
        used.append(os.path.basename(p))

    if not embs:
        raise SystemExit("No embeddings extracted.")

    np.savez(args.out, paths=np.array(used), embeddings=np.stack(embs, axis=0))
    print(f"Saved {len(used)} vectors to {args.out}")


if __name__ == "__main__":
    main()
