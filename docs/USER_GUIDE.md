# User guide — AI facial recognition attendance

## What you need

- Python 3.10–3.12 recommended
- Webcam (for live capture / recognition)
- Disk space for InsightFace models (downloaded once under `~/.insightface/models/`)

## Typical workflow

1. **Create environment** (from `the_project/`):

   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Initialize database**

   ```bash
   python src/init_db.py
   ```

3. **Collect face photos** per student (several clear frontal images). Either:

   - `python src/capture_frames.py` and press **`s`** to save to `data/raw/`, or  
   - Copy photos into `data/raw/<STUDENT_ID>/`.

4. **Enroll** each student into the embedding gallery:

   ```bash
   python src/enroll.py --student-id 230408916 --name "Your Name" --images-dir data/raw/230408916 --sync-db
   ```

   For more robust templates (recommended after baseline works):

   ```bash
   python src/enroll_augmented.py --student-id 230408916 --name "Your Name" --images-dir data/raw/230408916 --sync-db
   ```

5. **Run a class session** (live recognition + attendance):

   ```bash
   python src/run_recognition.py --source 0 --course "CS-Lab" --min-sim 0.35 --min-agree 5
   ```

   - **`q`** quit  
   - **`s`** save a snapshot to `data/raw/snapshots/` (mirrored preview, same as on screen)

6. **Export CSV** (CLI):

   ```bash
   python src/export_attendance_report.py
   ```

7. **Web portal** (review in browser):

   Easiest: `cp .env.example .env`, edit `SECRET_KEY` and `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`, then:

   ```bash
   python -m uvicorn web_app:app --app-dir src --host 127.0.0.1 --port 8000
   ```

   (`web_app` auto-loads `.env` from the project folder.)

   Alternatively, `export` those variables in the **same** terminal session, then run uvicorn or `python src/web_app.py`.

   Open `http://127.0.0.1:8000/login`. The bootstrap admin signs in with that email and password, enrolls students (four webcam poses + student credentials), reviews daily attendance photos, and can export all records as CSV. Students sign in with their own email and password and submit daily attendance from the student home page. Legacy live-session pages (Week 3) remain available to admins from the admin home screen.

## Evaluation (Week 4)

Prepare `data/eval/<student_id>/*.jpg` where folder names match enrolled `student_id` strings, then:

```bash
python src/evaluate_recognition.py --dataset data/eval --gallery-root data/embeddings
python src/run_eval_report.py
```

Reports land in `data/reports/`.

## Troubleshooting

- **Gallery empty / enroll fails:** see README; verify image paths exist and contain `.jpg`/`.png`. Use `python src/enroll.py ... -v`.  
- **False accepts / rejects:** tune `--min-sim`, `--min-agree`, and re-enroll with better photos.  
- **Portal login fails:** ensure `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` are set when the database has **no** users yet (first start), or sign in with an account that already exists in the `users` table. If you pasted several `export` commands on one line without `;`, the shell may only have run the last one.
