"""Append-only audit trail for security-relevant actions."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from typing import Optional, Tuple

import init_db as _idb

from attendance_db import ensure_db


def _hash_client(request) -> Tuple[str, str]:
    ip = (request.client.host if request.client else "") or ""
    ua = (request.headers.get("user-agent") or "")[:500]
    ip_h = hashlib.sha256(ip.encode("utf-8", errors="ignore")).hexdigest()[:24]
    ua_h = hashlib.sha256(ua.encode("utf-8", errors="ignore")).hexdigest()[:24]
    return ip_h, ua_h


def write_audit(
    request,
    event_type: str,
    *,
    actor_user_id: Optional[int] = None,
    detail: str = "",
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> None:
    """Insert one audit row. Pass ``conn`` to participate in caller transaction; otherwise commits."""
    own = conn is None
    if own:
        ensure_db()
        conn = sqlite3.connect(_idb.DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
    ts = datetime.now().isoformat(timespec="seconds")
    ip_h, ua_h = _hash_client(request)
    conn.execute(
        """
        INSERT INTO audit_events (created_at, event_type, actor_user_id, target_type, target_id, detail, ip_hash, ua_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            ts,
            event_type[:80],
            actor_user_id,
            target_type[:80] if target_type else None,
            (target_id[:120] if target_id else None),
            detail[:2000],
            ip_h,
            ua_h,
        ),
    )
    if own:
        conn.commit()
        conn.close()
