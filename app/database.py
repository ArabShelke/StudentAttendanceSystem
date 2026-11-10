

import sqlite3
import os


def init_db(database_path):

    os.makedirs(os.path.dirname(database_path), exist_ok=True)

    connection = sqlite3.connect(database_path)

    connection.execute("PRAGMA foreign_keys = ON")

    cursor = connection.cursor()

    # Students Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            course TEXT,
            semester INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Attendance Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            attendance_date DATE NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
            FOREIGN KEY(student_id) REFERENCES students(id),
            UNIQUE(student_id, attendance_date)
        )
    """)

    # Admin Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()

    print("Database initialized successfully!")
