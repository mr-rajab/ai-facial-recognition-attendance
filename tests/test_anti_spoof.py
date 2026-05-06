"""Sanity checks for heuristic presentation-attack scoring."""

import sys

import numpy as np
import pytest

_ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), ".."))
_SRC = __import__("os").path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def test_assess_returns_risk_keys():
    from anti_spoof import assess_presentation_attack

    rng = np.random.default_rng(0)
    bgr = (rng.random((200, 200, 3)) * 255).astype(np.uint8)
    out = assess_presentation_attack(bgr)
    assert "risk" in out and "score" in out and "detail" in out
    assert out["risk"] in ("none", "low", "medium", "high")
    assert 0.0 <= float(out["score"]) <= 1.0


def test_assess_jpeg_bytes_invalid():
    from anti_spoof import assess_jpeg_bytes

    out = assess_jpeg_bytes(b"not a jpeg")
    assert out["risk"] in ("none", "low", "medium", "high")
