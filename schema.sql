-- Employee Project Management System: schema (SQLite; MySQL-style constraints)
PRAGMA foreign_keys = ON;

CREATE TABLE Department (
    dept_id    INTEGER PRIMARY KEY,
    dept_name  VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE Employee (
    emp_id     INTEGER PRIMARY KEY,
    name       VARCHAR(50) NOT NULL,
    dept_id    INTEGER NOT NULL,
    salary     DECIMAL(10,2) NOT NULL CHECK (salary > 0),
    age        INTEGER NOT NULL CHECK (age BETWEEN 18 AND 65),
    city       VARCHAR(40) NOT NULL,
    FOREIGN KEY (dept_id) REFERENCES Department(dept_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE Project (
    project_id   INTEGER PRIMARY KEY,
    project_name VARCHAR(60) NOT NULL UNIQUE,
    budget       DECIMAL(12,2) NOT NULL CHECK (budget > 0)
);

CREATE TABLE Assignment (
    emp_id      INTEGER NOT NULL,
    project_id  INTEGER NOT NULL,
    role        VARCHAR(30) NOT NULL DEFAULT 'Member',
    PRIMARY KEY (emp_id, project_id),
    FOREIGN KEY (emp_id) REFERENCES Employee(emp_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (project_id) REFERENCES Project(project_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- Business rule: an employee may work on at most 3 projects
CREATE TRIGGER trg_max_projects
BEFORE INSERT ON Assignment
WHEN (SELECT COUNT(*) FROM Assignment WHERE emp_id = NEW.emp_id) >= 3
BEGIN
    SELECT RAISE(ABORT, 'Employee already assigned to 3 projects');
END;

INSERT INTO Department VALUES (1,'IT'),(2,'HR'),(3,'Marketing');

INSERT INTO Employee VALUES
(1,'Alice',1,70000,30,'New York'),
(2,'Bob',1,60000,28,'Chicago'),
(3,'Charlie',2,55000,35,'New York'),
(4,'David',2,48000,40,'Chicago'),
(5,'Eve',3,70000,30,'Seattle'),
(6,'Frank',3,75000,32,'Chicago'),
(7,'Grace',1,72000,29,'Seattle');

INSERT INTO Project VALUES
(1,'AI Research',50000),
(2,'Web Development',45000),
(3,'Recruitment',30000),
(4,'Employee Training',35000),
(5,'Marketing Plan',40000),
(6,'Campaign',60000),
(7,'Infrastructure',55000);

INSERT INTO Assignment VALUES
(1,1,'Lead'),(2,2,'Lead'),(3,3,'Lead'),(4,4,'Lead'),
(5,5,'Lead'),(6,6,'Lead'),(7,7,'Lead');
