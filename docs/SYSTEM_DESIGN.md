# System design (high level)

## Components

| Layer | Responsibility |
| --- | --- |
| **Capture** | `capture_frames.py`, `run_recognition.py` (`s` snapshots) — ingest BGR frames from camera or video. |
| **Detection + embedding** | `face_engine.py` wraps InsightFace `FaceAnalysis` (`buffalo_l`): RetinaFace-class detector + ArcFace-style recognition head via ONNXRuntime. |
| **Gallery** | `GalleryStore` persists one L2-normalized template vector per `student_id` under `data/embeddings/` plus `manifest.json`. |
| **Matching** | Cosine similarity = dot product after L2 normalization (`cosine_topk`). |
| **Temporal logic** | `tracking.py` associates boxes across frames (IoU). `run_recognition.py` maintains per-track vote buffers and majority agreement before committing attendance. |
| **Persistence** | SQLite (`init_db.py`): `students`, `sessions`, `attendance`. |
| **Reporting** | `export_attendance_report.py`, dashboard CSV export, `run_eval_report.py`. |
| **Web** | `web_app.py` (FastAPI + Jinja2 + signed cookie sessions). |

## Data flow (live session)

```text
Camera → OpenCV frame (BGR, mirrored for preview)
  → FaceEngine.get_faces (det + emb)
  → cosine match vs gallery (threshold → unknown)
  → IoUTracker.update (track IDs)
  → per-track votes → confirmed identity
  → SQLite attendance (once per student_id per run) + CSV frame log
```

## Extension points

- Swap `FaceEngine` providers for GPU.  
- Replace mean template in `enroll.py` with multi-vector prototypes or quality-weighted means.  
- Add HTTPS-only cookies and stricter auth (university SSO) for production dashboards.
