"""Week 2 Day 1: compare Haar vs InsightFace (RetinaFace) face counts on images or webcam frames."""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime

import cv2

from face_engine import FaceEngine, haar_face_boxes


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def list_images(root: str) -> list[str]:
    out: list[str] = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            if os.path.splitext(name.lower())[1] in IMAGE_EXTS:
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare Haar vs InsightFace detection counts.")
    parser.add_argument("--input-dir", default="data/raw", help="Directory of images.")
    parser.add_argument("--limit", type=int, default=0, help="Max images (0 = all).")
    parser.add_argument("--log", default="data/logs/detect_compare.csv", help="Output CSV log.")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    engine = FaceEngine()

    paths = list_images(args.input_dir)
    if args.limit > 0:
        paths = paths[: args.limit]

    log_exists = os.path.isfile(args.log)
    with open(args.log, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not log_exists:
            w.writerow(["timestamp", "path", "haar_count", "insightface_count"])

        ts = datetime.now().isoformat(timespec="seconds")
        for path in paths:
            img = cv2.imread(path)
            if img is None:
                continue
            h = len(haar_face_boxes(img))
            ins = len(engine.get_faces(img))
            w.writerow([ts, path, h, ins])
            print(f"{os.path.basename(path)}: Haar={h}, InsightFace={ins}")

    print(f"Wrote {args.log}")


if __name__ == "__main__":
    main()
