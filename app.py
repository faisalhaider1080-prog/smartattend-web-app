import os
from datetime import datetime, date
from functools import wraps
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import func
from config import Config
from extensions import db, login_manager
from models import User, Student, Department, ClassGroup, Teacher, Semester, Subject, Enrollment, Attendance, KNNPrediction
from ml_model import attendance_features, train_and_predict

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles: abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return deco

@app.cli.command("init-db")
def init_db():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        u=User(username="admin", role="admin"); u.set_password("Admin@12345"); db.session.add(u); db.session.commit()
    print("Database ready. Default login: admin / Admin@12345 (change it immediately).")

@app.route("/")
def home():
    if current_user.is_authenticated: return redirect(url_for("dashboard"))
    return redirect(url_for("auth_login"))

@app.route("/login", methods=["GET","POST"])
def auth_login():
    if request.method == "POST":
        user=User.query.filter_by(username=request.form.get("username","").strip()).first()
        if user and user.check_password(request.form.get("password","")):
            login_user(user); return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("auth_login"))

@app.route("/dashboard")
@login_required
def dashboard():
    today=date.today()
    return render_template("dashboard.html",
        students=Student.query.count(), semesters=Semester.query.count(),
        today_records=Attendance.query.filter_by(class_date=today).count(),
        present=Attendance.query.filter_by(class_date=today,status="Present").count(),
        recent=Attendance.query.order_by(Attendance.class_date.desc()).limit(8).all())

@app.route("/students", methods=["GET","POST"])
@role_required("admin")
def students():
    if request.method=="POST":
        s=Student(roll_no=request.form["roll_no"].strip(), full_name=request.form["full_name"].strip(), email=request.form.get("email"), class_id=int(request.form["class_id"]) if request.form.get("class_id") else None)
        db.session.add(s)
        try: db.session.commit(); flash("Student added.", "success")
        except Exception: db.session.rollback(); flash("Could not add student. Check duplicate roll number.", "danger")
        return redirect(url_for("students"))
    return render_template("students.html", students=Student.query.order_by(Student.roll_no).all(), classes=ClassGroup.query.all())

@app.route("/semesters", methods=["GET","POST"])
@role_required("admin")
def semesters():
    if request.method=="POST":
        try:
            sem=Semester(name=request.form["name"], academic_year=request.form["academic_year"], start_date=date.fromisoformat(request.form["start_date"]), end_date=date.fromisoformat(request.form["end_date"]))
            if sem.end_date < sem.start_date: raise ValueError()
            db.session.add(sem); db.session.commit(); flash("Semester created.", "success")
        except Exception: db.session.rollback(); flash("Invalid semester details or database error.", "danger")
        return redirect(url_for("semesters"))
    return render_template("semesters.html", semesters=Semester.query.order_by(Semester.start_date.desc()).all())

@app.route("/setup", methods=["GET","POST"])
@role_required("admin")
def setup():
    if request.method=="POST":
        kind=request.form["kind"]; name=request.form["name"].strip()
        if kind=="department": db.session.add(Department(name=name))
        elif kind=="class": db.session.add(ClassGroup(name=name))
        elif kind=="subject": db.session.add(Subject(code=request.form.get("code","").strip(), name=name))
        elif kind=="teacher": db.session.add(Teacher(full_name=name,email=request.form.get("email")))
        try: db.session.commit(); flash("Record added.", "success")
        except Exception: db.session.rollback(); flash("Could not add record; check for duplicates.", "danger")
        return redirect(url_for("setup"))
    return render_template("setup.html", departments=Department.query.all(), classes=ClassGroup.query.all(), subjects=Subject.query.all(), teachers=Teacher.query.all())

@app.route("/enrollments", methods=["GET","POST"])
@role_required("admin")
def enrollments():
    if request.method=="POST":
        e=Enrollment(student_id=int(request.form["student_id"]), semester_id=int(request.form["semester_id"]), subject_id=int(request.form["subject_id"]), teacher_id=int(request.form["teacher_id"]) if request.form.get("teacher_id") else None)
        db.session.add(e)
        try: db.session.commit(); flash("Enrollment created.", "success")
        except Exception: db.session.rollback(); flash("Enrollment already exists or invalid.", "danger")
        return redirect(url_for("enrollments"))
    return render_template("enrollments.html", enrollments=Enrollment.query.all(), students=Student.query.all(), semesters=Semester.query.all(), subjects=Subject.query.all(), teachers=Teacher.query.all())

@app.route("/attendance", methods=["GET","POST"])
@login_required
def attendance():
    if request.method=="POST":
        try:
            eid=int(request.form["enrollment_id"]); day=date.fromisoformat(request.form["class_date"]); status=request.form["status"]
            if status not in ("Present","Absent","Leave"): raise ValueError()
            row=Attendance.query.filter_by(enrollment_id=eid,class_date=day).first()
            if row: row.status=status; row.marked_by=current_user.id
            else: db.session.add(Attendance(enrollment_id=eid,class_date=day,status=status,marked_by=current_user.id))
            db.session.commit(); flash("Attendance saved.", "success")
        except Exception: db.session.rollback(); flash("Could not save attendance. Check the selected enrollment/date.", "danger")
        return redirect(url_for("attendance"))
    sem_id=request.args.get("semester_id", type=int)
    q=Attendance.query.join(Enrollment).order_by(Attendance.class_date.desc())
    if sem_id: q=q.filter(Enrollment.semester_id==sem_id)
    return render_template("attendance.html", rows=q.limit(300).all(), enrollments=Enrollment.query.all(), semesters=Semester.query.all(), selected=sem_id)

@app.route("/reports")
@login_required
def reports():
    sem_id=request.args.get("semester_id", type=int)
    enrollments=Enrollment.query
    if sem_id: enrollments=enrollments.filter_by(semester_id=sem_id)
    report=[]
    for e in enrollments.all():
        rows=Attendance.query.filter_by(enrollment_id=e.id).all()
        total=len(rows); present=sum(r.status=="Present" for r in rows); absent=sum(r.status=="Absent" for r in rows); leave=sum(r.status=="Leave" for r in rows)
        report.append({"student":e.student,"subject":e.subject,"semester":e.semester,"total":total,"present":present,"absent":absent,"leave":leave,"pct":round(present/total*100,1) if total else 0})
    return render_template("reports.html", report=report, semesters=Semester.query.all(), selected=sem_id)

@app.route("/reports/export")
@login_required
def export_report():
    import pandas as pd
    sem_id=request.args.get("semester_id", type=int)
    q=Enrollment.query
    if sem_id: q=q.filter_by(semester_id=sem_id)
    data=[]
    for e in q.all():
        rows=Attendance.query.filter_by(enrollment_id=e.id).all()
        total=len(rows); present=sum(r.status=="Present" for r in rows)
        data.append({"Roll No":e.student.roll_no,"Student":e.student.full_name,"Subject":e.subject.name,"Semester":e.semester.name,"Academic Year":e.semester.academic_year,"Classes":total,"Present":present,"Absent":sum(r.status=="Absent" for r in rows),"Leave":sum(r.status=="Leave" for r in rows),"Attendance %":round(present/total*100,1) if total else 0})
    output=BytesIO(); pd.DataFrame(data).to_excel(output,index=False); output.seek(0)
    return send_file(output,as_attachment=True,download_name="semester_attendance.xlsx",mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/ai-risk", methods=["GET","POST"])
@role_required("admin","teacher")
def ai_risk():
    semester_id=request.args.get("semester_id",type=int)
    semesters=Semester.query.all()
    results=[]
    if semester_id:
        # Historical labels are generated from completed attendance. This is a transparent baseline:
        # <75% is high risk; >=75% is low risk. KNN is trained only when enough examples exist.
        examples=[]; targets=[]
        enrollments=Enrollment.query.filter_by(semester_id=semester_id).all()
        current=[]
        for e in enrollments:
            rows=Attendance.query.filter_by(enrollment_id=e.id).order_by(Attendance.class_date).all()
            statuses=[r.status for r in rows if r.status in ("Present","Absent")]
            if len(statuses)<3: continue
            feat=attendance_features(statuses)
            label="High Risk" if feat[0] < .75 else "Low Risk"
            examples.append((feat,label))
            current.append((e,feat,label,len(statuses)))
        # Train/evaluate with the available labeled historical rows; avoid claiming future certainty.
        model=train_and_predict(examples)
        for e,feat,label,n in current:
            pred=model.predict([feat])[0] if model else label
            results.append({"student":e.student,"subject":e.subject,"features":feat,"risk":pred,"count":n,"basis":"KNN" if model else "Rule-based baseline (need 3+ records for KNN)"})
    return render_template("ai_risk.html", semesters=semesters, selected=semester_id, results=results)

if __name__=="__main__": app.run(debug=False)
