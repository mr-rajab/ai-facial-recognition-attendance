"""Create students with multi-angle enrollment images and gallery templates."""

from __future__ import annotations

import base64
import os
import re
import sqlite3
from datetime import datetime
from typing import Dict, List

import numpy as np

from auth_passwords import hash_password
from face_engine import FaceEngine, GalleryStore


POSES = ("upper", "left", "right", "lower")


def _safe_student_folder(student_number: str) -> str:
    s = re.sub(r"[^\w\-.]", "_", student_number.strip())[:80]
    if not s:
        raise ValueError("Invalid student number")
    return s


def _decode_data_url(data: str) -> bytes:
    data = (data or "").strip()
    if "," in data and data.startswith("data:"):
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def save_enrollment_images(root: str, student_number: str, images_b64: Dict[str, str]) -> Dict[str, str]:
    """Save JPEG bytes per pose under data/portal/enroll/<safe_id>/. Returns pose -> absolute path."""
    sid = _safe_student_folder(student_number)
    base = os.path.join(root, "data", "portal", "enroll", sid)
    os.makedirs(base, exist_ok=True)
    out: Dict[str, str] = {}
    for pose in POSES:
        raw = images_b64.get(pose) or ""
        if not raw:
            raise ValueError(f"Missing image for pose: {pose}")
        blob = _decode_data_url(raw)
        path = os.path.join(base, f"{pose}.jpg")
        with open(path, "wb") as f:
            f.write(blob)
        out[pose] = path
    return out


def build_mean_embedding(engine: FaceEngine, paths: List[str]) -> np.ndarray:
    vecs: List[np.ndarray] = []
    for path in paths:
        import cv2

        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"Could not read image: {path}")
        face = engine.largest_face(img)
        if face is None or face.embedding is None:
            raise ValueError(f"No face detected in {path}")
        if face.det_score < 0.35:
            raise ValueError(f"Face confidence too low in {path}")
        vecs.append(face.embedding.astype(np.float32))
    return np.mean(np.stack(vecs, axis=0), axis=0).astype(np.float32)


def create_student_account(
    conn: sqlite3.Connection,
    *,
    root: str,
    full_name: str,
    student_number: str,
    email: str,
    password: str,
    images_b64: Dict[str, str],
    gallery_root: str = "data/embeddings",
) -> int:
    """Insert students + users + enrollment_faces + gallery template. Returns users.id."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Invalid email")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    cur = conn.execute(
        "SELECT id FROM students WHERE student_id = ? OR LOWER(email) = LOWER(?);",
        (student_number.strip(), email),
    ).fetchone()
    if cur:
        raise ValueError("Student number or email already exists")

    paths = save_enrollment_images(root, student_number, images_b64)
    engine = FaceEngine()
    emb = build_mean_embedding(engine, [paths[p] for p in POSES])

    ts = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?);",
        (student_number.strip(), full_name.strip(), email),
    )
    student_row_id = int(cur.lastrowid)

    for pose in POSES:
        conn.execute(
            """
            INSERT INTO enrollment_faces (student_row_id, pose, image_path)
            VALUES (?, ?, ?);
            """,
            (student_row_id, pose, paths[pose]),
        )

    ph = hash_password(password)
    cur = conn.execute(
        """
        INSERT INTO users (email, password_hash, role, student_row_id, created_at)
        VALUES (?, ?, 'student', ?, ?);
        """,
        (email, ph, student_row_id, ts),
    )
    user_id = int(cur.lastrowid)

    store = GalleryStore(os.path.join(root, gallery_root))
    store.upsert(student_number.strip(), full_name.strip(), emb)

    return user_id
