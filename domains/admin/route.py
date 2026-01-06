from domains.admin import admin_bp
from .service import *

# Dashboard
admin_bp.route("/overview")(admin_overview)

# Faculties
admin_bp.route("/faculties")(admin_faculties)
admin_bp.route("/faculty/<int:faculty_id>")(admin_faculty_detail)
admin_bp.route("/add_faculty", methods=["GET", "POST"])(add_faculty)
admin_bp.route("/delete_faculty/<int:faculty_id>", methods=["POST"])(delete_faculty)
admin_bp.route("/edit_faculty/<int:faculty_id>", methods=["GET", "POST"])(edit_faculty)

# Departments
admin_bp.route("/add_department/<int:faculty_id>", methods=["POST"])(add_department)
admin_bp.route("/department/<int:department_id>")(admin_department_detail)
admin_bp.route("/delete_department/<int:department_id>", methods=["POST"])(delete_department)
admin_bp.route("/edit_department/<int:department_id>", methods=["GET", "POST"])(edit_department)

# Lecturers
admin_bp.route("/lecturers")(admin_lecturers)
admin_bp.route("/lecturer/<int:lecturer_id>")(admin_lecturer_detail)
admin_bp.route("/add_lecturer", methods=["POST"])(add_lecturer)
admin_bp.route("/delete_lecturer/<int:lecturer_id>", methods=["POST"])(delete_lecturer)
admin_bp.route("/edit_lecturer/<int:lecturer_id>", methods=["GET", "POST"])(edit_lecturer)

# Courses
admin_bp.route("/courses")(admin_courses)
admin_bp.route("/course/<int:course_id>")(admin_course_detail)
admin_bp.route("/add_course", methods=["POST"])(add_course)
admin_bp.route("/delete_course/<int:course_id>", methods=["POST"])(delete_course)
admin_bp.route("/edit_course/<int:course_id>", methods=["GET", "POST"])(edit_course)

# Students
admin_bp.route("/students")(admin_students)
admin_bp.route("/delete_student/<int:student_id>", methods=["POST"])(delete_student)
admin_bp.route("/import_students", methods=["GET", "POST"])(import_students)

# Utilities
admin_bp.route("/sync_enrollments")(sync_enrollments)
admin_bp.route("/course/<int:course_id>/attendance_report")(admin_course_attendance_report)
