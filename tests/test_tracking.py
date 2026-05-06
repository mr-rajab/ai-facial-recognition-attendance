import numpy as np

from tracking import IoUTracker, iou_xyxy


def test_iou_identical():
    a = np.array([0.0, 0.0, 10.0, 10.0], dtype=np.float32)
    assert abs(iou_xyxy(a, a) - 1.0) < 1e-5


def test_iou_disjoint():
    a = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32)
    b = np.array([2.0, 2.0, 3.0, 3.0], dtype=np.float32)
    assert iou_xyxy(a, b) < 1e-5


def test_tracker_assigns_stable_id():
    tr = IoUTracker(iou_threshold=0.2, max_missed=20)
    b1 = np.array([0.0, 0.0, 10.0, 10.0], dtype=np.float32)
    t1 = tr.update([b1])
    assert len(t1) == 1
    tid = next(iter(t1.keys()))
    b1_shift = np.array([0.5, 0.5, 10.5, 10.5], dtype=np.float32)
    t2 = tr.update([b1_shift])
    assert tid in t2

