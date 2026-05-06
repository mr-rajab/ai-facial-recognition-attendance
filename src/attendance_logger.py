import argparse
import sqlite3

from attendance_db import create_session, get_or_create_student, log_attendance, ensure_db
from init_db import DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert a sample attendance record.")
    parser.add_argument("--student-id", required=True, help="Student number.")
    parser.add_argument("--name", required=True, help="Student name.")
    parser.add_argument("--email", default="", help="Student email.")
    parser.add_argument("--course", default="CS-Project", help="Course name.")
    parser.add_argument("--status", default="present", help="Attendance status.")
    parser.add_argument("--confidence", type=float, default=0.9, help="Confidence score.")
    args = parser.parse_args()

    ensure_db(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    student_db_id = get_or_create_student(conn, args.student_id, args.name, args.email)
    session_id = create_session(conn, args.course)
    log_attendance(conn, session_id, student_db_id, args.status, args.confidence)

    conn.commit()
    conn.close()
    print("Attendance logged successfully.")


if __name__ == "__main__":
    main()
