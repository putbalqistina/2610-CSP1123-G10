import os
import sqlite3
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, session, url_for
from flask_apscheduler import APScheduler

app = Flask(__name__)
app.secret_key = "secretkey"
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Locate and load subjects.json path safely
base_path = os.path.dirname(__file__)
json_path = os.path.join(base_path, 'subjects.json')

def load_mmu_subjects():
    with open(json_path, 'r') as f:
        return json.load(f)

# Read dynamic data from JSON safely
try:
    with open(json_path, 'r') as f:
        mmu_subjects = json.load(f)
except FileNotFoundError:
    mmu_subjects = []

# --- Database setup ---
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
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
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            deadline TEXT NOT NULL,
            user_email TEXT NOT NULL,
            FOREIGN KEY (user_email) REFERENCES users (email)
        )
    ''') 
    
    try:
        conn.execute("ALTER TABLE assignments ADD COLUMN status TEXT DEFAULT 'to_do'")
    except sqlite3.OperationalError:
        pass  # prevents error if column already exists
    
    conn.commit()
    conn.close()

init_db()

# --- Hardcoded Dummy Data ---
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

assignments_data = {
    "CSP1123": ["Proposal", "Final Report"],
    "CDS1114": ["Lab 1", "Lab 2"],
    "CMT1134": ["Quiz 1", "Test 2"],
    "LCT1113": ["Blended Learning Week 2", "20% Presentation", "Debate Points"]
}


# --- Routes ---

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form["login"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        # Find user matching either the email or username
        user = conn.execute(
            "SELECT * FROM users WHERE (email = ? OR username = ?) AND password = ?",
            (login_input, login_input, password)
        ).fetchone()
        conn.close()

        if user:
            # CRITICAL FIX: Save user's EMAIL in session so dashboard queries work perfectly
            session["user"] = user["email"]
            return redirect(url_for("dashboard"))
        else:
            return "Invalid credentials ❌", 401

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        existing_user = conn.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?",
            (email, username)
        ).fetchone()

        if existing_user:
            conn.close()
            return render_template("register.html", error="Email or Username already registered!")

        conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route('/add_assignment', methods=['GET', 'POST'])
def add_assignment():
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for("login"))
    
    mmu_data = load_mmu_subjects() 

    if request.method == 'POST':
        subject = request.form.get('subject')
        title = request.form.get('title')
        deadline = request.form.get('deadline')
        
        conn = get_db()
        conn.execute(
            "INSERT INTO assignments (subject, title, deadline, user_email, status) VALUES (?, ?, ?, ?, 'to_do')",
            (subject, title, deadline, user_email)
        )
        conn.commit()
        conn.close()
        
        return redirect(url_for("dashboard"))

    return render_template("add_assignment.html", mmu_data=mmu_data)


@app.route('/dashboard')
def dashboard():
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('login'))

    conn = get_db()
    selected_filter = request.args.get('subject_filter', 'All')

    # Get unique subject dropdown list for the signed-in user
    subject_rows = conn.execute(
        "SELECT DISTINCT subject FROM assignments WHERE user_email = ?", 
        (user_email,)
    ).fetchall()
    user_subjects = [row['subject'] for row in subject_rows]

    # Filter assignments base configuration
    if selected_filter == 'All' or selected_filter == '':
        assignments = conn.execute(
            "SELECT * FROM assignments WHERE user_email = ?", 
            (user_email,)
        ).fetchall()
    else:
        assignments = conn.execute(
            "SELECT * FROM assignments WHERE user_email = ? AND subject = ?", 
            (user_email, selected_filter)
        ).fetchall()
    
    # --- Process Upcoming deadlines (The logic that was broken and dangling previously) ---
    today = datetime.today().date()
    upcoming = []
    
    for a in assignments:
        try:
            deadline = datetime.strptime(a["deadline"], "%Y-%m-%d").date()
            days_left = (deadline - today).days
            if 0 <= days_left <= 3:
                upcoming.append(a)
        except (ValueError, TypeError):
            pass # Skips iteration if formatting rules aren't matching standard format strings

    conn.close()
    return render_template('dashboard.html', subjects=user_subjects, assignments=assignments, upcoming=upcoming)


@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    user_identifier = session.get('user') 
    if not user_identifier:
        return redirect(url_for('login'))

    conn = get_db()

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        bio = request.form.get('bio')
        gender = request.form.get('gender')

        conn.execute('''
            UPDATE users 
            SET full_name = ?, username = ?, bio = ?, gender = ? 
            WHERE email = ? OR username = ?
        ''', (full_name, username, bio, gender, user_identifier, user_identifier))
        
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    user_data = conn.execute(
        "SELECT * FROM users WHERE email = ? OR username = ?", 
        (user_identifier, user_identifier)
    ).fetchone()
    conn.close()
    
    return render_template('index.html', user=user_data)


@app.route("/analytics")
def analytics():
    user_email = session.get("user")
    if not user_email:
        return redirect(url_for("login"))

    conn = get_db()
    assignments = conn.execute(
        "SELECT * FROM assignments WHERE user_email = ?", (user_email,)
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
        completed_pct = ongoing_pct = todo_pct = 0

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
        new_desc = request.form.get("description")
        if new_desc:
            data["description"] = new_desc

        new_comment = request.form.get("comment")
        if new_comment:
            data["comments"].append(new_comment)

        file = request.files.get("file")
        if file and file.filename != "":
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            data["attachment"] = file.filename

        status = request.form.get("status")
        conn = get_db()
        conn.execute("""
            UPDATE assignments 
            SET status = ?
            WHERE title = ?
        """, (status, title))
        conn.commit()
        conn.close()
        
        return redirect(url_for("assignment", title=title))
    
    conn = get_db()
    assignment_row = conn.execute("SELECT status FROM assignments WHERE title = ?", (title,)).fetchone()
    conn.close()

    status = assignment_row["status"] if assignment_row else "to_do"

    return render_template(
        "assignment.html",
        title=title,
        description=data["description"],
        comments=data["comments"],
        attachment=data["attachment"],
        status=status
    )


@app.route('/api/assignments')
def get_calendar_assignments():
    user_email = session.get('user')
    if not user_email:
        return json.dumps([])

    conn = get_db()
    rows = conn.execute(
        "SELECT title, deadline, subject FROM assignments WHERE user_email = ?",
        (user_email,)
    ).fetchall()
    conn.close()

    events = []
    for row in rows:
        events.append({
            "title": f"[{row['subject']}] {row['title']}",
            "start": row['deadline'], 
            "allDay": True,
            "color": "#3788d8"
        })
    
    return json.dumps(events)


@app.route('/calendar')
def calendar_view():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('calendar.html')


if __name__ == '__main__':
    app.run(debug=True)