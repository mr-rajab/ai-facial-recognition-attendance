import argparse
import csv
import os
from datetime import datetime

import cv2


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline face detection (Haar).")
    parser.add_argument("--source", default="0", help="Camera index or video path.")
    parser.add_argument("--out-dir", default="data/processed/detections", help="Output directory.")
    parser.add_argument("--log", default="data/logs/detection_log.csv", help="Log file.")
    args = parser.parse_args()

    ensure_dir(args.out_dir)
    ensure_dir(os.path.dirname(args.log))

    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError("Failed to open video source.")

    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    face_cascade = cv2.CascadeClassifier(cascade_path)

    log_exists = os.path.exists(args.log)
    with open(args.log, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if not log_exists:
            writer.writerow(["timestamp", "faces_detected", "saved_frame"])

        print("Press 's' to save a detection frame, 'q' to quit.")
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)

            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.imshow("Face Detection", frame)
            key = cv2.waitKey(1) & 0xFF

            saved = ""
            if key == ord("s"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"detection_{timestamp}.jpg"
                filepath = os.path.join(args.out_dir, filename)
                cv2.imwrite(filepath, frame)
                saved = filename
                print(f"Saved {filepath}")
            elif key == ord("q"):
                break

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            writer.writerow([timestamp, len(faces), saved])

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
