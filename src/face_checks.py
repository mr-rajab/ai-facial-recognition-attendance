"""Trained passive liveness (anti-spoof) for attendance selfies, plus hooks for
mask / glasses classification.

Liveness uses the MIT-licensed hairymax/Face-AntiSpoofing print/replay model
(3-class: live / print / replay, 128x128) running on CPU via onnxruntime. This
is a real trained model — unlike the older heuristic cues — so a face shown from
a phone screen or a printed photo is detected rather than passed through.

Reference inference recipe (from the model's repo):
  * convert image to RGB, crop the face bbox enlarged by 1.5x (square, zero-padded)
  * letterbox-resize the crop to 128x128, CHW, /255
  * softmax over 3 logits; index 0 = live, 1 = print, 2 = replay
  * "real" iff argmax == 0 AND p(live) >= threshold
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

import cv2
import numpy as np

_log = logging.getLogger("uvicorn.error")

_LIVENESS_REL = os.path.join("data", "models", "AntiSpoofing_print-replay_1.5_128.onnx")
_MASK_REL = os.path.join("data", "models", "mask_classifier.onnx")
_GLASSES_REL = os.path.join("data", "models", "glasses_classifier.onnx")
_IMG_SIZE = 128
_LIVE_LABELS = {0: "live", 1: "print", 2: "replay"}

_live_sess = None
_live_lock = threading.Lock()


def _get_live_session(root: str):
    global _live_sess
    with _live_lock:
        if _live_sess is None:
            import onnxruntime as ort

            path = os.path.join(root, _LIVENESS_REL)
            _live_sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        return _live_sess


def _get_engine():
    # Reuse the identity-verification engine so we don't load a second buffalo_l.
    from attendance_identity import _get_face_engine

    return _get_face_engine()


def _increased_crop(img: np.ndarray, bbox, inc: float = 1.5) -> np.ndarray:
    """Square crop around the face bbox, enlarged by ``inc`` and zero-padded."""
    real_h, real_w = img.shape[:2]
    x, y, x2b, y2b = [float(v) for v in bbox]
    w, h = x2b - x, y2b - y
    side = max(w, h)
    xc, yc = x + w / 2, y + h / 2
    x, y = int(xc - side * inc / 2), int(yc - side * inc / 2)
    x1 = 0 if x < 0 else x
    y1 = 0 if y < 0 else y
    x2 = real_w if x + side * inc > real_w else x + int(side * inc)
    y2 = real_h if y + side * inc > real_h else y + int(side * inc)
    crop = img[y1:y2, x1:x2, :]
    crop = cv2.copyMakeBorder(
        crop,
        y1 - y, int(side * inc - y2 + y),
        x1 - x, int(side * inc) - x2 + x,
        cv2.BORDER_CONSTANT, value=[0, 0, 0],
    )
    return crop


def _letterbox_128(img: np.ndarray) -> np.ndarray:
    new_size = _IMG_SIZE
    old = img.shape[:2]
    ratio = float(new_size) / max(old)
    scaled = (int(old[0] * ratio), int(old[1] * ratio))
    img = cv2.resize(img, (scaled[1], scaled[0]))
    dw, dh = new_size - scaled[1], new_size - scaled[0]
    top, bottom = dh // 2, dh - dh // 2
    left, right = dw // 2, dw - dw // 2
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    img = img.transpose(2, 0, 1).astype(np.float32) / 255.0
    return np.expand_dims(img, axis=0)


def assess_liveness(root: str, bgr: np.ndarray, bbox) -> Dict[str, Any]:
    """Run the trained anti-spoof model on a face. ``bbox`` is (x1,y1,x2,y2)."""
    try:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        crop = _increased_crop(rgb, bbox, 1.5)
        if crop is None or crop.size == 0:
            return {"available": True, "label": "unknown", "real_score": 0.0, "spoof_score": 0.5,
                    "is_real": False, "risk": "medium"}
        sess = _get_live_session(root)
        name = sess.get_inputs()[0].name
        logits = sess.run([], {name: _letterbox_128(crop)})[0][0].astype(np.float64)
        e = np.exp(logits - np.max(logits))
        sm = e / np.sum(e)
        idx = int(np.argmax(sm))
        real = float(sm[0])
        thr = float(os.environ.get("LIVENESS_REAL_THRESHOLD", "0.55"))

        # The model only sees screen/print artifacts when the face is reasonably
        # large; a small/distant face crop is too low-res and reads as "live".
        # So require a minimum face size — which also forces a spoof phone to be
        # held close, where the model reliably catches it.
        bw, bh = int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])
        face_max = max(bw, bh)
        frame_max = max(int(bgr.shape[0]), int(bgr.shape[1]))
        ratio = (face_max / frame_max) if frame_max > 0 else 0.0
        min_px = float(os.environ.get("LIVENESS_MIN_FACE_PX", "110"))
        min_ratio = float(os.environ.get("LIVENESS_MIN_FACE_RATIO", "0.14"))
        too_small = (face_max < min_px) or (ratio < min_ratio)

        model_real = idx == 0 and real >= thr
        is_real = model_real and not too_small
        if too_small:
            label, risk = "too_small", "medium"
        elif is_real:
            label, risk = _LIVE_LABELS.get(idx, "unknown"), "none"
        elif idx == 0:
            label, risk = "uncertain", "medium"   # leans live but below threshold
        else:
            label, risk = _LIVE_LABELS.get(idx, "unknown"), "high"  # print / replay

        _log.warning(
            "LIVENESS probs live=%.3f print=%.3f replay=%.3f -> model=%s real=%.3f "
            "is_real=%s too_small=%s (face_max=%dpx ratio=%.2f thr=%.2f) bbox=%dx%d frame=%dx%d",
            sm[0], sm[1], sm[2], _LIVE_LABELS.get(idx), real, is_real, too_small,
            face_max, ratio, thr, bw, bh, bgr.shape[1], bgr.shape[0],
        )
        return {
            "available": True,
            "label": label,
            "real_score": round(real, 4),
            "spoof_score": round(1.0 - real, 4),
            "is_real": bool(is_real),
            "too_small": bool(too_small),
            "risk": risk,
            "probs": {k: round(float(sm[i]), 4) for i, k in _LIVE_LABELS.items()},
        }
    except Exception:
        # Never block attendance because the model failed to load/run; fail "open"
        # but mark for review.
        _log.exception("LIVENESS model failed — failing open")
        return {"available": False, "label": "unknown", "real_score": 0.0, "spoof_score": 0.0,
                "is_real": True, "risk": "none"}


# ── Mask / glasses (trained classifiers; wired in below) ──────────────────
from mask_glasses import detect_glasses, detect_mask  # noqa: E402


def assess_selfie_bytes(root: str, jpeg_bytes: bytes) -> Dict[str, Any]:
    """Full check on a selfie: detect the face once, then liveness + mask + glasses."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"face": False}
    eng = _get_engine()
    face = eng.largest_face(bgr)
    if face is None or face.embedding is None:
        return {"face": False}
    bbox = [int(v) for v in face.bbox_xyxy[:4]]
    return {
        "face": True,
        "bbox": bbox,
        "liveness": assess_liveness(root, bgr, bbox),
        "mask": detect_mask(root, bgr, face),
        "glasses": detect_glasses(root, bgr, face),
    }
