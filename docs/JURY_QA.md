# Presentation Day — Jury Q&A Preparation
### AI-Based Facial Recognition Attendance System
**Team:** Ahmad Rajab (230408916) · Abdallatif Al Afandi (220408911)

Below are 20 questions the jury is likely to ask, each with a confident, accurate answer
based on **our actual system**. Read these out loud until they feel natural.

---

**Q1. In one sentence, what is your project?**
A real, deployed web system that marks student attendance using face recognition and blocks
cheating (photos/phone screens) with a trained anti-spoofing model — running privately on our
own server with no paid cloud and no special hardware.

**Q2. How does the face recognition actually work?**
We use InsightFace's `buffalo_l` pack. A RetinaFace detector finds the face; an ArcFace model
turns it into a 512-dimensional "embedding" (a numeric fingerprint). At registration we average
4 angles into one template per student. To recognize, we embed the new selfie and compare with
**cosine similarity** — close vectors mean the same person.

**Q3. What is an embedding, in simple terms?**
A list of 512 numbers describing a face. The same person's photos produce vectors that point in
nearly the same direction; different people point in different directions. We measure the angle
between them (cosine similarity).

**Q4. A student showed a friend's photo on a phone — how do you stop that?**
A trained liveness model (3-class: live / print / replay) inspects the face crop and classifies a
screen as `replay` and a printed photo as `print`, so it's rejected. We also require a **minimum
face size**: a small/distant face is too low-resolution for the model to see screen artifacts, so
we refuse it ("move closer"). That forces the cheater to bring the phone close — exactly where the
model reliably catches it. We tested and confirmed this with logs.

**Q5. Why not just use the blur/edge heuristics you started with?**
We did first, and we proved in testing they fail — a sharp, well-framed phone replay passed as
"low risk." Heuristics can't reliably tell a real face from a high-quality screen. A trained model
learns the actual texture/reflection cues, so it's far stronger.

**Q6. Why InsightFace instead of OpenCV face recognition, dlib, or a cloud API?**
OpenCV's classic methods (LBPH/Eigenfaces) are inaccurate and lighting-sensitive. dlib is decent
but older and slower on CPU. Cloud APIs (AWS/Azure/Face++) cost money per call, need internet, and
send student faces to a third party — a privacy problem. InsightFace's ArcFace is state-of-the-art,
**free, offline, and runs on CPU**.

**Q7. Do you need a GPU?**
No. All models run as optimized **ONNX** graphs on the CPU via ONNX Runtime, fast enough for
real-time attendance on an ordinary VPS.

**Q8. What's your recognition accuracy / threshold?**
ArcFace is highly accurate on standard benchmarks. In our system we use a cosine threshold around
**0.35 to recognize** and require **≥0.50 to auto-approve**; anything in between goes to admin
review. Thresholds are configurable via environment variables so we can tune precision vs recall.

**Q9. How do you prevent one person from registering twice (or as someone else)?**
At registration we embed the new face and compare it to every enrolled template. If it matches an
existing student above 0.5, we **refuse the new account** and name the match. So one face = one
account.

**Q10. How is attendance tied to a real class?**
The admin creates classes, enrolls students, and **opens a session** (an attendance window). A
student can only submit for an open session they're enrolled in, and only **once** per session
(duplicate-protected). The kiosk page records into the same table.

**Q11. What happens when the system isn't sure?**
It does **not** auto-approve. Low similarity, detected mask/glasses, or uncertain liveness send the
record to the admin **review queue** as "pending," where a human approves or rejects it. Safety over
convenience.

**Q12. Where is the data stored and is it secure?**
In a local **SQLite** database on our server. Passwords are **bcrypt**-hashed, sessions are
**signed** cookies, all traffic is **HTTPS**, endpoints are **rate-limited**, and we keep an
**audit log**. Face images and embeddings never leave our server.

**Q13. Why SQLite and not MySQL/PostgreSQL?**
For one institution's scale, SQLite is ACID-compliant, needs zero database server to administer,
and is a single portable file (easy backup). It's the right tool for this size; the code can move
to PostgreSQL later if we scale to many campuses.

**Q14. Why FastAPI instead of Flask or Django?**
FastAPI is async (better for the slower computer-vision work), validates uploads/forms
automatically, and is very fast with little boilerplate. Django would be heavy overkill;
Flask would need much more manual plumbing.

**Q15. Is it really deployed, or a localhost demo?**
Really deployed. It's live at **https://attendance.cloud** over HTTPS, reverse-proxied by
OpenLiteSpeed to a Uvicorn process kept alive by **systemd** (auto-restart on crash, auto-start on
boot). You can open it right now.

**Q16. How does the kiosk "quick attendance" stay safe if it has no login?**
Because identity comes from the **live face** plus the **liveness check** and **identity match**,
not a password. The system recognizes the student, confirms it's a live person (not a screen),
checks they're enrolled in an **open** session, prevents duplicates, and records it. It's the
standard face-kiosk model, protected by the AI checks.

**Q17. What about privacy / ethics (GDPR-style concerns)?**
Faces are processed and stored **only on our own server**, never sent to any external service.
We store compact embeddings + the submission photo for audit. A real rollout would add explicit
consent, retention limits, and deletion on request — we designed it so that's easy because nothing
is in a third-party cloud.

**Q18. What are the system's limitations?**
Single-frame passive liveness could, in theory, be challenged by a very large, high-quality screen
held close; mask/glasses are flagged but not blocked; SQLite suits one institution. We list these
honestly and have concrete next steps.

**Q19. What would you add next?**
Optional **active liveness** (blink/turn) and multi-frame checks, a mobile app with push
notifications, timetable integration, configurable mask/glasses blocking, and PostgreSQL + GPU
batch recognition for very large lecture halls.

**Q20. What was the hardest problem and how did you solve it?**
Anti-spoofing. Our first heuristic version was fooled by phone replays. We integrated a trained
liveness model — but discovered (from our own logs) that it failed on **small/distant faces** while
catching large ones. We diagnosed the exact cause (low-resolution crops hide screen artifacts) and
added a **minimum-face-size gate**, which both closes the bypass and forces attackers into the range
where the model wins. That's real engineering: measure, diagnose, fix, verify.

---

### Bonus rapid-fire (in case they probe)
- **Embedding size?** 512-D, L2-normalized.
- **Detector?** RetinaFace (`det_10g`). **Recognizer?** ArcFace (`w600k_r50`).
- **Liveness model?** hairymax/Face-AntiSpoofing (MIT), 3-class, 128×128, ONNX/CPU.
- **Similarity metric?** Cosine similarity.
- **Enrollment angles?** 4 (upper/left/right/lower), averaged.
- **Auto-approve rule?** live AND large-enough face AND similarity ≥ 0.50 AND no mask/glasses flag.
- **Server stack?** AlmaLinux 9 + OpenLiteSpeed + Uvicorn + systemd + Let's Encrypt.

### Demo tips for the day
1. Sign in as admin → show dashboard, classes, an **open session**.
2. Open **/quick-attendance** → show your real face → **records present** for the class.
3. Hold a **phone with a face** → show it's **blocked** (replay) / "move closer".
4. Show the record appearing in **admin Reviews** and the **student dashboard**.
5. Try to **register a duplicate face** → show it's refused.
6. Toggle **dark mode**; show it's mobile-responsive.
