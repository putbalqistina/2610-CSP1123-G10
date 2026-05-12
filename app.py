
import os
import sqlite3
import json
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "secretkey"

# Cari path fail subjects.json
base_path = os.path.dirname(__file__)
json_path = os.path.join(base_path, 'subjects.json')

def load_mmu_subjects():
    base_path = os.path.dirname(__file__)
    with open(os.path.join(base_path, 'subjects.json'), 'r') as f:
        return json.load(f)

# Baca data dari JSON
with open(json_path, 'r') as f:
    mmu_subjects = json.load(f)

# connect with database
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

# create table
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

    conn.commit()
    conn.close()

init_db()


app.config['UPLOAD_FOLDER'] = 'static/uploads'
# dummy subjects
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



@app.route('/')
def index():
    # Semak jika user sudah login
    if 'user' in session:
        return redirect('/dashboard') # Jika dah login, pergi dashboard
    
    # Jika belum login, hantar ke page login (atau register)
    # Jangan terus render dashboard.html di sini!
    return redirect('/login')

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        login = request.form["login"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE (email = ? OR username = ?) AND password = ?",
            (login.lower(), login, password)
        ).fetchone()
        conn.close()


        if user:
            session["user"] = login
            return redirect("/dashboard")
        else:
            return "Invalid credentials ❌"

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()

        # 🔍 Check if email already exists
        existing_user = conn.execute(
            "SELECT * FROM users WHERE email = ? OR username = ?",
            (email, username)
        ).fetchone()

        if existing_user:
            conn.close()
            return render_template("register.html", error="Email already registered!")

        conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, password)
        )
        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("register.html")

@app.route('/add_assignment', methods=['GET', 'POST'])
def add_assignment():
    user_email = session.get('user')
    if not user_email:
        return redirect("/login")
    
    # Gunakan fungsi yang anda dah buat untuk elakkan ralat path
    mmu_data = load_mmu_subjects() 

    if request.method == 'POST':
        subject = request.form.get('subject')
        title = request.form.get('title')
        deadline = request.form.get('deadline')
        
        conn = get_db()
        conn.execute(
            "INSERT INTO assignments (subject, title, deadline, user_email) VALUES (?, ?, ?, ?)",
            (subject, title, deadline, user_email)
        )
        conn.commit()
        conn.close()
        
        return redirect("/dashboard")

    # Pastikan nama variable yang dihantar (mmu_data) sama dengan dalam HTML
    return render_template("add_assignment.html", mmu_data=mmu_data)

@app.route('/dashboard')
def dashboard():
    user_email = session.get('user')
    conn = get_db()

    # 1. Ambil pilihan filter dari URL (Contoh: /dashboard?subject_filter=CSP1123)
    selected_filter = request.args.get('subject_filter', 'All')

    # 2. Senarai asal (hardcoded dalam app.py anda)
    all_subjects = [
        {"code": "CSP1123", "name": "Mini IT Project"},
        {"code": "CDS1114", "name": "Digital Systems"},
        {"code": "CMT1134", "name": "Mathematics III"},
        {"code": "LCT1113", "name": "Critical Thinking"}
    ]
# 3. Logik penapisan
    if selected_filter == 'All':
        filtered_subjects = all_subjects
    else:
        # Hanya ambil subjek yang code-nya sama dengan pilihan user
        filtered_subjects = [s for s in all_subjects if s['code'] == selected_filter]
    # Ambil tugasan daripada database berdasarkan user yang login
    user_subjects = conn.execute(
        "SELECT DISTINCT subject FROM assignments WHERE user_email = ?",
        (user_email,)
    ).fetchall()
    conn.close()

    # Hantar 'user_assignments' ke dashboard.html
    return render_template('dashboard.html', subjects=filtered_subjects)

# app.py

# app.py

@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    # 1. Pastikan user dah login (ambil dari session)
    user_identifier = session.get('user') 
    if not user_identifier:
        return redirect(url_for('login'))

    conn = get_db()

    if request.method == 'POST':
        # 2. Ambil data baru dari borang (index.html)
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        bio = request.form.get('bio')
        gender = request.form.get('gender')

        # 3. Update data dalam database SQLite
        conn.execute('''
            UPDATE users 
            SET full_name = ?, username = ?, bio = ?, gender = ? 
            WHERE email = ? OR username = ?
        ''', (full_name, username, bio, gender, user_identifier, user_identifier))
        
        conn.commit()
        conn.close()

        # 4. INI BAHAGIAN PENTING: Redirect balik ke dashboardselepas save
        return redirect(url_for('dashboard'))

    # Jika GET (buka page edit), kita papar data asal
    user_data = conn.execute(
        "SELECT * FROM users WHERE email = ? OR username = ?", 
        (user_identifier, user_identifier)
    ).fetchone()
    conn.close()
    
    return render_template('index.html', user=user_data)

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

        return redirect(url_for("assignment", title=title))

    return render_template(
        "assignment.html",
        title=title,
        description=data["description"],
        comments=data["comments"],
        attachment=data["attachment"]
    )


if __name__ == '__main__':
    app.run(debug=True)