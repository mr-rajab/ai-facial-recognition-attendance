"""Week 2 Day 4: match a probe image against the enrolled gallery (cosine top-k)."""

from __future__ import annotations

import argparse
import os

import cv2

from face_engine import FaceEngine, GalleryStore, cosine_topk


def main() -> None:
    parser = argparse.ArgumentParser(description="Top-k identity match for one image.")
    parser.add_argument("--probe", required=True, help="Path to probe image.")
    parser.add_argument("--gallery-root", default="data/embeddings", help="Gallery directory.")
    parser.add_argument("--k", type=int, default=5, help="Top-k matches.")
    args = parser.parse_args()

    store = GalleryStore(args.gallery_root)
    mat, ids, names = store.load_matrix()
    if mat.shape[0] == 0:
        raise SystemExit("Gallery is empty. Run enroll.py first.")

    img = cv2.imread(args.probe)
    if img is None:
        raise SystemExit(f"Could not read image: {args.probe}")

    engine = FaceEngine()
    face = engine.largest_face(img)
    if face is None or face.embedding is None:
        raise SystemExit("No face detected in probe image.")

    top = cosine_topk(face.embedding, mat, ids, k=min(args.k, len(ids)))
    name_by_id = {sid: nm for sid, nm in zip(ids, names)}
    print(f"Probe: {os.path.basename(args.probe)}")
    for rank, (sid, score) in enumerate(top, start=1):
        label_name = name_by_id.get(sid, "")
        print(f"  {rank}. {sid}  ({label_name})  cosine={score:.4f}")


if __name__ == "__main__":
    main()
