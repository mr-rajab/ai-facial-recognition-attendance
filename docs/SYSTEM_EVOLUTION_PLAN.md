# System evolution plan — security, reliability, and features

This document turns the high-level goals (“smarter,” harder to abuse, more complete) into a **threat model**, **layered controls**, **product backlog**, and a **phased roadmap**. It is meant for graduation-project scope: honest about limits, actionable for implementation.

---

## 1. Goals and non-goals

### Goals

- **Reduce** casual cheating (wrong person on a stolen login, obvious photo/screen replay).
- **Make abuse visible** to admins (flags, audit trail, exports).
- **Operate reliably** in teaching demos (clear errors, backups, documented env).
- **Stay maintainable** (small stack: FastAPI, SQLite, file gallery, InsightFace).

### Non-goals (do not claim in thesis/UI)

- **“Unbreakable”** or **100%** detection of deepfakes, masks, or coerced live attendance.
- **Certified liveness** (FIDO, iBeta PAD) without dedicated hardware/SDK and formal evaluation.

**Preferred wording:** *risk-based controls with optional human review.*

---

## 2. Threat model (who attacks what)

| Actor | Capability | Impact | Mitigation direction |
|--------|------------|--------|----------------------|
| Student shares password | Logs in as victim | Fake attendance | MFA, device/session alerts, rate limits |
| Non-enrolled person | Has password only | Submitted selfie fails 1:1 | **Done:** template match before insert |
| Imposter with victim’s face media | Password + photo/video of victim | May pass 1:1 | Stronger liveness, spoof scores, admin review |
| Insider / admin | DB/files | Data integrity | Audit log, least privilege, backups |
| Script kiddie | Brute login / spam API | Noise / DoS | Rate limit, CAPTCHA on abuse, IP throttle |
| Privacy / compliance | Mishandling PII | Legal/reputational | Retention policy, consent, minimize stored biometrics |

---

## 3. Defense in depth (architecture)

Stack layers so **one failure does not collapse the whole system**.

### Layer A — Identity and session

| Control | Purpose | Status |
|---------|---------|--------|
| Password hashing (bcrypt) | Stolen DB ≠ instant login | Done |
| Bootstrap admin | First-time setup | Done |
| Session cookie signing (`SECRET_KEY`) | Session forgery | Done |
| **MFA (TOTP or WebAuthn)** | Stolen password insufficient | Planned |
| **Session lifetime + rotation** | Hijacked tab / XSS window | Planned |
| **HTTPS + secure cookie flags** in production | Network sniffing | Doc / deploy |
| **Rate limits** on `/login`, attendance, quick API | Brute force / abuse | Done (SlowAPI; disable with `RATE_LIMIT_ENABLED=0`) |

### Layer B — Face (who is in front of the camera)

| Control | Purpose | Status |
|---------|---------|--------|
| 1:1 match to **this student’s** gallery template | Wrong person rejected | Done |
| Configurable `ATTEND_IDENTITY_MIN_SIM` | Tune FAR/FRR | Done |
| **Log similarity on accept** (DB or audit) | Forensics / calibration | Done (`identity_similarity` + `attendance_submit` audit) |
| Optional **template refresh** (re-enroll with approval) | Aging / hair / glasses | Planned |

### Layer C — Presentation / replay (photo, screen, print)

| Control | Purpose | Status |
|---------|---------|--------|
| Heuristic replay score + admin UI | Highlight suspicious frames | Done |
| **Quarantine policy** (block vs `pending`+flag) | Product choice | Planned |
| **Passive ML anti-spoof** (small ONNX) | Stronger than heuristics alone | Optional phase |
| **Active liveness** (2–3 poses or short clip) | Much stronger than one JPEG | Optional phase |

### Layer D — Process and evidence

| Control | Purpose | Status |
|---------|---------|--------|
| Admin approve/reject | Human gate | Done |
| CSV export with spoof columns | Evidence bundle | Done |
| **Immutable audit log** (login, submit, review) | Accountability | Done (`audit_events` + `/admin/export/audit.csv`) |
| **Reject reason** (required text) | Teaching / disputes | Done |
| **SHA-256 of image file** | Tamper-evident file reference | Done (`photo_sha256` column) |

### Layer E — Operations

| Control | Purpose | Status |
|---------|---------|--------|
| `initialize_db` + migrations | Schema drift | Partial |
| **Scheduled backup** (DB + embeddings + portal images) | Recovery | Done (`scripts/backup_portal_data.sh`) |
| **Health/readiness** (DB, disk, model) | Ops | Partial (`/api/ready` includes row counts + `RATE_LIMIT_ENABLED`) |
| Structured logging | Debug without leaking secrets | Planned |

---

## 4. Product backlog (“fully functional”)

Prioritize items that **close demo gaps** and **support admins**.

### Admin

- [ ] Student list: **deactivate** / **reset password** / **trigger re-enroll**.
- [ ] **Per-student export** (attendance history + hashes).
- [x] Dashboard: counts by day + spoof/status breakdown — **Analytics** page (`/admin/analytics`).
- [ ] Bulk actions (e.g. reject obvious spam with reason).

### Student

- [x] **One submission per calendar day** (server local date; timezone config still optional).
- [x] Clear states + **admin reject reason** visible on history.
- [ ] Optional **resubmit** after reject (same day or next day—policy).

### System

- [ ] **Email or in-app notifications** (optional SMTP): “Your attendance was approved/rejected.”
- [ ] **PWA** basics: manifest, icons, install hint (mobile labs).
- [ ] **Security headers** (CSP, HSTS) via reverse proxy + small FastAPI middleware.

### ML / enrollment quality

- [ ] Enrollment **quality gate** (blur, min face size, min detector score)—block weak templates up front.
- [ ] Admin “**calibration**” page: run N probe images, plot similarity distribution, suggest threshold.

---

## 5. Phased roadmap (implementation order)

### Phase 1 — Hardening (short, high leverage)

**Target:** 1–2 weeks of focused work for a small team, or a solid sprint for one developer.

1. ~~**One attendance submission per student per calendar day**~~ **Shipped:** server checks `substr(submitted_at,1,10)` vs today; `?error=daily_limit`.
2. ~~**`audit_events` table + hooks**~~ **Shipped:** `audit_log.write_audit` on login ok/fail, logout, attendance submit, identity fail, daily limit block, approve/reject; table `audit_events`.
3. ~~**Rate limiting**~~ **Shipped:** `slowapi` on `POST /login` (20/min), `POST /student/attendance` (15/min), `POST /api/quick-attendance` (30/min); `RATE_LIMIT_ENABLED=0` in pytest `conftest.py`.
4. ~~**Production checklist**~~ **Shipped:** section in `docs/DEPLOYMENT.md` (TLS, secrets, backups, audit CSV).
5. ~~**Backup script**~~ **Shipped:** `scripts/backup_portal_data.sh` (DB + `data/embeddings` + `data/portal`).

**Exit criteria:** Demo survives scripted abuse; you can answer “who did what, when” from the DB.

### Phase 2 — Trust and UX

**Target:** 2–4 weeks cumulative.

1. **MFA for admin** (TOTP), then optional for students. *(Not implemented.)*
2. ~~**Reject reason** required on reject; show to student on history row.~~ **Shipped:** `reject_reason` column + textarea on admin reviews + student history column.
3. ~~**Similarity score stored**~~ **Shipped:** `identity_similarity` on insert; `photo_sha256` for file integrity; CSV + reviews table.
4. ~~**Admin analytics** page~~ **Shipped:** `/admin/analytics` (by day, spoof buckets, status counts, last 100 audit rows); `/admin/export/audit.csv`.

**Exit criteria:** Supervisors can run a course **without** manual spreadsheet side-channel.

### Phase 3 — Stronger liveness (optional, research-heavy)

**Target:** 4–8+ weeks; depends on thesis depth.

1. **Video or multi-frame challenge** (random head pose / blink)—server validates sequence with existing `FaceEngine` + simple rules.
2. **OR** integrate a maintained **ONNX anti-spoof** model; measure false reject on classmates.
3. Policy: **auto-quarantine** when spoof `high` + still store row for admin only.

**Exit criteria:** Documented evaluation (small user study + confusion matrix), not vague claims.

### Phase 4 — Scale (only if needed)

- Postgres + object storage for blobs; async workers for inference; horizontal app replicas.
- **Only** if deployment outgrows single-machine SQLite.

---

## 6. Documentation and thesis alignment

- Keep a **one-page “Limitations”** section: single-frame JPEG, heuristic spoof, no certified PAD.
- Cite **NIST-style** framing: *presentation attack detection* vs *face recognition* as separate problems.
- **Ethics:** consent for biometric storage, retention period, right to delete account + templates + photos.

---

## 7. How to use this file

- Treat unchecked items as **GitHub issues** or a **Kanban** column per phase.
- After each phase, **update this doc** (date + what shipped) so the report matches the repo.

---

## 8. Related project docs

- `the_project/docs/DEPLOYMENT.md` — environment and runtime.
- `the_project/docs/USER_GUIDE.md` — operator flow.
- `the_project/docs/SYSTEM_DESIGN.md` — architecture narrative (extend with audit + rate limit when implemented).
- `the_project/README.md` — quick start; link to this plan for “future work.”

---

*Last updated: plan authorship aligned with repository evolution; amend in place as features land.*
