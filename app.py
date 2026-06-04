import os
import sqlite3
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import uuid

from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory
from flask_apscheduler import APScheduler
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secretkey"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Ensure upload folder directory structure exists on startup
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Locate and load subjects.json path safely
base_path = os.path.dirname(__file__)
json_path = os.path.join(base_path, 'subjects.json')

# --- Helper Functions ---

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def load_mmu_subjects():
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'zip'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_color_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS subject_colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            subject TEXT,
            color_code TEXT,
            UNIQUE(user_email, subject)
        )
    ''')
    conn.commit()
    conn.close()

# Panggil fungsi ini semasa startup aplikasi Flask
init_color_db()

# --- Data Stores ---

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
        "attachment": []
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
        user = conn.execute(
            "SELECT * FROM users WHERE (email = ? OR username = ?) AND password = ?",
            (login_input, login_input, password)
        ).fetchone()
        conn.close()

        if user:
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
    user_data = conn.execute(
        "SELECT * FROM users WHERE email = ? OR username = ?", 
        (user_email, user_email)
    ).fetchone()
    
    selected_filter = request.args.get('subject_filter', 'All')
    

    subject_rows = conn.execute(
        "SELECT DISTINCT subject FROM assignments WHERE user_email = ?", 
        (user_email,)
    ).fetchall()
    user_subjects = [row['subject'] for row in subject_rows]

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
    
    today = datetime.today().date()
    upcoming = []
    
    for a in assignments:
        try:
            deadline = datetime.strptime(a["deadline"], "%Y-%m-%d").date()
            days_left = (deadline - today).days
            if 0 <= days_left <= 3:
                upcoming.append(a)
        except (ValueError, TypeError):
            pass

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
    short_code = code.split(" - ")[0].strip()
    assignments = assignments_data.get(short_code, [])
    return render_template('subject.html', code=code, assignments=assignments)


@app.route('/assignment/<title>', methods=["GET", "POST"])
def assignment(title):
    if title not in assignment_store:
        assignment_store[title] = {
            "description": "",
            "comments": [],
            "attachment": []
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

        if (
            file and
            file.filename != "" and
            len(data["attachment"]) < 3 and 
            allowed_file(file.filename)
        ):
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + "_" + filename
            path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(path)
            data["attachment"].append(unique_filename)

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

    selected_subject = request.args.get('subject_filter', 'All')

    conn = get_db()
    
    # 1. Ambil data tugasan
    if selected_subject == 'All' or selected_subject == '':
        rows = conn.execute(
            "SELECT title, deadline, subject FROM assignments WHERE user_email = ?",
            (user_email,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT title, deadline, subject FROM assignments WHERE user_email = ? AND subject = ?",
            (user_email, selected_subject)
        ).fetchall()

    # 2. Ambil peta warna (color map) yang telah disimpan oleh user ini
    color_rows = conn.execute(
        "SELECT subject, color_code FROM subject_colors WHERE user_email = ?",
        (user_email,)
    ).fetchall()
    
    # Tukar kepada dictionary python { 'Nama Subjek': '#HEXCOLOR' }
    user_colors = {c_row['subject']: c_row['color_code'] for c_row in color_rows}
    conn.close()

    events = []
    for row in rows:
        subj = row['subject']
        # Semak jika user ada set warna sendiri, jika tiada guna warna default biru
        chosen_color = user_colors.get(subj, "#3788d8")

        events.append({
            "title": f"[{subj}] {row['title']}",
            "start": row['deadline'], 
            "allDay": True,
            "color": chosen_color
        })
    
    return json.dumps(events)

@app.route('/api/save-subject-color', methods=['POST'])
def save_subject_color():
    user_email = session.get('user')
    if not user_email:
        return json.dumps({"status": "error", "message": "Unauthorized"}), 401

    data = request.json
    subject = data.get('subject')
    color_code = data.get('color')

    if not subject or not color_code:
        return json.dumps({"status": "error", "message": "Missing data"}), 400

    conn = get_db()
    try:
        # Guna INSERT OR REPLACE supaya jika warna sudah ada, ia akan dikemas kini (update)
        conn.execute('''
            INSERT OR REPLACE INTO subject_colors (user_email, subject, color_code)
            VALUES (?, ?, ?)
        ''', (user_email, subject, color_code))
        conn.commit()
        status = "success"
    except Exception as e:
        status = "error"
    finally:
        conn.close()

    return json.dumps({"status": status})

@app.route('/calendar')
def calendar_view():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    user_email = session.get('user')
    conn = get_db()
    
    # Ambil senarai unik subjek yang didaftarkan oleh user ini sahaja
    subject_rows = conn.execute(
        "SELECT DISTINCT subject FROM assignments WHERE user_email = ?", 
        (user_email,)
    ).fetchall()
    user_subjects = [row['subject'] for row in subject_rows]
    conn.close()
    
    # Hantar senarai subjek ke frontend calendar.html
    return render_template('calendar.html', subjects=user_subjects)


@app.route('/delete/<filename>')
def delete_file(filename):
    path = os.path.join(
        app.config['UPLOAD_FOLDER'],
        filename
    )

    if os.path.exists(path):
        os.remove(path)

    for assignment in assignment_store.values():
        if filename in assignment["attachment"]:
            assignment["attachment"].remove(filename)

    return redirect(request.referrer or url_for('dashboard'))


if __name__ == '__main__':
    app.run(debug=True)