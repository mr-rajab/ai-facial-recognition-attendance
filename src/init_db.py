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


if __name__ == "__main__":
    initialize_db()
    print(f"Initialized database at {DB_PATH}")
