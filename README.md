# Student Percentage Generator

A beginner-friendly Flask application for entering student marks, calculating results, managing records, viewing class rankings, and downloading PDF marksheets.

## What the app does

- Stores student records and marks in `instance/students.db` using SQLite.
- Calculates totals, percentages, grades, and pass/fail results automatically.
- Prevents duplicate roll numbers within the same class and section (case-insensitive).
- Provides a dashboard, searchable records, individual results, editing, and deletion.
- Shows class rankings. Students with the same total share the same rank, and the next rank is skipped (for example: 1, 1, 3).
- Generates a downloadable PDF marksheet for each student.
- Includes secure login using hashed passwords and a real SQLite-backed user table.
- Includes CSRF protection for form submissions and validates marks on the server.

Each of the six subjects has a maximum of 100 marks. A student passes only when every subject mark is at least 35. The percentage is shown to two decimal places. Grades use these percentage cutoffs: 90 A+, 80 A, 70 B, 60 C, 50 D, 40 E, and below 40 F.

## Project files

- `app.py` — Flask routes, database model, validation, calculations, PDF generation, and sample-data command.
- `requirements.txt` — Python packages required by the app.
- `static/style.css` — responsive navy-and-white interface styling.
- `static/script.js` — mobile navigation, delete confirmation, and notification controls.
- `templates/base.html` — shared page layout and navigation.
- `templates/dashboard.html` — summary cards, quick actions, and recent records.
- `templates/add_student.html` and `templates/edit_student.html` — student entry and editing pages.
- `templates/_student_form.html` — shared student form fields.
- `templates/records.html` — searchable and filterable student list.
- `templates/result.html` — individual result and PDF download link.
- `templates/rankings.html` — class and section rankings.
- `instance/students.db` — created automatically the first time the app runs; student data remains between restarts.

## Setup on Windows

Open the `Student_Percentage_Generator` folder in VS Code. In the VS Code terminal, run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell prevents activation, allow local scripts for your Windows user and activate again:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

Run the app:

```powershell
python -m flask --app app run --debug
```

Open the local address printed in the terminal (usually `http://127.0.0.1:5000`). The app now redirects unauthenticated users to a real login screen. The default administrator account is created automatically when the database initializes: username `admin`, password `admin123`.

For a production setup, change the password before exposing the app to others by setting `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables or by updating the stored user record in the database.

## Deploy on Render

Create a **Web Service** from this repository and use these commands:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn --bind 0.0.0.0:$PORT app:app`

Set `SECRET_KEY` to a long, random value, and set `ADMIN_USERNAME` and `ADMIN_PASSWORD` to non-default credentials in the service's environment variables. The default credentials are only suitable for local testing.

The app currently stores data in SQLite at `instance/students.db`. Render's free web services do not provide persistent disks, so records may be lost when the service restarts or redeploys. Use a host/storage plan with a persistent disk or migrate to a managed database before entering important student records.

## Add sample student records

With the virtual environment active and the terminal in this project folder, run:

```powershell
python -m flask --app app seed-samples
```

The command is safe to run more than once: it skips sample roll numbers that are already present in the corresponding class and section.

## Using the application

1. Choose **Add student**, fill in student details and all six whole-number marks, then save.
2. Open **Student records** to search by roll number, filter records, open a result, edit it, or delete it.
3. Use **Download PDF** on an individual result page to save a marksheet.
4. Open **Class rankings**, choose a class and optionally a section, then show the results.

## Security and customization notes

- The app uses CSRF-protected POST forms and parameterized SQLAlchemy queries.
- By default, the app is intended for local use and testing. Before exposing it to a network, configure a persistent random `SECRET_KEY` environment variable and add authentication and production deployment settings.
- Replace `SCHOOL NAME` and the logo placeholder in `app.py`'s PDF layout with your school's details when ready.
- Do not delete `instance/students.db` unless you intentionally want to remove the saved records. This database file is excluded from Git to help protect student data.
