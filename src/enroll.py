"""Week 2 Day 5: enroll a student template (mean embedding) from images or video."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from typing import List, Tuple

import cv2
import numpy as np

from attendance_db import ensure_db, get_or_create_student
from face_engine import FaceEngine, GalleryStore
from init_db import DB_PATH


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def _list_images(folder: str) -> List[str]:
    out: List[str] = []
    for dirpath, _, files in os.walk(folder):
        for name in files:
            if os.path.splitext(name.lower())[1] in IMAGE_EXTS:
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def _embeddings_from_images(
    engine: FaceEngine,
    paths: List[str],
    min_det_score: float,
    verbose: bool,
) -> Tuple[List[np.ndarray], dict[str, int]]:
    vecs: List[np.ndarray] = []
    stats = {"read_fail": 0, "no_face": 0, "low_det": 0, "ok": 0}

    for path in paths:
        img = cv2.imread(path)
        if img is None:
            stats["read_fail"] += 1
            if verbose:
                print(f"[skip] unreadable: {path}", file=sys.stderr)
            continue
        face = engine.largest_face(img)
        if face is None or face.embedding is None:
            stats["no_face"] += 1
            if verbose:
                print(f"[skip] no face: {path}", file=sys.stderr)
            continue
        if face.det_score < min_det_score:
            stats["low_det"] += 1
            if verbose:
                print(
                    f"[skip] low det_score={face.det_score:.3f} (<{min_det_score}): {path}",
                    file=sys.stderr,
                )
            continue
        vecs.append(face.embedding.astype(np.float32))
        stats["ok"] += 1
        if verbose:
            print(f"[ok] det_score={face.det_score:.3f}: {path}", file=sys.stderr)

    return vecs, stats


def _embeddings_from_video(
    engine: FaceEngine,
    path: str,
    max_frames: int,
    stride: int,
    min_det_score: float,
) -> List[np.ndarray]:
    cap = cv2.VideoCapture(path)
    vecs: List[np.ndarray] = []
    idx = 0
    taken = 0
    while taken < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % stride != 0:
            idx += 1
            continue
        idx += 1
        face = engine.largest_face(frame)
        if face is None or face.embedding is None or face.det_score < min_det_score:
            continue
        vecs.append(face.embedding.astype(np.float32))
        taken += 1
    cap.release()
    return vecs


def main() -> None:
    parser = argparse.ArgumentParser(description="Enroll student face template into gallery (+ optional DB).")
    parser.add_argument("--student-id", required=True, help="External student id / number.")
    parser.add_argument("--name", required=True, help="Display name.")
    parser.add_argument("--email", default="", help="Email when syncing to SQLite.")
    parser.add_argument("--images-dir", default="", help="Folder of face images for this student.")
    parser.add_argument("--images", nargs="*", default=[], help="Explicit image paths.")
    parser.add_argument("--video", default="", help="Optional video path (sampled frames).")
    parser.add_argument("--max-video-frames", type=int, default=30, help="Max frames from video.")
    parser.add_argument("--video-stride", type=int, default=5, help="Read every Nth frame from video.")
    parser.add_argument("--min-det-score", type=float, default=0.35, help="Min detector score to keep a face.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-image skip reasons.")
    parser.add_argument("--gallery-root", default="data/embeddings", help="Gallery root.")
    parser.add_argument("--sync-db", action="store_true", help="Upsert row in students table.")
    args = parser.parse_args()

    paths: List[str] = []
    paths.extend(args.images)
    if args.images_dir:
        if not os.path.isdir(args.images_dir):
            print(
                f"Error: --images-dir is not an existing directory:\n  {os.path.abspath(args.images_dir)}\n"
                f"Create it and add .jpg/.png face photos, or point to a folder that already exists "
                f"(e.g. data/raw with your captured frames).",
                file=sys.stderr,
            )
            sys.exit(1)
        paths.extend(_list_images(args.images_dir))

    paths = sorted(set(paths))

    if not paths and not args.video:
        print(
            "Error: no images to process.\n"
            "  • Pass existing photos with: --images-dir path/to/folder\n"
            "  • Or explicit files: --images a.jpg b.jpg\n"
            "  • Or add --video clip.mp4\n"
            "Supported extensions: " + ", ".join(sorted(IMAGE_EXTS)),
            file=sys.stderr,
        )
        sys.exit(1)

    if paths:
        print(
            f"Found {len(paths)} image file(s). Loading face models (first run may download weights)...",
            flush=True,
        )
    elif args.video:
        print("Loading face models from video (first run may download weights)...", flush=True)

    engine = FaceEngine()
    vecs: List[np.ndarray] = []
    stats = {"read_fail": 0, "no_face": 0, "low_det": 0, "ok": 0}

    if paths:
        v, st = _embeddings_from_images(engine, paths, args.min_det_score, args.verbose)
        vecs.extend(v)
        stats.update(st)

    if args.video:
        if not os.path.isfile(args.video):
            print(f"Error: video not found: {args.video}", file=sys.stderr)
            sys.exit(1)
        vecs.extend(
            _embeddings_from_video(
                engine,
                args.video,
                max_frames=args.max_video_frames,
                stride=args.video_stride,
                min_det_score=args.min_det_score,
            )
        )

    if not vecs:
        print(
            "No usable face embeddings collected.\n"
            f"  Summary: ok={stats['ok']}, no_face={stats['no_face']}, "
            f"low_det={stats['low_det']}, unreadable={stats['read_fail']} (images scanned: {len(paths)})\n"
            "  Try: clearer frontal photos, better lighting, or lower threshold:\n"
            f"    --min-det-score 0.25\n"
            "  Re-run with -v to see each file.",
            file=sys.stderr,
        )
        sys.exit(1)

    mean = np.mean(np.stack(vecs, axis=0), axis=0).astype(np.float32)
    store = GalleryStore(args.gallery_root)
    store.upsert(args.student_id, args.name, mean)

    if args.sync_db:
        ensure_db(DB_PATH)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        get_or_create_student(conn, args.student_id, args.name, args.email)
        conn.commit()
        conn.close()

    print(f"Enrolled template for {args.student_id} ({args.name}) using {len(vecs)} face samples.")


if __name__ == "__main__":
    main()
