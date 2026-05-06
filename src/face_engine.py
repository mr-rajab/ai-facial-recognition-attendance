"""InsightFace-based detection, optional Haar fallback, alignment, embeddings, gallery (Week 2–3)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

import cv2
import numpy as np

MANIFEST_NAME = "manifest.json"


@dataclass
class FaceResult:
    bbox_xyxy: np.ndarray  # float32 (4,)
    det_score: float
    kps: Optional[np.ndarray]  # (5, 2) or None
    embedding: Optional[np.ndarray]  # (D,) L2-normalized when from InsightFace


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return v
    return (v / n).astype(np.float32)


class FaceEngine:
    """Wraps InsightFace FaceAnalysis (RetinaFace + ArcFace-style recognition)."""

    def __init__(
        self,
        det_size: Tuple[int, int] = (640, 640),
        ctx_id: int = -1,
        model_name: str = "buffalo_l",
    ) -> None:
        from insightface.app import FaceAnalysis

        providers = ["CPUExecutionProvider"]
        self._app = FaceAnalysis(name=model_name, providers=providers)
        self._app.prepare(ctx_id=ctx_id, det_size=det_size)

    def get_faces(self, bgr: np.ndarray) -> List[FaceResult]:
        faces = self._app.get(bgr)
        out: List[FaceResult] = []
        for f in faces:
            emb = getattr(f, "embedding", None)
            if emb is not None:
                emb = _l2_normalize(np.asarray(emb, dtype=np.float32))
            kps = getattr(f, "kps", None)
            if kps is not None:
                kps = np.asarray(kps, dtype=np.float32)
            bbox = np.asarray(f.bbox, dtype=np.float32)
            out.append(
                FaceResult(
                    bbox_xyxy=bbox,
                    det_score=float(f.det_score),
                    kps=kps,
                    embedding=emb,
                )
            )
        return out

    def largest_face(self, bgr: np.ndarray) -> Optional[FaceResult]:
        faces = self.get_faces(bgr)
        if not faces:
            return None
        areas = [(f.bbox_xyxy[2] - f.bbox_xyxy[0]) * (f.bbox_xyxy[3] - f.bbox_xyxy[1]) for f in faces]
        return faces[int(np.argmax(areas))]


def haar_face_boxes(bgr: np.ndarray, scale_factor: float = 1.2, min_neighbors: int = 5) -> List[Tuple[int, int, int, int]]:
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    face_cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    rects = face_cascade.detectMultiScale(gray, scaleFactor=scale_factor, minNeighbors=min_neighbors)
    out: List[Tuple[int, int, int, int]] = []
    for (x, y, w, h) in rects:
        out.append((int(x), int(y), int(x + w), int(y + h)))
    return out


def aligned_crop(bgr: np.ndarray, kps: np.ndarray, size: int = 112) -> np.ndarray:
    from insightface.utils import face_align

    return face_align.norm_crop(bgr, landmark=kps, image_size=size)


def cosine_topk(
    probe: np.ndarray,
    gallery_embeddings: np.ndarray,
    gallery_labels: Sequence[str],
    k: int = 5,
) -> List[Tuple[str, float]]:
    """probe and gallery rows L2-normalized -> cosine sim is dot product."""
    p = _l2_normalize(np.asarray(probe, dtype=np.float32))
    g = np.asarray(gallery_embeddings, dtype=np.float32)
    sims = g @ p
    order = np.argsort(-sims)[:k]
    return [(gallery_labels[int(i)], float(sims[int(i)])) for i in order]


@dataclass
class GalleryEntry:
    student_id: str
    name: str
    embedding: np.ndarray


class GalleryStore:
    """File-backed gallery under ``root_dir`` (default ``data/embeddings``)."""

    def __init__(self, root_dir: str = "data/embeddings") -> None:
        self.root_dir = root_dir
        self.templates_dir = os.path.join(root_dir, "templates")
        os.makedirs(self.templates_dir, exist_ok=True)
        self.manifest_path = os.path.join(root_dir, MANIFEST_NAME)

    def _load_manifest(self) -> dict[str, Any]:
        if not os.path.isfile(self.manifest_path):
            return {"version": 1, "entries": []}
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_manifest(self, data: dict[str, Any]) -> None:
        os.makedirs(self.root_dir, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def upsert(self, student_id: str, name: str, embedding: np.ndarray) -> None:
        emb = _l2_normalize(np.asarray(embedding, dtype=np.float32))
        path = os.path.join(self.templates_dir, f"{student_id}.npy")
        np.save(path, emb)

        data = self._load_manifest()
        entries: List[dict[str, Any]] = list(data.get("entries", []))
        filtered = [e for e in entries if e.get("student_id") != student_id]
        filtered.append(
            {
                "student_id": student_id,
                "name": name,
                "template_file": os.path.relpath(path, self.root_dir),
            }
        )
        data["entries"] = filtered
        self._save_manifest(data)

    def remove(self, student_id: str) -> None:
        data = self._load_manifest()
        entries = [e for e in data.get("entries", []) if e.get("student_id") != student_id]
        data["entries"] = entries
        self._save_manifest(data)
        path = os.path.join(self.templates_dir, f"{student_id}.npy")
        if os.path.isfile(path):
            os.remove(path)

    def load_matrix(self) -> Tuple[np.ndarray, List[str], List[str]]:
        """Returns embeddings (N, D), student_ids, names."""
        data = self._load_manifest()
        entries = list(data.get("entries", []))
        embs: List[np.ndarray] = []
        ids: List[str] = []
        names: List[str] = []
        for e in entries:
            sid = str(e["student_id"])
            rel = e["template_file"]
            path = os.path.join(self.root_dir, rel)
            if not os.path.isfile(path):
                continue
            vec = np.load(path).astype(np.float32).reshape(-1)
            embs.append(_l2_normalize(vec))
            ids.append(sid)
            names.append(str(e.get("name", "")))
        if not embs:
            return np.zeros((0, 512), dtype=np.float32), [], []
        mat = np.stack(embs, axis=0)
        return mat, ids, names

    def get_entry(self, student_id: str) -> Optional[GalleryEntry]:
        mat, ids, names = self.load_matrix()
        for i, sid in enumerate(ids):
            if sid == student_id:
                return GalleryEntry(student_id=sid, name=names[i], embedding=mat[i])
        return None
