# Presentation Generator — Prompts for Claude
### AI-Based Facial Recognition Attendance System
**Team:** Ahmad Rajab (230408916) · Abdallatif Al Afandi (220408911)

This file gives you (1) a **MASTER PROMPT** that generates the whole slide deck in one go, and
(2) **per-slide prompts** to generate/refine slides individually. Paste them into Claude
(use the Artifacts / "design" feature and ask for an HTML/React slide deck or a downloadable file).

> **Brand look to request:** primary teal `#0f766e` (deep) / `#2dd4bf` (bright accent),
> ink `#18202b`, light bg `#f6f7f9`, surfaces white; clean sans-serif; rounded cards; subtle
> shadows; a scanning-face motif. Offer a **dark variant** (bg `#0e1217`, surface `#161c24`,
> text `#e8edf4`). 16:9. Minimal text per slide + speaker notes.

---

## ✅ MASTER PROMPT (paste this whole block)

> You are a senior presentation designer. Create a **professional 16:9 graduation-project slide
> deck** as a single self-contained HTML file (inline CSS, no external assets; each slide a full
> 1280×720 section; include simple keyboard arrow navigation and a slide counter). Also add concise
> **speaker notes** under each slide (collapsible or as HTML comments).
>
> **Visual style:** modern, clean, lots of white space, rounded cards, soft shadows. Brand colors:
> deep teal `#0f766e`, bright teal accent `#2dd4bf`, ink `#18202b`, light background `#f6f7f9`,
> white surfaces. Use a face-scan / biometric motif (a stylized face inside scan brackets) on the
> title and section slides. Use icons (inline SVG) for features. Keep ≤6 bullet points per slide.
>
> **Project facts to use (accurate — do not invent):**
> - Title: **AI-Based Facial Recognition Attendance System**. Live at **https://attendance.cloud**.
> - Team: **Ahmad Rajab (230408916)** and **Abdallatif Al Afandi (220408911)**.
> - Purpose: mark class attendance by face in ~1–2s and **block cheating** (printed photos / phone
>   screen replays).
> - AI: **InsightFace `buffalo_l`** — RetinaFace detector + **ArcFace** recognizer producing
>   **512-D embeddings**; matched by **cosine similarity**; per-student template = mean of **4
>   enrollment angles**. Runs as **ONNX** on **CPU** (no GPU).
> - Anti-spoofing: a **trained passive liveness model** (3 classes: live / print / replay, 128×128,
>   ONNX, CPU). Plus a **minimum-face-size gate** that forces a spoof phone close, where it's
>   reliably caught. Plus **duplicate-face prevention** at registration (one face = one account),
>   and **mask/glasses flagging**.
> - Stack: **Python 3.11, FastAPI, Uvicorn, Jinja2** server-rendered UI, **SQLite**, **bcrypt**
>   passwords, signed session cookies, **SlowAPI** rate limiting, **OpenCV/NumPy**.
> - Deployment: **AlmaLinux 9 VPS**, **OpenLiteSpeed (CyberPanel)** reverse proxy → Uvicorn on
>   127.0.0.1:8123, **systemd** service (auto-restart/boot), **Let's Encrypt** HTTPS, HTTP→HTTPS
>   redirect.
> - Features: admin portal (dashboard, classes, sessions, **review queue** with filters, analytics,
>   audit CSV, student CRUD), student portal (submit attendance, history, support), **kiosk quick
>   attendance** (no login, secured by liveness+identity), **support tickets**, **admin
>   announcements**, **light/dark theme**, responsive.
> - Why better than alternatives: top-tier accuracy that is **free, offline, private** (vs paid
>   cloud APIs that send faces away), **no GPU/special hardware** (vs IR/depth), and **real
>   anti-spoofing** (vs weak heuristics) — and it's **actually deployed**, not a localhost demo.
>
> **Deck outline (one slide each):** 1) Title + team + live URL. 2) The problem with traditional
> attendance. 3) Our solution (one-line + 3 pillars: recognize, verify-live, manage). 4) Live demo
> screenshot placeholder. 5) System architecture diagram (browser → OpenLiteSpeed/TLS → Uvicorn/
> FastAPI → {Face engine, Liveness, SQLite}). 6) How face recognition works (detect → embed 512-D →
> cosine match), with a simple visual. 7) Enrollment (4 angles → mean template) + duplicate-face
> prevention. 8) Anti-spoofing deep-dive (live/print/replay + the size-gate insight we discovered).
> 9) Security overview (bcrypt, HTTPS, signed sessions, rate limit, audit, review queue). 10)
> Technology stack (logos/labels grid). 11) Technology comparison table (InsightFace vs OpenCV/dlib/
> cloud; trained liveness vs heuristics/hardware; FastAPI vs Flask/Django; SQLite vs MySQL). 12) Why
> our system is better (5 points). 13) Features tour (admin/student/kiosk). 14) Deployment (VPS,
> reverse proxy, systemd, TLS). 15) Testing & results (heuristics failed → trained model + size gate
> verified by logs). 16) Limitations & future work. 17) Conclusion + thank-you + Q&A.
>
> Generate the full HTML deck now. Make the title and section slides visually striking with the
> scan-face motif.

---

## 🎯 Per-slide prompts (to generate or refine one slide at a time)

**Slide 1 — Title.** "Design a striking 16:9 title slide: big title *AI-Based Facial Recognition
Attendance System*, subtitle *Graduation Project*, the live URL **attendance.cloud**, and the team
**Ahmad Rajab (230408916)** & **Abdallatif Al Afandi (220408911)**. Center a stylized glowing face
inside scan brackets on a deep-teal gradient. Brand teal `#0f766e`/`#2dd4bf`."

**Slide 2 — Problem.** "Slide titled *The Problem*. Show 4 pain points of traditional attendance:
slow roll-call, forgeable sign-ins, proxy/'buddy' attendance, hard to audit. Use icons + one short
line each. Calm, professional."

**Slide 3 — Our Solution.** "Slide *Our Solution*: one bold sentence — *mark attendance by face in
seconds while blocking photo/screen cheating.* Then 3 pillars as cards: **Recognize** (ArcFace),
**Verify Live** (anti-spoof), **Manage** (classes, review, analytics)."

**Slide 4 — Live Demo.** "A 'Live Demo' slide with a browser frame placeholder (I'll drop a
screenshot of attendance.cloud), and 3 demo steps: show face → recorded present → phone replay
blocked."

**Slide 5 — Architecture.** "Draw a clean top-down architecture diagram: Browser (HTTPS) →
OpenLiteSpeed (TLS + reverse proxy) → Uvicorn/FastAPI → three boxes: InsightFace face engine
(ONNX), Liveness/anti-spoof (ONNX), SQLite DB. Label the loopback :8123. Minimal, labeled arrows."

**Slide 6 — How recognition works.** "Explain face recognition simply in 3 steps with a visual:
(1) Detect face (RetinaFace), (2) Embed into a 512-number vector (ArcFace), (3) Compare by cosine
similarity. Show two vectors close = same person, far = different."

**Slide 7 — Enrollment.** "Slide *Enrollment & One-Face-One-Account*: 4 angle thumbnails
(upper/left/right/lower) → averaged into one template. Add a callout: duplicate-face check rejects a
second account for the same face."

**Slide 8 — Anti-spoofing (key slide).** "Slide *Stopping the Cheaters*. Show the trained liveness
model classifying **live / print / replay**. Then highlight our engineering insight: small/distant
faces fooled the model, so we added a **minimum-face-size gate** that forces the spoof close where
it's caught — verified by logs (live≈0.95 on tiny crops vs print≈0.83 when large). Make the insight
visually prominent."

**Slide 9 — Security.** "Slide *Security & Trust*: bcrypt password hashing, HTTPS everywhere, signed
session cookies, rate limiting, audit log, and an admin review queue for uncertain cases. Icon grid."

**Slide 10 — Tech stack.** "A tidy labeled grid of the stack: Python 3.11, FastAPI, Uvicorn, Jinja2,
SQLite, ONNX Runtime, InsightFace/ArcFace, OpenCV, bcrypt, OpenLiteSpeed, systemd, Let's Encrypt.
Group by layer (App / AI / Data / Deploy)."

**Slide 11 — Comparison table.** "A comparison table slide. Rows: Face engine (InsightFace/ArcFace
vs OpenCV LBPH vs dlib vs Cloud API), Anti-spoof (trained model vs heuristics vs IR hardware), Web
framework (FastAPI vs Flask vs Django), Database (SQLite vs MySQL). Mark our choice with a teal
check and a one-line reason each."

**Slide 12 — Why we're better.** "Slide *Why Our System Wins* with 5 points: (1) actually stops
cheating, (2) private & offline AI, (3) zero running cost, (4) really deployed on HTTPS, (5) complete
product. Bold, confident."

**Slide 13 — Features.** "Feature tour slide split into Admin / Student / Kiosk columns with 4–5
icon bullets each (classes, sessions, review queue, analytics, audit, exports / submit attendance,
history, support / face-kiosk present)."

**Slide 14 — Deployment.** "Slide *Real Deployment*: AlmaLinux 9 VPS, OpenLiteSpeed reverse proxy,
Uvicorn + systemd (auto-restart), Let's Encrypt TLS, public domain attendance.cloud. Small server/
cloud icons."

**Slide 15 — Testing & results.** "Slide *Testing & Results*: heuristic anti-spoof failed phone
replays → integrated trained model → found small-face bypass via logs → added size gate → verified
fixed. Plus pytest unit/integration tests and full end-to-end checks."

**Slide 16 — Limitations & future.** "Two columns: *Limitations* (single-frame liveness edge cases,
mask/glasses flagged-not-blocked, SQLite single-institution) and *Future Work* (active blink/turn
liveness, mobile app + push, timetable integration, PostgreSQL + GPU for large halls)."

**Slide 17 — Thank you / Q&A.** "Closing slide: large *Thank You*, the live URL attendance.cloud,
both team members with IDs, and *Questions?* with the scan-face motif."

---

## 🗣️ Optional: ask Claude for speaker notes
After the deck is generated, paste: *"For each slide, add 3–4 sentences of speaker notes I can read
aloud in ~30–45 seconds, in simple confident English."*

## 🖼️ Screenshots to capture and drop into the deck
- Login page (scan-face), Admin dashboard (stat cards), Open session, Quick-attendance recording a
  pass, a **phone replay being blocked**, the Review queue with a flagged row, dark mode.
