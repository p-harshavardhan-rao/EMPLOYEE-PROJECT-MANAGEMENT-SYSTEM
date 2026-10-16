"""Employee Project Management System - console application (Python 3 + sqlite3)."""
import sqlite3, os

DB_FILE = "epms.db"

def connect(path=DB_FILE):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(path=DB_FILE):
    if os.path.exists(path):
        os.remove(path)
    conn = connect(path)
    with open("schema.sql") as f:
        conn.executescript(f.read())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ---------- CREATE ----------
def add_employee(conn, name, dept, salary, age, city):
    if not name.strip():
        raise ValueError("Name must not be empty")
    row = conn.execute("SELECT dept_id FROM Department WHERE dept_name=?", (dept,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown department '{dept}'")
    try:
        cur = conn.execute(
            "INSERT INTO Employee(name,dept_id,salary,age,city) VALUES (?,?,?,?,?)",
            (name.strip(), row[0], salary, age, city))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Rule violated: {e}")

def add_project(conn, name, budget):
    try:
        cur = conn.execute("INSERT INTO Project(project_name,budget) VALUES (?,?)", (name, budget))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Rule violated: {e}")

def assign(conn, emp_id, project_id, role="Member"):
    try:
        conn.execute("INSERT INTO Assignment VALUES (?,?,?)", (emp_id, project_id, role))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Assignment rejected: {e}")

# ---------- READ ----------
def list_employees(conn):
    return conn.execute("""SELECT e.emp_id, e.name, d.dept_name, e.salary, e.age, e.city
                           FROM Employee e JOIN Department d ON e.dept_id=d.dept_id
                           ORDER BY e.emp_id""").fetchall()

def search_employees(conn, name_pattern=None, city_prefix=None):
    sql = """SELECT e.emp_id, e.name, d.dept_name, e.salary, e.city
             FROM Employee e JOIN Department d ON e.dept_id=d.dept_id WHERE 1=1"""
    args = []
    if name_pattern:
        sql += " AND e.name LIKE ?"; args.append(name_pattern)
    if city_prefix:
        sql += " AND e.city LIKE ?"; args.append(city_prefix + "%")
    return conn.execute(sql + " ORDER BY e.emp_id", args).fetchall()

# ---------- UPDATE ----------
def update_salary(conn, emp_id, new_salary):
    try:
        cur = conn.execute("UPDATE Employee SET salary=? WHERE emp_id=?", (new_salary, emp_id))
        if cur.rowcount == 0:
            raise ValueError(f"No employee with ID {emp_id}")
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Rule violated: {e}")

# ---------- DELETE (controlled) ----------
def delete_employee(conn, emp_id, confirm=False):
    if not confirm:
        raise ValueError("Deletion cancelled: confirmation not given")
    try:
        cur = conn.execute("DELETE FROM Employee WHERE emp_id=?", (emp_id,))
        if cur.rowcount == 0:
            raise ValueError(f"No employee with ID {emp_id}")
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError(f"Cannot delete: employee still has project assignments ({e})")

# ---------- TRANSACTION ----------
def transfer_employee(conn, emp_id, from_project, to_project):
    """Move an employee from one project to another atomically."""
    try:
        conn.execute("BEGIN")
        cur = conn.execute("DELETE FROM Assignment WHERE emp_id=? AND project_id=?",
                           (emp_id, from_project))
        if cur.rowcount == 0:
            raise ValueError("Employee is not assigned to the source project")
        conn.execute("INSERT INTO Assignment(emp_id,project_id,role) VALUES (?,?, 'Member')",
                     (emp_id, to_project))
        conn.commit()
    except (sqlite3.IntegrityError, ValueError) as e:
        conn.rollback()
        raise ValueError(f"Transfer rolled back: {e}")

# ---------- REPORTS ----------
REPORTS = {
 "Headcount per department (GROUP BY)":
  """SELECT d.dept_name, COUNT(*) AS employees FROM Employee e
     JOIN Department d ON e.dept_id=d.dept_id GROUP BY d.dept_name ORDER BY employees DESC, d.dept_name""",
 "Departments with average salary > 65000 (HAVING)":
  """SELECT d.dept_name, ROUND(AVG(e.salary),2) AS avg_salary FROM Employee e
     JOIN Department d ON e.dept_id=d.dept_id GROUP BY d.dept_name
     HAVING AVG(e.salary) > 65000 ORDER BY d.dept_name""",
 "Employees on a project with budget > 50000 (EXISTS)":
  """SELECT e.name FROM Employee e WHERE EXISTS (
       SELECT 1 FROM Assignment a JOIN Project p ON a.project_id=p.project_id
       WHERE a.emp_id=e.emp_id AND p.budget>50000) ORDER BY e.name""",
 "Total project budget per employee (JOIN + SUM)":
  """SELECT e.name, SUM(p.budget) AS total_budget FROM Employee e
     JOIN Assignment a ON e.emp_id=a.emp_id JOIN Project p ON a.project_id=p.project_id
     GROUP BY e.emp_id, e.name ORDER BY e.emp_id""",
 "Employees not on any project (NOT EXISTS)":
  """SELECT e.name FROM Employee e WHERE NOT EXISTS (
       SELECT 1 FROM Assignment a WHERE a.emp_id=e.emp_id) ORDER BY e.name""",
 "Salary above ALL HR salaries (> ALL via MAX)":
  """SELECT name, salary FROM Employee WHERE salary >
       (SELECT MAX(e.salary) FROM Employee e JOIN Department d ON e.dept_id=d.dept_id
        WHERE d.dept_name='HR') ORDER BY name""",
}

def run_report(conn, title):
    cur = conn.execute(REPORTS[title])
    cols = [c[0] for c in cur.description]
    return cols, cur.fetchall()
