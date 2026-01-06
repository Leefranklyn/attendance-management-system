from flask import (
    render_template, redirect, url_for,
    flash, request, Response
)
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from extensions import db

from models import (
    Faculty, Department, Course,
    User, Enrollment,
    AttendanceSession, AttendanceRecord
)
from utils import calculate_current_level
from io import StringIO
import csv
from datetime import datetime

# ---------- HELPERS ----------

def admin_only():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return False
    return True

# ---------- DASHBOARD ----------

@login_required
def admin_overview():
    if not admin_only():
        return redirect(url_for("dashboard"))

    return render_template(
        "admin/overview.html",
        faculties=Faculty.query.all(),
        departments=Department.query.all(),
        lecturers=User.query.filter_by(role="lecturer").all(),
        courses=Course.query.all(),
        students=User.query.filter_by(role="student").all()
    )

# ---------- FACULTIES ----------

@login_required
def admin_faculties():
    if not admin_only():
        return redirect(url_for("dashboard"))

    return render_template(
        "admin/faculties.html",
        faculties=Faculty.query.all()
    )

@login_required
def admin_faculty_detail(faculty_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    faculty = Faculty.query.get_or_404(faculty_id)
    return render_template("admin/faculty_detail.html", faculty=faculty)

@login_required
def add_faculty():
    if not admin_only():
        return redirect(url_for("dashboard"))

    name = request.form["name"].strip()
    if Faculty.query.filter_by(name=name).first():
        flash("Faculty already exists.", "warning")
    else:
        db.session.add(Faculty(name=name))
        db.session.commit()
        flash("Faculty added successfully.", "success")

    return redirect(url_for("admin.admin_faculties"))

@login_required
def delete_faculty(faculty_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    faculty = Faculty.query.get_or_404(faculty_id)
    if faculty.departments:
        flash("Delete departments first.", "danger")
    else:
        db.session.delete(faculty)
        db.session.commit()
        flash("Faculty deleted.", "success")

    return redirect(url_for("admin.admin_faculties"))

@login_required
def edit_faculty(faculty_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    faculty = Faculty.query.get_or_404(faculty_id)

    if request.method == "POST":
        faculty.name = request.form["name"].strip()
        db.session.commit()
        flash("Faculty updated.", "success")
        return redirect(url_for("admin.admin_faculties"))

    return render_template("admin/edit_faculty.html", faculty=faculty)

# ---------- DEPARTMENTS ----------

@login_required
def add_department(faculty_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    name = request.form["name"].strip()
    levels = int(request.form["levels"])

    if Department.query.filter_by(name=name, faculty_id=faculty_id).first():
        flash("Department already exists.", "warning")
    else:
        db.session.add(
            Department(
                name=name,
                faculty_id=faculty_id,
                levels=levels
            )
        )
        db.session.commit()
        flash("Department added.", "success")

    return redirect(url_for("admin.admin_faculty_detail", faculty_id=faculty_id))

@login_required
def admin_department_detail(department_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    department = Department.query.get_or_404(department_id)
    levels = list(range(1, department.levels + 1))
    return render_template(
        "admin/department_detail.html",
        department=department,
        levels=levels
    )

@login_required
def delete_department(department_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    department = Department.query.get_or_404(department_id)
    if department.courses:
        flash("Delete courses first.", "danger")
    else:
        db.session.delete(department)
        db.session.commit()
        flash("Department deleted.", "success")

    return redirect(url_for("admin.admin_faculties"))

@login_required
def edit_department(department_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    department = Department.query.get_or_404(department_id)

    if request.method == "POST":
        department.name = request.form["name"].strip()
        department.levels = int(request.form["levels"])
        db.session.commit()
        flash("Department updated.", "success")
        return redirect(
            url_for(
                "admin.admin_faculty_detail",
                faculty_id=department.faculty_id
            )
        )

    return render_template("admin/edit_department.html", department=department)

# ---------- LECTURERS ----------

@login_required
def admin_lecturers():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    lecturers = User.query.filter_by(role='lecturer').order_by(User.name).all()
    departments = Department.query.all()
    
    for lecturer in lecturers:
        lecturer.course_count = lecturer.taught_courses.count()
        
    return render_template('admin/lecturers.html', lecturers=lecturers, departments=departments)

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

# ---------- COURSES ----------

@login_required
def admin_courses():
    if not admin_only():
        return redirect(url_for("dashboard"))

    courses = Course.query.all()
    for c in courses:
        c.enrolled_count = c.enrollments.count()

    return render_template(
        "admin/courses.html",
        courses=courses,
        departments=Department.query.all(),
        lecturers=User.query.filter_by(role="lecturer").all()
    )

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

@login_required
def add_course():
    if not admin_only():
        return redirect(url_for("dashboard"))

    course = Course(
        code=request.form["code"].upper().strip(),
        title=request.form["title"].strip(),
        department_id=request.form["department_id"],
        level=int(request.form["level"]),
        lecturer_id=request.form["lecturer_id"]
    )
    db.session.add(course)
    db.session.commit()
    flash("Course added.", "success")

    return redirect(request.referrer or url_for("admin.admin_courses"))

@login_required
def delete_course(course_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    db.session.delete(Course.query.get_or_404(course_id))
    db.session.commit()
    flash("Course deleted.", "success")
    return redirect(url_for("admin.admin_courses"))

@login_required
def edit_course(course_id):
    if not admin_only():
        return redirect(url_for("dashboard"))

    course = Course.query.get_or_404(course_id)

    if request.method == "POST":
        course.code = request.form["code"].upper()
        course.title = request.form["title"]
        course.department_id = request.form["department_id"]
        course.level = int(request.form["level"])
        course.lecturer_id = request.form["lecturer_id"]
        db.session.commit()
        flash("Course updated.", "success")
        return redirect(url_for("admin.admin_courses"))

    return render_template(
        "admin/edit_course.html",
        course=course,
        departments=Department.query.all(),
        lecturers=User.query.filter_by(role="lecturer").all()
    )

# ---------- STUDENTS ----------

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