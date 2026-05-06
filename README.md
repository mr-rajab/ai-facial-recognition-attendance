# AI-Based Facial Recognition Attendance System

This folder (`the_project/`) contains the **full 5-week stack** plus subsequent security and portal hardening work:

| Week | Focus |
| --- | --- |
| **1** | Capture, Haar baseline, SQLite schema, loaders, preprocessing |
| **2** | InsightFace detection + embeddings, alignment, gallery, `enroll` / `match` |
| **3** | Live `run_recognition` (voting + IoU tracking + DB), benchmark, CSV export |
| **4** | Evaluation (masked vs unmasked), augmented re-enroll, **FastAPI** portal (admin + student accounts, daily attendance), pytest + eval report |
| **5** | Docs (`docs/`), deployment/env notes, `scripts/smoke_integration.sh`, snapshot key **`s`** in live recognition |
| **+** | Security hardening: anti-spoof, identity verification, audit trail, rate limiting, bcrypt auth, backup script |

Detailed narrative: `docs/USER_GUIDE.md`, `docs/DEPLOYMENT.md`, `docs/SYSTEM_DESIGN.md`.  
Roadmap / security layers / phased backlog: `docs/SYSTEM_EVOLUTION_PLAN.md`.  
Plan table: `../Project_Technology_Plan/Weekly_Project_Plan.md`.

---

## What we built (Week 1)

| Component | File | What it does |
| --- | --- | --- |
| Capture | `src/capture_frames.py` | Opens the default (or chosen) camera, mirrors preview, saves JPEGs on keypress. |
| Baseline detection | `src/detect_faces.py` | Haar frontal-face detector, draws boxes, optional save + CSV log of face counts. |
| Database schema | `src/init_db.py` | Creates SQLite `students`, `sessions`, `attendance` with foreign keys. |
| Sample attendance | `src/attendance_logger.py` | CLI: creates/gets student, opens a session, inserts one attendance row. |
| Dataset summary | `src/data_loader.py` | Walks `data/raw/`, counts images per subfolder (label = folder name). |
| Preprocessing | `src/preprocess.py` | Resize + grayscale, preserves folder structure under output dir. |

**Artifacts produced when you run the tools**

- `data/raw/` — saved frames (by default flat filenames; for training-style layout use subfolders per student; see below).
- `data/processed/` — preprocessed images (from `preprocess.py`).
- `data/processed/detections/` — optional annotated frames from `detect_faces.py` when you press save.
- `data/logs/capture_log.csv`, `data/logs/detection_log.csv` — timestamps and metadata.
- `data/attendance.db` — SQLite database after `init_db` / `attendance_logger`.
- `data/embeddings/` — enrollment gallery (`manifest.json` + `templates/*.npy`) after `enroll.py`.
- `data/processed/aligned/` — aligned face crops after `align_faces.py` (default output).
- `data/logs/detect_compare.csv`, `data/logs/recognition_frames.csv` — Week 2–3 diagnostics.
- `data/reports/attendance_*.csv` — exports from `export_attendance_report.py`.

---

## What we built (Week 2)

| Component | File | What it does |
| --- | --- | --- |
| Shared engine + gallery | `src/face_engine.py` | InsightFace `buffalo_l` (det + rec), Haar helper, L2-normalized embeddings, cosine top-k, file-backed `GalleryStore`. |
| Detection compare | `src/detect_compare.py` | Walks images: logs Haar count vs InsightFace count to `data/logs/detect_compare.csv`. |
| Aligned crops | `src/align_faces.py` | Largest face per image → `insightface.utils.face_align.norm_crop` → JPEGs under `data/processed/aligned/`. |
| Batch embeddings | `src/extract_embeddings.py` | Optional `.npz` of embeddings for a folder (debug / analysis). |
| Top-k match | `src/match_face.py` | One probe image vs enrolled gallery. |
| Enrollment | `src/enroll.py` | Mean embedding from images and/or video; writes template + manifest; optional `--sync-db`. |

**First run note:** InsightFace downloads ONNX models (e.g. under `~/.insightface/models/`). Ensure disk space and network access once.

---

## What we built (Week 3)

| Component | File | What it does |
| --- | --- | --- |
| DB helpers | `src/attendance_db.py` | Shared `get_or_create_student`, `create_session`, `log_attendance` (used by Week 1 logger + pipeline). |
| IoU tracker | `src/tracking.py` | Greedy IoU association + missed-frame expiry for stable track IDs. |
| Live pipeline | `src/run_recognition.py` | Webcam/video: detect → embed → match → per-track vote buffer → mark each student once per session in SQLite; CSV frame log. |
| Benchmark | `src/benchmark_inference.py` | Mean/median ms per frame and approximate FPS. |
| CSV report | `src/export_attendance_report.py` | Joins `attendance` + `students` + `sessions` → `data/reports/`. |

---

## What we built (Week 4)

| Component | File | What it does |
| --- | --- | --- |
| Augmentations | `src/augmentation.py` | Flip, brightness, synthetic lower-face mask, noise helper for robustness experiments. |
| Augmented enroll | `src/enroll_augmented.py` | Rebuilds template from originals **plus** augmented variants (mean embedding). |
| Evaluation | `src/evaluate_recognition.py` | Closed-set top-1 accuracy on `data/eval/<student_id>/*`; **unmasked** vs **synthetic mask** JSON metrics. |
| Eval report | `src/run_eval_report.py` | Runs evaluation, writes `data/reports/evaluation_metrics.json` + `evaluation_report.md`. |
| Web portal | `src/web_app.py`, `src/portal_router.py` | Email/password login; **admin**: enroll students (4 webcam poses + account), review daily photos, CSV export; **student**: submit daily attendance; legacy live-session pages remain for Week 3 flows. |
| Student router | `src/portal_students.py` | Handles multi-angle webcam enrollment for new students: decodes four pose images, builds gallery template, creates the user account. |
| Bootstrap admin | `src/portal_bootstrap.py` | On first startup, reads `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` env vars and inserts the initial admin user if the `users` table is empty. |
| Password auth | `src/auth_passwords.py` | Bcrypt `hash_password` / `verify_password` helpers used across all portal login and account creation paths. |
| UI templates | `templates/*.html` | See [Templates](#templates) section below. |
| Config sample | `.env.example` | `SECRET_KEY`, optional `BOOTSTRAP_ADMIN_*` for the first admin user. |
| Unit tests | `tests/` | IoU / tracker + cosine matching sanity checks (`pytest`). |

---

## What we built (Week 5)

| Component | Path | What it does |
| --- | --- | --- |
| User guide | `docs/USER_GUIDE.md` | End-to-end operator instructions. |
| Deployment | `docs/DEPLOYMENT.md` | Env vars, security notes, smoke test reference. |
| System design | `docs/SYSTEM_DESIGN.md` | Architecture summary for the report / defense. |
| Evolution plan | `docs/SYSTEM_EVOLUTION_PLAN.md` | Threat model, defense-in-depth, product backlog, phased roadmap. |
| Smoke script | `scripts/smoke_integration.sh` | `init_db` + `pytest` + import check for `web_app`. |
| Live snapshots | `src/run_recognition.py` | Press **`s`** to save the current preview frame under `--snap-dir` (default `data/raw/snapshots/`). |

---

## Security & portal hardening (post Week 5)

| Component | File | What it does |
| --- | --- | --- |
| Anti-spoof | `src/anti_spoof.py` | Heuristic presentation-attack scoring for selfie submissions: border-edge ratio, Laplacian texture, frequency content. Not a certified liveness product — flags suspicious prints/screens for admin review. |
| Identity verify | `src/attendance_identity.py` | Checks that a submitted attendance selfie's embedding matches the enrolled template for that specific student account before marking attendance. |
| Audit log | `src/audit_log.py` | Append-only audit trail (SQLite `audit_log` table) for security-relevant events: logins, enrollments, attendance submissions. Stores hashed IP + user-agent, never raw PII. |
| Rate limiter | `src/rate_limit.py` | Shared `slowapi` `Limiter` instance; disabled automatically when `RATE_LIMIT_ENABLED=0` (e.g. during `pytest`). |
| Quick recognition | `src/quick_recognition.py` | Stateless JPEG → gallery match used by the `/quick-attendance` route (no login required). Calls `anti_spoof` before matching. |
| Backup script | `scripts/backup_portal_data.sh` | Copies `data/attendance.db`, `data/embeddings/`, and `data/portal/` to a timestamped `backups/<stamp>/` folder. |

---

## Templates

| Template | What it renders |
| --- | --- |
| `login.html` | Email / password login form. |
| `index.html` | Legacy live-session landing (Week 3 flow). |
| `session.html` | Live-session detail / frame log view. |
| `admin_home.html` | Admin dashboard with student list and quick links. |
| `admin_student_new.html` | Four-pose webcam enrollment form for creating a new student account. |
| `admin_student_edit.html` | Edit student name / email / password. |
| `admin_reviews.html` | Daily attendance submission review queue (with selfie thumbnails and anti-spoof flags). |
| `admin_sessions.html` | List of all attendance sessions with per-session detail links. |
| `admin_classes.html` | Class / course management view. |
| `admin_class_detail.html` | Per-class attendance roster and session breakdown. |
| `admin_analytics.html` | Aggregate attendance analytics and charts. |
| `student_home.html` | Student dashboard showing recent attendance records. |
| `student_attendance_new.html` | Selfie capture form for submitting daily attendance. |
| `register_student.html` | Self-registration page (if enabled). |
| `quick_attendance.html` | Anonymous quick-attendance page: one webcam frame → face match → greeting (no official record). |

---

## Requirements

- **Python:** **3.10–3.12 strongly recommended.** Very new interpreters (e.g. 3.14 preview) may need newer `onnx` / `ml_dtypes` stacks; `requirements.txt` pins compatible versions where needed.
- **Hardware:** webcam for live scripts; **CPU** works (`onnxruntime`); GPU optional (install `onnxruntime-gpu` separately if applicable).
- **OS:** macOS, Linux, or Windows (camera index and permissions differ by OS).

---

## Setup (important: run commands from this folder)

All scripts use **paths relative to `the_project/`** (for example `data/raw`).
Always `cd` into `the_project` first, or paths will be wrong.

### 1. Go to the project directory

```bash
cd "/path/to/the_project"
```

(Adjust the path to wherever you cloned the repository.)

### 2. Create and activate a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Includes `insightface`, `onnxruntime`, `onnx`, `ml_dtypes`, plus Week 1 packages.

### 4. Initialize the database (once, or after deleting `data/attendance.db`)

```bash
python src/init_db.py
```

You should see: `Initialized database at data/attendance.db`.

---

## How to run each script

Run every command with the virtual environment **activated** and **current working directory** = `the_project/`.

### Webcam capture — `capture_frames.py`

Opens a live window.

- **`s`** — save the current frame to `data/raw/` (default) as `frame_YYYYMMDD_HHMMSS.jpg` and append a row to `data/logs/capture_log.csv`.
- **`q`** — quit.

```bash
python src/capture_frames.py
```

Useful options:

```bash
python src/capture_frames.py --device 0 --out-dir data/raw --log data/logs/capture_log.csv
python src/capture_frames.py --width 1280 --height 720
```

If the camera fails to open, try `--device 1` (second camera) or check OS privacy settings for camera access.

---

### Baseline face detection — `detect_faces.py`

Uses OpenCV's Haar cascade on a **camera index** (default `0`) or a **video file path**.

- **`s`** — save the annotated frame under `data/processed/detections/` (default) and log the filename when non-empty.
- **`q`** — quit.

Each loop iteration appends a row to `data/logs/detection_log.csv` (`timestamp`, `faces_detected`, `saved_frame`).

```bash
python src/detect_faces.py
```

Examples:

```bash
python src/detect_faces.py --source 0
python src/detect_faces.py --source /path/to/video.mp4 --out-dir data/processed/detections
```

---

### Initialize SQLite — `init_db.py`

Creates `data/attendance.db` and tables if they do not exist.

```bash
python src/init_db.py
```

---

### Log sample attendance — `attendance_logger.py`

Ensures the DB exists, then inserts **one** attendance record: creates a student row if needed, creates a new session, then adds an `attendance` row.

Required: `--student-id`, `--name`. Optional: `--email`, `--course`, `--status`, `--confidence`.

```bash
python src/attendance_logger.py --student-id 123456789 --name "Student Name" --email student@example.com --course "CS-Graduation-Project" --status present --confidence 0.9
```

Inspect the DB with any SQLite browser, or:

```bash
sqlite3 data/attendance.db "SELECT * FROM attendance;"
```

---

### Dataset label counts — `data_loader.py`

Expects images under `data/raw/`. Each **immediate subfolder name** is treated as the label (e.g. student ID).

Recommended layout:

```text
data/raw/
  123456789/
    img_001.jpg
    img_002.jpg
  987654321/
    img_001.jpg
```

```bash
python src/data_loader.py
python src/data_loader.py --data-dir data/raw
```

---

### Preprocess images — `preprocess.py`

Walks `--input-dir`, resizes to `W,H`, converts to grayscale, writes under `--output-dir` mirroring subfolders.

```bash
python src/preprocess.py
python src/preprocess.py --input-dir data/raw --output-dir data/processed --size 160,160
```

---

### Compare Haar vs InsightFace — `detect_compare.py`

```bash
python src/detect_compare.py --input-dir data/raw --log data/logs/detect_compare.csv
python src/detect_compare.py --input-dir data/raw --limit 20
```

---

### Align faces — `align_faces.py`

```bash
python src/align_faces.py --input-dir data/raw --output-dir data/processed/aligned
```

---

### Enroll a student — `enroll.py`

Put several clear frontal photos in a folder (or pass explicit paths / a short video).

```bash
python src/enroll.py --student-id 123456789 --name "Student Name" --images-dir data/raw/123456789 --sync-db
python src/enroll.py --student-id 987654321 --name "Another Student" --images data/raw/a.jpg data/raw/b.jpg --video data/raw/clips/demo.mp4
```

---

### Match one image — `match_face.py`

Requires at least one enrolled template.

```bash
python src/match_face.py --probe data/raw/some_face.jpg --k 5
```

---

### Batch embeddings (optional) — `extract_embeddings.py`

```bash
python src/extract_embeddings.py --input-dir data/raw/123456789 --out data/embeddings/batch.npz
```

---

### Live recognition + attendance — `run_recognition.py`

Creates a **new session** row, then marks each recognized **student_id** at most **once** when the vote buffer agrees (`--min-agree` of `--min-sim` matches).

```bash
python src/init_db.py
python src/run_recognition.py --source 0 --course "CS-Lab" --min-sim 0.35 --vote-window 10 --min-agree 5
python src/run_recognition.py --source 0 --no-db
```

Tune `--min-sim` upward if you see false positives; increase `--min-agree` for stricter confirmation.

- **`s`** — save the current preview frame to `--snap-dir` (default `data/raw/snapshots/`).  
- **`q`** — quit.

Frame-level log: `data/logs/recognition_frames.csv` (includes optional `marked` column when a DB row is written).

---

### Benchmark — `benchmark_inference.py`

```bash
python src/benchmark_inference.py --source 0 --warmup 10 --frames 120
```

Uses a **video file** as `--source` if the camera is unavailable (loops the file).

---

### Export attendance CSV — `export_attendance_report.py`

```bash
python src/export_attendance_report.py
python src/export_attendance_report.py --session-id 3 --out data/reports/session3.csv
```

---

### Augmented re-enroll — `enroll_augmented.py`

Rebuilds a stronger template using flips, brightness, and a synthetic lower-face mask variant per image.

```bash
python src/enroll_augmented.py --student-id 123456789 --name "Student Name" --images-dir data/raw/123456789 --sync-db
```

---

### Evaluation — `evaluate_recognition.py` / `run_eval_report.py`

Layout:

```text
data/eval/
  123456789/
    img1.jpg
    img2.jpg
```

Folder names must match enrolled `student_id` values in the gallery.

```bash
python src/evaluate_recognition.py --dataset data/eval --gallery-root data/embeddings
python src/run_eval_report.py
```

---

### Web portal — `web_app.py`

**Recommended:** copy `.env.example` → `.env`, set `SECRET_KEY` and `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`, then start once (the app **auto-loads** `.env` and creates the first admin if `users` is empty):

```bash
cp .env.example .env
# edit .env — set a real email/password for the bootstrap admin
python -m uvicorn web_app:app --app-dir src --host 127.0.0.1 --port 8000
```

**Or** export in the shell (each `export` must run **before** uvicorn, on **separate lines** or separated by `;`):

```bash
export SECRET_KEY="use-a-long-random-string"
export BOOTSTRAP_ADMIN_EMAIL="you@university.edu"
export BOOTSTRAP_ADMIN_PASSWORD="your-secure-password"
python -m uvicorn web_app:app --app-dir src --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/login`, sign in with that email and password, then use the admin dashboard to create student accounts (with four enrollment photos). Students sign in with the email and password you set for them and submit daily attendance from **Student home**. Admins review submissions under **Reviews** and can download **Export all records (CSV)**.

**Quick attendance** (before login): open `/quick-attendance` or use the link on the login page — the browser camera sends one frame to the server, which matches the face gallery and shows a greeting (and optional speech). It does not submit official attendance; students still use **Sign in** for that.

---

### Backup portal data — `backup_portal_data.sh`

Copies the SQLite database, embeddings gallery, and any portal-uploaded photos to a timestamped folder under `backups/`.

```bash
bash scripts/backup_portal_data.sh
```

The backup is written to `backups/YYYYMMDD_HHMMSS/` relative to `the_project/`.

---

### Automated tests

```bash
python -m pytest tests/ -q
bash scripts/smoke_integration.sh
```

The test suite covers:

| File | What it tests |
| --- | --- |
| `tests/test_tracking.py` | IoU tracker association and missed-frame expiry. |
| `tests/test_face_engine.py` | Cosine similarity and gallery store sanity checks. |
| `tests/test_anti_spoof.py` | Heuristic anti-spoof scoring returns expected keys and score range. |
| `tests/test_attendance_identity.py` | Identity verification rejects submissions when no gallery template exists. |
| `tests/test_web_app.py` | FastAPI portal endpoints (login, attendance submission) via `TestClient`. |

---

## Project structure

```text
the_project/
  requirements.txt
  README.md
  .env.example
  scripts/
    smoke_integration.sh
    backup_portal_data.sh
  src/
    __init__.py
    # --- Week 1 ---
    capture_frames.py
    detect_faces.py
    init_db.py
    attendance_logger.py
    data_loader.py
    preprocess.py
    # --- Week 2 ---
    face_engine.py
    detect_compare.py
    align_faces.py
    extract_embeddings.py
    match_face.py
    enroll.py
    # --- Week 3 ---
    attendance_db.py
    tracking.py
    run_recognition.py
    benchmark_inference.py
    export_attendance_report.py
    # --- Week 4 ---
    augmentation.py
    enroll_augmented.py
    evaluate_recognition.py
    run_eval_report.py
    web_app.py
    portal_router.py
    portal_students.py
    portal_bootstrap.py
    auth_passwords.py
    # --- Security hardening ---
    anti_spoof.py
    attendance_identity.py
    audit_log.py
    rate_limit.py
    quick_recognition.py
  templates/
    login.html
    index.html
    session.html
    admin_home.html
    admin_student_new.html
    admin_student_edit.html
    admin_reviews.html
    admin_sessions.html
    admin_classes.html
    admin_class_detail.html
    admin_analytics.html
    student_home.html
    student_attendance_new.html
    register_student.html
    quick_attendance.html
  data/
    raw/
    raw/snapshots/
    eval/
    processed/
    processed/aligned/
    embeddings/
    embeddings/templates/
    logs/
    reports/
    portal/
    attendance.db
  docs/
    daily_log.md
    USER_GUIDE.md
    DEPLOYMENT.md
    SYSTEM_DESIGN.md
    SYSTEM_EVOLUTION_PLAN.md
  tests/
    conftest.py
    test_tracking.py
    test_face_engine.py
    test_anti_spoof.py
    test_attendance_identity.py
    test_web_app.py
  backups/
    <YYYYMMDD_HHMMSS>/   ← created by backup_portal_data.sh
```

---

## Notes and troubleshooting

- **Imports:** `attendance_logger.py` imports `init_db` from the same package; running as `python src/attendance_logger.py` relies on Python adding `src` to `sys.path` for that invocation. If you see `ModuleNotFoundError: init_db`, run from `the_project` as shown above, or use `python -m` style after adding proper package layout in a later week.
- **Camera permissions:** On macOS, grant Terminal or your IDE camera access in **System Settings → Privacy & Security → Camera**.
- **Rate limiting:** The web portal applies per-IP rate limits via `slowapi`. Set `RATE_LIMIT_ENABLED=0` in your environment to disable during testing.
- **Anti-spoof:** The heuristic scores in `anti_spoof.py` are advisory — they flag potentially spoofed selfies for admin review rather than hard-blocking submissions. They are not a replacement for certified liveness detection.
- **Privacy:** Store only data your institution allows; student photos and DB files should not be committed to public repos (add `.gitignore` rules if needed).

---

## Maintenance / extensions

Possible next work (beyond the 5-week scope): mask-aware fine-tuning, DeepSORT-style tracking, university SSO for the dashboard, packaging with Docker, certified liveness/anti-spoof model, and formal ethics/IRB documentation for classroom deployment.
