import sys

import numpy as np
import pytest

_ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), ".."))
_SRC = __import__("os").path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def test_verify_rejects_without_template(tmp_path):
    from attendance_identity import verify_selfie_matches_enrolled_student

    root = str(tmp_path)
    fake_jpeg = bytes([0xFF, 0xD8, 0xFF, 0xD9]) + b"x" * 2000
    ok, reason, sim = verify_selfie_matches_enrolled_student(root, "99999", fake_jpeg)
    assert ok is False
    assert reason == "no_gallery_template"
    assert sim == 0.0


def test_verify_bad_jpeg_bytes(tmp_path):
    from attendance_identity import verify_selfie_matches_enrolled_student

    pytest.importorskip("cv2")
    root = str(tmp_path)
    import json
    import os

    emb_root = tmp_path / "data" / "embeddings"
    tpl = emb_root / "templates"
    tpl.mkdir(parents=True)
    vec = np.ones(512, dtype=np.float32)
    vec = vec / np.linalg.norm(vec)
    np.save(tpl / "S1.npy", vec)
    manifest = {
        "version": 1,
        "entries": [{"student_id": "S1", "name": "Test", "template_file": "templates/S1.npy"}],
    }
    (emb_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    ok, reason, sim = verify_selfie_matches_enrolled_student(root, "S1", b"not-a-valid-jpeg-image")
    assert ok is False
    assert reason == "bad_image"
