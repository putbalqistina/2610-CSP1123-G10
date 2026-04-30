from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secretkey"

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

@app.route("/")
def home():
    return render_template("landingpage.html")

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

        # Check if email already exists
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

        return render_template("register.html", success=True)

    return render_template("register.html", success=False)

# dummy subjects
subjects = [
    {"code": "CSP1123", "name": "Mini IT Project"},
    {"code": "CDS1114", "name": "Digital Systems"},
    {"code": "CMT1134", "name": "Mathematics III"},
    {"code": "LCT1113", "name": "Critical Thinking"}
]

# dummy assignments
assignments_data = {
    "CSP1123": ["Proposal", "Final Report"],
    "CDS1114": ["Lab 1", "Lab 2"],
    "CMT1134": ["Quiz 1", "Test 2"],
    "LCT1113": ["Blended Learning Week 2", "20% Presentation", "Debate Points"]
}

@app.route('/add_assignment', methods=['GET', 'POST'])
def add_assignment():
    user_email = session.get('user')
    if not user_email:
        return redirect("/login")

    if request.method == 'POST':
        # Retrieve data from the HTML form 'name' attributes
        subject = request.form.get('subject')
        title = request.form.get('title')
        deadline = request.form.get('deadline')
        
        # Connect to DB and insert the record
        conn = get_db()
        conn.execute(
            "INSERT INTO assignments (subject, title, deadline, user_email) VALUES (?, ?, ?, ?)",
            (subject, title, deadline, user_email)
        )
        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("add_assignment.html")

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', subjects=subjects)

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
        
        conn.execute('''
            UPDATE users 
            SET full_name = ?, bio = ?, gender = ? 
            WHERE email = ?
        ''', (full_name, bio, gender, user_email))
        conn.commit()
        conn.close()
        return redirect("/dashboard")

    # get user data to pre-fill the form
    user_data = conn.execute("SELECT * FROM users WHERE email = ?", (user_email,)).fetchone()
    conn.close()
    return render_template("index.html", user=user_data)

if __name__ == "__main__":
    app.run(debug=True)