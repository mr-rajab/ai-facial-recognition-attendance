"""Week 2 Day 2: export landmark-aligned face crops to data/processed/aligned/."""

from __future__ import annotations

import argparse
import os

import cv2

from face_engine import FaceEngine, aligned_crop


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Save aligned face crops (InsightFace landmarks).")
    parser.add_argument("--input-dir", default="data/raw", help="Root of images (mirrors subfolders).")
    parser.add_argument("--output-dir", default="data/processed/aligned", help="Output root.")
    parser.add_argument("--size", type=int, default=112, help="Square crop size (InsightFace default 112).")
    args = parser.parse_args()

    engine = FaceEngine()

    for dirpath, _, files in os.walk(args.input_dir):
        rel = os.path.relpath(dirpath, args.input_dir)
        out_dir = os.path.join(args.output_dir, rel if rel != "." else "")
        os.makedirs(out_dir, exist_ok=True)

        for name in files:
            ext = os.path.splitext(name.lower())[1]
            if ext not in IMAGE_EXTS:
                continue
            in_path = os.path.join(dirpath, name)
            img = cv2.imread(in_path)
            if img is None:
                continue
            faces = engine.get_faces(img)
            if not faces:
                continue
            largest = max(
                faces,
                key=lambda f: (f.bbox_xyxy[2] - f.bbox_xyxy[0]) * (f.bbox_xyxy[3] - f.bbox_xyxy[1]),
            )
            if largest.kps is None:
                continue
            crop = aligned_crop(img, largest.kps, size=args.size)
            stem = os.path.splitext(name)[0]
            out_path = os.path.join(out_dir, f"{stem}_aligned.jpg")
            cv2.imwrite(out_path, crop)
            print(f"Saved {out_path}")

    print("Alignment pass complete.")


if __name__ == "__main__":
    main()
