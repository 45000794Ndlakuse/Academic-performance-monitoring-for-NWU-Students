"""
Database layer for PSR application.
Uses SQLite for lightweight, file-based persistence.
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "psr.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            factor_names TEXT NOT NULL,
            total_assessments TEXT NOT NULL,
            weight_lower REAL DEFAULT 0.01,
            weight_upper REAL DEFAULT 0.40,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            student_number TEXT NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (module_id) REFERENCES modules(id)
        );

        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            module_id INTEGER NOT NULL,
            factor_index INTEGER NOT NULL,
            score REAL NOT NULL,
            assessment_number INTEGER NOT NULL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );

        CREATE TABLE IF NOT EXISTS psr_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            module_id INTEGER NOT NULL,
            min_pmark REAL,
            max_pmark REAL,
            avg_pmark REAL,
            rank_position INTEGER,
            dea_class INTEGER,
            weights_min TEXT,
            weights_max TEXT,
            factor_averages TEXT,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        );
    """)

    # Seed demo module and students if empty
    c.execute("SELECT COUNT(*) FROM modules")
    if c.fetchone()[0] == 0:
        _seed_demo_data(c)

    conn.commit()
    conn.close()


def _seed_demo_data(cursor):
    """Seed with the 26-student dataset from the paper (Appendix A)."""
    cursor.execute("""
        INSERT INTO modules (name, factor_names, total_assessments, weight_lower, weight_upper)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "Advanced Computing IV",
        json.dumps(["Semester Test", "Class Tests", "Theoretical Assignments", "Attendance"]),
        json.dumps([1, 4, 9, 12]),
        0.01,
        0.40
    ))
    module_id = cursor.lastrowid

    paper_data = [
        (2,  "Student 02", [100.00, 95.24, 97.92, 100.00]),
        (3,  "Student 03", [96.67,  82.62, 75.05, 100.00]),
        (4,  "Student 04", [35.00,  35.27, 21.01,  77.78]),
        (5,  "Student 05", [61.67,  56.90, 40.59,  77.78]),
        (6,  "Student 06", [75.00,  63.10, 57.59,  88.89]),
        (7,  "Student 07", [58.33,  22.39, 34.68, 100.00]),
        (8,  "Student 08", [58.33,  43.76, 53.53,  87.50]),
        (9,  "Student 09", [93.33,  91.51, 87.75, 100.00]),
        (10, "Student 10", [93.33,  68.15, 74.07, 100.00]),
        (11, "Student 11", [88.33,  53.38, 64.91, 100.00]),
        (12, "Student 12", [73.33,  57.01, 63.71, 100.00]),
        (13, "Student 13", [76.67,  87.13, 65.83,  88.89]),
        (14, "Student 14", [10.00,  44.40, 52.97,  77.78]),
        (15, "Student 15", [83.33,  57.27, 23.65,  88.89]),
        (16, "Student 16", [51.67,  46.19, 26.36,  77.78]),
        (17, "Student 17", [90.00,  58.15, 68.42,  77.78]),
        (18, "Student 18", [63.33,  58.30, 42.67, 100.00]),
        (19, "Student 19", [73.33,  63.38, 41.01, 100.00]),
        (20, "Student 20", [60.00,  55.24, 51.58,  88.89]),
        (21, "Student 21", [85.00,  59.46, 35.90,  75.00]),
        (22, "Student 22", [40.00,  54.07, 42.67,  88.89]),
        (23, "Student 23", [85.00,  72.14, 61.85, 100.00]),
        (24, "Student 24", [90.00,  64.76, 76.67, 100.00]),
        (25, "Student 25", [83.33,  60.46, 26.07,  66.67]),
        (26, "Student 26", [65.00,  55.48, 24.53, 100.00]),
        (1,  "Student 01", [73.33,  64.74, 13.92,  62.50]),
    ]

    for student_num, name, averages in paper_data:
        cursor.execute(
            "INSERT INTO students (module_id, student_number, name) VALUES (?, ?, ?)",
            (module_id, str(student_num), name)
        )
        student_id = cursor.lastrowid
        for factor_idx, avg in enumerate(averages):
            cursor.execute("""
                INSERT INTO assessments (student_id, module_id, factor_index, score, assessment_number)
                VALUES (?, ?, ?, ?, 1)
            """, (student_id, module_id, factor_idx, avg))


def get_module(module_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM modules WHERE id=?", (module_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "factor_names": json.loads(row["factor_names"]),
        "total_assessments": json.loads(row["total_assessments"]),
        "weight_lower": row["weight_lower"],
        "weight_upper": row["weight_upper"],
    }


def get_all_modules() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM modules ORDER BY created_at DESC").fetchall()
    conn.close()
    return [{
        "id": r["id"],
        "name": r["name"],
        "factor_names": json.loads(r["factor_names"]),
        "total_assessments": json.loads(r["total_assessments"]),
    } for r in rows]


def get_students_for_module(module_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM students WHERE module_id=? ORDER BY student_number",
        (module_id,)
    ).fetchall()
    students = []
    for r in rows:
        # Calculate factor averages from assessments
        avgs = conn.execute("""
            SELECT factor_index, AVG(score) as avg_score
            FROM assessments WHERE student_id=? AND module_id=?
            GROUP BY factor_index ORDER BY factor_index
        """, (r["id"], module_id)).fetchall()
        factor_avgs = [float(a["avg_score"]) for a in avgs]
        students.append({
            "id": r["id"],
            "student_number": r["student_number"],
            "name": r["name"],
            "factor_averages": factor_avgs
        })
    conn.close()
    return students


def get_student_detail(student_id: int) -> dict | None:
    conn = get_connection()
    r = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not r:
        conn.close()
        return None
    avgs = conn.execute("""
        SELECT factor_index, AVG(score) as avg_score, COUNT(*) as count
        FROM assessments WHERE student_id=?
        GROUP BY factor_index ORDER BY factor_index
    """, (student_id,)).fetchall()
    conn.close()
    return {
        "id": r["id"],
        "student_number": r["student_number"],
        "name": r["name"],
        "module_id": r["module_id"],
        "factor_averages": [float(a["avg_score"]) for a in avgs],
        "assessment_counts": [a["count"] for a in avgs]
    }


def save_psr_result(student_id, module_id, result: dict):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO psr_results
        (student_id, module_id, min_pmark, max_pmark, avg_pmark, rank_position,
         dea_class, weights_min, weights_max, factor_averages)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        student_id, module_id,
        result.get("min_pmark"), result.get("max_pmark"), result.get("avg_pmark"),
        result.get("rank"), result.get("dea_class"),
        json.dumps(result.get("weights_min", [])),
        json.dumps(result.get("weights_max", [])),
        json.dumps(result.get("factor_averages", []))
    ))
    conn.commit()
    conn.close()


def add_module(name, factor_names, total_assessments, weight_lower=0.01, weight_upper=0.40):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO modules (name, factor_names, total_assessments, weight_lower, weight_upper)
        VALUES (?, ?, ?, ?, ?)
    """, (name, json.dumps(factor_names), json.dumps(total_assessments), weight_lower, weight_upper))
    mid = c.lastrowid
    conn.commit()
    conn.close()
    return mid


def add_student(module_id, student_number, name, factor_averages):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO students (module_id, student_number, name) VALUES (?, ?, ?)",
              (module_id, student_number, name))
    sid = c.lastrowid
    for i, avg in enumerate(factor_averages):
        c.execute("""
            INSERT INTO assessments (student_id, module_id, factor_index, score, assessment_number)
            VALUES (?, ?, ?, ?, 1)
        """, (sid, module_id, i, avg))
    conn.commit()
    conn.close()
    return sid


def update_student_scores(student_id, module_id, factor_averages):
    conn = get_connection()
    conn.execute("DELETE FROM assessments WHERE student_id=? AND module_id=?", (student_id, module_id))
    for i, avg in enumerate(factor_averages):
        conn.execute("""
            INSERT INTO assessments (student_id, module_id, factor_index, score, assessment_number)
            VALUES (?, ?, ?, ?, 1)
        """, (student_id, module_id, i, avg))
    conn.commit()
    conn.close()
