"""Admin / student portal: accounts, multi-angle enrollment, daily attendance, reviews, CSV."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import shutil

import init_db as _idb

from anti_spoof import assess_jpeg_bytes
from attendance_identity import verify_selfie_matches_enrolled_student
from attendance_db import close_session, ensure_db
from audit_log import write_audit
from auth_passwords import verify_password, hash_password
from face_engine import GalleryStore
from portal_students import create_student_account
from quick_recognition import quick_match_from_jpeg
from rate_limit import limiter


def _conn() -> sqlite3.Connection:
    ensure_db()
    c = sqlite3.connect(_idb.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _session_user(request: Request) -> Optional[dict]:
    uid = request.session.get("user_id")
    if uid is None:
        return None
    return {
        "id": int(uid),
        "role": request.session.get("role"),
        "email": request.session.get("email", ""),
        "student_row_id": request.session.get("student_row_id"),
    }


def _user_count() -> int:
    c = _conn()
    n = int(c.execute("SELECT COUNT(*) FROM users;").fetchone()[0])
    c.close()
    return n


def build_router(templates: Jinja2Templates, root: str) -> APIRouter:
    r = APIRouter()

    @r.get("/quick-attendance", response_class=HTMLResponse)
    def quick_attendance_page(request: Request) -> Any:
        return templates.TemplateResponse(request, "quick_attendance.html", {})

    @r.post("/api/quick-attendance")
    @limiter.limit("30/minute")
    async def api_quick_attendance(request: Request, photo: UploadFile = File(...)) -> JSONResponse:
        data = await photo.read()
        if len(data) < 500:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "reason": "small", "message": "Image too small. Capture again."},
            )
        try:
            out = quick_match_from_jpeg(root, data)
        except Exception as ex:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "reason": "error", "message": str(ex)[:200]},
            )
        return JSONResponse(content=out)

    @r.get("/")
    def root_redirect(request: Request) -> RedirectResponse:
        u = _session_user(request)
        if not u:
            return RedirectResponse("/login", status_code=303)
        if u["role"] == "admin":
            return RedirectResponse("/admin", status_code=303)
        return RedirectResponse("/student", status_code=303)

    @r.get("/api/ready")
    def api_ready() -> dict:
        env_path = os.path.join(root, ".env") if os.path.isfile(os.path.join(root, ".env")) else None
        conn = _conn()
        audit_n = int(conn.execute("SELECT COUNT(*) FROM audit_events;").fetchone()[0])
        daily_n = int(conn.execute("SELECT COUNT(*) FROM daily_attendance;").fetchone()[0])
        conn.close()
        return {
            "ok": True,
            "project_root": root,
            "env_file": env_path,
            "users_in_database": _user_count(),
            "daily_attendance_rows": daily_n,
            "audit_events_rows": audit_n,
            "rate_limit_enabled": os.environ.get("RATE_LIMIT_ENABLED", "1"),
            "bootstrap_hint": "Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD in .env, restart, then log in with that email.",
        }

    @r.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> Any:
        if _session_user(request):
            u = _session_user(request)
            if u and u["role"] == "admin":
                return RedirectResponse("/admin", status_code=303)
            return RedirectResponse("/student", status_code=303)
        uc = _user_count()
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": request.query_params.get("error", ""),
                "nousers": request.query_params.get("nousers", ""),
                "user_count": uc,
            },
        )

    @r.post("/login")
    @limiter.limit("20/minute")
    def login_post(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
    ) -> RedirectResponse:
        if _user_count() == 0:
            return RedirectResponse("/login?nousers=1", status_code=303)
        email = (email or "").strip().lower()
        password = (password or "").strip()
        conn = _conn()
        row = conn.execute(
            "SELECT id, password_hash, role, student_row_id FROM users WHERE email = ?;",
            (email,),
        ).fetchone()
        conn.close()
        if not row or not verify_password(password, row["password_hash"]):
            write_audit(
                request,
                "login_fail",
                detail=f"email={email}",
                target_type="user",
            )
            return RedirectResponse("/login?error=1", status_code=303)
        request.session.clear()
        request.session["user_id"] = row["id"]
        request.session["role"] = row["role"]
        request.session["email"] = email
        request.session["student_row_id"] = row["student_row_id"]
        write_audit(
            request,
            "login_ok",
            actor_user_id=int(row["id"]),
            detail="session_created",
            target_type="user",
            target_id=str(row["id"]),
        )
        if row["role"] == "admin":
            return RedirectResponse("/admin", status_code=303)
        return RedirectResponse("/student", status_code=303)

    @r.get("/logout")
    def logout(request: Request) -> RedirectResponse:
        u = _session_user(request)
        if u:
            write_audit(request, "logout", actor_user_id=u["id"], target_type="user", target_id=str(u["id"]))
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @r.get("/admin", response_class=HTMLResponse)
    def admin_home(request: Request) -> Any:
        u = _session_user(request)
        if not u:
            return RedirectResponse("/login", status_code=303)
        if u["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin only")
        conn = _conn()
        students = conn.execute(
            "SELECT id, student_id, name, email FROM students ORDER BY id DESC LIMIT 200;"
        ).fetchall()
        active_sessions = int(
            conn.execute("SELECT COUNT(*) FROM sessions WHERE end_time IS NULL;").fetchone()[0]
        )
        pending = int(
            conn.execute("SELECT COUNT(*) FROM daily_attendance WHERE status = 'pending';").fetchone()[0]
        )
        spoof_pending = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM daily_attendance
                WHERE status = 'pending' AND spoof_risk IN ('medium', 'high');
                """
            ).fetchone()[0]
        )
        conn.close()
        return templates.TemplateResponse(
            request,
            "admin_home.html",
            {
                "user": u,
                "students": students,
                "active_sessions": active_sessions,
                "pending_reviews": pending,
                "spoof_pending": spoof_pending,
            },
        )

    @r.get("/admin/students/new", response_class=HTMLResponse)
    def admin_new_student_form(request: Request) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        flash = request.session.pop("flash_error", "")
        return templates.TemplateResponse(request, "admin_student_new.html", {"user": u, "flash": flash})

    @r.post("/admin/students/new")
    def admin_new_student_post(
        request: Request,
        full_name: str = Form(...),
        student_number: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        img_upper: str = Form(...),
        img_left: str = Form(...),
        img_right: str = Form(...),
        img_lower: str = Form(...),
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        images = {"upper": img_upper, "left": img_left, "right": img_right, "lower": img_lower}
        conn = _conn()
        try:
            create_student_account(
                conn,
                root=root,
                full_name=full_name,
                student_number=student_number,
                email=email,
                password=password,
                images_b64=images,
            )
            conn.commit()
        except Exception as ex:
            conn.rollback()
            conn.close()
            request.session["flash_error"] = str(ex)[:500]
            return RedirectResponse("/admin/students/new", status_code=303)
        conn.close()
        return RedirectResponse("/admin?created=1", status_code=303)

    @r.post("/admin/students/{student_row_id}/delete")
    def admin_delete_student(request: Request, student_row_id: int) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        row = conn.execute(
            "SELECT s.id, s.student_id, s.name, u.id AS user_id "
            "FROM students s LEFT JOIN users u ON u.student_row_id = s.id "
            "WHERE s.id = ?;",
            (student_row_id,),
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Student not found")
        if row["user_id"] and int(row["user_id"]) == u["id"]:
            conn.close()
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        student_number = row["student_id"]
        target_user_id = row["user_id"]

        conn.execute("DELETE FROM daily_attendance WHERE student_row_id = ?;", (student_row_id,))
        conn.execute("DELETE FROM attendance WHERE student_id = ?;", (student_row_id,))
        conn.execute("DELETE FROM enrollment_faces WHERE student_row_id = ?;", (student_row_id,))
        if target_user_id:
            conn.execute("DELETE FROM users WHERE id = ?;", (target_user_id,))
        conn.execute("DELETE FROM students WHERE id = ?;", (student_row_id,))
        conn.commit()
        conn.close()

        write_audit(
            request,
            "student_delete",
            actor_user_id=u["id"],
            detail=f"student_id={student_number}; name={row['name']}",
            target_type="student",
            target_id=str(student_number),
        )

        store = GalleryStore(os.path.join(root, "data", "embeddings"))
        store.remove(student_number)

        enroll_dir = os.path.join(root, "data", "portal", "enroll", student_number)
        if os.path.isdir(enroll_dir):
            shutil.rmtree(enroll_dir, ignore_errors=True)

        return RedirectResponse("/admin?deleted=1", status_code=303)

    def _safe_sid(s: str) -> str:
        return re.sub(r"[^\w\-.]", "_", s.strip())[:80]

    @r.get("/admin/students/{student_row_id}/edit", response_class=HTMLResponse)
    def admin_edit_student_form(request: Request, student_row_id: int) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        row = conn.execute(
            """
            SELECT s.id, s.student_id, s.name, s.email AS student_email,
                   u.email AS login_email
            FROM students s
            LEFT JOIN users u ON u.student_row_id = s.id
            WHERE s.id = ?;
            """,
            (student_row_id,),
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Student not found")
        flash = request.session.pop("flash_error", "")
        return templates.TemplateResponse(
            request,
            "admin_student_edit.html",
            {"user": u, "s": row, "flash": flash},
        )

    @r.post("/admin/students/{student_row_id}/edit")
    def admin_edit_student_post(
        request: Request,
        student_row_id: int,
        full_name: str = Form(...),
        student_number: str = Form(...),
        email: str = Form(...),
        password: str = Form(""),
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)

        full_name = full_name.strip()
        new_sid = student_number.strip()
        email = email.strip().lower()
        password = (password or "").strip()

        def _flash(msg: str) -> RedirectResponse:
            request.session["flash_error"] = msg
            return RedirectResponse(f"/admin/students/{student_row_id}/edit", status_code=303)

        if not full_name:
            return _flash("Full name is required.")
        if not new_sid:
            return _flash("Student number is required.")
        if not email or "@" not in email:
            return _flash("Valid email is required.")
        if password and len(password) < 6:
            return _flash("New password must be at least 6 characters.")

        conn = _conn()
        row = conn.execute(
            """
            SELECT s.id, s.student_id, s.name, u.id AS user_id
            FROM students s
            LEFT JOIN users u ON u.student_row_id = s.id
            WHERE s.id = ?;
            """,
            (student_row_id,),
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Student not found")

        old_sid = row["student_id"]

        # conflict checks
        if new_sid != old_sid:
            if conn.execute(
                "SELECT id FROM students WHERE student_id = ? AND id != ?;",
                (new_sid, student_row_id),
            ).fetchone():
                conn.close()
                return _flash("Student number is already taken.")

        if conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ? AND (student_row_id != ? OR student_row_id IS NULL);",
            (email, student_row_id),
        ).fetchone():
            conn.close()
            return _flash("Email is already in use by another account.")

        # rename gallery + enrollment folder when student number changes
        if new_sid != old_sid:
            store = GalleryStore(os.path.join(root, "data", "embeddings"))
            entry = store.get_entry(old_sid)
            if entry is not None:
                store.remove(old_sid)
                store.upsert(new_sid, full_name, entry.embedding)

            old_dir = os.path.join(root, "data", "portal", "enroll", _safe_sid(old_sid))
            new_dir = os.path.join(root, "data", "portal", "enroll", _safe_sid(new_sid))
            if os.path.isdir(old_dir) and old_dir != new_dir:
                shutil.move(old_dir, new_dir)
                for pose in ("upper", "left", "right", "lower"):
                    new_path = os.path.join(new_dir, f"{pose}.jpg")
                    conn.execute(
                        "UPDATE enrollment_faces SET image_path = ? WHERE student_row_id = ? AND pose = ?;",
                        (new_path, student_row_id, pose),
                    )
        elif full_name != row["name"]:
            # only name changed — update manifest display name
            store = GalleryStore(os.path.join(root, "data", "embeddings"))
            entry = store.get_entry(old_sid)
            if entry is not None:
                store.upsert(old_sid, full_name, entry.embedding)

        conn.execute(
            "UPDATE students SET student_id = ?, name = ?, email = ? WHERE id = ?;",
            (new_sid, full_name, email, student_row_id),
        )
        conn.execute(
            "UPDATE users SET email = ? WHERE student_row_id = ?;",
            (email, student_row_id),
        )
        if password:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE student_row_id = ?;",
                (hash_password(password), student_row_id),
            )

        write_audit(
            request,
            "student_edit",
            actor_user_id=u["id"],
            detail=f"student_row_id={student_row_id}; sid={old_sid}->{new_sid}",
            target_type="student",
            target_id=new_sid,
            conn=conn,
        )
        conn.commit()
        conn.close()
        return RedirectResponse("/admin?edited=1", status_code=303)

    @r.get("/admin/reviews", response_class=HTMLResponse)
    def admin_reviews(request: Request) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        show_all = request.query_params.get("all") == "1"
        conn = _conn()
        where = "" if show_all else "WHERE d.status = 'pending'"
        rows = conn.execute(
            f"""
            SELECT d.id, d.submitted_at, d.status, d.photo_path,
                   d.spoof_risk, d.spoof_score, d.spoof_detail,
                   d.identity_similarity, d.reject_reason,
                   s.student_id, s.name, u.email AS student_email
            FROM daily_attendance d
            JOIN students s ON s.id = d.student_row_id
            JOIN users u ON u.id = d.user_id
            {where}
            ORDER BY d.submitted_at DESC
            LIMIT 200;
            """
        ).fetchall()
        pending_count = int(
            conn.execute("SELECT COUNT(*) FROM daily_attendance WHERE status = 'pending';").fetchone()[0]
        )
        conn.close()
        return templates.TemplateResponse(
            request,
            "admin_reviews.html",
            {"user": u, "rows": rows, "show_all": show_all, "pending_count": pending_count},
        )

    @r.get("/admin/photo/{submission_id}")
    def admin_photo(request: Request, submission_id: int) -> FileResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            raise HTTPException(status_code=403)
        conn = _conn()
        row = conn.execute(
            "SELECT photo_path FROM daily_attendance WHERE id = ?;", (submission_id,)
        ).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404)
        path = row["photo_path"]
        if not path.startswith(root):
            path = os.path.join(root, path.lstrip("/"))
        if not os.path.isfile(path):
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="image/jpeg")

    @r.post("/admin/reviews/{submission_id}/approve")
    def approve_submission(request: Request, submission_id: int) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        ts = datetime.now().isoformat(timespec="seconds")
        conn = _conn()
        conn.execute(
            """
            UPDATE daily_attendance
            SET status = 'approved', reviewed_at = ?, reviewer_user_id = ?
            WHERE id = ?;
            """,
            (ts, u["id"], submission_id),
        )
        write_audit(
            request,
            "review_approve",
            actor_user_id=u["id"],
            detail=f"submission_id={submission_id}",
            target_type="daily_attendance",
            target_id=str(submission_id),
            conn=conn,
        )
        conn.commit()
        conn.close()
        return RedirectResponse("/admin/reviews", status_code=303)

    @r.post("/admin/reviews/{submission_id}/reject")
    def reject_submission(
        request: Request,
        submission_id: int,
        reason: str = Form(""),
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        reason = (reason or "").strip() or "No reason provided"
        ts = datetime.now().isoformat(timespec="seconds")
        conn = _conn()
        conn.execute(
            """
            UPDATE daily_attendance
            SET status = 'rejected', reviewed_at = ?, reviewer_user_id = ?, reject_reason = ?
            WHERE id = ?;
            """,
            (ts, u["id"], reason[:500], submission_id),
        )
        write_audit(
            request,
            "review_reject",
            actor_user_id=u["id"],
            detail=f"submission_id={submission_id}; reason={reason[:300]}",
            target_type="daily_attendance",
            target_id=str(submission_id),
            conn=conn,
        )
        conn.commit()
        conn.close()
        return RedirectResponse("/admin/reviews", status_code=303)

    @r.get("/admin/export/records.csv")
    def export_all_csv(request: Request) -> PlainTextResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            raise HTTPException(status_code=403)
        conn = _conn()
        rows = conn.execute(
            """
            SELECT d.id, d.submitted_at, d.status, d.photo_path, d.reviewed_at,
                   d.spoof_risk, d.spoof_score, d.spoof_detail,
                   d.identity_similarity, d.reject_reason, d.photo_sha256,
                   s.student_id, s.name, u.email AS student_email
            FROM daily_attendance d
            JOIN students s ON s.id = d.student_row_id
            JOIN users u ON u.id = d.user_id
            ORDER BY d.submitted_at DESC;
            """
        ).fetchall()
        conn.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "submission_id",
                "student_number",
                "full_name",
                "student_email",
                "submitted_at",
                "status",
                "reviewed_at",
                "photo_path",
                "spoof_risk",
                "spoof_score",
                "spoof_detail",
                "identity_similarity",
                "reject_reason",
                "photo_sha256",
            ]
        )
        for row in rows:
            w.writerow(
                [
                    row["id"],
                    row["student_id"],
                    row["name"],
                    row["student_email"],
                    row["submitted_at"],
                    row["status"],
                    row["reviewed_at"] or "",
                    row["photo_path"],
                    row["spoof_risk"] or "none",
                    row["spoof_score"] if row["spoof_score"] is not None else "",
                    row["spoof_detail"] or "",
                    row["identity_similarity"] if row["identity_similarity"] is not None else "",
                    row["reject_reason"] or "",
                    row["photo_sha256"] or "",
                ]
            )
        return PlainTextResponse(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="attendance_records.csv"'},
        )

    @r.get("/admin/export/audit.csv")
    def export_audit_csv(request: Request) -> PlainTextResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            raise HTTPException(status_code=403)
        conn = _conn()
        rows = conn.execute(
            """
            SELECT id, created_at, event_type, actor_user_id, target_type, target_id, detail, ip_hash, ua_hash
            FROM audit_events
            ORDER BY id DESC
            LIMIT 10000;
            """
        ).fetchall()
        conn.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            ["id", "created_at", "event_type", "actor_user_id", "target_type", "target_id", "detail", "ip_hash", "ua_hash"]
        )
        for row in rows:
            w.writerow(
                [
                    row["id"],
                    row["created_at"],
                    row["event_type"],
                    row["actor_user_id"] if row["actor_user_id"] is not None else "",
                    row["target_type"] or "",
                    row["target_id"] or "",
                    row["detail"] or "",
                    row["ip_hash"] or "",
                    row["ua_hash"] or "",
                ]
            )
        return PlainTextResponse(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="audit_events.csv"'},
        )

    @r.get("/student", response_class=HTMLResponse)
    def student_home(request: Request) -> Any:
        u = _session_user(request)
        if not u:
            return RedirectResponse("/login", status_code=303)
        if u["role"] != "student":
            return RedirectResponse("/admin", status_code=303)
        sid = u["student_row_id"]
        conn = _conn()
        rows = conn.execute(
            """
            SELECT d.id, d.submitted_at, d.status, d.photo_path, d.reject_reason,
                   COALESCE(c.name, '') AS class_name
            FROM daily_attendance d
            LEFT JOIN sessions s ON s.id = d.session_id
            LEFT JOIN classes c ON c.id = s.class_id
            WHERE d.user_id = ?
            ORDER BY d.submitted_at DESC
            LIMIT 100;
            """,
            (u["id"],),
        ).fetchall()
        open_sessions = conn.execute(
            """
            SELECT s.id AS session_id, s.course, s.start_time, c.name AS class_name
            FROM sessions s
            JOIN classes c ON c.id = s.class_id
            JOIN class_enrollments e ON e.class_id = c.id
            WHERE e.student_row_id = ? AND s.end_time IS NULL
            ORDER BY s.start_time DESC;
            """,
            (sid,),
        ).fetchall() if sid else []
        submitted_session_ids = set()
        for sess in open_sessions:
            dup = conn.execute(
                "SELECT id FROM daily_attendance WHERE user_id = ? AND session_id = ? LIMIT 1;",
                (u["id"], sess["session_id"]),
            ).fetchone()
            if dup:
                submitted_session_ids.add(sess["session_id"])
        conn.close()
        return templates.TemplateResponse(
            request,
            "student_home.html",
            {
                "user": u,
                "rows": rows,
                "open_sessions": open_sessions,
                "submitted_session_ids": submitted_session_ids,
            },
        )

    @r.get("/student/attendance/new", response_class=HTMLResponse)
    def student_new_attendance(request: Request) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "student":
            return RedirectResponse("/login", status_code=303)
        session_id_raw = request.query_params.get("session_id", "")
        session_info = None
        if session_id_raw.isdigit():
            conn = _conn()
            session_info = conn.execute(
                """
                SELECT s.id, s.course, s.start_time, c.name AS class_name
                FROM sessions s
                LEFT JOIN classes c ON c.id = s.class_id
                WHERE s.id = ? AND s.end_time IS NULL;
                """,
                (int(session_id_raw),),
            ).fetchone()
            conn.close()
        return templates.TemplateResponse(
            request,
            "student_attendance_new.html",
            {"user": u, "session_info": session_info},
        )

    @r.post("/student/attendance")
    @limiter.limit("15/minute")
    async def student_submit_attendance(
        request: Request,
        photo: UploadFile = File(...),
        session_id: Optional[int] = Form(None),
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "student":
            return RedirectResponse("/login", status_code=303)
        sid = u["student_row_id"]
        if not sid:
            raise HTTPException(status_code=400, detail="No student profile")
        data = await photo.read()
        back = f"/student/attendance/new?session_id={session_id}" if session_id else "/student/attendance/new"
        if len(data) < 1000:
            return RedirectResponse(f"{back}&error=small", status_code=303)
        conn = _conn()
        if session_id:
            dup = conn.execute(
                "SELECT id FROM daily_attendance WHERE user_id = ? AND session_id = ? LIMIT 1;",
                (u["id"], session_id),
            ).fetchone()
        else:
            today = datetime.now().date().isoformat()
            dup = conn.execute(
                "SELECT id FROM daily_attendance WHERE user_id = ? AND session_id IS NULL AND substr(submitted_at, 1, 10) = ? LIMIT 1;",
                (u["id"], today),
            ).fetchone()
        if dup:
            write_audit(
                request,
                "attendance_duplicate",
                actor_user_id=u["id"],
                detail=f"session_id={session_id}; duplicate_blocked",
                target_type="daily_attendance",
                conn=conn,
            )
            conn.commit()
            conn.close()
            return RedirectResponse(f"{back}&error=already_submitted", status_code=303)
        st = conn.execute("SELECT student_id FROM students WHERE id = ?;", (sid,)).fetchone()
        if not st:
            conn.close()
            raise HTTPException(status_code=400, detail="No student profile")
        student_number = str(st["student_id"])
        try:
            ok_face, id_reason, id_sim = verify_selfie_matches_enrolled_student(root, student_number, data)
        except Exception:
            conn.close()
            return RedirectResponse(f"{back}&error=identity", status_code=303)
        if not ok_face:
            write_audit(
                request,
                "attendance_identity_fail",
                actor_user_id=u["id"],
                detail=f"reason={id_reason}; sim={id_sim:.4f}",
                target_type="student",
                target_id=student_number,
                conn=conn,
            )
            conn.commit()
            conn.close()
            return RedirectResponse(f"{back}&error=identity", status_code=303)
        sp = assess_jpeg_bytes(data)
        auto_ok = sp["risk"] in ("none", "low") and float(id_sim) >= 0.50
        status = "approved" if auto_ok else "pending"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel_dir = os.path.join("data", "portal", "daily", str(u["id"]))
        abs_dir = os.path.join(root, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        fname = f"{ts}.jpg"
        abs_path = os.path.join(abs_dir, fname)
        with open(abs_path, "wb") as f:
            f.write(data)
        submitted = datetime.now().isoformat(timespec="seconds")
        sha = hashlib.sha256(data).hexdigest()
        cur = conn.execute(
            """
            INSERT INTO daily_attendance (
                user_id, student_row_id, photo_path, submitted_at, status,
                spoof_risk, spoof_score, spoof_detail,
                identity_similarity, photo_sha256, session_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                u["id"],
                sid,
                abs_path,
                submitted,
                status,
                sp["risk"],
                sp["score"],
                sp["detail"],
                float(id_sim),
                sha,
                session_id,
            ),
        )
        new_id = int(cur.lastrowid)
        write_audit(
            request,
            "attendance_submit",
            actor_user_id=u["id"],
            detail=f"id={new_id}; session_id={session_id}; status={status}; spoof={sp['risk']}; id_sim={id_sim:.4f}",
            target_type="daily_attendance",
            target_id=str(new_id),
            conn=conn,
        )
        conn.commit()
        conn.close()
        return RedirectResponse("/student?ok=1", status_code=303)

    @r.get("/sessions/{session_id}", response_class=HTMLResponse)
    def session_detail(request: Request, session_id: int) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        sess = conn.execute(
            "SELECT id, course, start_time, end_time FROM sessions WHERE id = ?;",
            (session_id,),
        ).fetchone()
        if not sess:
            conn.close()
            raise HTTPException(status_code=404)
        rows = conn.execute(
            """
            SELECT s.student_id, s.name, a.timestamp, a.status, a.confidence
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            WHERE a.session_id = ?
            ORDER BY a.timestamp;
            """,
            (session_id,),
        ).fetchall()
        conn.close()
        return templates.TemplateResponse(
            request,
            "session.html",
            {"role": "admin", "session": sess, "rows": rows},
        )

    @r.get("/export/session/{session_id}.csv")
    def export_session_csv(request: Request, session_id: int) -> PlainTextResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            raise HTTPException(status_code=403)
        conn = _conn()
        rows = conn.execute(
            """
            SELECT s.student_id, s.name, a.timestamp, a.status, a.confidence,
                   sess.course AS course, sess.id AS session_id
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            JOIN sessions sess ON sess.id = a.session_id
            WHERE a.session_id = ?
            ORDER BY a.timestamp;
            """,
            (session_id,),
        ).fetchall()
        conn.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["student_id", "name", "timestamp", "status", "confidence", "course", "session_id"])
        for row in rows:
            w.writerow(
                [
                    row["student_id"],
                    row["name"],
                    row["timestamp"],
                    row["status"],
                    row["confidence"],
                    row["course"],
                    row["session_id"],
                ]
            )
        return PlainTextResponse(
            buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="session_{session_id}.csv"'},
        )

    @r.post("/sessions/{session_id}/close")
    def close_session_route(request: Request, session_id: int) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        close_session(conn, session_id)
        conn.commit()
        conn.close()
        back = request.query_params.get("back", f"/sessions/{session_id}")
        return RedirectResponse(back, status_code=303)

    # ── Session manager ───────────────────────────────────────────────────────

    @r.get("/admin/sessions", response_class=HTMLResponse)
    def admin_sessions_page(request: Request) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        classes = conn.execute(
            "SELECT id, name FROM classes ORDER BY name;"
        ).fetchall()
        active = conn.execute(
            """
            SELECT s.id, s.course, s.start_time, c.name AS class_name,
                   COUNT(d.id) AS attendance_count
            FROM sessions s
            LEFT JOIN classes c ON c.id = s.class_id
            LEFT JOIN daily_attendance d ON d.session_id = s.id AND d.status != 'rejected'
            WHERE s.end_time IS NULL
            GROUP BY s.id
            ORDER BY s.start_time DESC;
            """
        ).fetchall()
        recent = conn.execute(
            """
            SELECT s.id, s.course, s.start_time, s.end_time, c.name AS class_name,
                   COUNT(d.id) AS attendance_count
            FROM sessions s
            LEFT JOIN classes c ON c.id = s.class_id
            LEFT JOIN daily_attendance d ON d.session_id = s.id AND d.status != 'rejected'
            WHERE s.end_time IS NOT NULL
            GROUP BY s.id
            ORDER BY s.start_time DESC
            LIMIT 30;
            """
        ).fetchall()
        conn.close()
        flash = request.session.pop("flash_error", "")
        return templates.TemplateResponse(
            request,
            "admin_sessions.html",
            {
                "user": u,
                "classes": classes,
                "active": active,
                "recent": recent,
                "flash": flash,
            },
        )

    @r.post("/admin/sessions/new")
    def admin_open_session(
        request: Request,
        class_id: int = Form(...),
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        cls = conn.execute("SELECT id, name FROM classes WHERE id = ?;", (class_id,)).fetchone()
        if not cls:
            conn.close()
            request.session["flash_error"] = "Class not found."
            return RedirectResponse("/admin/sessions", status_code=303)
        already = conn.execute(
            "SELECT id FROM sessions WHERE class_id = ? AND end_time IS NULL;", (class_id,)
        ).fetchone()
        if already:
            conn.close()
            request.session["flash_error"] = f"A session for '{cls['name']}' is already open."
            return RedirectResponse("/admin/sessions", status_code=303)
        ts = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO sessions (course, start_time, class_id) VALUES (?, ?, ?);",
            (cls["name"], ts, class_id),
        )
        conn.commit()
        conn.close()
        return RedirectResponse("/admin/sessions?opened=1", status_code=303)

    @r.get("/admin/analytics", response_class=HTMLResponse)
    def admin_analytics(request: Request) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        by_day = conn.execute(
            """
            SELECT date(submitted_at) AS d, COUNT(*) AS c
            FROM daily_attendance
            WHERE date(submitted_at) >= date('now', '-14 days')
            GROUP BY date(submitted_at)
            ORDER BY d DESC;
            """
        ).fetchall()
        spoof_counts = conn.execute(
            """
            SELECT COALESCE(spoof_risk, 'none') AS spoof_risk, COUNT(*) AS c
            FROM daily_attendance
            GROUP BY spoof_risk
            ORDER BY c DESC;
            """
        ).fetchall()
        status_counts = conn.execute(
            """
            SELECT status, COUNT(*) AS c FROM daily_attendance GROUP BY status ORDER BY c DESC;
            """
        ).fetchall()
        last_audit = conn.execute(
            """
            SELECT created_at, event_type, actor_user_id, detail
            FROM audit_events
            ORDER BY id DESC
            LIMIT 100;
            """
        ).fetchall()
        conn.close()
        return templates.TemplateResponse(
            request,
            "admin_analytics.html",
            {
                "user": u,
                "by_day": by_day,
                "spoof_counts": spoof_counts,
                "status_counts": status_counts,
                "last_audit": last_audit,
            },
        )

    # ── Classes ───────────────────────────────────────────────────────────────

    @r.get("/admin/classes", response_class=HTMLResponse)
    def admin_classes(request: Request) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        classes = conn.execute(
            """
            SELECT c.id, c.name, c.description, c.created_at,
                   COUNT(e.id) AS student_count
            FROM classes c
            LEFT JOIN class_enrollments e ON e.class_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC;
            """
        ).fetchall()
        conn.close()
        flash = request.session.pop("flash_error", "")
        return templates.TemplateResponse(
            request, "admin_classes.html", {"user": u, "classes": classes, "flash": flash}
        )

    @r.post("/admin/classes/new")
    def admin_create_class(
        request: Request,
        name: str = Form(...),
        description: str = Form(""),
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        name = name.strip()
        if not name:
            request.session["flash_error"] = "Class name is required."
            return RedirectResponse("/admin/classes", status_code=303)
        ts = datetime.now().isoformat(timespec="seconds")
        conn = _conn()
        conn.execute(
            "INSERT INTO classes (name, description, created_at) VALUES (?, ?, ?);",
            (name, description.strip(), ts),
        )
        conn.commit()
        conn.close()
        return RedirectResponse("/admin/classes?created=1", status_code=303)

    @r.get("/admin/classes/{class_id}", response_class=HTMLResponse)
    def admin_class_detail(request: Request, class_id: int) -> Any:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        cls = conn.execute(
            "SELECT id, name, description, created_at FROM classes WHERE id = ?;",
            (class_id,),
        ).fetchone()
        if not cls:
            conn.close()
            raise HTTPException(status_code=404, detail="Class not found")
        enrolled = conn.execute(
            """
            SELECT e.id AS enrollment_id, s.id AS student_row_id,
                   s.student_id, s.name, e.enrolled_at
            FROM class_enrollments e
            JOIN students s ON s.id = e.student_row_id
            WHERE e.class_id = ?
            ORDER BY s.name;
            """,
            (class_id,),
        ).fetchall()
        enrolled_ids = {r["student_row_id"] for r in enrolled}
        available = conn.execute(
            "SELECT id, student_id, name FROM students ORDER BY name;"
        ).fetchall()
        available = [s for s in available if s["id"] not in enrolled_ids]
        conn.close()
        flash = request.session.pop("flash_error", "")
        return templates.TemplateResponse(
            request,
            "admin_class_detail.html",
            {
                "user": u,
                "cls": cls,
                "enrolled": enrolled,
                "available": available,
                "flash": flash,
            },
        )

    @r.post("/admin/classes/{class_id}/enroll")
    def admin_enroll_students(
        request: Request,
        class_id: int,
        student_row_ids: List[int] = Form(default=[]),
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        if not student_row_ids:
            request.session["flash_error"] = "No students selected."
            return RedirectResponse(f"/admin/classes/{class_id}", status_code=303)
        conn = _conn()
        cls = conn.execute("SELECT id FROM classes WHERE id = ?;", (class_id,)).fetchone()
        if not cls:
            conn.close()
            raise HTTPException(status_code=404, detail="Class not found")
        ts = datetime.now().isoformat(timespec="seconds")
        added = 0
        for sid in student_row_ids:
            try:
                conn.execute(
                    "INSERT INTO class_enrollments (class_id, student_row_id, enrolled_at) VALUES (?, ?, ?);",
                    (class_id, sid, ts),
                )
                added += 1
            except Exception:
                pass  # already enrolled — skip
        conn.commit()
        conn.close()
        if added == 0:
            request.session["flash_error"] = "Selected students are already enrolled."
        return RedirectResponse(f"/admin/classes/{class_id}", status_code=303)

    @r.post("/admin/classes/{class_id}/unenroll/{enrollment_id}")
    def admin_unenroll_student(
        request: Request,
        class_id: int,
        enrollment_id: int,
    ) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        conn.execute(
            "DELETE FROM class_enrollments WHERE id = ? AND class_id = ?;",
            (enrollment_id, class_id),
        )
        conn.commit()
        conn.close()
        return RedirectResponse(f"/admin/classes/{class_id}", status_code=303)

    @r.post("/admin/classes/{class_id}/delete")
    def admin_delete_class(request: Request, class_id: int) -> RedirectResponse:
        u = _session_user(request)
        if not u or u["role"] != "admin":
            return RedirectResponse("/login", status_code=303)
        conn = _conn()
        conn.execute("DELETE FROM class_enrollments WHERE class_id = ?;", (class_id,))
        conn.execute("DELETE FROM classes WHERE id = ?;", (class_id,))
        conn.commit()
        conn.close()
        return RedirectResponse("/admin/classes?deleted=1", status_code=303)

    # ── Self-registration (hidden — not linked from any page) ─────────────────

    @r.get("/register-student", response_class=HTMLResponse)
    def register_student_page(request: Request) -> Any:
        if _session_user(request):
            return RedirectResponse("/", status_code=303)
        flash = request.session.pop("flash_error", "")
        return templates.TemplateResponse(request, "register_student.html", {"flash": flash})

    @r.post("/register-student")
    @limiter.limit("5/minute")
    def register_student_post(
        request: Request,
        full_name: str = Form(...),
        student_number: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        img_upper: str = Form(...),
        img_left: str = Form(...),
        img_right: str = Form(...),
        img_lower: str = Form(...),
    ) -> RedirectResponse:
        if _session_user(request):
            return RedirectResponse("/", status_code=303)
        images = {"upper": img_upper, "left": img_left, "right": img_right, "lower": img_lower}
        conn = _conn()
        try:
            create_student_account(
                conn,
                root=root,
                full_name=full_name,
                student_number=student_number,
                email=email,
                password=password,
                images_b64=images,
            )
            conn.commit()
        except Exception as ex:
            conn.rollback()
            conn.close()
            request.session["flash_error"] = str(ex)[:500]
            return RedirectResponse("/register-student", status_code=303)
        conn.close()
        write_audit(request, "self_register", detail=f"email={email.strip().lower()}", target_type="user")
        return RedirectResponse("/login?registered=1", status_code=303)

    return r
