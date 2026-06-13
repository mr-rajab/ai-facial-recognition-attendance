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
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        raise ValueError(
            "The server could not save the enrollment photos due to a storage "
            "permission issue. Please try again, or contact an administrator."
        )
    out: Dict[str, str] = {}
    for pose in POSES:
        raw = images_b64.get(pose) or ""
        if not raw:
            raise ValueError(f"The {pose} photo is missing. Please capture all four angles and try again.")
        try:
            blob = _decode_data_url(raw)
        except Exception:
            raise ValueError(f"The {pose} photo was not valid. Please retake all four angles.")
        path = os.path.join(base, f"{pose}.jpg")
        try:
            with open(path, "wb") as f:
                f.write(blob)
        except OSError:
            raise ValueError(
                "The server could not save the enrollment photos. Please try again, "
                "or contact an administrator."
            )
        out[pose] = path
    return out


def _reject_if_duplicate_face(store: GalleryStore, emb: np.ndarray, exclude_student_id: str = "") -> None:
    """Raise ValueError if ``emb`` matches an already-enrolled student.

    Prevents one person from holding two accounts. The threshold is tunable via
    DUP_FACE_MIN_SIM (cosine similarity on ArcFace embeddings; same identity
    typically scores well above 0.5, different people well below)."""
    from face_engine import cosine_topk

    mat, ids, names = store.load_matrix()
    if mat.shape[0] == 0:
        return
    min_sim = float(os.environ.get("DUP_FACE_MIN_SIM", "0.5"))
    top = cosine_topk(emb, mat, ids, k=1)
    if not top:
        return
    sid, sim = top[0]
    if exclude_student_id and sid == exclude_student_id:
        return  # same student number re-enrolling — allowed
    if float(sim) >= min_sim:
        name = ""
        for i, s in enumerate(ids):
            if s == sid:
                name = names[i] if i < len(names) else ""
                break
        who = f"{name} ({sid})" if name and name.strip() else f"student {sid}"
        raise ValueError(
            f"This face is already enrolled to {who}. A student can only have one "
            f"account (face match {float(sim) * 100:.0f}%). If this is a mistake, "
            f"contact an administrator."
        )


def build_mean_embedding(engine: FaceEngine, paths: List[str]) -> np.ndarray:
    vecs: List[np.ndarray] = []
    for path in paths:
        import cv2

        img = cv2.imread(path)
        if img is None:
            raise ValueError("One of the photos could not be read. Please retake all four angles.")
        face = engine.largest_face(img)
        if face is None or face.embedding is None:
            raise ValueError(
                "No face was detected in one of the photos. Center your face in the "
                "frame with good lighting and retake all four angles."
            )
        if face.det_score < 0.35:
            raise ValueError(
                "One of the photos wasn't clear enough. Move closer with good lighting "
                "and retake all four angles."
            )
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

    # Refuse to create a second account for a face that is already enrolled.
    store = GalleryStore(os.path.join(root, gallery_root))
    _reject_if_duplicate_face(store, emb, exclude_student_id=student_number.strip())

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

    store.upsert(student_number.strip(), full_name.strip(), emb)

    return user_id
