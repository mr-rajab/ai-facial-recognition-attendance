"""Week 3 Day 5: export attendance rows joined with students/sessions to CSV."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from datetime import datetime

from init_db import DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Export attendance report to CSV.")
    parser.add_argument("--session-id", type=int, default=0, help="Filter by session id (0 = all).")
    parser.add_argument("--out", default="", help="Output CSV path (default under data/reports/).")
    args = parser.parse_args()

    out = args.out
    if not out:
        os.makedirs("data/reports", exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join("data/reports", f"attendance_{stamp}.csv")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if args.session_id > 0:
        rows = conn.execute(
            """
            SELECT s.student_id, s.name, a.timestamp, a.status, a.confidence,
                   sess.course AS course, sess.id AS session_id
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            JOIN sessions sess ON sess.id = a.session_id
            WHERE a.session_id = ?
            ORDER BY a.timestamp;
            """,
            (args.session_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT s.student_id, s.name, a.timestamp, a.status, a.confidence,
                   sess.course AS course, sess.id AS session_id
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            JOIN sessions sess ON sess.id = a.session_id
            ORDER BY a.timestamp;
            """
        ).fetchall()

    conn.close()

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["student_id", "name", "timestamp", "status", "confidence", "course", "session_id"])
        for r in rows:
            w.writerow(
                [
                    r["student_id"],
                    r["name"],
                    r["timestamp"],
                    r["status"],
                    r["confidence"],
                    r["course"],
                    r["session_id"],
                ]
            )

    print(f"Exported {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
