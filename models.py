# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()

class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    departments = db.relationship('Department', backref='faculty', lazy=True)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    levels = db.Column(db.Integer, default=4)
    __table_args__ = (db.UniqueConstraint('name', 'faculty_id', name='unique_dept_faculty'),)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    matric_number = db.Column(db.String(50), unique=True, nullable=True)  # Students only
    username = db.Column(db.String(80), unique=True, nullable=True)       # Lecturers/Admin
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'lecturer', 'student'
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    current_level = db.Column(db.Integer, nullable=True)  # Students only
    department = db.relationship('Department', backref='users')

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('code', 'department_id', 'level'),)
    
    lecturer = db.relationship('User', backref=db.backref('taught_courses', lazy='dynamic'))
    department_rel = db.relationship('Department', backref='courses')
    # This line is critical!
    enrollments = db.relationship('Enrollment', back_populates='course', lazy='dynamic')
    
    

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'course_id'),)

    student = db.relationship('User', backref='enrollments')
    course = db.relationship('Course', back_populates='enrollments')

class AttendanceSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    is_open = db.Column(db.Boolean, default=False)
    course = db.relationship('Course', backref='sessions')
    
    records = db.relationship('AttendanceRecord', backref='session', lazy='dynamic')

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_session.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('session_id', 'student_id'),)
    student = db.relationship('User')
    
