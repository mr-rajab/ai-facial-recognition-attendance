"""Week 4 Day 2: rebuild enrollment template using augmented copies of each image."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from typing import List

import cv2
import numpy as np

from attendance_db import ensure_db, get_or_create_student
from augmentation import default_train_variants
from face_engine import FaceEngine, GalleryStore
from init_db import DB_PATH

from enroll import _list_images


def _embeddings_from_image_variants(engine: FaceEngine, bgr: np.ndarray, min_det_score: float) -> List[np.ndarray]:
    vecs: List[np.ndarray] = []
    for variant in default_train_variants(bgr):
        face = engine.largest_face(variant)
        if face is None or face.embedding is None:
            continue
        if face.det_score < min_det_score:
            continue
        vecs.append(face.embedding.astype(np.float32))
    return vecs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enroll with data augmentation (flip, brightness, synthetic mask variants)."
    )
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--images-dir", required=True)
    parser.add_argument("--email", default="")
    parser.add_argument("--min-det-score", type=float, default=0.30)
    parser.add_argument("--gallery-root", default="data/embeddings")
    parser.add_argument("--sync-db", action="store_true")
    args = parser.parse_args()

    if not os.path.isdir(args.images_dir):
        print(f"Not a directory: {args.images_dir}", file=sys.stderr)
        sys.exit(1)

    paths = _list_images(args.images_dir)
    if not paths:
        print("No images found.", file=sys.stderr)
        sys.exit(1)

    engine = FaceEngine()
    all_vecs: List[np.ndarray] = []
    for path in paths:
        img = cv2.imread(path)
        if img is None:
            continue
        all_vecs.extend(_embeddings_from_image_variants(engine, img, args.min_det_score))

    if not all_vecs:
        raise SystemExit("No embeddings from augmented set. Add clearer photos or lower --min-det-score.")

    mean = np.mean(np.stack(all_vecs, axis=0), axis=0).astype(np.float32)
    store = GalleryStore(args.gallery_root)
    store.upsert(args.student_id, args.name, mean)

    if args.sync_db:
        ensure_db(DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        get_or_create_student(conn, args.student_id, args.name, args.email)
        conn.commit()
        conn.close()

    print(f"Augmented enroll OK for {args.student_id} using {len(all_vecs)} augmented face samples.")


if __name__ == "__main__":
    main()
