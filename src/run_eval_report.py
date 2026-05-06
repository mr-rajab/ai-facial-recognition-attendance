"""Week 4 Day 5: run evaluation and write a short Markdown + JSON report bundle."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluate_recognition.py and emit Markdown summary.")
    parser.add_argument("--dataset", default="data/eval")
    parser.add_argument("--gallery-root", default="data/embeddings")
    parser.add_argument("--min-sim", type=float, default=0.30)
    parser.add_argument("--out-dir", default="data/reports")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "evaluation_metrics.json")
    md_path = os.path.join(args.out_dir, "evaluation_report.md")

    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "evaluate_recognition.py"),
        "--dataset",
        args.dataset,
        "--gallery-root",
        args.gallery_root,
        "--min-sim",
        str(args.min_sim),
        "--out-json",
        json_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout + proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = [
        "# Automated evaluation report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Dataset",
        "",
        f"- Root: `{data.get('dataset')}`",
        f"- Gallery: `{data.get('gallery')}`",
        f"- min_sim: `{data.get('min_sim')}`",
        "",
        "## Metrics",
        "",
        "### Unmasked",
        "",
        "```json",
        json.dumps(data.get("unmasked", {}), indent=2),
        "```",
        "",
        "### Synthetic lower-face mask",
        "",
        "```json",
        json.dumps(data.get("masked", {}), indent=2),
        "```",
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
