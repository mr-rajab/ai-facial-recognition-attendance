import argparse
import os
from collections import Counter


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def list_images(data_dir: str):
    images = []
    for root, _, files in os.walk(data_dir):
        for name in files:
            _, ext = os.path.splitext(name.lower())
            if ext in IMAGE_EXTS:
                label = os.path.basename(root)
                images.append((os.path.join(root, name), label))
    return images


def main() -> None:
    parser = argparse.ArgumentParser(description="Load images and summarize labels.")
    parser.add_argument("--data-dir", default="data/raw", help="Input data directory.")
    args = parser.parse_args()

    images = list_images(args.data_dir)
    labels = [label for _, label in images if label]
    counts = Counter(labels)

    print(f"Total images: {len(images)}")
    for label, count in counts.most_common():
        print(f"{label}: {count}")


if __name__ == "__main__":
    main()
