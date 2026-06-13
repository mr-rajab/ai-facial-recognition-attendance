import os
import sqlite3


DB_PATH = "data/attendance.db"


def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def initialize_db(db_path: str = DB_PATH) -> None:
    ensure_dir(os.path.dirname(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL,
            FOREIGN KEY(session_id) REFERENCES sessions(id),
            FOREIGN KEY(student_id) REFERENCES students(id)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
            student_row_id INTEGER REFERENCES students(id),
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS enrollment_faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_row_id INTEGER NOT NULL REFERENCES students(id),
            pose TEXT NOT NULL,
            image_path TEXT NOT NULL,
            UNIQUE(student_row_id, pose)
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            student_row_id INTEGER NOT NULL REFERENCES students(id),
            photo_path TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_at TEXT,
            reviewer_user_id INTEGER REFERENCES users(id),
            spoof_risk TEXT DEFAULT 'none',
            spoof_score REAL,
            spoof_detail TEXT,
            identity_similarity REAL,
            reject_reason TEXT,
            photo_sha256 TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor_user_id INTEGER,
            target_type TEXT,
            target_id TEXT,
            detail TEXT,
            ip_hash TEXT,
            ua_hash TEXT
        );
        """
    )

    _migrate_portal_schema(conn)

    conn.commit()
    conn.close()


def _migrate_portal_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS class_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL REFERENCES classes(id),
            student_row_id INTEGER NOT NULL REFERENCES students(id),
            enrolled_at TEXT NOT NULL,
            UNIQUE(class_id, student_row_id)
        );
        """
    )
    # ── Messaging: student↔admin support threads + public group chat ──────
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_row_id INTEGER REFERENCES students(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            topic TEXT NOT NULL DEFAULT 'support',
            subject TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            last_message_at TEXT NOT NULL,
            admin_unread INTEGER NOT NULL DEFAULT 0,
            student_unread INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL REFERENCES support_threads(id),
            sender_user_id INTEGER NOT NULL REFERENCES users(id),
            sender_role TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS group_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_user_id INTEGER NOT NULL REFERENCES users(id),
            sender_role TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_support_msg_thread ON support_messages(thread_id, id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_support_thread_user ON support_threads(user_id, last_message_at);")

    sess_cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions);").fetchall()}
    if "class_id" not in sess_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN class_id INTEGER REFERENCES classes(id);")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(daily_attendance);").fetchall()}
    if "spoof_risk" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN spoof_risk TEXT DEFAULT 'none';")
    if "spoof_score" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN spoof_score REAL;")
    if "spoof_detail" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN spoof_detail TEXT;")
    if "identity_similarity" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN identity_similarity REAL;")
    if "reject_reason" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN reject_reason TEXT;")
    if "photo_sha256" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN photo_sha256 TEXT;")
    conn.execute(
        "UPDATE daily_attendance SET spoof_risk = 'none' WHERE spoof_risk IS NULL OR spoof_risk = '';"
    )
    if "session_id" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN session_id INTEGER REFERENCES sessions(id);")
    # Trained-liveness + mask/glasses results
    if "liveness_label" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN liveness_label TEXT;")
    if "liveness_score" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN liveness_score REAL;")
    if "mask_flag" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN mask_flag INTEGER DEFAULT 0;")
    if "glasses_flag" not in cols:
        conn.execute("ALTER TABLE daily_attendance ADD COLUMN glasses_flag INTEGER DEFAULT 0;")


if __name__ == "__main__":
    initialize_db()
    print(f"Initialized database at {DB_PATH}")
