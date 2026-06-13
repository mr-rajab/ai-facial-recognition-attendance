#!/usr/bin/env python3
"""Seed the attendance database with realistic demo data for a live presentation.

Idempotent: wipes previously generated demo rows (keeps the bootstrap admin) and
regenerates a fresh, internally-consistent dataset:

  - ~45 students, each with a login account and 4 enrolled face poses
  - 6 classes with descriptions and rosters
  - ~5 weeks worth of sessions (most closed, a couple live right now)
  - legacy `attendance` rows + portal `daily_attendance` selfie submissions
  - approved / pending / rejected reviews with spoof + identity scores
  - an audit-event trail

Run:  .venv/bin/python scripts/seed_demo_data.py
"""
from __future__ import annotations

import hashlib
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from auth_passwords import hash_password  # noqa: E402

DB_PATH = os.path.join(ROOT, "data", "attendance.db")
FACES_DIR = os.path.join(ROOT, "data", "demo_faces")

random.seed(20260612)
NOW = datetime(2026, 6, 12, 13, 30, 0)
STUDENT_PASSWORD = "Student123!"

# ── Name pools (matches the existing roster's regional flavour) ───────────────
FIRST = [
    "Ahmad", "Mohammed", "Omar", "Yusuf", "Ali", "Khalil", "Hassan", "Bilal",
    "Tariq", "Samir", "Karim", "Hamza", "Rami", "Anas", "Zaid", "Bashar",
    "Mehmet", "Emre", "Burak", "Kerem", "Furkan", "Yigit", "Baris", "Onur",
    "Layla", "Fatima", "Noor", "Salma", "Rana", "Hala", "Dina", "Maya",
    "Aisha", "Yasmin", "Lina", "Zeynep", "Elif", "Esra", "Merve", "Defne",
    "Ibrahim", "Mustafa", "Adam", "Daniel", "Sara",
]
LAST = [
    "Rajab", "Selem", "AlAfandi", "Musadi", "Haddad", "Nasser", "Khoury",
    "Saleh", "Mansour", "Darwish", "Hamdan", "Qassem", "Najjar", "Aydin",
    "Yilmaz", "Demir", "Kaya", "Sahin", "Celik", "Arslan", "Dogan", "Koc",
    "Ozturk", "Kurt", "Shahin", "Barakat", "Ismail", "Othman", "Zahran",
]

# Real enrolled students already present in the embeddings gallery — keep them.
GALLERY_STUDENTS = [
    ("230408916", "Ahmad Rajab"),
    ("2026001", "Radwan Selem"),
    ("220408911", "Abdallatif AlAfandi"),
    ("210202908", "Ahmet Musadi"),
    ("230408912", "Yusuf Haddad"),
]

CLASSES = [
    ("CS101 — Introduction to Programming",
     "First-year fundamentals: Python syntax, control flow, functions and basic data structures."),
    ("CS201 — Data Structures & Algorithms",
     "Lists, trees, graphs, hashing and complexity analysis with hands-on lab work."),
    ("CS305 — Database Systems",
     "Relational modelling, SQL, normalization, transactions and indexing."),
    ("CS340 — Computer Networks",
     "Layered architectures, TCP/IP, routing, and application protocols."),
    ("AI401 — Machine Learning",
     "Supervised and unsupervised learning, model evaluation, and a vision capstone."),
    ("MATH202 — Linear Algebra",
     "Vector spaces, matrices, eigenvalues and their applications in computing."),
]

# weekday(): Mon=0 .. Sun=6   (course meeting days + start hour/min)
CLASS_SCHEDULE = [
    {"days": (0, 2), "hour": 9, "minute": 0, "dur": 90},    # CS101 Mon/Wed 09:00
    {"days": (1, 3), "hour": 11, "minute": 0, "dur": 90},   # CS201 Tue/Thu 11:00
    {"days": (0, 3), "hour": 13, "minute": 30, "dur": 90},  # CS305 Mon/Thu 13:30
    {"days": (2,), "hour": 15, "minute": 0, "dur": 120},    # CS340 Wed 15:00
    {"days": (1, 4), "hour": 10, "minute": 0, "dur": 90},   # AI401 Tue/Fri 10:00
    {"days": (4,), "hour": 13, "minute": 0, "dur": 120},    # MATH202 Fri 13:00
]

REJECT_REASONS = [
    "Face did not match the enrolled identity.",
    "Possible spoof detected (screen replay).",
    "Low image quality — face not clearly visible.",
    "No face detected in the submitted frame.",
]


def _avatar(student_id: str, name: str) -> str:
    """Render a clean profile-style placeholder so review thumbnails look real."""
    path = os.path.join(FACES_DIR, f"{student_id}.jpg")
    if os.path.isfile(path):
        return path
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        # PIL missing: write a 1px file so FileResponse still serves something.
        with open(path, "wb") as fh:
            fh.write(b"\xff\xd8\xff\xd9")
        return path

    palette = [
        (37, 99, 235), (5, 150, 105), (217, 119, 6), (190, 24, 93),
        (124, 58, 237), (13, 148, 136), (220, 38, 38), (2, 132, 199),
    ]
    bg = palette[hash(student_id) % len(palette)]
    size = 480
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    # soft vignette so it reads as a captured frame, not flat colour
    d.ellipse([-120, -120, size + 120, size + 120], outline=(0, 0, 0), width=0)
    light = tuple(min(255, c + 35) for c in bg)
    d.ellipse([size * 0.18, size * 0.10, size * 0.82, size * 0.74], fill=light)  # head
    d.ellipse([size * 0.05, size * 0.62, size * 0.95, size * 1.35], fill=light)  # shoulders

    initials = "".join(p[0] for p in name.split()[:2]).upper() or "S"
    font = None
    for fp in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            font = ImageFont.truetype(fp, 150)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    try:
        box = d.textbbox((0, 0), initials, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        d.text(((size - tw) / 2 - box[0], (size * 0.30 - th / 2) - box[1]),
               initials, fill=bg, font=font)
    except Exception:
        pass
    img.save(path, "JPEG", quality=88)
    return path


def _email(first: str, last: str, sid: str) -> str:
    return f"{first}.{last}{sid[-3:]}".lower().replace(" ", "") + "@std.university.edu"


def main() -> None:
    os.makedirs(FACES_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF;")
    cur = conn.cursor()

    # ── wipe previous demo data, keep the bootstrap admin ─────────────────────
    for t in ("attendance", "daily_attendance", "enrollment_faces",
              "class_enrollments", "sessions", "classes", "audit_events"):
        cur.execute(f"DELETE FROM {t};")
    cur.execute("DELETE FROM users WHERE role = 'student';")
    cur.execute("DELETE FROM students;")
    cur.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1;")
    row = cur.fetchone()
    admin_id = row[0] if row else None

    # ── students + accounts + enrolled face poses ─────────────────────────────
    used_ids: set[str] = set()
    students: list[dict] = []

    def add_student(sid: str, name: str) -> None:
        first, last = (name.split() + ["", ""])[:2]
        email = _email(first or "student", last or sid, sid)
        cur.execute(
            "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?);",
            (sid, name, email),
        )
        srow = cur.lastrowid
        created = (NOW - timedelta(days=random.randint(40, 75))).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO users (email, password_hash, role, student_row_id, created_at) "
            "VALUES (?, ?, 'student', ?, ?);",
            (email, hash_password(STUDENT_PASSWORD), srow, created),
        )
        uid = cur.lastrowid
        photo = _avatar(sid, name)
        rel = os.path.relpath(photo, ROOT)
        for pose in ("upper", "left", "right", "lower"):
            cur.execute(
                "INSERT INTO enrollment_faces (student_row_id, pose, image_path) "
                "VALUES (?, ?, ?);",
                (srow, pose, rel),
            )
        students.append({"row": srow, "uid": uid, "sid": sid, "name": name, "photo": rel})

    for sid, name in GALLERY_STUDENTS:
        used_ids.add(sid)
        add_student(sid, name)

    target_total = 46
    while len(students) < target_total:
        year = random.choice(["21", "22", "23", "24"])
        sid = f"{year}0408{random.randint(900, 999)}"
        if sid in used_ids:
            continue
        used_ids.add(sid)
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        add_student(sid, name)

    # ── classes + rosters ─────────────────────────────────────────────────────
    class_ids: list[int] = []
    rosters: dict[int, list[dict]] = {}
    for i, (cname, cdesc) in enumerate(CLASSES):
        created = (NOW - timedelta(days=random.randint(55, 80))).isoformat(timespec="seconds")
        cur.execute(
            "INSERT INTO classes (name, description, created_at) VALUES (?, ?, ?);",
            (cname, cdesc, created),
        )
        cid = cur.lastrowid
        class_ids.append(cid)
        size = random.randint(16, 26)
        roster = random.sample(students, size)
        rosters[cid] = roster
        for st in roster:
            enrolled = (NOW - timedelta(days=random.randint(35, 50))).isoformat(timespec="seconds")
            cur.execute(
                "INSERT INTO class_enrollments (class_id, student_row_id, enrolled_at) "
                "VALUES (?, ?, ?);",
                (cid, st["row"], enrolled),
            )

    # ── sessions + attendance + selfie submissions ────────────────────────────
    n_attendance = n_daily = n_sessions = n_pending = 0
    audit: list[tuple] = []

    def add_audit(ts: datetime, etype: str, actor, detail, ttype=None, tid=None) -> None:
        ip = hashlib.sha256(f"ip{etype}{ts}".encode()).hexdigest()[:32]
        ua = hashlib.sha256(b"Mozilla/5.0 demo").hexdigest()[:32]
        audit.append((ts.isoformat(timespec="seconds"), etype, actor, ttype, tid, detail, ip, ua))

    for cid, sched in zip(class_ids, CLASS_SCHEDULE):
        cname = CLASSES[class_ids.index(cid)][0]
        roster = rosters[cid]
        # walk back 35 days; create a session each scheduled meeting day
        for back in range(35, -1, -1):
            day = NOW.date() - timedelta(days=back)
            if day.weekday() not in sched["days"]:
                continue
            start = datetime(day.year, day.month, day.day, sched["hour"], sched["minute"])
            if start > NOW:
                continue
            is_today = day == NOW.date()
            active = is_today and start <= NOW  # leave today's meeting open
            end = None if active else (start + timedelta(minutes=sched["dur"]))
            cur.execute(
                "INSERT INTO sessions (course, start_time, end_time, class_id) VALUES (?, ?, ?, ?);",
                (cname, start.isoformat(timespec="seconds"),
                 end.isoformat(timespec="seconds") if end else None, cid),
            )
            sess_id = cur.lastrowid
            n_sessions += 1
            add_audit(start, "session_opened", admin_id, f"Opened session for {cname}",
                      "session", str(sess_id))

            base_rate = random.uniform(0.80, 0.93)
            for st in roster:
                if random.random() > base_rate:
                    continue  # absent
                offset = random.randint(0, 14)
                ts = start + timedelta(minutes=offset, seconds=random.randint(0, 59))
                if active and ts > NOW:
                    ts = NOW - timedelta(minutes=random.randint(1, 8))
                late = offset >= 10
                sim = round(random.uniform(0.46, 0.82), 3)

                # legacy live-recognition row
                cur.execute(
                    "INSERT INTO attendance (session_id, student_id, timestamp, status, confidence) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (sess_id, st["row"], ts.isoformat(timespec="seconds"),
                     "late" if late else "present", sim),
                )
                n_attendance += 1

                # portal selfie submission / review
                roll = random.random()
                spoof_risk, spoof_score, ident, status, reason = "none", round(random.uniform(0.01, 0.18), 3), sim, "approved", None
                if active:
                    status = "pending"
                    n_pending += 1
                elif roll < 0.06:
                    status = "rejected"
                    if random.random() < 0.5:
                        spoof_risk = random.choice(["medium", "high"])
                        spoof_score = round(random.uniform(0.55, 0.92), 3)
                        reason = REJECT_REASONS[1]
                    else:
                        ident = round(random.uniform(0.12, 0.33), 3)
                        reason = random.choice([REJECT_REASONS[0], REJECT_REASONS[2], REJECT_REASONS[3]])
                elif roll < 0.10:
                    spoof_risk = "low"
                    spoof_score = round(random.uniform(0.25, 0.45), 3)

                reviewed_at = None
                reviewer = None
                if status in ("approved", "rejected"):
                    reviewed_at = (ts + timedelta(minutes=random.randint(3, 40))).isoformat(timespec="seconds")
                    reviewer = admin_id
                sha = hashlib.sha256(f"{st['sid']}{ts}".encode()).hexdigest()
                cur.execute(
                    """INSERT INTO daily_attendance
                       (user_id, student_row_id, photo_path, submitted_at, status,
                        reviewed_at, reviewer_user_id, spoof_risk, spoof_score,
                        spoof_detail, identity_similarity, reject_reason, photo_sha256, session_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                    (st["uid"], st["row"], st["photo"], ts.isoformat(timespec="seconds"), status,
                     reviewed_at, reviewer, spoof_risk, spoof_score,
                     f"laplacian_var={round(random.uniform(40, 320), 1)}", ident, reason, sha, sess_id),
                )
                n_daily += 1
                if status == "approved":
                    add_audit(datetime.fromisoformat(reviewed_at), "attendance_approved",
                              admin_id, f"Approved attendance for {st['name']}", "submission", str(cur.lastrowid))
                elif status == "rejected":
                    add_audit(datetime.fromisoformat(reviewed_at), "attendance_rejected",
                              admin_id, f"Rejected: {reason}", "submission", str(cur.lastrowid))

            if end:
                add_audit(end, "session_closed", admin_id, f"Closed session for {cname}",
                          "session", str(sess_id))

    # a few login events to flesh out the audit feed
    for st in random.sample(students, 12):
        ts = NOW - timedelta(hours=random.randint(1, 60))
        add_audit(ts, "login", st["uid"], f"Student login: {st['name']}")
    add_audit(NOW - timedelta(minutes=20), "login", admin_id, "Admin login")
    for cid in class_ids:
        cname = CLASSES[class_ids.index(cid)][0]
        ts = NOW - timedelta(days=random.randint(55, 80))
        add_audit(ts, "class_created", admin_id, f"Created class {cname}", "class", str(cid))

    audit.sort(key=lambda r: r[0])
    cur.executemany(
        "INSERT INTO audit_events (created_at, event_type, actor_user_id, target_type, target_id, detail, ip_hash, ua_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
        audit,
    )

    conn.commit()

    def count(t: str) -> int:
        return conn.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0]

    n_accounts = conn.execute("SELECT COUNT(*) FROM users WHERE role='student';").fetchone()[0]
    print("Demo data seeded:")
    print(f"  students            {count('students')}")
    print(f"  student accounts    {n_accounts}")
    print(f"  classes             {count('classes')}")
    print(f"  class_enrollments   {count('class_enrollments')}")
    print(f"  sessions            {count('sessions')}  ({conn.execute('SELECT COUNT(*) FROM sessions WHERE end_time IS NULL').fetchone()[0]} live now)")
    print(f"  attendance (live)   {count('attendance')}")
    print(f"  daily_attendance    {count('daily_attendance')}  ({n_pending} pending review)")
    print(f"  audit_events        {count('audit_events')}")
    print(f"  face avatars        {FACES_DIR}")
    print(f"\nStudent login password (all students): {STUDENT_PASSWORD}")
    conn.close()


if __name__ == "__main__":
    main()
