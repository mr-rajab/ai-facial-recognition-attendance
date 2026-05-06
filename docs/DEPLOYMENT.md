# Deployment notes

## Threat model (course prototype)

This project is a **local prototype**. It is **not** hardened for public internet exposure. Treat embeddings (`data/embeddings/`), raw images (`data/raw/`), and SQLite (`data/attendance.db`) as **sensitive**.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Signs session cookies for the FastAPI portal. Use a long random value in any shared environment. |
| `BOOTSTRAP_ADMIN_EMAIL` | When the `users` table is empty, the app creates the first **admin** account with this email on startup. |
| `BOOTSTRAP_ADMIN_PASSWORD` | Password for that first admin (remove from `.env` after bootstrap if you prefer). |
| `HOST`, `PORT` | Optional bind for `python src/web_app.py` (defaults `127.0.0.1:8000`). |
| `RATE_LIMIT_ENABLED` | Set to `0` to disable SlowAPI limits (e.g. some test environments). Default on. |

See `.env.example`.

## Production checklist (beyond local demos)

- **TLS:** Terminate HTTPS at nginx/Caddy; set `https_only=True` on `SessionMiddleware` when cookies must never go over cleartext.
- **Secrets:** Strong `SECRET_KEY`; rotate if leaked; never commit `.env`.
- **Rate limits:** Keep defaults for `POST /login`, `POST /student/attendance`, and `POST /api/quick-attendance`; tune in `portal_router.py` / env if needed.
- **Backups:** Run `bash scripts/backup_portal_data.sh` on a schedule (cron); verify restore on a copy at least once.
- **Process:** Run as a non-root user; restrict file permissions on `data/` and `backups/`.
- **Review:** Use **Admin → Analytics & audit log** for incident review; CSV exports include `identity_similarity`, `reject_reason`, and `photo_sha256`.

You can `export $(grep -v '^#' .env | xargs)` before starting the server (only if you understand the file contents).

## Running the web UI

From `the_project/`:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export BOOTSTRAP_ADMIN_EMAIL='you@university.edu'
export BOOTSTRAP_ADMIN_PASSWORD='...'
python src/web_app.py
```

Then open `/login`, sign in as admin, and create student accounts from the dashboard. Students use the email and password you set for them.

Bind to all interfaces **only** on a trusted network:

```bash
HOST=0.0.0.0 PORT=8000 python src/web_app.py
```

Place a reverse proxy (nginx, Caddy) with TLS in front for anything beyond local demos.

## Secure storage

- Keep the repo **private** or add `.gitignore` rules for `data/embeddings/`, `data/raw/`, `*.db`, and `.env`.  
- Back up `data/attendance.db` if you rely on it for grading evidence.  
- Do not commit real student photos to public Git hosting.

## Smoke test

```bash
bash scripts/smoke_integration.sh
```

## Hardware

- **CPU:** `onnxruntime` CPUExecutionProvider (default).  
- **GPU:** install `onnxruntime-gpu` matching your CUDA version and adjust `FaceEngine` providers in `face_engine.py` if you extend the project for GPU inference.
