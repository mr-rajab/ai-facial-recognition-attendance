"""Image augmentations for robustness evaluation and augmented enrollment (Week 4)."""

from __future__ import annotations

from typing import List

import cv2
import numpy as np


def hflip(bgr: np.ndarray) -> np.ndarray:
    return cv2.flip(bgr, 1)


def adjust_brightness(bgr: np.ndarray, beta: int) -> np.ndarray:
    """Linear brightness shift (beta in [-80, 80] typical)."""
    out = cv2.convertScaleAbs(bgr, alpha=1.0, beta=float(beta))
    return out


def synthesize_lower_face_mask(bgr: np.ndarray, cover_frac: float = 0.42) -> np.ndarray:
    """Occlude lower face (rough mask / bandana proxy) for masked-vs-unmasked experiments."""
    out = bgr.copy()
    h, w = out.shape[:2]
    y0 = int(h * (1.0 - cover_frac))
    out[y0:h, :] = (0, 0, 0)
    return out


def gaussian_noise(bgr: np.ndarray, sigma: float = 12.0) -> np.ndarray:
    noise = np.random.randn(*bgr.shape).astype(np.float32) * sigma
    x = bgr.astype(np.float32) + noise
    return np.clip(x, 0, 255).astype(np.uint8)


def default_train_variants(bgr: np.ndarray) -> List[np.ndarray]:
    """Augmentations used when rebuilding templates (Week 4 Day 2)."""
    return [
        bgr,
        hflip(bgr),
        adjust_brightness(bgr, 35),
        adjust_brightness(bgr, -35),
        synthesize_lower_face_mask(bgr, 0.35),
    ]
