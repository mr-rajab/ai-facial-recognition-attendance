# How to Use — AI Facial Recognition Attendance System

This guide walks through every role and workflow in plain language.  
All commands assume you are inside the `the_project/` directory with the virtual environment active.

---

## 1. First-time setup

### 1.1 Navigate to the project folder

```bash
cd "/path/to/the_project"
```

### 1.2 Create and activate a virtual environment

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

### 1.3 Install dependencies

```bash
pip install -r requirements.txt
```

InsightFace will download its ONNX models the first time it runs (~200 MB). Make sure you have internet access and enough disk space.

### 1.4 Initialize the database

```bash
python src/init_db.py
```

Expected output: `Initialized database at data/attendance.db`

---

## 2. Enrolling students (admin task)

Enrollment saves a face "template" (embedding) for each student so the system can recognize them later.

### Step 1 — Collect face photos

You need several clear, well-lit, frontal photos per student.

**Option A — capture directly from the webcam:**
```bash
python src/capture_frames.py
```
Press `s` to save a frame, `q` to quit.  
Photos are saved to `data/raw/`.

Move the saved photos into a subfolder named after the student ID:
```
data/raw/
  123456789/
    frame_20250101_120000.jpg
    frame_20250101_120010.jpg
```

**Option B — copy existing photos** into `data/raw/<student_id>/`.

Aim for 5–10 varied poses per student (slightly different angles, lighting).

### Step 2 — Run enrollment

```bash
python src/enroll.py \
  --student-id 123456789 \
  --name "Student Name" \
  --images-dir data/raw/123456789 \
  --sync-db
```

`--sync-db` writes the student record to the attendance database at the same time.

**For a more robust template** (recommended), use augmented enrollment:
```bash
python src/enroll_augmented.py \
  --student-id 123456789 \
  --name "Student Name" \
  --images-dir data/raw/123456789 \
  --sync-db
```

This generates flipped and brightness-varied variants internally, producing a stronger average embedding.

Repeat for every student.

---

## 3. Running a live attendance session

Once students are enrolled, start the live recognition pipeline before or at the start of class.

```bash
python src/run_recognition.py \
  --source 0 \
  --course "CS-Lab" \
  --min-sim 0.35 \
  --min-agree 5
```

| Flag | Meaning |
|---|---|
| `--source 0` | Webcam index (try `1` if `0` doesn't open) |
| `--course` | Label stored with the session in the database |
| `--min-sim` | Minimum cosine similarity to count as a match (0–1). Raise if you see false positives. |
| `--min-agree` | How many matching frames in the vote window before marking attendance |

**Keyboard shortcuts during the session:**

| Key | Action |
|---|---|
| `s` | Save a snapshot of the current frame to `data/raw/snapshots/` |
| `q` | Quit and close the session |

Each recognized student is marked **once per session** in the database.  
A per-frame log is written to `data/logs/recognition_frames.csv`.

### Running without saving to the database (test mode)

```bash
python src/run_recognition.py --source 0 --no-db
```

---

## 4. Exporting attendance records

### CSV export (command line)

```bash
python src/export_attendance_report.py
```

Exports all sessions. Reports are saved to `data/reports/`.

Export a specific session only:
```bash
python src/export_attendance_report.py --session-id 3 --out data/reports/session3.csv
```

---

## 5. Web portal

The web portal gives admins and students a browser-based interface.

### 5.1 Configure and start the server

Copy the example environment file and fill in your values:
```bash
cp .env.example .env
```

Open `.env` and set:
```
SECRET_KEY=use-a-long-random-string-here
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=your-secure-password
```

Start the server:
```bash
python -m uvicorn web_app:app --app-dir src --host 127.0.0.1 --port 8000
```

Open your browser at `http://127.0.0.1:8000/login`.

### 5.2 Admin workflow

1. Sign in with the email and password you set in `.env`.
2. From the **Admin home** screen:
   - **Enroll a new student** — provide student details and capture four webcam poses; the system creates their gallery template and login account.
   - **Review daily attendance** — browse submitted selfies and approve or reject them.
   - **Export CSV** — download all attendance records as a spreadsheet.
   - **Live session** — start a legacy live recognition session from the browser (Week 3 flow).

### 5.3 Student workflow

1. Sign in with the email and password the admin created for you.
2. From the **Student home** screen, click **Submit attendance**.
3. Allow camera access — the browser captures a frame, sends it to the server, and records your submission.
4. You will see a confirmation message if your face is recognized.

### 5.4 Quick attendance (no login required)

Open `http://127.0.0.1:8000/quick-attendance` (or click the link on the login page).  
The browser camera sends one frame; the server responds with a greeting if a match is found.  
This does **not** submit official attendance — students still need to sign in for that.

---

## 6. Checking a single photo (one-shot match)

To test whether a photo matches any enrolled student:

```bash
python src/match_face.py --probe data/raw/some_face.jpg --k 5
```

Prints the top-5 matches with cosine similarity scores.

---

## 7. Evaluation (measuring accuracy)

Prepare a labeled test set:
```
data/eval/
  123456789/
    test1.jpg
    test2.jpg
  987654321/
    test1.jpg
```

Folder names must match the enrolled `student_id` values.

Run the evaluation:
```bash
python src/evaluate_recognition.py --dataset data/eval --gallery-root data/embeddings
```

Generate a full report (JSON + Markdown):
```bash
python src/run_eval_report.py
```

Reports land in `data/reports/evaluation_metrics.json` and `data/reports/evaluation_report.md`.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| Camera does not open | Try `--source 1` or `--source 2`; check OS camera permissions (macOS: System Settings → Privacy → Camera) |
| `ModuleNotFoundError` | Make sure the virtual environment is active and you ran `pip install -r requirements.txt` |
| InsightFace download fails | Check internet connection; models are cached under `~/.insightface/models/` after first download |
| Gallery is empty / enroll fails | Verify that `data/raw/<STUDENT_ID>/` contains `.jpg` or `.png` files; add `-v` flag to `enroll.py` for verbose output |
| Too many false positives | Raise `--min-sim` (e.g. `0.45`) and/or raise `--min-agree` |
| Too many missed faces | Lower `--min-sim` (e.g. `0.28`) and re-enroll with more varied photos |
| Portal login fails | Confirm `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` are set **before** first launch when the `users` table is empty |
| Student not recognized in portal | Re-enroll the student using `enroll_augmented.py` with better photos |

---

## 9. Key file locations

| Item | Path |
|---|---|
| Student photos | `data/raw/<student_id>/` |
| Face templates (gallery) | `data/embeddings/templates/` |
| Attendance database | `data/attendance.db` |
| Per-frame recognition log | `data/logs/recognition_frames.csv` |
| Exported attendance CSVs | `data/reports/` |
| Webcam snapshots | `data/raw/snapshots/` |
| Evaluation reports | `data/reports/evaluation_report.md` |
