import argparse
import csv
import os
from datetime import datetime

import cv2


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture frames from webcam.")
    parser.add_argument("--device", type=int, default=0, help="Camera device index.")
    parser.add_argument("--out-dir", default="data/raw", help="Output directory.")
    parser.add_argument("--width", type=int, default=0, help="Frame width.")
    parser.add_argument("--height", type=int, default=0, help="Frame height.")
    parser.add_argument("--log", default="data/logs/capture_log.csv", help="Log file.")
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    ensure_dir(os.path.dirname(args.log))

    cap = cv2.VideoCapture(args.device)
    if args.width > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    if args.height > 0:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    if not cap.isOpened():
        raise RuntimeError("Failed to open camera device.")

    log_exists = os.path.exists(args.log)
    with open(args.log, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not log_exists:
            writer.writerow(["timestamp", "filename"])

        print("Press 's' to save a frame, 'q' to quit.")
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            cv2.imshow("Capture Frames", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("s"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"frame_{timestamp}.jpg"
                filepath = os.path.join(args.out_dir, filename)
                cv2.imwrite(filepath, frame)
                writer.writerow([timestamp, filename])
                print(f"Saved {filepath}")
            elif key == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
