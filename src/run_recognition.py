"""Week 3 Day 1–3: detect → embed (InsightFace) → match → voting → tracking → optional DB attendance."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from collections import Counter
from datetime import datetime
from typing import List, Optional, Tuple

import cv2
import numpy as np

from attendance_db import create_session, ensure_db, get_or_create_student, log_attendance
from face_engine import FaceEngine, GalleryStore, cosine_topk
from init_db import DB_PATH
from tracking import IoUTracker, iou_xyxy


def _resolve_identity(
    votes: List[Tuple[str, float]],
    min_sim: float,
    min_agree: int,
) -> Optional[Tuple[str, float]]:
    recent = [(lab, s) for lab, s in votes if lab != "unknown" and s >= min_sim]
    if len(recent) < min_agree:
        return None
    counts = Counter([lab for lab, _ in recent])
    best_lab, cnt = counts.most_common(1)[0]
    if cnt < min_agree:
        return None
    sims = [s for lab, s in recent if lab == best_lab]
    return best_lab, float(np.mean(sims))


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end recognition with voting + IoU tracking.")
    parser.add_argument("--source", default="0", help="Camera index or video/image path.")
    parser.add_argument("--gallery-root", default="data/embeddings", help="Enrollment gallery.")
    parser.add_argument("--course", default="CS-Graduation-Project", help="Session course label.")
    parser.add_argument("--min-sim", type=float, default=0.35, help="Min cosine similarity to accept match.")
    parser.add_argument("--vote-window", type=int, default=10, help="Max recent votes kept per track.")
    parser.add_argument("--min-agree", type=int, default=5, help="Min agreeing frames to confirm identity.")
    parser.add_argument("--iou-threshold", type=float, default=0.3, help="Tracker IoU match threshold.")
    parser.add_argument("--no-db", action="store_true", help="Do not write SQLite attendance rows.")
    parser.add_argument("--log", default="data/logs/recognition_frames.csv", help="Per-frame CSV log.")
    parser.add_argument(
        "--snap-dir",
        default="data/raw/snapshots",
        help="Directory for frames saved when you press 's' in the preview window.",
    )
    args = parser.parse_args()

    store = GalleryStore(args.gallery_root)
    gmat, gids, gnames = store.load_matrix()
    if gmat.shape[0] == 0:
        raise SystemExit("Gallery empty. Run enroll.py first.")

    id_to_name = {sid: name for sid, name in zip(gids, gnames)}
    engine = FaceEngine()
    tracker = IoUTracker(iou_threshold=args.iou_threshold)

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Could not open source: {args.source}")

    ensure_db(DB_PATH)
    conn: Optional[sqlite3.Connection] = None
    session_id: Optional[int] = None
    marked: set[str] = set()

    if not args.no_db:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        session_id = create_session(conn, args.course)

    os.makedirs(os.path.dirname(args.log), exist_ok=True)
    log_exists = os.path.isfile(args.log)
    log_fp = open(args.log, "a", newline="", encoding="utf-8")
    log_writer = csv.writer(log_fp)
    if not log_exists:
        log_writer.writerow(
            ["timestamp", "track_id", "bbox", "best_label", "best_sim", "faces", "marked"]
        )

    print("Keys: s = save snapshot, q = quit. Logging recognition to", args.log)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            faces = engine.get_faces(frame)
            boxes = [f.bbox_xyxy.copy() for f in faces]
            tracks = tracker.update(boxes)

            ts = datetime.now().isoformat(timespec="seconds")

            order = sorted(range(len(faces)), key=lambda i: faces[i].det_score, reverse=True)
            used_tracks: set[int] = set()
            for bi in order:
                f = faces[bi]
                emb = f.embedding
                if emb is None:
                    continue
                top = cosine_topk(emb, gmat, gids, k=1)
                label, sim = top[0]
                if sim < args.min_sim:
                    label = "unknown"

                best_tid: Optional[int] = None
                best_iou = 0.0
                for tid, tr in tracks.items():
                    if tid in used_tracks:
                        continue
                    iou_val = iou_xyxy(tr.bbox_xyxy, f.bbox_xyxy)
                    if iou_val > best_iou:
                        best_iou = iou_val
                        best_tid = tid
                if best_tid is None or best_iou < 0.05:
                    continue
                used_tracks.add(best_tid)

                tr = tracks[best_tid]
                tr.add_vote(label, sim, max_votes=args.vote_window)

                resolved = _resolve_identity(tr.votes, args.min_sim, args.min_agree)
                marked_flag = ""
                if resolved and conn is not None and session_id is not None:
                    sid, conf = resolved
                    if sid not in marked:
                        name = id_to_name.get(sid, sid)
                        db_student_id = get_or_create_student(conn, sid, name, "")
                        log_attendance(conn, session_id, db_student_id, "present", conf)
                        conn.commit()
                        marked.add(sid)
                        marked_flag = sid

                log_writer.writerow(
                    [
                        ts,
                        best_tid,
                        " ".join(f"{v:.1f}" for v in f.bbox_xyxy.tolist()),
                        label,
                        f"{sim:.4f}",
                        len(faces),
                        marked_flag,
                    ]
                )

            for f in faces:
                x1, y1, x2, y2 = [int(v) for v in f.bbox_xyxy.tolist()]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)

            cv2.imshow("Recognition", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                os.makedirs(args.snap_dir, exist_ok=True)
                snap_name = datetime.now().strftime("snap_%Y%m%d_%H%M%S.jpg")
                snap_path = os.path.join(args.snap_dir, snap_name)
                cv2.imwrite(snap_path, frame)
                print(f"Saved snapshot {snap_path}")
            elif key == ord("q"):
                break
    finally:
        log_fp.close()
        cap.release()
        cv2.destroyAllWindows()
        if conn is not None:
            conn.close()

    print("Session complete.")


if __name__ == "__main__":
    main()
