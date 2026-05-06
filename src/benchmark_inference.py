"""Week 3 Day 4: measure ms/frame and approximate FPS for InsightFace on a source."""

from __future__ import annotations

import argparse
import statistics
import time

import cv2

from face_engine import FaceEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark face detection+embedding throughput.")
    parser.add_argument("--source", default="0", help="Camera index or video path.")
    parser.add_argument("--warmup", type=int, default=10, help="Warmup frames (discarded).")
    parser.add_argument("--frames", type=int, default=120, help="Timed frames.")
    args = parser.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Could not open source: {args.source}")

    engine = FaceEngine()

    for _ in range(args.warmup):
        ret, frame = cap.read()
        if not ret:
            break
        engine.get_faces(frame)

    times_ms: list[float] = []
    n = 0
    while n < args.frames:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        t0 = time.perf_counter()
        engine.get_faces(frame)
        times_ms.append((time.perf_counter() - t0) * 1000.0)
        n += 1

    cap.release()

    if not times_ms:
        raise SystemExit("No frames processed.")

    avg = statistics.mean(times_ms)
    med = statistics.median(times_ms)
    fps = 1000.0 / avg if avg > 0 else 0.0
    print(f"Frames: {len(times_ms)}")
    print(f"Mean: {avg:.2f} ms/frame (~{fps:.1f} FPS)")
    print(f"Median: {med:.2f} ms/frame")


if __name__ == "__main__":
    main()
