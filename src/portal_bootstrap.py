"""Create first admin user from environment when ``users`` is empty."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

import init_db as _idb

from auth_passwords import hash_password


def ensure_bootstrap_admin() -> None:
    _idb.initialize_db(_idb.DB_PATH)
    conn = sqlite3.connect(_idb.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    n = int(conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0])
    if n > 0:
        conn.close()
        return
    email = (os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
    password = (os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or "").strip()
    if not email or not password:
        conn.close()
        return
    ts = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO users (email, password_hash, role, student_row_id, created_at)
        VALUES (?, ?, 'admin', NULL, ?);
        """,
        (email, hash_password(password), ts),
    )
    conn.commit()
    conn.close()
