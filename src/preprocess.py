import argparse
import os

import cv2


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def preprocess_image(image, size):
    image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess raw images.")
    parser.add_argument("--input-dir", default="data/raw", help="Input directory.")
    parser.add_argument("--output-dir", default="data/processed", help="Output directory.")
    parser.add_argument("--size", default="160,160", help="Output size W,H.")
    args = parser.parse_args()

    size_parts = args.size.split(",")
    size = (int(size_parts[0]), int(size_parts[1]))

    for root, _, files in os.walk(args.input_dir):
        rel_dir = os.path.relpath(root, args.input_dir)
        out_dir = os.path.join(args.output_dir, rel_dir)
        ensure_dir(out_dir)

        for name in files:
            _, ext = os.path.splitext(name.lower())
            if ext not in IMAGE_EXTS:
                continue

            in_path = os.path.join(root, name)
            out_path = os.path.join(out_dir, name)

            image = cv2.imread(in_path)
            if image is None:
                continue

            processed = preprocess_image(image, size)
            cv2.imwrite(out_path, processed)

    print("Preprocessing complete.")


if __name__ == "__main__":
    main()
