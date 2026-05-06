"""
Heuristic presentation-attack (anti-spoof) cues for single JPEGs.

This is **not** a certified liveness product. Phone screens, prints, and laptop
displays often differ from live faces in border structure, frequency content, and
local texture — we score those cues so admins can review suspicious submissions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


def _border_edge_ratio(gray: np.ndarray) -> float:
    """Share of Canny edges that fall in a thin outer frame (common for photos of devices)."""
    h, w = gray.shape[:2]
    border = max(3, min(h, w) // 35)
    mask = np.zeros_like(gray, dtype=np.uint8)
    mask[:border, :] = 1
    mask[-border:, :] = 1
    mask[:, :border] = 1
    mask[:, -border:] = 1
    edges = cv2.Canny(gray, 55, 165)
    bp = float(np.count_nonzero(mask))
    if bp < 1:
        return 0.0
    return float(np.count_nonzero((edges > 0) & (mask > 0))) / bp


def _fft_grid_energy(gray: np.ndarray) -> Tuple[float, float]:
    """Mid-frequency ring energy vs total — LCD/OLED moiré and pixel grids often spike here."""
    h, w = gray.shape[:2]
    cy, cx = h // 2, w // 2
    half = min(128, cy, cx, h - cy, w - cx)
    if half < 24:
        crop = gray
    else:
        crop = gray[cy - half : cy + half, cx - half : cx + half]
    small = cv2.resize(crop, (128, 128), interpolation=cv2.INTER_AREA)
    f = np.fft.fft2(small.astype(np.float32))
    mag = np.abs(np.fft.fftshift(f))
    mag[63:65, 63:65] = 0
    total = float(mag.sum()) + 1e-6
    yy, xx = np.ogrid[:128, :128]
    r = np.sqrt((xx - 64) ** 2 + (yy - 64) ** 2)
    ring = (r >= 16) & (r <= 58)
    ring_e = float(mag[ring].sum()) / total
    dc_ratio = float(mag[63, 63]) / total
    return ring_e, dc_ratio


def _center_laplacian_var(gray: np.ndarray) -> float:
    h, w = gray.shape[:2]
    roi = gray[h // 5 : 4 * h // 5, w // 5 : 4 * w // 5]
    if roi.size < 400:
        roi = gray
    lap = cv2.Laplacian(roi, cv2.CV_64F)
    return float(lap.var())


def _saturation_mean(bgr: np.ndarray) -> float:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 1].mean())


def assess_jpeg_bytes(jpeg_bytes: bytes) -> Dict[str, Any]:
    """Decode JPEG then run :func:`assess_presentation_attack`."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"risk": "low", "score": 0.1, "detail": "decode_fail", "signals": ["bad_jpeg"]}
    return assess_presentation_attack(bgr)


def assess_presentation_attack(bgr: np.ndarray) -> Dict[str, Any]:
    """
    Returns keys: risk ('none'|'low'|'medium'|'high'), score (0..1),
    detail (short admin-facing string), signals (list of short codes).
    """
    signals: List[str] = []
    score = 0.0

    if bgr is None or bgr.size < 400:
        return {"risk": "low", "score": 0.15, "detail": "image_too_small", "signals": ["small"]}

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    ber = _border_edge_ratio(gray)
    if ber > 0.095:
        signals.append("strong_frame_edges")
        score += min(0.34, (ber - 0.095) * 2.4)

    ring_e, _dc = _fft_grid_energy(gray)
    if ring_e > 0.28:
        signals.append("lcd_like_frequency_peaks")
        score += min(0.32, (ring_e - 0.28) * 2.0)

    lapv = _center_laplacian_var(gray)
    if lapv < 42.0:
        signals.append("very_flat_texture")
        score += 0.18
    elif lapv > 3200.0:
        signals.append("extreme_sharpness")
        score += 0.1

    sm = _saturation_mean(bgr)
    if sm < 12.0:
        signals.append("very_low_saturation")
        score += 0.12

    score = float(min(1.0, max(0.0, score)))

    if score < 0.26:
        risk = "none"
    elif score < 0.42:
        risk = "low"
    elif score < 0.62:
        risk = "medium"
    else:
        risk = "high"

    detail = ",".join(signals) if signals else "no_spoof_signals"
    return {"risk": risk, "score": round(score, 4), "detail": detail[:500], "signals": signals}
