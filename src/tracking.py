"""Simple IoU-based face track association (Week 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


def iou_xyxy(a: np.ndarray, b: np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = [float(x) for x in a]
    bx1, by1, bx2, by2 = [float(x) for x in b]
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0.0, inter_x2 - inter_x1)
    ih = max(0.0, inter_y2 - inter_y1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter + 1e-9
    return inter / union


@dataclass
class FaceTrack:
    track_id: int
    bbox_xyxy: np.ndarray
    missed: int = 0
    votes: List[Tuple[str, float]] = field(default_factory=list)

    def add_vote(self, label: str, score: float, max_votes: int) -> None:
        self.votes.append((label, score))
        if len(self.votes) > max_votes:
            self.votes = self.votes[-max_votes:]


class IoUTracker:
    def __init__(self, iou_threshold: float = 0.3, max_missed: int = 8) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self._next_id = 1
        self.tracks: Dict[int, FaceTrack] = {}

    def update(self, boxes: List[np.ndarray]) -> Dict[int, FaceTrack]:
        """Assign each box to best-matching track by IoU; spawn new tracks for leftovers."""
        unmatched_tracks = set(self.tracks.keys())
        unmatched_boxes = list(range(len(boxes)))

        pairs: List[Tuple[float, int, int]] = []
        for ti in self.tracks:
            for bi in range(len(boxes)):
                pairs.append((iou_xyxy(self.tracks[ti].bbox_xyxy, boxes[bi]), ti, bi))
        pairs.sort(reverse=True)

        assigned_t = set()
        assigned_b = set()
        for score, ti, bi in pairs:
            if score < self.iou_threshold:
                break
            if ti in assigned_t or bi in assigned_b:
                continue
            assigned_t.add(ti)
            assigned_b.add(bi)
            unmatched_tracks.discard(ti)
            unmatched_boxes.remove(bi)
            self.tracks[ti].bbox_xyxy = boxes[bi].astype(np.float32)
            self.tracks[ti].missed = 0

        for ti in unmatched_tracks:
            self.tracks[ti].missed += 1

        for bi in unmatched_boxes:
            tid = self._next_id
            self._next_id += 1
            self.tracks[tid] = FaceTrack(track_id=tid, bbox_xyxy=boxes[bi].astype(np.float32))

        dead = [tid for tid, tr in self.tracks.items() if tr.missed > self.max_missed]
        for tid in dead:
            del self.tracks[tid]

        return self.tracks
