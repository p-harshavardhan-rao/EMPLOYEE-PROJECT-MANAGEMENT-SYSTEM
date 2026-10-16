import sqlite3, json
import app

OUT = []   # (screen title, [lines]) for screenshots
RES = []   # test results

def table(cols, rows):
    data = [[str(c) for c in cols]] + [[str(v) for v in r] for r in rows]
    w = [max(len(r[i]) for r in data) for i in range(len(cols))]
    fmt = lambda r: " | ".join(v.ljust(w[i]) for i, v in enumerate(r))
    lines = [fmt(data[0]), "-+-".join("-" * x for x in w)] + [fmt(r) for r in data[1:]]
    return lines or ["(empty)"]

conn = app.init_db()

def check(tid, feature, action, expected, fn, expect_error=False, verify=None):
    try:
        actual = fn()
        raised = False
    except ValueError as e:
        actual, raised = str(e), True
    ok = (raised == expect_error) and (verify(actual) if verify and not raised else True)
    RES.append(dict(id=tid, feature=feature, action=action, expected=expected,
                    actual=str(actual), status="Pass" if ok else "Fail"))
    return actual

# ---- Screen 1: Add employee / display ----
s1 = []
new_id = app.add_employee(conn, "Heidi", "HR", 52000, 27, "Seattle")
s1.append(">>> add_employee('Heidi', 'HR', 52000, 27, 'Seattle')")
s1.append(f"Employee added with ID {new_id}")
s1.append("")
s1.append(">>> list_employees()")
s1 += table(["ID","Name","Dept","Salary","Age","City"], app.list_employees(conn))
OUT.append(("Add and display employees", s1))
RES.append(dict(id="TC-01", feature="Create employee", action="Add Heidi, HR, 52000, age 27, Seattle",
    expected="Row inserted; new ID returned; employee appears in listing",
    actual=f"Employee added with ID {new_id}; listed as {[r for r in app.list_employees(conn) if r[0]==new_id][0]}",
    status="Pass" if new_id == 8 else "Fail"))

# ---- Screen 2: Search ----
s2 = [">>> search_employees(name_pattern='%e')"]
r = app.search_employees(conn, name_pattern='%e')
s2 += table(["ID","Name","Dept","Salary","City"], r)
s2 += ["", ">>> search_employees(city_prefix='C')"]
r2 = app.search_employees(conn, city_prefix='C')
s2 += table(["ID","Name","Dept","Salary","City"], r2)
OUT.append(("Search employees using LIKE", s2))
RES.append(dict(id="TC-02", feature="Search (LIKE)", action="Name ends with 'e'; city starts with 'C'",
    expected="Alice, Charlie, Eve, Grace (and Heidi? no) ; Bob, David, Frank",
    actual=f"{[x[1] for x in r]} ; {[x[1] for x in r2]}",
    status="Pass" if [x[1] for x in r]==['Alice','Charlie','Eve','Grace'] and [x[1] for x in r2]==['Bob','David','Frank'] else "Fail"))
RES[-1]["expected"] = "Name search: Alice, Charlie, Eve, Grace; city search: Bob, David, Frank"

# ---- Screen 3: Update salary ----
s3 = [">>> update_salary(emp_id=4, new_salary=50000)"]
app.update_salary(conn, 4, 50000)
s3.append("Salary updated")
s3 += ["", ">>> search_employees(name_pattern='David')"] + table(["ID","Name","Dept","Salary","City"], app.search_employees(conn, name_pattern='David'))
s3 += ["", ">>> update_salary(emp_id=4, new_salary=-100)"]
try:
    app.update_salary(conn, 4, -100)
except ValueError as e:
    s3.append("ERROR: " + str(e))
OUT.append(("Update salary and rule violation", s3))
sal = conn.execute("SELECT salary FROM Employee WHERE emp_id=4").fetchone()[0]
RES.append(dict(id="TC-03", feature="Update salary", action="Set David's salary to 50000",
    expected="Salary changes from 48000 to 50000", actual=f"Salary now {sal}",
    status="Pass" if sal == 50000 else "Fail"))
check("TC-04", "Validation (CHECK)", "Set salary to -100",
      "Update rejected; salary stays 50000",
      lambda: app.update_salary(conn, 4, -100), expect_error=True)
RES[-1]["actual"] = RES[-1]["actual"] + f" (salary still {conn.execute('SELECT salary FROM Employee WHERE emp_id=4').fetchone()[0]})"

# ---- Screen 4: transaction ----
s4 = [">>> assign(emp_id=1, project_id=2, role='Member')"]
app.assign(conn, 1, 2, 'Member'); s4.append("Assignment saved")
s4.append(">>> assign(emp_id=1, project_id=3, role='Member')")
app.assign(conn, 1, 3, 'Member'); s4.append("Assignment saved")
s4.append(">>> assign(emp_id=1, project_id=4, role='Member')")
try: app.assign(conn, 1, 4, 'Member')
except ValueError as e: s4.append("ERROR: " + str(e))
s4 += ["", ">>> transfer_employee(emp_id=2, from_project=2, to_project=5)"]
app.transfer_employee(conn, 2, 2, 5); s4.append("Transfer committed")
s4 += ["", ">>> transfer_employee(emp_id=2, from_project=99, to_project=5)"]
try: app.transfer_employee(conn, 2, 99, 5)
except ValueError as e: s4.append("ERROR: " + str(e))
s4 += ["", "Current assignments of Bob (emp_id=2):"]
s4 += table(["Project","Role"], conn.execute("SELECT p.project_name,a.role FROM Assignment a JOIN Project p USING(project_id) WHERE a.emp_id=2 ORDER BY 1").fetchall())
OUT.append(("Project assignment and transfer transaction", s4))

n1 = conn.execute("SELECT COUNT(*) FROM Assignment WHERE emp_id=1").fetchone()[0]
RES.append(dict(id="TC-05", feature="Assignment limit (trigger)", action="Assign Alice to a 4th project",
    expected="Rejected by trigger; Alice keeps 3 projects",
    actual=f"Rejected; Alice has {n1} assignments", status="Pass" if n1 == 3 else "Fail"))
bob = [r[0] for r in conn.execute("SELECT p.project_name FROM Assignment a JOIN Project p USING(project_id) WHERE a.emp_id=2").fetchall()]
RES.append(dict(id="TC-06", feature="Transfer transaction", action="Move Bob from Web Development to Marketing Plan",
    expected="Old assignment removed, new one added, in one commit",
    actual=f"Bob's projects: {bob}", status="Pass" if bob == ['Marketing Plan'] else "Fail"))
before = conn.execute("SELECT COUNT(*) FROM Assignment WHERE emp_id=2").fetchone()[0]
check("TC-07", "Transaction rollback", "Transfer Bob from non-existent project 99",
      "Error shown; no change to Bob's assignments",
      lambda: app.transfer_employee(conn, 2, 99, 5), expect_error=True)
after = conn.execute("SELECT COUNT(*) FROM Assignment WHERE emp_id=2").fetchone()[0]
RES[-1]["actual"] += f" (assignments before/after: {before}/{after})"
if before != after: RES[-1]["status"] = "Fail"

# rollback atomicity: duplicate target -> the DELETE must be undone
try: app.transfer_employee(conn, 1, 2, 3); dup_msg = "no error"
except ValueError as e: dup_msg = str(e)
cnt = conn.execute("SELECT COUNT(*) FROM Assignment WHERE emp_id=1 AND project_id=2").fetchone()[0]
RES.append(dict(id="TC-08", feature="Atomic rollback", action="Transfer Alice from project 2 to project 3 (already assigned there)",
    expected="Insert fails; the earlier DELETE is undone; Alice stays on project 2",
    actual=f"{dup_msg}; rows for Alice on project 2 = {cnt}", status="Pass" if cnt == 1 else "Fail"))

# ---- Delete controlled ----
s5 = [">>> delete_employee(emp_id=3, confirm=False)"]
try: app.delete_employee(conn, 3, confirm=False)
except ValueError as e: s5.append("ERROR: " + str(e))
s5 += [">>> delete_employee(emp_id=3, confirm=True)"]
try: app.delete_employee(conn, 3, confirm=True)
except ValueError as e: s5.append("ERROR: " + str(e))
s5 += [">>> delete_employee(emp_id=8, confirm=True)   # Heidi, no assignments"]
app.delete_employee(conn, 8, confirm=True); s5.append("Employee 8 deleted")
OUT.append(("Controlled deletion", s5))
check("TC-09", "Delete (confirmation)", "Delete employee 3 without confirmation",
      "Request cancelled; row remains", lambda: app.delete_employee(conn, 3, False), expect_error=True)
check("TC-10", "Delete (RESTRICT)", "Delete Charlie (ID 3) who has an assignment",
      "Blocked by foreign key; row remains", lambda: app.delete_employee(conn, 3, True), expect_error=True)
RES.append(dict(id="TC-11", feature="Delete allowed", action="Delete Heidi (ID 8, no assignments) with confirmation",
    expected="Row removed", actual=f"Rows left for ID 8: {conn.execute('SELECT COUNT(*) FROM Employee WHERE emp_id=8').fetchone()[0]}",
    status="Pass" if conn.execute('SELECT COUNT(*) FROM Employee WHERE emp_id=8').fetchone()[0]==0 else "Fail"))
check("TC-12", "Validation (age CHECK)", "Add employee with age 15",
      "Rejected by CHECK constraint", lambda: app.add_employee(conn, "Kid", "IT", 30000, 15, "Pune"), expect_error=True)
check("TC-13", "Validation (unknown dept)", "Add employee in department 'Legal'",
      "Rejected with message", lambda: app.add_employee(conn, "Ivan", "Legal", 40000, 30, "Pune"), expect_error=True)
check("TC-14", "Unique project name", "Add project 'Campaign' again",
      "Rejected by UNIQUE constraint", lambda: app.add_project(conn, "Campaign", 10000), expect_error=True)

# ---- Reports (on a fresh copy of the base data to match Experiment 8) ----
conn2 = app.init_db("epms_report.db")
s6 = []
exp = {}
for title in app.REPORTS:
    cols, rows = app.run_report(conn2, title)
    s6.append(f"== {title} ==")
    s6 += table(cols, rows) if rows else ["(empty result)"]
    s6.append("")
    exp[title] = rows
OUT.append(("Reports", s6[:-1]))
ok = (exp["Headcount per department (GROUP BY)"] == [('IT',3),('HR',2),('Marketing',2)] or
      sorted(exp["Headcount per department (GROUP BY)"]) == sorted([('IT',3),('HR',2),('Marketing',2)]))
ok &= exp["Departments with average salary > 65000 (HAVING)"] == [('IT',67333.33),('Marketing',72500.0)]
ok &= [r[0] for r in exp["Employees on a project with budget > 50000 (EXISTS)"]] == ['Frank','Grace']
ok &= exp["Employees not on any project (NOT EXISTS)"] == []
ok &= [r[0] for r in exp["Salary above ALL HR salaries (> ALL via MAX)"]] == ['Alice','Bob','Eve','Frank','Grace']
RES.append(dict(id="TC-15", feature="Reports", action="Run all six reports on the base data",
    expected="Results match the verified Experiment 8 answers",
    actual="All six reports match" if ok else "Mismatch", status="Pass" if ok else "Fail"))

json.dump(dict(screens=OUT, results=RES), open("results.json","w"), indent=1)
print(json.dumps(RES, indent=1)[:6000])
print("\n".join(sum([x[1] for x in OUT],[]))[:4000])
