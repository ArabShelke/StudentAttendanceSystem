
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)

import os
import sqlite3
from datetime import date

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from app.database import init_db
from app.routes import students_bp


def create_app():

    app = Flask(__name__, instance_relative_config=True)

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "development-secret-key-change-before-deployment"
    )

    app.config["DATABASE"] = os.path.join(
        app.instance_path,
        "attendance.db"
    )

    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize database
    init_db(app.config["DATABASE"])

    # Create default admin if no admin exists
    db = sqlite3.connect(app.config["DATABASE"])

    admin_exists = db.execute(
        "SELECT id FROM admins LIMIT 1"
    ).fetchone()

    if not admin_exists:

        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "ChangeMe@123")

        password_hash = generate_password_hash(password)

        db.execute("""
            INSERT INTO admins (username, password_hash)
            VALUES (?, ?)
        """, (username, password_hash))

        db.commit()

    db.close()

    # Protect all application pages
    @app.before_request
    def protect_pages():

        allowed_endpoints = ["login", "static"]

        if request.endpoint in allowed_endpoints:
            return

        if not session.get("admin_id"):
            return redirect(url_for("login"))

    # LOGIN
    @app.route("/login", methods=["GET", "POST"])
    def login():

        if session.get("admin_id"):
            return redirect(url_for("home"))

        if request.method == "POST":

            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            db = sqlite3.connect(app.config["DATABASE"])
            db.row_factory = sqlite3.Row

            admin = db.execute("""
                SELECT * FROM admins
                WHERE username = ?
            """, (username,)).fetchone()

            db.close()

            if admin and check_password_hash(
                admin["password_hash"], password
            ):

                session.clear()
                session["admin_id"] = admin["id"]
                session["admin_username"] = admin["username"]

                return redirect(url_for("home"))

            flash("Invalid username or password!", "error")

        return render_template("login.html")

    # LOGOUT
    @app.route("/logout", methods=["GET", "POST"])
    def logout():

        session.clear()

        flash("You have logged out successfully!", "success")

        return redirect(url_for("login"))

    # DASHBOARD
    @app.route("/")
    def home():

        db = sqlite3.connect(app.config["DATABASE"])
        db.row_factory = sqlite3.Row

        today = date.today().isoformat()

        total_students = db.execute(
            "SELECT COUNT(*) FROM students"
        ).fetchone()[0]

        present = db.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE attendance_date = ? AND status = 'Present'
        """, (today,)).fetchone()[0]

        absent = db.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE attendance_date = ? AND status = 'Absent'
        """, (today,)).fetchone()[0]

        total_marked = present + absent

        percentage = (
            round((present / total_marked) * 100, 2)
            if total_marked else 0
        )

        recent_records = db.execute("""
            SELECT
                students.roll_no,
                students.name,
                attendance.attendance_date,
                attendance.status
            FROM attendance
            JOIN students
                ON students.id = attendance.student_id
            ORDER BY attendance.id DESC
            LIMIT 5
        """).fetchall()

        db.close()

        return render_template(
            "dashboard.html",
            total_students=total_students,
            present=present,
            absent=absent,
            percentage=percentage,
            recent_records=recent_records
        )

    # Register student, attendance and reports routes
    app.register_blueprint(students_bp)

    return app
