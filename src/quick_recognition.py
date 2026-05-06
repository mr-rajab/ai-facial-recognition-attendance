"""Match a single JPEG against the enrolled gallery (no login). Used for quick attendance."""

from __future__ import annotations

import os
import threading
from typing import Any, Dict

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


def quick_match_from_jpeg(root: str, jpeg_bytes: bytes) -> Dict[str, Any]:
    """Decode JPEG, detect face, cosine-match gallery. ``root`` is project root (parent of ``data/embeddings``)."""
    from anti_spoof import assess_presentation_attack

    min_sim = float(os.environ.get("QUICK_ATTEND_MIN_SIM", "0.35"))
    min_det = float(os.environ.get("QUICK_ATTEND_MIN_DET_SCORE", "0.25"))
    gallery_root = os.path.join(root, "data", "embeddings")

    from face_engine import GalleryStore, cosine_topk

    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"ok": False, "reason": "bad_image", "message": "Could not read the image."}

    presentation = assess_presentation_attack(bgr)

    store = GalleryStore(gallery_root)
    mat, ids, names = store.load_matrix()
    if mat.shape[0] == 0:
        return {
            "ok": False,
            "reason": "empty_gallery",
            "message": "No enrolled students yet. An admin must create student accounts first.",
            "presentation": presentation,
        }

    engine = _get_face_engine()
    face = engine.largest_face(bgr)
    if face is None or face.embedding is None:
        return {
            "ok": False,
            "reason": "no_face",
            "message": "No face detected. Try facing the camera with good lighting.",
            "presentation": presentation,
        }
    if float(face.det_score) < min_det:
        return {
            "ok": False,
            "reason": "low_det_score",
            "message": "Face not clear enough. Move closer and look at the camera.",
            "presentation": presentation,
        }

    top = cosine_topk(face.embedding, mat, ids, k=1)
    if not top:
        return {
            "ok": False,
            "reason": "no_match",
            "message": "No match found.",
            "presentation": presentation,
        }

    sid, sim = top[0]
    if float(sim) < min_sim:
        return {
            "ok": False,
            "reason": "below_threshold",
            "message": "Could not recognize with enough confidence.",
            "best_student_id": sid,
            "confidence": round(float(sim), 4),
            "presentation": presentation,
        }

    display_name = ""
    for i, s in enumerate(ids):
        if s == sid:
            display_name = names[i] if i < len(names) else ""
            break

    greeting = f"Hello, {display_name}" if display_name.strip() else f"Hello, student {sid}"

    out: Dict[str, Any] = {
        "ok": True,
        "student_id": sid,
        "name": display_name,
        "confidence": round(float(sim), 4),
        "greeting": greeting,
        "presentation": presentation,
    }
    if presentation.get("risk") in ("medium", "high"):
        out["spoof_warning"] = (
            "Heuristic check: this frame resembles a screen or print more than a typical live selfie. "
            "Admins see the same flags on official attendance uploads."
        )
    return out
