"""Shared SQLite helpers for attendance (Week 1 + Week 3 pipeline)."""

import sqlite3
from datetime import datetime
from typing import Optional

import init_db as _idb

from init_db import initialize_db


def get_or_create_student(conn: sqlite3.Connection, student_id: str, name: str, email: str) -> int:
    row = conn.execute(
        "SELECT id FROM students WHERE student_id = ?;", (student_id,)
    ).fetchone()
    if row:
        return int(row[0])

    cur = conn.execute(
        "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?);",
        (student_id, name, email),
    )
    return int(cur.lastrowid)


def create_session(conn: sqlite3.Connection, course: str) -> int:
    start_time = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO sessions (course, start_time) VALUES (?, ?);",
        (course, start_time),
    )
    return int(cur.lastrowid)


def log_attendance(
    conn: sqlite3.Connection,
    session_id: int,
    student_db_id: int,
    status: str,
    confidence: float,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO attendance (session_id, student_id, timestamp, status, confidence)
        VALUES (?, ?, ?, ?, ?);
        """,
        (session_id, student_db_id, timestamp, status, confidence),
    )


def ensure_db(db_path: Optional[str] = None) -> None:
    p = _idb.DB_PATH if db_path is None else db_path
    initialize_db(p)


def close_session(conn: sqlite3.Connection, session_id: int) -> None:
    end_time = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "UPDATE sessions SET end_time = ? WHERE id = ?;",
        (end_time, session_id),
    )
