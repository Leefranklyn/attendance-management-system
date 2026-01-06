# app.py - Complete final version (all fixes included)
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Faculty, Department, Course, Enrollment, AttendanceSession, AttendanceRecord
from utils import parse_matric, calculate_current_level
from config import Config
import os
from io import StringIO
import csv
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                name='Administrator',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: username='admin', password='admin123'")

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
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

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_overview'))
    elif current_user.role == 'lecturer':
        return redirect(url_for('lecturer_dashboard'))
    elif current_user.role == 'student':
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

# ==================== ADMIN PANEL ROUTES ====================

@app.route('/admin/overview')
@login_required
def admin_overview():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    faculties = Faculty.query.all()
    departments = Department.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    courses = Course.query.all()
    students = User.query.filter_by(role='student').all()

    return render_template('admin/overview.html',
                          faculties=faculties,
                          departments=departments,
                          lecturers=lecturers,
                          courses=courses,
                          students=students)

@app.route('/admin/faculties')
@login_required
def admin_faculties():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    faculties = Faculty.query.all()
    return render_template('admin/faculties.html', faculties=faculties)

@app.route('/admin/faculty/<int:faculty_id>')
@login_required
def admin_faculty_detail(faculty_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    faculty = Faculty.query.get_or_404(faculty_id)
    return render_template('admin/faculty_detail.html', faculty=faculty)

@app.route('/admin/add_faculty', methods=['GET', 'POST'])
@login_required
def add_faculty():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        name = request.form['name'].strip()
        if Faculty.query.filter_by(name=name).first():
            flash('Faculty already exists.', 'warning')
        else:
            faculty = Faculty(name=name)
            db.session.add(faculty)
            db.session.commit()
            flash('Faculty added successfully!', 'success')
        return redirect(url_for('admin_faculties'))
    return render_template('admin/add_faculty.html')

@app.route('/admin/add_department/<int:faculty_id>', methods=['GET', 'POST'])
@login_required
def add_department(faculty_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    faculty = Faculty.query.get_or_404(faculty_id)
    if request.method == 'POST':
        name = request.form['name'].strip()
        try:
            levels = int(request.form['levels'])
            if levels < 1 or levels > 6:
                raise ValueError
        except (ValueError, KeyError):
            flash('Please provide a valid number of levels (1-6).', 'danger')
            return redirect(url_for('admin_faculty_detail', faculty_id=faculty_id))

        if Department.query.filter_by(name=name, faculty_id=faculty_id).first():
            flash('Department already exists in this faculty.', 'warning')
        else:
            department = Department(name=name, faculty_id=faculty_id, levels=levels)
            db.session.add(department)
            db.session.commit()
            flash(f'Department "{name}" added with {levels} levels!', 'success')
        return redirect(url_for('admin_faculty_detail', faculty_id=faculty_id))
    return redirect(url_for('admin_faculty_detail', faculty_id=faculty_id))

@app.route('/admin/department/<int:department_id>')
@login_required
def admin_department_detail(department_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    department = Department.query.get_or_404(department_id)
    level_list = list(range(1, department.levels + 1))
    return render_template('admin/department_detail.html', department=department, levels=level_list)

@app.route('/admin/department/<int:department_id>/level/<int:level>')
@login_required
def admin_level_detail(department_id, level):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    department = Department.query.get_or_404(department_id)
    if level < 1 or level > department.levels:
        flash('Invalid level.', 'danger')
        return redirect(url_for('admin_department_detail', department_id=department_id))
    
    courses = Course.query.filter_by(department_id=department_id, level=level).all()
    lecturers = User.query.filter_by(role='lecturer').all()
    
    # Pre-calculate enrolled count for each course
    for course in courses:
        course.enrolled_count = course.enrollments.count()
    
    return render_template('admin/courses.html',
                          courses=courses,
                          departments=Department.query.all(),
                          lecturers=lecturers,
                          context_title=f"{level * 100} Level Courses - {department.name}",
                          context_breadcrumb=[
                              ('Faculties', url_for('admin_faculties')),
                              (department.faculty.name, url_for('admin_faculty_detail', faculty_id=department.faculty.id)),
                              (department.name, url_for('admin_department_detail', department_id=department.id)),
                              (f"{level * 100} Level", None)
                          ],
                          show_add_button=True,
                          prefill_department_id=department.id,
                          prefill_level=level)

@app.route('/admin/lecturers')
@login_required
def admin_lecturers():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    lecturers = User.query.filter_by(role='lecturer').order_by(User.name).all()
    departments = Department.query.all()
    
    for lecturer in lecturers:
        lecturer.course_count = lecturer.taught_courses.count()
        
    return render_template('admin/lecturers.html', lecturers=lecturers, departments=departments)

@app.route('/admin/lecturer/<int:lecturer_id>')
@login_required
def admin_lecturer_detail(lecturer_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    lecturer = User.query.get_or_404(lecturer_id)
    if lecturer.role != 'lecturer':
        flash('Not a lecturer.', 'danger')
        return redirect(url_for('admin_lecturers'))
    
    courses = Course.query.filter_by(lecturer_id=lecturer.id).all()
    course_data = []
    total_enrolled = 0
    
    for course in courses:
        # FIX: Explicit join to safely order by name
        students = db.session.query(User)\
            .join(Enrollment, Enrollment.student_id == User.id)\
            .filter(Enrollment.course_id == course.id)\
            .order_by(User.name)\
            .all()
        
        enrolled_count = len(students)
        total_enrolled += enrolled_count
        
        course_data.append({
            'course': course,
            'enrolled_count': enrolled_count,
            'students': students
        })
    
    return render_template('admin/lecturer_detail.html',
                          lecturer=lecturer,
                          course_data=course_data,
                          total_courses=len(courses),
                          total_enrolled=total_enrolled)

@app.route('/admin/add_lecturer', methods=['POST'])
@login_required
def add_lecturer():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    username = request.form['username'].strip()
    password = request.form['password']
    name = request.form['name'].strip()
    department_id = request.form.get('department_id') or None

    if User.query.filter_by(username=username).first():
        flash('Username already taken.', 'warning')
    else:
        lecturer = User(
            username=username,
            password_hash=generate_password_hash(password),
            name=name,
            role='lecturer',
            department_id=department_id
        )
        db.session.add(lecturer)
        db.session.commit()
        flash('Lecturer added successfully!', 'success')
    return redirect(url_for('admin_lecturers'))

@app.route('/admin/courses')
@login_required
def admin_courses():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    courses = Course.query.all()
    departments = Department.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    
    # Pre-calculate enrolled count
    for course in courses:
        course.enrolled_count = course.enrollments.count()
    
    return render_template('admin/courses.html', 
                          courses=courses, 
                          departments=departments, 
                          lecturers=lecturers)

@app.route('/admin/course/<int:course_id>')
@login_required
def admin_course_detail(course_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    sessions = AttendanceSession.query.filter_by(course_id=course_id)\
                                      .order_by(AttendanceSession.date.desc())\
                                      .all()
    
    enrolled_students = course.enrollments.count()
    
    return render_template('admin/course_detail.html',
                          course=course,
                          sessions=sessions,
                          enrolled_students=enrolled_students)

@app.route('/admin/course/<int:course_id>/attendance_report')
@login_required
def admin_course_attendance_report(course_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    sessions = AttendanceSession.query.filter_by(course_id=course_id)\
                                      .order_by(AttendanceSession.date)\
                                      .all()
    students = [enrollment.student for enrollment in course.enrollments]
    
    output = StringIO()
    writer = csv.writer(output)
    
    header = ['Matric Number', 'Student Name']
    for session in sessions:
        header.append(session.date.strftime('%Y-%m-%d'))
    header += ['Total Present', 'Percentage']
    writer.writerow(header)
    
    for student in students:
        row = [student.matric_number or 'N/A', student.name]
        present_count = 0
        for session in sessions:
            record = AttendanceRecord.query.filter_by(
                session_id=session.id,
                student_id=student.id
            ).first()
            if record:
                present_count += 1
                row.append('Present')
            else:
                row.append('Absent')
        percentage = round((present_count / len(sessions) * 100), 1) if sessions else 0
        row += [present_count, f"{percentage}%"]
        writer.writerow(row)
    
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={course.code}_attendance_report.csv"}
    )

@app.route('/admin/add_course', methods=['POST'])
@login_required
def add_course():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    code = request.form['code'].upper().strip()
    title = request.form['title'].strip()
    department_id = request.form['department_id']
    level = int(request.form['level'])
    lecturer_id = request.form['lecturer_id']

    if Course.query.filter_by(code=code, department_id=department_id, level=level).first():
        flash('Course already exists.', 'warning')
    else:
        course = Course(
            code=code,
            title=title,
            department_id=department_id,
            level=level,
            lecturer_id=lecturer_id
        )
        db.session.add(course)
        db.session.commit()
        flash('Course added successfully!', 'success')
    
    # Smart redirect
    if 'prefill_level' in request.form or request.referrer and 'level' in request.referrer:
        return redirect(request.referrer or url_for('admin_courses'))
    return redirect(url_for('admin_courses'))

# DELETE ROUTES

@app.route('/admin/delete_faculty/<int:faculty_id>', methods=['POST'])
@login_required
def delete_faculty(faculty_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    faculty = Faculty.query.get_or_404(faculty_id)
    if faculty.departments:
        flash('Cannot delete faculty with departments. Delete departments first.', 'danger')
    else:
        db.session.delete(faculty)
        db.session.commit()
        flash('Faculty deleted successfully.', 'success')
    return redirect(url_for('admin_faculties'))

@app.route('/admin/delete_department/<int:department_id>', methods=['POST'])
@login_required
def delete_department(department_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    department = Department.query.get_or_404(department_id)
    if department.courses:
        flash('Cannot delete department with courses. Delete courses first.', 'danger')
    else:
        db.session.delete(department)
        db.session.commit()
        flash('Department deleted successfully.', 'success')
    return redirect(url_for('admin_faculties'))

@app.route('/admin/delete_lecturer/<int:lecturer_id>', methods=['POST'])
@login_required
def delete_lecturer(lecturer_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    lecturer = User.query.get_or_404(lecturer_id)
    if lecturer.taught_courses:
        flash('Cannot delete lecturer assigned to courses. Reassign courses first.', 'danger')
    else:
        db.session.delete(lecturer)
        db.session.commit()
        flash('Lecturer deleted successfully.', 'success')
    return redirect(url_for('admin_lecturers'))

@app.route('/admin/delete_course/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully.', 'success')
    return redirect(url_for('admin_courses'))

# EDIT ROUTES

@app.route('/admin/edit_faculty/<int:faculty_id>', methods=['GET', 'POST'])
@login_required
def edit_faculty(faculty_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    faculty = Faculty.query.get_or_404(faculty_id)
    if request.method == 'POST':
        new_name = request.form['name'].strip()
        if Faculty.query.filter_by(name=new_name).first() and new_name != faculty.name:
            flash('Faculty name already exists.', 'warning')
        else:
            faculty.name = new_name
            db.session.commit()
            flash('Faculty updated successfully.', 'success')
        return redirect(url_for('admin_faculties'))
    return render_template('admin/edit_faculty.html', faculty=faculty)

@app.route('/admin/edit_department/<int:department_id>', methods=['GET', 'POST'])
@login_required
def edit_department(department_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    department = Department.query.get_or_404(department_id)
    if request.method == 'POST':
        new_name = request.form['name'].strip()
        new_levels = int(request.form['levels'])
        if Department.query.filter_by(name=new_name, faculty_id=department.faculty_id).first() and new_name != department.name:
            flash('Department name already exists in this faculty.', 'warning')
        else:
            department.name = new_name
            department.levels = new_levels
            db.session.commit()
            flash('Department updated successfully.', 'success')
        return redirect(url_for('admin_faculty_detail', faculty_id=department.faculty_id))
    return render_template('admin/edit_department.html', department=department)

@app.route('/admin/edit_lecturer/<int:lecturer_id>', methods=['GET', 'POST'])
@login_required
def edit_lecturer(lecturer_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    lecturer = User.query.get_or_404(lecturer_id)
    departments = Department.query.all()
    if request.method == 'POST':
        lecturer.name = request.form['name'].strip()
        lecturer.username = request.form['username'].strip()
        if request.form['password']:
            lecturer.password_hash = generate_password_hash(request.form['password'])
        lecturer.department_id = request.form.get('department_id') or None
        db.session.commit()
        flash('Lecturer updated successfully.', 'success')
        return redirect(url_for('admin_lecturers'))
    return render_template('admin/edit_lecturer.html', lecturer=lecturer, departments=departments)

@app.route('/admin/edit_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    departments = Department.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    if request.method == 'POST':
        course.code = request.form['code'].upper().strip()
        course.title = request.form['title'].strip()
        course.department_id = request.form['department_id']
        course.level = int(request.form['level'])
        course.lecturer_id = request.form['lecturer_id']
        db.session.commit()
        flash('Course updated successfully.', 'success')
        return redirect(url_for('admin_courses'))
    return render_template('admin/edit_course.html', course=course, departments=departments, lecturers=lecturers)

from datetime import datetime  # Make sure this is at the top

@app.route('/admin/students')
@login_required
def admin_students():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    search = request.args.get('search', '').strip()
    
    students = User.query.filter_by(role='student')
    
    # Get filters
    faculty_id = request.args.get('faculty_id', type=int)
    department_id = request.args.get('department_id', type=int)
    level = request.args.get('level', type=int)    
    
    if search:
        students = students.filter(User.name.ilike(f'%{search}%'))
    if faculty_id:
        students = students.join(Department).filter(Department.faculty_id == faculty_id)
    if department_id:
        students = students.filter(User.department_id == department_id)
    if level:
        students = students.filter(User.current_level == level)
    
    students = students.order_by(User.name).all()
    
    # Pre-calculate everything needed for modals
    student_data = []
    for student in students:
        enrolled_courses = [enrollment.course for enrollment in student.enrollments]
        enrolled_count = len(enrolled_courses)
        
        course_stats = []
        for course in enrolled_courses:
            sessions = AttendanceSession.query.filter_by(course_id=course.id).all()
            total_sessions = len(sessions)
            if sessions:
                session_ids = [s.id for s in sessions]
                present_count = AttendanceRecord.query.filter(
                    AttendanceRecord.student_id == student.id,
                    AttendanceRecord.session_id.in_(session_ids)
                ).count()
            else:
                present_count = 0
            percentage = round((present_count / total_sessions * 100), 1) if total_sessions > 0 else 0
            
            course_stats.append({
                'course': course,
                'present_count': present_count,
                'total_sessions': total_sessions,
                'percentage': percentage
            })
        
        student_data.append({
            'student': student,
            'enrolled_count': enrolled_count,
            'course_stats': course_stats
        })
    
    faculties = Faculty.query.all()
    departments = Department.query.all()
    total_students = User.query.filter_by(role='student').count()
    
    current_year = datetime.now().year
    years = list(range(current_year - 10, current_year + 1))
    
    return render_template('admin/students.html',
                          student_data=student_data,
                          faculties=faculties,
                          departments=departments,
                          total_students=total_students,
                          selected_faculty=faculty_id,
                          selected_department=department_id,
                          level=level,
                          years=years)

@app.route('/admin/import_students', methods=['GET', 'POST'])
@login_required
def import_students():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded.', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            added = 0
            skipped = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    name = row['Name'].strip()
                    matric = row['Matric Number'].strip().lower()
                    entry_year = int(row['Year of Entry'])
                    dept_name = row['Department'].strip()
                    transfer_str = row.get('Transfer', 'No').strip().lower()
                    
                    # Is transfer?
                    is_transfer = transfer_str in ['yes', 'true', '1', 'y']
                    
                    # Effective year for level calculation
                    effective_year = entry_year - 1 if is_transfer else entry_year
                    
                    # ... validation and department lookup ...
                    
                    department = Department.query.filter_by(name=dept_name).first()
                    if not department:
                        errors.append(f"Row {row_num}: Department '{dept_name}' not found")
                        continue
                    
                    user = User.query.filter_by(matric_number=matric).first()
                    if user:
                        skipped += 1
                    else:
                        default_password = 'student123'
                        user = User(
                            matric_number=matric,
                            password_hash=generate_password_hash(default_password),
                            name=name,
                            role='student',
                            department_id=department.id
                        )
                        db.session.add(user)
                        added += 1

                    # Use effective year for level and enrollment
                    current_level = calculate_current_level(effective_year)
                    user.current_level = current_level
                    user.department_id = department.id
                    db.session.commit()

                    # Enroll in courses for current level
                    courses = Course.query.filter_by(
                        department_id=department.id,
                        level=current_level
                    ).all()
                    
                    for course in courses:
                        if not Enrollment.query.filter_by(student_id=user.id, course_id=course.id).first():
                            db.session.add(Enrollment(student_id=user.id, course_id=course.id))
                    db.session.commit()

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
            
            msg = f'Import complete: {added} added, {skipped} skipped.'
            if errors:
                msg += f' {len(errors)} errors.'
                flash(msg, 'warning')
                for err in errors[:10]:  # show first 10
                    flash(err, 'danger')
            else:
                flash(msg, 'success')
            
            return redirect(url_for('admin_overview'))
    
    return render_template('admin/import_students.html')


@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        flash('Can only delete student accounts.', 'danger')
        return redirect(url_for('admin_students'))
    
    # Optional: delete related records
    Enrollment.query.filter_by(student_id=student.id).delete()
    AttendanceRecord.query.filter_by(student_id=student.id).delete()
    
    db.session.delete(student)
    db.session.commit()
    flash(f'Student {student.name} deleted successfully.', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/sync_enrollments')
@login_required
def sync_enrollments():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    students = User.query.filter_by(role='student').all()
    synced = 0
    for student in students:
        if student.department_id and student.current_level:
            courses = Course.query.filter_by(
                department_id=student.department_id,
                level=student.current_level
            ).all()
            for course in courses:
                if not Enrollment.query.filter_by(student_id=student.id, course_id=course.id).first():
                    db.session.add(Enrollment(student_id=student.id, course_id=course.id))
                    synced += 1
    db.session.commit()
    flash(f'Sync complete: {synced} enrollments added.', 'success')
    return redirect(url_for('admin_overview'))

# ==================== LECTURER ROUTES ====================

@app.route('/lecturer')
@login_required
def lecturer_dashboard():
    if current_user.role != 'lecturer':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    courses = Course.query.filter_by(lecturer_id=current_user.id).all()
    # Pre-calculate stats
    total_students = 0
    for course in courses:
        course.enrolled_count = course.enrollments.count()
        total_students += course.enrolled_count
    
    course_ids = [c.id for c in courses]
    if course_ids:
        active_sessions = AttendanceSession.query.filter(
            AttendanceSession.course_id.in_(course_ids),
            AttendanceSession.is_open == True
            ).all()
    else:
        active_sessions = []
    
    return render_template('lecturer/dashboard.html',
                          courses=courses,
                          total_students=total_students,
                          active_sessions=active_sessions)

from datetime import date

@app.route('/lecturer/course/<int:course_id>')
@login_required
def lecturer_course_detail(course_id):
    if current_user.role != 'lecturer':
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    if course.lecturer_id != current_user.id:
        flash('You are not assigned to this course.', 'danger')
        return redirect(url_for('lecturer_dashboard'))
    
    sessions = AttendanceSession.query.filter_by(course_id=course_id)\
                                      .order_by(AttendanceSession.date)\
                                      .all()
    
    active_session = AttendanceSession.query.filter_by(
        course_id=course_id, is_open=True
    ).first()
    
    enrolled_students = course.enrollments.count()
    
    today_date = date.today().isoformat()
    
    # FIX: Get students ordered by name via explicit join
    students = db.session.query(User)\
        .join(Enrollment, Enrollment.student_id == User.id)\
        .filter(Enrollment.course_id == course_id)\
        .order_by(User.name)\
        .all()
    
    # Pre-calculate attendance data
    attendance_data = []
    total_sessions = len(sessions)
    
    for student in students:
        present_count = 0
        session_status = []
        
        for session in sessions:
            record = AttendanceRecord.query.filter_by(
                session_id=session.id,
                student_id=student.id
            ).first()
            if record:
                present_count += 1
                session_status.append('Present')
            else:
                session_status.append('Absent')
        
        percentage = round((present_count / total_sessions * 100), 1) if total_sessions > 0 else 0
        attendance_data.append({
            'student': student,
            'session_status': session_status,
            'present_count': present_count,
            'percentage': percentage
        })
    
    return render_template('lecturer/course_detail.html',
                          course=course,
                          sessions=sessions,
                          active_session=active_session,
                          enrolled_students=enrolled_students,
                          today_date=today_date,
                          students=students,
                          attendance_data=attendance_data,
                          total_sessions=total_sessions)

@app.route('/lecturer/open_session/<int:course_id>', methods=['POST'])
@login_required
def open_attendance_session(course_id):
    if current_user.role != 'lecturer':
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    if course.lecturer_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('lecturer_dashboard'))
    
    date_str = request.form['date']
    duration = int(request.form['duration'])
    
    from datetime import datetime, timedelta
    session_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    end_time = datetime.now() + timedelta(minutes=duration)
    
    # Close any existing open session
    open_session = AttendanceSession.query.filter_by(course_id=course_id, is_open=True).first()
    if open_session:
        open_session.is_open = False
        db.session.commit()
    
    # Create new session
    session = AttendanceSession(
        course_id=course_id,
        date=session_date,
        start_time=datetime.now().time(),
        end_time=end_time.time(),
        is_open=True
    )
    db.session.add(session)
    db.session.commit()
    
    flash(f'Attendance opened for {duration} minutes!', 'success')
    return redirect(url_for('lecturer_course_detail', course_id=course_id))

@app.route('/lecturer/close_session/<int:session_id>', methods=['POST'])
@login_required
def close_attendance_session(session_id):
    session = AttendanceSession.query.get_or_404(session_id)
    if session.course.lecturer_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('lecturer_dashboard'))
    
    session.is_open = False
    db.session.commit()
    flash('Attendance session closed.', 'info')
    return redirect(url_for('lecturer_course_detail', course_id=session.course_id))

@app.route('/lecturer/course/<int:course_id>/export_csv')
@login_required
def lecturer_course_csv(course_id):
    if current_user.role != 'lecturer':
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    if course.lecturer_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('lecturer_dashboard'))
    
    sessions = AttendanceSession.query.filter_by(course_id=course_id)\
                                      .order_by(AttendanceSession.date)\
                                      .all()
    
    # FIX: Get students ordered by name via explicit join
    students = db.session.query(User)\
        .join(Enrollment, Enrollment.student_id == User.id)\
        .filter(Enrollment.course_id == course_id)\
        .order_by(User.name)\
        .all()
    
    output = StringIO()
    writer = csv.writer(output)
    
    header = ['Matric Number', 'Student Name']
    for idx, session in enumerate(sessions, 1):
        header.append(f'Week {idx} ({session.date.strftime("%d %b %Y")})')
    header += ['Total Present', 'Percentage']
    writer.writerow(header)
    
    total_sessions = len(sessions)
    for student in students:
        row = [student.matric_number or 'N/A', student.name]
        present_count = 0
        
        for session in sessions:
            record = AttendanceRecord.query.filter_by(
                session_id=session.id,
                student_id=student.id
            ).first()
            if record:
                row.append('Present')
                present_count += 1
            else:
                row.append('Absent')
        
        percentage = round((present_count / total_sessions * 100), 1) if total_sessions > 0 else 0
        row += [f'{present_count}/{total_sessions}', f'{percentage}%']
        writer.writerow(row)
    
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={course.code}_{course.title.replace(' ', '_')}_attendance.csv"}
    )

@app.route('/student')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get student's enrolled courses
    enrollments = current_user.enrollments
    courses = [enrollment.course for enrollment in enrollments]
    
    course_stats = []
    for course in courses:
        sessions = AttendanceSession.query.filter_by(course_id=course.id).all()
        total_sessions = len(sessions)
        
        # CORRECT WAY to count present records across multiple sessions
        if sessions:
            session_ids = [s.id for s in sessions]
            present_count = AttendanceRecord.query.filter(
                AttendanceRecord.student_id == current_user.id,
                AttendanceRecord.session_id.in_(session_ids)
            ).count()
        else:
            present_count = 0
        
        percentage = round((present_count / total_sessions * 100), 1) if total_sessions > 0 else 0
        
        active_session = AttendanceSession.query.filter_by(
            course_id=course.id,
            is_open=True
        ).first()
        
        already_marked = False
        if active_session:
            already_marked = AttendanceRecord.query.filter_by(
                session_id=active_session.id,
                student_id=current_user.id
            ).first() is not None
        
        course_stats.append({
            'course': course,
            'total_sessions': total_sessions,
            'present_count': present_count,
            'percentage': percentage,
            'active_session': active_session,
            'already_marked': already_marked
        })
    
    return render_template('student/dashboard.html', course_stats=course_stats)

@app.route('/student/change_password', methods=['GET', 'POST'])
@login_required
def student_change_password():
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect.', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
        elif len(new_password) < 6:
            flash('New password must be at least 6 characters.', 'danger')
        else:
            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('student_dashboard'))
    
    return render_template('student/change_password.html')

@app.route('/student/course/<int:course_id>')
@login_required
def student_course_detail(course_id):
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    
    # Check enrollment
    enrollment = Enrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course_id
    ).first()
    if not enrollment:
        flash('You are not enrolled in this course.', 'danger')
        return redirect(url_for('student_dashboard'))
    
    sessions = AttendanceSession.query.filter_by(course_id=course_id)\
                                      .order_by(AttendanceSession.date.desc())\
                                      .all()
    
    total_sessions = len(sessions)
    
    # Pre-calculate present count
    if sessions:
        session_ids = [s.id for s in sessions]
        present_count = AttendanceRecord.query.filter(
            AttendanceRecord.student_id == current_user.id,
            AttendanceRecord.session_id.in_(session_ids)
        ).count()
    else:
        present_count = 0
    
    percentage = round((present_count / total_sessions * 100), 1) if total_sessions > 0 else 0
    
    # Active session
    active_session = AttendanceSession.query.filter_by(
        course_id=course_id,
        is_open=True
    ).first()
    
    already_marked = False
    if active_session:
        already_marked = AttendanceRecord.query.filter_by(
            session_id=active_session.id,
            student_id=current_user.id
        ).first() is not None
    
    # Pre-calculate attendance records for each session
    session_records = {}
    for session in sessions:
        record = AttendanceRecord.query.filter_by(
            session_id=session.id,
            student_id=current_user.id
        ).first()
        session_records[session.id] = record  # None if absent, record if present
    
    return render_template('student/course_detail.html',
                          course=course,
                          sessions=sessions,
                          total_sessions=total_sessions,
                          present_count=present_count,
                          percentage=percentage,
                          active_session=active_session,
                          already_marked=already_marked,
                          session_records=session_records)

@app.route('/student/mark_present/<int:session_id>', methods=['POST'])
@login_required
def mark_present(session_id):
    if current_user.role != 'student':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    session = AttendanceSession.query.get_or_404(session_id)
    
    if not session.is_open:
        flash('This attendance session is closed.', 'danger')
        return redirect(url_for('student_course_detail', course_id=session.course_id))
    
    # Check if already marked
    existing = AttendanceRecord.query.filter_by(
        session_id=session_id,
        student_id=current_user.id
    ).first()
    
    if existing:
        flash('You have already marked present for this session.', 'info')
    else:
        record = AttendanceRecord(
            session_id=session_id,
            student_id=current_user.id,
            timestamp=datetime.utcnow()
        )
        db.session.add(record)
        db.session.commit()
        flash('Attendance marked successfully!', 'success')
    
    return redirect(url_for('student_course_detail', course_id=session.course_id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)