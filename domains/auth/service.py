from flask import (
    render_template, redirect, url_for,
    flash, request, Response
)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user
from models import (
    Faculty, Department, Course,
    User, Enrollment,
    AttendanceSession, AttendanceRecord
)
from utils import parse_matric, calculate_current_level
from io import StringIO
import csv
from datetime import datetime

def login():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip().lower()
        password = request.form['password']

        user = User.query.filter(
            (User.matric_number == identifier) | (User.username == identifier)
        ).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            
            db.session.refresh(user)

            if user.role == 'student':
                # First-time setup: parse matric to get department and level
                if user.department_id is None or user.current_level is None:
                    dept_name, enroll_year, _ = parse_matric(identifier)
                    if dept_name and enroll_year:
                        department = Department.query.filter_by(name=dept_name).first()
                        if department:
                            user.department_id = department.id
                            user.current_level = calculate_current_level(enroll_year)
                            db.session.commit()

                # ALWAYS run auto-enrollment (catches new/missed courses)
                if user.department_id and user.current_level:
                    courses = Course.query.filter_by(
                        department_id=user.department_id,
                        level=user.current_level
                    ).all()

                    for course in courses:
                        if not Enrollment.query.filter_by(
                            student_id=user.id, 
                            course_id=course.id
                        ).first():
                            db.session.add(Enrollment(student_id=user.id, course_id=course.id))
                    db.session.commit()

            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')

    return render_template('login.html')

@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))