"""Mask and glasses flags for attendance selfies.

These are review *flags* (non-blocking): they surface in the admin review queue so
a human notices when a submission was made with a mask or glasses on. The current
implementation is landmark/region heuristic (v1); the public `detect_mask` /
`detect_glasses` signatures are stable so a trained ONNX classifier can be dropped
in later without touching the callers.

Each detector returns: {"flag": bool, "score": float (0..1), "method": str}.
Tunable via env: MASK_FLAG_THRESHOLD, GLASSES_FLAG_THRESHOLD.
"""

from __future__ import annotations

import os
from typing import Any, Dict

import cv2
import numpy as np


def _clip_region(bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int):
    h, w = bgr.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 6 or y2 - y1 < 6:
        return None
    return bgr[y1:y2, x1:x2]


def detect_glasses(root: str, bgr: np.ndarray, face) -> Dict[str, Any]:
    """Heuristic: glasses add strong frame edges + lens reflections across the eye band."""
    try:
        kps = getattr(face, "kps", None)
        bbox = [float(v) for v in face.bbox_xyxy[:4]]
        fh = bbox[3] - bbox[1]
        if kps is None or fh <= 0:
            return {"flag": False, "score": 0.0, "method": "heuristic-v1"}
        le, re_, nose = kps[0], kps[1], kps[2]
        eyes_y = (le[1] + re_[1]) / 2.0
        ex1 = min(le[0], re_[0]) - 0.18 * fh
        ex2 = max(le[0], re_[0]) + 0.18 * fh
        y1 = eyes_y - 0.16 * fh
        y2 = max(eyes_y + 0.10 * fh, nose[1] - 0.04 * fh)
        roi = _clip_region(bgr, ex1, y1, ex2, y2)
        if roi is None:
            return {"flag": False, "score": 0.0, "method": "heuristic-v1"}
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 170)
        edge_density = float(np.count_nonzero(edges)) / float(edges.size)
        reflections = float(np.count_nonzero(gray > 232)) / float(gray.size)
        # frames -> edge density; lenses -> bright specular spots
        score = min(1.0, edge_density * 4.2 + reflections * 6.0)
        thr = float(os.environ.get("GLASSES_FLAG_THRESHOLD", "0.45"))
        return {"flag": bool(score >= thr), "score": round(score, 3), "method": "heuristic-v1"}
    except Exception:
        return {"flag": False, "score": 0.0, "method": "heuristic-v1"}


def detect_mask(root: str, bgr: np.ndarray, face) -> Dict[str, Any]:
    """Heuristic: a mask covers nose+mouth with a large, low-texture, often non-skin
    region of uniform colour."""
    try:
        kps = getattr(face, "kps", None)
        bbox = [float(v) for v in face.bbox_xyxy[:4]]
        fh = bbox[3] - bbox[1]
        fw = bbox[2] - bbox[0]
        if kps is None or fh <= 0:
            return {"flag": False, "score": 0.0, "method": "heuristic-v1"}
        nose = kps[2]
        cx = (bbox[0] + bbox[2]) / 2.0
        x1 = cx - 0.34 * fw
        x2 = cx + 0.34 * fw
        y1 = nose[1] + 0.04 * fh
        y2 = bbox[3] - 0.02 * fh
        roi = _clip_region(bgr, x1, y1, x2, y2)
        if roi is None:
            return {"flag": False, "score": 0.0, "method": "heuristic-v1"}

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        texture = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        texture_score = max(0.0, 1.0 - texture / 140.0)            # low texture -> mask-like

        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        ab_std = float(lab[:, :, 1].std() + lab[:, :, 2].std())
        uniform_score = max(0.0, 1.0 - ab_std / 30.0)              # uniform colour -> mask-like

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        skin = ((h <= 25) | (h >= 172)) & (s >= 40) & (s <= 190) & (v >= 60)
        skin_frac = float(np.count_nonzero(skin)) / float(skin.size)
        nonskin_score = max(0.0, 1.0 - skin_frac / 0.45)           # little skin -> mask-like

        score = 0.4 * texture_score + 0.3 * uniform_score + 0.3 * nonskin_score
        thr = float(os.environ.get("MASK_FLAG_THRESHOLD", "0.62"))
        return {"flag": bool(score >= thr), "score": round(score, 3), "method": "heuristic-v1"}
    except Exception:
        return {"flag": False, "score": 0.0, "method": "heuristic-v1"}
