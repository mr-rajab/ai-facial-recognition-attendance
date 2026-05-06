"""Verify an attendance selfie matches the enrolled template for that student account."""

from __future__ import annotations

import os
import threading
from typing import Optional, Tuple

import cv2
import numpy as np

_engine = None
_engine_lock = threading.Lock()


def _get_face_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            from face_engine import FaceEngine

            _engine = FaceEngine()
        return _engine


def verify_selfie_matches_enrolled_student(
    root: str,
    student_id: str,
    jpeg_bytes: bytes,
    *,
    min_sim: Optional[float] = None,
    min_det: Optional[float] = None,
) -> Tuple[bool, str, float]:
    """
    Compare the largest face in ``jpeg_bytes`` to **only** this student's gallery template.

    Returns ``(ok, reason, similarity)``. ``reason`` is ``ok`` or a short code such as
    ``face_mismatch``, ``no_face``, ``no_gallery_template``.
    """
    if min_sim is None:
        min_sim = float(os.environ.get("ATTEND_IDENTITY_MIN_SIM", "0.35"))
    if min_det is None:
        min_det = float(os.environ.get("ATTEND_IDENTITY_MIN_DET_SCORE", "0.25"))

    from face_engine import GalleryStore

    store = GalleryStore(os.path.join(root, "data", "embeddings"))
    entry = store.get_entry(str(student_id).strip())
    if entry is None:
        return False, "no_gallery_template", 0.0

    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return False, "bad_image", 0.0

    eng = _get_face_engine()
    face = eng.largest_face(bgr)
    if face is None or face.embedding is None:
        return False, "no_face", 0.0
    if float(face.det_score) < min_det:
        return False, "face_not_clear", 0.0

    probe = np.asarray(face.embedding, dtype=np.float32).reshape(-1)
    tpl = np.asarray(entry.embedding, dtype=np.float32).reshape(-1)
    sim = float(np.dot(probe, tpl))

    if sim < min_sim:
        return False, "face_mismatch", sim
    return True, "ok", sim
