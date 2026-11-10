import csv
import io

from flask import make_response
import sqlite3

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app
)

students_bp = Blueprint("students", __name__)


# Database connection
def get_db():
    connection = sqlite3.connect(current_app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# READ: Display all students
@students_bp.route("/students")
def list_students():

    db = get_db()

    students = db.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()

    db.close()

    return render_template(
        "students.html",
        students=students
    )



# CREATE: Add a new student
@students_bp.route("/students/add", methods=["POST"])
def add_student():

    roll_no = request.form.get("roll_no", "").strip()
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    course = request.form.get("course", "").strip()
    semester = request.form.get("semester", "").strip()

    if not roll_no or not name:
        flash("Roll number and name are required!", "error")
        return redirect(url_for("students.list_students"))

    db = None

    try:
        semester_value = int(semester) if semester else None

        if semester_value is not None and not 1 <= semester_value <= 12:
            raise ValueError

        db = get_db()

        db.execute("""
            INSERT INTO students
            (roll_no, name, email, course, semester)
            VALUES (?, ?, ?, ?, ?)
        """, (roll_no, name, email, course, semester_value))

        db.commit()
        flash("Student added successfully!", "success")

    except sqlite3.IntegrityError:
        flash("Roll number already exists!", "error")

    except ValueError:
        flash("Please enter a valid semester number!", "error")

    finally:
        if db is not None:
            db.close()

    return redirect(url_for("students.list_students"))


# UPDATE: Edit student details
@students_bp.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):

    db = get_db()

    student = db.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()

    if student is None:
        db.close()
        return "Student not found", 404

    if request.method == "POST":

        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        course = request.form.get("course", "").strip()
        semester = request.form.get("semester", "").strip()

        try:
            semester_value = int(semester) if semester else None

            if not roll_no or not name:
                raise ValueError

            if semester_value is not None and not 1 <= semester_value <= 12:
                raise ValueError

            db.execute("""
                UPDATE students
                SET roll_no = ?, name = ?, email = ?,
                    course = ?, semester = ?
                WHERE id = ?
            """, (
                roll_no, name, email,
                course, semester_value, student_id
            ))

            db.commit()
            db.close()

            flash("Student updated successfully!", "success")
            return redirect(url_for("students.list_students"))

        except sqlite3.IntegrityError:
            db.close()
            flash("Roll number already exists!", "error")

        except ValueError:
            db.close()
            flash("Please enter valid student details!", "error")

        return redirect(url_for("students.edit_student", student_id=student_id))

    db.close()

    return render_template(
        "edit_student.html",
        student=student
    )


# DELETE: Remove student
@students_bp.route("/students/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):

    db = get_db()

    db.execute(
        "DELETE FROM attendance WHERE student_id = ?",
        (student_id,)
    )

    db.execute(
        "DELETE FROM students WHERE id = ?",
        (student_id,)
    )

    db.commit()
    db.close()

    flash("Student deleted successfully!", "success")

    return redirect(url_for("students.list_students"))


from datetime import date


# ATTENDANCE: Display and mark daily attendance
@students_bp.route("/attendance", methods=["GET", "POST"])
def attendance():

    db = get_db()

    if request.method == "POST":

        attendance_date = request.form.get("attendance_date")

        if not attendance_date:
            db.close()
            flash("Please select an attendance date!", "error")
            return redirect(url_for("students.attendance"))

        students = db.execute(
            "SELECT id FROM students"
        ).fetchall()

        for student in students:

            student_id = student["id"]
            status = request.form.get(f"status_{student_id}")

            if status not in ("Present", "Absent"):
                continue

            db.execute("""
                INSERT INTO attendance
                (student_id, attendance_date, status)
                VALUES (?, ?, ?)

                ON CONFLICT(student_id, attendance_date)
                DO UPDATE SET status = excluded.status
            """, (student_id, attendance_date, status))

        db.commit()
        db.close()

        flash("Attendance saved successfully!", "success")

        return redirect(
            url_for("students.attendance",
                    attendance_date=attendance_date)
        )

    # Selected date or today's date
    selected_date = request.args.get(
        "attendance_date",
        date.today().isoformat()
    )

    # Fetch students and their attendance
    students = db.execute("""
        SELECT
            students.id,
            students.roll_no,
            students.name,
            attendance.status
        FROM students
        LEFT JOIN attendance
            ON students.id = attendance.student_id
            AND attendance.attendance_date = ?
        ORDER BY students.roll_no
    """, (selected_date,)).fetchall()

    # Attendance summary
    summary = db.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent
        FROM attendance
        WHERE attendance_date = ?
    """, (selected_date,)).fetchone()

    total = summary["total"] or 0
    present = summary["present"] or 0
    absent = summary["absent"] or 0

    percentage = round((present / total) * 100, 2) if total else 0

    db.close()

    return render_template(
        "attendance.html",
        students=students,
        selected_date=selected_date,
        total=total,
        present=present,
        absent=absent,
        percentage=percentage
    )

# REPORTS: Monthly attendance report
@students_bp.route("/reports")
def reports():

    db = get_db()

    selected_month = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )

    # Validate month format
    try:
        date.fromisoformat(selected_month + "-01")
    except ValueError:
        db.close()
        flash("Invalid month selected!", "error")
        return redirect(url_for("students.reports"))

    # Individual student attendance summary
    student_reports = db.execute("""
        SELECT
            s.id,
            s.roll_no,
            s.name,

            COUNT(a.id) AS total_classes,

            SUM(
                CASE WHEN a.status = 'Present'
                THEN 1 ELSE 0 END
            ) AS present,

            SUM(
                CASE WHEN a.status = 'Absent'
                THEN 1 ELSE 0 END
            ) AS absent

        FROM students s

        LEFT JOIN attendance a
            ON s.id = a.student_id
            AND strftime('%Y-%m', a.attendance_date) = ?

        GROUP BY s.id
        ORDER BY s.roll_no
    """, (selected_month,)).fetchall()

    total_classes = sum(r["total_classes"] for r in student_reports)
    total_present = sum(r["present"] or 0 for r in student_reports)
    total_absent = sum(r["absent"] or 0 for r in student_reports)

    overall_percentage = (
        round(total_present / total_classes * 100, 2)
        if total_classes else 0
    )

    db.close()

    return render_template(
        "reports.html",
        student_reports=student_reports,
        selected_month=selected_month,
        total_classes=total_classes,
        total_present=total_present,
        total_absent=total_absent,
        overall_percentage=overall_percentage
    )

# EXPORT ATTENDANCE REPORT
@students_bp.route("/reports/export")
def export_report():

    db = get_db()

    records = db.execute("""
        SELECT
            students.roll_no,
            students.name,
            students.course,
            attendance.attendance_date,
            attendance.status
        FROM attendance
        JOIN students
            ON students.id = attendance.student_id
        ORDER BY attendance.attendance_date DESC
    """).fetchall()

    db.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Roll Number",
        "Student Name",
        "Course",
        "Attendance Date",
        "Status"
    ])

    for record in records:
        writer.writerow([
            record["roll_no"],
            record["name"],
            record["course"],
            record["attendance_date"],
            record["status"]
        ])

    response = make_response("\ufeff" + output.getvalue())

    response.headers["Content-Disposition"] = (
        "attachment; filename=attendance_report.csv"
    )

    response.headers["Content-Type"] = (
        "text/csv; charset=utf-8"
    )

    return response
