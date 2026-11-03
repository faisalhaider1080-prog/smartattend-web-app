# SmartAttend — Semester-based AI/ML Attendance Web App

A Flask web application for managing attendance across multiple semesters, with a KNN-based attendance-risk prototype. **No face recognition is used.** Teachers/admins record attendance manually.

## Features
- Admin login and role-gated setup pages
- Students, semesters, departments, classes, subjects, teachers
- Student-subject-semester enrollments
- Daily attendance with duplicate-day protection (one record per enrollment/date)
- Semester-wise attendance percentages and Excel export
- KNN attendance-risk prototype

## Quick start (SQLite)
1. Install Python 3.10+.
2. Create and activate a virtual environment.
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` (optional; default uses SQLite).
5. Initialize database: `flask --app app init-db`
6. Run: `python app.py`
7. Open `http://127.0.0.1:5000`

Initial administrator: `admin` / `Admin@12345`. Change this immediately and do not deploy with the default password.

## MySQL
Create a database:
```sql
CREATE DATABASE smartattend CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
Set `DATABASE_URL` in `.env`:
`mysql+pymysql://USER:PASSWORD@localhost/smartattend?charset=utf8mb4`
Then run the initialization command and start the app.

## Important setup notes
- Add students, semester(s), subjects, teachers and enrollments before marking attendance.
- A separate enrollment is required for each student + semester + subject.
- Attendance percentages are calculated per enrollment (student + subject + semester).
- Previous semester records remain stored separately.
- Admin/teacher/student portal login accounts are not fully provisioned in this starter build; the admin account is created by `init-db`. Add account-management workflows before production use.
- Add CSRF protection, password reset, audit logs, pagination, database migrations, backups, HTTPS, and stronger authorization before public deployment.

## KNN note
The demo KNN classifies attendance risk using features derived from current and recent attendance. Initial labels are rule-derived from the 75% threshold; this is a transparent prototype, not proof of predictive accuracy. For meaningful prediction, use consented historical attendance data, define an outcome window (e.g. future semester risk), split data by student/time to prevent leakage, and evaluate precision/recall before operational use.

## Data protection
Attendance is student education data. Restrict access, collect only necessary information, disclose use to students, retain data according to institutional policy, and provide correction mechanisms.
