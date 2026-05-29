from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from flask_apscheduler import APScheduler
import datetime
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import schedule
import time
import os
app = Flask(__name__)
app.secret_key = "secretkey"

app.config['UPLOAD_FOLDER'] = 'static/uploads'

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            full_name TEXT,
            bio TEXT,
            gender TEXT,
            profile_pic TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            deadline TEXT NOT NULL,
            user_email TEXT NOT NULL,
            email_sent INTEGER DEFAULT 0,
            alert_shown INTEGER DEFAULT 0,
            FOREIGN KEY (user_email) REFERENCES users (email)
        )
    """)
    
    try:
        conn.execute("ALTER TABLE assignments ADD COLUMN status TEXT DEFAULT 'to_do'")
    except:
        pass  # prevents error if column already exists
    
    conn.commit()
    conn.close()


init_db()

def send_email(to_email, subject, body):
    sender = "yourgmail@gmail.com"
    password = "your_app_password"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

def check_deadlines():
    conn = get_db()

    assignments = conn.execute(
        "SELECT * FROM assignments"
    ).fetchall()

    today = datetime.today().date()

    for a in assignments:
        deadline_date = datetime.strptime(a["deadline"], "%Y-%m-%d").date()

        if deadline_date == today + timedelta(days=1):
            send_email(
                a["user_email"],
                "Assignment Reminder",
                f"Your assignment '{a['title']}' is due tomorrow."
            )

            conn.execute(
                "UPDATE assignments SET email_sent = 1 WHERE id = ?",
                (a["id"],)
            )
    conn.commit()
    conn.close()



@app.route("/")
def home():
    return render_template("landingpage.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form["login"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            """
            SELECT * FROM users
            WHERE (email = ? OR username = ?)
            AND password = ?
            """,
            (login_input, login_input, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = user["email"]
            return redirect("/dashboard")
        else:
            return "Invalid credentials ❌"

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()

        existing_user = conn.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?",
            (email, username)
        ).fetchone()

        if existing_user:
            conn.close()
            return render_template(
                "register.html",
                error="Email or username already registered!",
                success=False
            )

        conn.execute(
            """
            INSERT INTO users (username, email, password)
            VALUES (?, ?, ?)
            """,
            (username, email, password)
        )

        conn.commit()
        conn.close()

        return render_template("register.html", success=True)

    return render_template("register.html", success=False)


subjects = [
    {"code": "CSP1123", "name": "Mini IT Project"},
    {"code": "CDS1114", "name": "Digital Systems"},
    {"code": "CMT1134", "name": "Mathematics III"},
    {"code": "LCT1113", "name": "Critical Thinking"}
]

assignment_store = {
    "Proposal": {
        "description": "This is assignment description",
        "comments": ["my part - done", "need to finish before 20/4"],
        "attachment": None
    }
}

# dummy assignments
assignments_data = {
    "CSP1123": ["Proposal", "Final Report"],
    "CDS1114": ["Lab 1", "Lab 2"],
    "CMT1134": ["Quiz 1", "Test 2"],
    "LCT1113": ["Blended Learning Week 2", "20% Presentation", "Debate Points"]
    }
@app.route("/add_assignment", methods=["GET", "POST"])
def add_assignment():
    if "user" not in session:
        return redirect("/login")

    user_email = session["user"]

    if request.method == "POST":
        subject = request.form.get("subject")
        title = request.form.get("title")
        deadline = request.form.get("deadline")

        conn = get_db()
        conn.execute(
            """
            INSERT INTO assignments (subject, title, deadline, user_email)
            VALUES (?, ?, ?, ?)
            """,
            (subject, title, deadline, user_email)
        )
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_assignment.html", subjects=subjects)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    user_email = session["user"]

    conn = get_db()

    assignments = conn.execute(
        """
        SELECT * FROM assignments
        WHERE user_email = ?
        ORDER BY deadline ASC
        """,
        (user_email,)
    ).fetchall()

    conn.close()



    today = datetime.today().date()

    upcoming = []

    for a in assignments:
        deadline = datetime.strptime(a["deadline"], "%Y-%m-%d").date()

        days_left = (deadline - today).days

        # only assignments due within next 3 days
        if 0 <= days_left <= 3:
            upcoming.append(a)

    conn.close()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM assignments")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assignments WHERE status = 'completed'")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assignments WHERE status = 'ongoing'")
    ongoing = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assignments WHERE status = 'to_do'")
    todo = cursor.fetchone()[0]

    conn.close()

    if total == 0:
        completed_pct = ongoing_pct = todo_pct = 0
    else:
        completed_pct = (completed / total) * 100
        ongoing_pct = (ongoing / total) * 100
        todo_pct = (todo / total) * 100

    return render_template(
        "dashboard.html",
        subjects=subjects,
        assignments=assignments,
        upcoming=upcoming,
    )

@app.route("/analytics")
def analytics():

    if "user" not in session:
        return redirect("/login")

    conn = get_db()

    assignments = conn.execute(
        """
        SELECT * FROM assignments
        WHERE user_email = ?
        """,
        (session["user"],)
    ).fetchall()

    conn.close()

    completed = 0
    ongoing = 0
    todo = 0

    for a in assignments:

        if a["status"] == "completed":
            completed += 1

        elif a["status"] == "ongoing":
            ongoing += 1

        elif a["status"] == "to_do":
            todo += 1

    total = completed + ongoing + todo

    if total > 0:
        completed_pct = round((completed / total) * 100)
        ongoing_pct = round((ongoing / total) * 100)
        todo_pct = round((todo / total) * 100)

    else:
        completed_pct = 0
        ongoing_pct = 0
        todo_pct = 0

    return render_template(
        "analytics.html",
        completed=completed,
        ongoing=ongoing,
        todo=todo,
        completed_pct=completed_pct,
        ongoing_pct=ongoing_pct,
        todo_pct=todo_pct
    )

@app.route('/subject/<code>')
def subject(code):
    assignments = assignments_data.get(code, [])
    return render_template('subject.html', code=code, assignments=assignments)

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user" not in session:
        return redirect("/login")

    user_email = session["user"]
    conn = get_db()

    if request.method == "POST":
        full_name = request.form.get("full_name")
        bio = request.form.get("bio")
        gender = request.form.get("gender")

        conn.execute(
            """
            UPDATE users
            SET full_name = ?, bio = ?, gender = ?
            WHERE email = ?
            """,
            (full_name, bio, gender, user_email)
        )

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    user_data = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (user_email,)
    ).fetchone()

    conn.close()

    return render_template("index.html", user=user_data)

@app.route('/assignment/<title>', methods=["GET", "POST"])
def assignment(title):

    if title not in assignment_store:
        assignment_store[title] = {
            "description": "",
            "comments": [],
            "attachment": None
        }

    data = assignment_store[title]

    if request.method == "POST":

        # update description
        new_desc = request.form.get("description")
        if new_desc:
            data["description"] = new_desc

        # add comment
        new_comment = request.form.get("comment")
        if new_comment:
            data["comments"].append(new_comment)

        # file upload
        file = request.files.get("file")
        if file and file.filename != "":
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            data["attachment"] = file.filename

        status = request.form.get("status")
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE assignments 
            SET status = ?
            WHERE title = ?
        """, (status, title))

        conn.commit()
        conn.close()
        return redirect(url_for("assignment", title=title))
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM assignments WHERE title = ?", (title,))
    assignment = cursor.fetchone()

    conn.close()

    return render_template(
        "assignment.html",
        title=title,
        description=data["description"],
        comments=data["comments"],
        attachment=data["attachment"],
        status = assignment[0] if assignment else "to_do"
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)