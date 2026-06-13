# AI-Based Facial Recognition Attendance System
## Graduation Project — Full Technical Report (A → Z)

**Live system:** https://attendance.cloud
**Team:**
- **Ahmad Rajab** — 230408916
- **Abdallatif Al Afandi** — 220408911

---

## 1. Executive summary

We built a complete, production-deployed **facial-recognition attendance system** that lets
students mark class attendance with their face instead of signatures, cards, or codes.
It is not a demo on a laptop — it is a real web application running on a public domain
(`attendance.cloud`) over HTTPS, with an admin portal, a student portal, a face-recognition
AI pipeline, and a **trained anti-spoofing (liveness) defense** that blocks students from
cheating with a photo or a phone screen.

Key outcomes:
- **Contactless, fast attendance** — a student shows their face and is marked present in ~1–2 seconds.
- **Anti-cheating** — a trained liveness model rejects printed photos and phone/laptop screen replays; a minimum-face-size rule forces the spoof close where it is reliably caught; one person can never hold two accounts (duplicate-face check at registration).
- **Full management** — classes, enrollments, sessions, a review queue, analytics, audit log, CSV export, support tickets, and admin announcements.
- **Real deployment** — reverse-proxied behind OpenLiteSpeed, kept alive by systemd, secured with Let's Encrypt TLS.

---

## 2. Problem statement & objectives

**Problem.** Traditional attendance (paper sign-in, RFID cards, PIN codes) is slow, easy to forge
(proxy/"buddy" attendance), and hard to audit. Manual roll-call wastes class time and produces
error-prone records.

**Objectives.**
1. Recognize a student's identity from their face reliably and quickly.
2. Stop the most common cheat: a student marking a friend present using a **photo or phone video**.
3. Tie attendance to real **classes and sessions**, with an admin able to open/close sessions and review/override records.
4. Keep an **audit trail** and give the admin **analytics and exports**.
5. Deploy it as a **real, secure web service** anyone can reach from a browser.

---

## 3. System overview — what it does

### Roles
- **Admin** — creates students (with 4-angle face enrollment), manages classes & rosters, opens/closes attendance sessions, reviews flagged submissions, sees analytics & audit, exports CSV, posts announcements, answers support tickets.
- **Student** — signs in, submits attendance for an open session with a selfie, views their attendance history, opens support tickets, reads announcements.
- **Kiosk / Quick attendance (public)** — a shared screen where a student shows their face and is recorded present in their open class — no login, secured by the liveness + identity checks.

### Core features
| Area | Feature |
| --- | --- |
| Enrollment | 4-angle guided face capture (upper/left/right/lower), live face detection, duplicate-face rejection |
| Recognition | ArcFace 512-D embeddings, cosine matching against a per-student gallery template |
| Attendance | Per-session daily attendance, auto-approve when clean, else queued for admin review |
| Anti-spoof | Trained print/replay liveness model + minimum-face-size gate; mask & glasses flags |
| Admin | Dashboard, classes, sessions, review queue (with filters), analytics, audit CSV, student CRUD |
| Communication | Student↔admin support tickets (topics, statuses), admin-only announcements |
| Platform | Light/dark theme, responsive UI, server-rendered pages, live polling |

---

## 4. Architecture

```
                          Browser (student / admin / kiosk)
                                     │  HTTPS
                                     ▼
        ┌───────────────────────────────────────────────────┐
        │  OpenLiteSpeed (CyberPanel)  — public :443/:80     │
        │  • TLS termination (Let's Encrypt)                 │
        │  • HTTP→HTTPS redirect                              │
        │  • Reverse proxy  /  →  127.0.0.1:8123             │
        └───────────────────────────────────────────────────┘
                                     │  (loopback)
                                     ▼
        ┌───────────────────────────────────────────────────┐
        │  Uvicorn (ASGI)  ·  systemd service attendance     │
        │  ┌──────────────  FastAPI app  ──────────────────┐ │
        │  │ Routing · Sessions · Rate limit · Templates    │ │
        │  │ Portal logic (admin/student/kiosk/support)     │ │
        │  └────────────────────────────────────────────────┘ │
        │        │                 │                  │        │
        │        ▼                 ▼                  ▼        │
        │   Face engine       Liveness/anti-      SQLite DB    │
        │   InsightFace       spoof (ONNX)        attendance   │
        │   buffalo_l         + mask/glasses      .db          │
        │   (ONNX Runtime)                                     │
        └───────────────────────────────────────────────────┘
```

**Request flow for attendance:** browser captures a selfie → POST to FastAPI →
detect face (RetinaFace) → **liveness check (live/print/replay + size gate)** →
identity match (ArcFace cosine vs the student's enrolled template) → mask/glasses flags →
write a `daily_attendance` row (auto-approved or pending review) → admin & student see it.

---

## 5. Technology stack (and the role of each piece)

| Layer | Technology | Why it's here |
| --- | --- | --- |
| Language | **Python 3.11** | First-class AI/CV ecosystem; the face models are Python-native |
| Web framework | **FastAPI** | Async, fast, type-validated forms/uploads, tiny boilerplate |
| ASGI server | **Uvicorn** (uvloop/httptools) | High-performance async server that runs FastAPI |
| Web/proxy | **OpenLiteSpeed (CyberPanel)** | Public TLS endpoint + reverse proxy to the app |
| Templating | **Jinja2** (server-rendered) | Simple, SEO-/no-JS-friendly pages; no SPA complexity |
| Sessions | **Starlette SessionMiddleware** + `itsdangerous` | Signed, tamper-proof cookies; "remember me" |
| Passwords | **bcrypt** | Slow, salted password hashing (industry standard) |
| Rate limiting | **SlowAPI** | Throttles login/attendance/support endpoints |
| Face detection + recognition | **InsightFace `buffalo_l`** | RetinaFace detector + ArcFace recognizer (state-of-the-art, free) |
| Model runtime | **ONNX Runtime (CPU)** | Runs all models fast on a CPU-only VPS — no GPU needed |
| Anti-spoof / liveness | **hairymax/Face-AntiSpoofing** (ONNX, MIT) | Trained 3-class live/print/replay detector |
| Image processing | **OpenCV**, **NumPy** | Decode, crop, align, letterbox, math on embeddings |
| Database | **SQLite** | Zero-admin, file-based, perfect for this scale; ACID |
| Data/exports | **pandas** | CSV/report generation |
| Process mgmt | **systemd** | Auto-start on boot, auto-restart on crash |
| TLS | **Let's Encrypt** | Free automated HTTPS certificates |
| Testing | **pytest**, **httpx** | Unit/integration tests |

### The AI pipeline in detail
1. **Detection** — RetinaFace (`det_10g.onnx`) finds the largest face and its bounding box + 5 keypoints.
2. **Alignment & embedding** — ArcFace (`w600k_r50.onnx`) maps the aligned face to a **512-dimensional unit vector** (an "embedding"). Same person → vectors point the same way; different people → far apart.
3. **Enrollment** — at registration we capture **4 angles**, embed each, and store the **mean, L2-normalized embedding** as that student's gallery template (`data/embeddings/`).
4. **Matching** — a new selfie's embedding is compared to templates with **cosine similarity**; above a threshold (≈0.35 to recognize, ≥0.50 to auto-approve) it's a match.
5. **Liveness / anti-spoof** — the face crop (enlarged 1.5×, letterboxed to 128×128) is fed to the trained model, which outputs `live / print / replay` probabilities. We accept only **live AND large-enough** faces (a minimum-face-size gate, because tiny crops are too low-res for the model to see screen artifacts).
6. **Mask / glasses** — flagged for the admin's awareness (they reduce recognition reliability).

---

## 6. Security & anti-cheating (the heart of the project)

| Threat | Defense |
| --- | --- |
| Photo / printed face | **Trained liveness model** classifies it as `print` and blocks it |
| Phone / laptop **screen replay** | Same model classifies it as `replay`; the **min-face-size gate** forces the spoof close, where the model reliably catches it |
| One student, two accounts | **Duplicate-face check at registration** rejects a face already enrolled (cosine ≥ 0.5) |
| Marking a friend present | Attendance is matched **against that student's own template**, not just "any known face" |
| Password theft | **bcrypt** hashes; never stored in plaintext |
| Session forgery | **Signed** session cookies (`itsdangerous`); tampering invalidates them |
| Eavesdropping | **HTTPS everywhere** + forced HTTP→HTTPS redirect |
| Brute force / spam | **Rate limiting** on login, attendance, support |
| Disputes / accountability | **Audit log** of logins, attendance, reviews, registrations |
| Bad auto-decisions | Borderline cases (low similarity, mask, glasses, liveness uncertain) go to an **admin review queue**, not auto-approved |

---

## 7. Data model (SQLite)

- `students` — id, student_id (number), name, email
- `users` — login accounts (email, **bcrypt** hash, role admin/student, link to student)
- `enrollment_faces` — the 4 saved enrollment images per student
- `classes`, `class_enrollments` — classes and their rosters
- `sessions` — an open/closed attendance window for a class
- `daily_attendance` — each submission: photo, time, status, **identity_similarity**, **spoof_risk/score**, **liveness_label**, **mask_flag/glasses_flag**, session link
- `audit_events` — security/audit trail
- `support_threads`, `support_messages` — student↔admin tickets
- `group_messages` — admin announcements

Face **templates** (embeddings) live as files under `data/embeddings/` (manifest + `.npy` per student).

---

## 8. Deployment (how it actually runs)

- **Host:** AlmaLinux 9 VPS.
- **App:** Uvicorn serving FastAPI on `127.0.0.1:8123`, managed by a **systemd** unit (`attendance.service`) — starts on boot, restarts on crash, runs as a non-root user.
- **Web server:** **OpenLiteSpeed** (via CyberPanel) terminates TLS on the public domain and **reverse-proxies** all traffic to the app; HTTP is **301-redirected to HTTPS**.
- **TLS:** Let's Encrypt certificate for `attendance.cloud`.
- **AI models:** InsightFace `buffalo_l` and the anti-spoof ONNX model are cached on disk and loaded once into memory (singleton), so requests are fast.

---

## 9. Technology comparison & justification

### 9.1 Face recognition engine — **InsightFace (ArcFace)** vs alternatives
| Option | Verdict |
| --- | --- |
| **OpenCV LBPH / Haar / Eigenfaces** (classic) | Easy but weak — poor accuracy, sensitive to lighting/pose; not viable for real identity |
| **dlib / face_recognition** | Good and popular, but older ResNet embeddings; lower accuracy than ArcFace and slower on CPU |
| **FaceNet (Google)** | Strong, but no maintained free pretrained pipeline as clean as InsightFace; more glue code |
| **Cloud APIs** (AWS Rekognition, Azure Face, Face++) | Accurate but **per-call cost**, **internet dependency**, and **privacy concern** (student faces leave the building); vendor lock-in |
| **InsightFace `buffalo_l` (ArcFace) — chosen** | **State-of-the-art accuracy**, **free & offline**, ONNX models run on CPU, includes detector + recognizer + landmarks in one pack |

**Why ours is better:** top-tier accuracy with **zero per-use cost**, **no data leaves our server** (privacy), and **no GPU required**.

### 9.2 Anti-spoofing — **trained passive liveness** vs alternatives
| Option | Verdict |
| --- | --- |
| **Heuristics only** (blur, moiré, edges) — our first version | Cheap but **easily fooled** by a sharp phone replay (we proved this in testing) |
| **Special hardware** (IR / depth / 3D cameras) | Very strong but **expensive**, not usable from an ordinary laptop/phone webcam |
| **Active challenge** (blink/turn on command) | Robust but slower and changes the UX; can be defeated by a video |
| **Trained passive RGB model (chosen)** | Detects print & screen replays from a **single ordinary photo**, on CPU, in real time |

**Why ours is better:** real protection on **commodity webcams**, no extra hardware, and we **engineered around the model's weak spot** (small faces) with a minimum-face-size gate that forces the attacker into the range where detection is reliable — a genuine, tested improvement, not a textbook copy.

### 9.3 Web framework — **FastAPI** vs Flask / Django
- **Flask:** minimal but no built-in async, validation, or typed request handling — more manual work.
- **Django:** powerful but heavy (ORM, admin, migrations) and overkill for an API-first, AI-centric app.
- **FastAPI (chosen):** async (handles slow CV work better), automatic request/file validation, very fast, small codebase.

### 9.4 Database — **SQLite** vs MySQL / PostgreSQL
- For one institution's scale, **SQLite** is ACID-compliant, needs **zero server/admin**, is a single portable file (easy backup), and is plenty fast. MySQL/Postgres add operational overhead with no benefit here — and the code can migrate to them later if needed.

### 9.5 Model runtime — **ONNX Runtime** vs PyTorch / TensorFlow
- Running full PyTorch/TF on a CPU VPS is heavy. **ONNX Runtime** loads the same models as lightweight, optimized graphs — **smaller footprint, faster CPU inference, no GPU**.

### 9.6 Frontend — **server-rendered Jinja2** vs React/Vue SPA
- An SPA adds a build pipeline, a second codebase, and SEO/no-JS issues. **Server-rendered pages** are simpler, load fast, work without heavy JS, and we still add **live polling** (announcements, support, attendance) where it matters.

---

## 10. Why this system is better overall
1. **It actually stops cheating** — a trained liveness model + a size gate + per-student identity matching + duplicate-face prevention, all verified by real phone-replay tests.
2. **Private & offline AI** — all face data and inference stay on our server; nothing is sent to a paid cloud.
3. **Zero running cost** — free models, free DB, free TLS, CPU-only.
4. **Truly deployed** — public HTTPS domain, auto-restarting service, not a localhost demo.
5. **Complete product** — enrollment, attendance, review, analytics, audit, exports, support, announcements, dark mode, mobile-responsive.
6. **Engineered, not assembled** — we diagnosed real failures (e.g., small-face spoof bypass) and fixed them with measured thresholds.

---

## 11. Testing & verification
- **Unit/integration tests** with pytest (identity verification, duplicate-face logic, routes).
- **Live anti-spoof testing** — confirmed via logs that the model catches a phone replay when the face is large (e.g., p(print)=0.83) and that the **size gate** closes the small-face bypass.
- **End-to-end checks** of every flow (enrollment, attendance, review, kiosk, support, announcements) against the deployed site.

---

## 12. Limitations & future work
- **Single-frame passive liveness** can theoretically be challenged by a very high-quality, large screen held close; future: add an optional **active blink/turn challenge** and **multi-frame** checks.
- **Mask/glasses** are flagged but not yet blocked; could become configurable.
- **SQLite** suits one institution; multi-campus scale would move to PostgreSQL.
- Future: mobile app, push notifications, timetable integration, GPU batch recognition for large halls.

---

## 13. How to study / run it (quick study guide)
- **Entry point:** `src/web_app.py` builds the FastAPI app; routes live in `src/portal_router.py`.
- **AI:** `src/face_engine.py` (InsightFace + gallery), `src/attendance_identity.py` (1:1 verify), `src/face_checks.py` (liveness/mask/glasses), `src/quick_recognition.py` (1:N kiosk).
- **Accounts/enrollment:** `src/portal_students.py`, `src/auth_passwords.py`.
- **DB schema:** `src/init_db.py`.
- **Templates/UI:** `templates/`, `static/css/app.css`, `static/js/`.
- **Run locally:** create venv → `pip install -r requirements.txt` → `python src/init_db.py` → `uvicorn web_app:app --app-dir src`.

**One-line pitch for the jury:** *"A real, deployed facial-recognition attendance system that uses
state-of-the-art ArcFace recognition and a trained liveness model to mark students present in
seconds while blocking photo and phone-screen cheating — all running privately on our own server
with no paid cloud and no special hardware."*
