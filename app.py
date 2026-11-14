import os
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError


app = Flask(__name__, instance_relative_config=True)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)

database_path = (Path(app.instance_path) / "students.db").resolve().as_posix()
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or os.urandom(32),
    SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "error"

SUBJECTS = (
    ("mathematics", "Mathematics"),
    ("english", "English"),
    ("science", "Science"),
    ("social_science", "Social Science"),
    ("computer", "Computer"),
    ("hindi", "Hindi"),
)
MARK_FIELDS = tuple(field for field, _label in SUBJECTS)
MAX_MARKS = 100
TOTAL_MAXIMUM = MAX_MARKS * len(SUBJECTS)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    roll_number = db.Column(db.String(30, collation="NOCASE"), nullable=False)
    class_name = db.Column(db.String(40, collation="NOCASE"), nullable=False)
    section = db.Column(db.String(20, collation="NOCASE"), nullable=False)
    mathematics = db.Column(db.Integer, nullable=False)
    english = db.Column(db.Integer, nullable=False)
    science = db.Column(db.Integer, nullable=False)
    social_science = db.Column(db.Integer, nullable=False)
    computer = db.Column(db.Integer, nullable=False)
    hindi = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "class_name",
            "section",
            "roll_number",
            name="uq_student_class_section_roll",
        ),
    )

    @property
    def total_obtained(self):
        return sum(getattr(self, field) for field in MARK_FIELDS)

    @property
    def percentage(self):
        return round(self.total_obtained / TOTAL_MAXIMUM * 100, 2)

    @property
    def grade(self):
        total = self.total_obtained
        if total >= 540:
            return "A+"
        if total >= 480:
            return "A"
        if total >= 420:
            return "B"
        if total >= 360:
            return "C"
        if total >= 300:
            return "D"
        if total >= 240:
            return "E"
        return "F"

    @property
    def passed(self):
        return all(getattr(self, field) >= 35 for field in MARK_FIELDS)

    @property
    def result_status(self):
        return "PASS" if self.passed else "FAIL"


def validate_student_form(form, existing_student=None):
    values = {
        "name": form.get("name", "").strip(),
        "roll_number": form.get("roll_number", "").strip(),
        "class_name": form.get("class_name", "").strip(),
        "section": form.get("section", "").strip(),
    }
    errors = {}
    length_limits = {
        "name": 100,
        "roll_number": 30,
        "class_name": 40,
        "section": 20,
    }

    for field, limit in length_limits.items():
        if not values[field]:
            errors[field] = "This field is required."
        elif len(values[field]) > limit:
            errors[field] = f"Must be {limit} characters or fewer."

    for field in MARK_FIELDS:
        raw_mark = form.get(field, "").strip()
        try:
            mark = int(raw_mark)
        except (TypeError, ValueError):
            errors[field] = "Enter a whole number from 0 to 100."
            continue
        if not 0 <= mark <= MAX_MARKS:
            errors[field] = "Marks must be between 0 and 100."
        else:
            values[field] = mark

    if not errors:
        duplicate_query = Student.query.filter(
            func.lower(Student.roll_number) == values["roll_number"].lower(),
            func.lower(Student.class_name) == values["class_name"].lower(),
            func.lower(Student.section) == values["section"].lower(),
        )
        if existing_student is not None:
            duplicate_query = duplicate_query.filter(Student.id != existing_student.id)
        if duplicate_query.first() is not None:
            errors["roll_number"] = "That roll number is already used in this class and section."

    return values, errors


def class_names():
    return [
        row[0]
        for row in db.session.query(Student.class_name)
        .distinct()
        .order_by(func.lower(Student.class_name))
        .all()
    ]


def sections_for(class_name):
    if not class_name:
        return []
    return [
        row[0]
        for row in db.session.query(Student.section)
        .filter(func.lower(Student.class_name) == class_name.lower())
        .distinct()
        .order_by(func.lower(Student.section))
        .all()
    ]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_template_data():
    return {"subjects": SUBJECTS}


def ensure_default_admin():
    admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123").strip() or "admin123"
    user = User.query.filter(func.lower(User.username) == admin_username.lower()).first()
    if user is None:
        db.session.add(
            User(
                username=admin_username,
                password_hash=generate_password_hash(admin_password),
            )
        )
        db.session.commit()
    return admin_username, admin_password


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard"))

        flash("Invalid username or password.", "error")
        return render_template("login.html", username=username), 401

    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    total_students = Student.query.count()
    passed_students = Student.query.filter(
        *[getattr(Student, field) >= 35 for field in MARK_FIELDS]
    ).count()
    failed_students = total_students - passed_students
    average_percentage = 0.0
    if total_students:
        average_total = db.session.query(
            func.avg(
                Student.mathematics
                + Student.english
                + Student.science
                + Student.social_science
                + Student.computer
                + Student.hindi
            )
        ).scalar()
        average_percentage = round(average_total / TOTAL_MAXIMUM * 100, 2)

    recent_students = Student.query.order_by(Student.created_at.desc(), Student.id.desc()).limit(5).all()
    return render_template(
        "dashboard.html",
        total_students=total_students,
        passed_students=passed_students,
        failed_students=failed_students,
        average_percentage=average_percentage,
        recent_students=recent_students,
    )


@app.route("/students/new", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        values, errors = validate_student_form(request.form)
        if errors:
            return render_template(
                "add_student.html",
                student=None,
                form_data=request.form,
                errors=errors,
            ), 400

        student = Student(**values)
        db.session.add(student)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return render_template(
                "add_student.html",
                student=None,
                form_data=request.form,
                errors={"roll_number": "That roll number is already in use."},
            ), 409

        flash(f"Student record for {student.name} was added.", "success")
        return redirect(url_for("student_result", student_id=student.id))

    return render_template("add_student.html", student=None, form_data={}, errors={})


@app.route("/students")
@login_required
def student_records():
    query = Student.query
    search = request.args.get("q", "").strip()
    class_filter = request.args.get("class_name", "").strip()
    section_filter = request.args.get("section", "").strip()

    if search:
        query = query.filter(Student.roll_number.ilike(f"%{search}%"))
    if class_filter:
        query = query.filter(func.lower(Student.class_name) == class_filter.lower())
    if section_filter:
        query = query.filter(func.lower(Student.section) == section_filter.lower())

    students = query.order_by(
        func.lower(Student.class_name),
        func.lower(Student.section),
        func.lower(Student.name),
    ).all()
    return render_template(
        "records.html",
        students=students,
        search=search,
        class_filter=class_filter,
        section_filter=section_filter,
        available_classes=class_names(),
        available_sections=sections_for(class_filter),
    )


@app.route("/students/<int:student_id>")
@login_required
def student_result(student_id):
    student = db.get_or_404(Student, student_id)
    return render_template("result.html", student=student)


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = db.get_or_404(Student, student_id)
    if request.method == "POST":
        values, errors = validate_student_form(request.form, existing_student=student)
        if errors:
            return render_template(
                "edit_student.html",
                student=student,
                form_data=request.form,
                errors=errors,
            ), 400

        for field, value in values.items():
            setattr(student, field, value)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return render_template(
                "edit_student.html",
                student=student,
                form_data=request.form,
                errors={"roll_number": "That roll number is already in use."},
            ), 409

        flash(f"Student record for {student.name} was updated.", "success")
        return redirect(url_for("student_result", student_id=student.id))

    return render_template("edit_student.html", student=student, form_data={}, errors={})


@app.post("/students/<int:student_id>/delete")
@login_required
def delete_student(student_id):
    student = db.get_or_404(Student, student_id)
    name = student.name
    db.session.delete(student)
    db.session.commit()
    flash(f"Student record for {name} was deleted.", "success")
    return redirect(url_for("student_records"))


@app.route("/rankings")
@login_required
def class_rankings():
    selected_class = request.args.get("class_name", "").strip()
    selected_section = request.args.get("section", "").strip()
    students = []

    if selected_class:
        query = Student.query.filter(func.lower(Student.class_name) == selected_class.lower())
        if selected_section:
            query = query.filter(func.lower(Student.section) == selected_section.lower())
        total_expression = (
            Student.mathematics
            + Student.english
            + Student.science
            + Student.social_science
            + Student.computer
            + Student.hindi
        )
        students = query.order_by(total_expression.desc(), func.lower(Student.name)).all()

        previous_total = None
        current_rank = 0
        for position, student in enumerate(students, start=1):
            if student.total_obtained != previous_total:
                current_rank = position
                previous_total = student.total_obtained
            student.rank = current_rank

    return render_template(
        "rankings.html",
        students=students,
        selected_class=selected_class,
        selected_section=selected_section,
        available_classes=class_names(),
        available_sections=sections_for(selected_class),
    )


@app.route("/students/<int:student_id>/marksheet.pdf")
@login_required
def student_marksheet(student_id):
    student = db.get_or_404(Student, student_id)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Marksheet - {student.name}",
        author="Student Percentage Generator",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SchoolTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            textColor=colors.HexColor("#142d4e"),
            alignment=TA_LEFT,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subtle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#64748b"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CenteredLabel",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#64748b"),
        )
    )
    story = []
    logo_placeholder = Paragraph(
        "<b>LOGO</b><br/><font size='7'>PLACEHOLDER</font>",
        ParagraphStyle(
            name="LogoPlaceholder",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#142d4e"),
        ),
    )
    school_block = [
        Paragraph("SCHOOL NAME", styles["SchoolTitle"]),
        Paragraph("STUDENT ACADEMIC MARKSHEET", styles["Subtle"]),
    ]
    header = Table([[logo_placeholder, school_block]], colWidths=[29 * mm, 145 * mm], rowHeights=[22 * mm])
    header.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (0, 0), 1, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([header, Spacer(1, 8 * mm)])

    student_details = [
        ["Student Name", escape(student.name), "Roll Number", escape(student.roll_number)],
        ["Class", escape(student.class_name), "Section", escape(student.section)],
    ]
    details_table = Table(student_details, colWidths=[27 * mm, 62 * mm, 27 * mm, 58 * mm])
    details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#475569")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe3ec")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([details_table, Spacer(1, 7 * mm)])

    marks_rows = [["Subject", "Maximum Marks", "Marks Obtained"]]
    for field, label in SUBJECTS:
        marks_rows.append([label, str(MAX_MARKS), str(getattr(student, field))])
    marks_rows.append(["Total", str(TOTAL_MAXIMUM), str(student.total_obtained)])
    marks_table = Table(marks_rows, colWidths=[94 * mm, 40 * mm, 40 * mm], repeatRows=1)
    marks_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#142d4e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -2), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eaf0f7")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe3ec")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([marks_table, Spacer(1, 7 * mm)])

    summary_rows = [
        ["Percentage", f"{student.percentage:.2f}%", "Grade", student.grade],
        ["Result", student.result_status, "Generated On", date.today().strftime("%d %B %Y")],
    ]
    summary_table = Table(summary_rows, colWidths=[27 * mm, 62 * mm, 27 * mm, 58 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("FONTNAME", (1, 1), (1, 1), "Helvetica-Bold"),
                (
                    "TEXTCOLOR",
                    (1, 1),
                    (1, 1),
                    colors.HexColor("#15803d") if student.passed else colors.HexColor("#b42318"),
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe3ec")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 15 * mm)])
    story.append(
        Paragraph(
            "This marksheet is generated electronically. The school logo and name can be customized for your institution.",
            styles["CenteredLabel"],
        )
    )
    document.build(story)
    buffer.seek(0)
    safe_roll = "".join(character for character in student.roll_number if character.isalnum() or character in "-_")
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"marksheet-{safe_roll or student.id}.pdf",
    )


@app.cli.command("seed-samples")
def seed_samples():
    """Insert a small set of sample students without duplicating existing records."""
    examples = [
        ("Aarav Sharma", "101", "10", "A", (95, 91, 94, 88, 98, 90)),
        ("Diya Patel", "102", "10", "A", (84, 89, 92, 81, 95, 87)),
        ("Kabir Singh", "103", "10", "A", (76, 80, 78, 74, 85, 79)),
        ("Meera Das", "201", "9", "B", (68, 72, 70, 67, 82, 73)),
        ("Arjun Rao", "202", "9", "B", (28, 62, 58, 60, 75, 64)),
    ]
    inserted = 0
    for name, roll, class_name, section, marks in examples:
        exists = Student.query.filter(
            func.lower(Student.roll_number) == roll.lower(),
            func.lower(Student.class_name) == class_name.lower(),
            func.lower(Student.section) == section.lower(),
        ).first()
        if exists is None:
            mark_values = dict(zip(MARK_FIELDS, marks))
            db.session.add(
                Student(
                    name=name,
                    roll_number=roll,
                    class_name=class_name,
                    section=section,
                    **mark_values,
                )
            )
            inserted += 1
    db.session.commit()
    print(f"Added {inserted} sample student record(s).")


with app.app_context():
    db.create_all()
    ensure_default_admin()


if __name__ == "__main__":
    app.run(debug=True)
