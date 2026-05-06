import numpy as np

from face_engine import cosine_topk, _l2_normalize


def test_cosine_topk_perfect_match():
    g = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    probe = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    top = cosine_topk(probe, g, ["a", "b"], k=2)
    assert top[0][0] == "a"
    assert abs(top[0][1] - 1.0) < 1e-4


def test_l2_normalize():
    v = np.array([3.0, 4.0], dtype=np.float32)
    n = _l2_normalize(v)
    assert abs(float(np.linalg.norm(n)) - 1.0) < 1e-5
