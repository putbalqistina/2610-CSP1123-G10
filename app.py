import os
import sqlite3
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import uuid
import secrets

from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory
from flask_apscheduler import APScheduler
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = "secretkey"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "assignmate4u@gmail.com"
app.config["MAIL_PASSWORD"] = "mdom ybrf nwcf hcic"
app.config["MAIL_DEFAULT_SENDER"] = "assignmate4u@gmail.com"

mail = Mail(app)
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
    
def log_activity(title, activity):

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    conn = get_db()

    conn.execute("""
        INSERT INTO activity_logs
        (assignment_title, activity, timestamp)
        VALUES (?, ?, ?)
    """, (
        title,
        activity,
        timestamp
    ))

    conn.commit()
    conn.close()

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'docx', 'xlsx', 'zip'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS 

def init_all_tables():
    conn = get_db()
    
    # 1. Jadual Users
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            full_name TEXT,
            bio TEXT,
            gender TEXT,
            profile_pic TEXT,
            reset_token TEXT,
            reset_expiry TEXT
        )
    """)

    # 2. Jadual Assignments (Lengkap dengan semua kolum)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            deadline TEXT NOT NULL,
            user_email TEXT NOT NULL,
            status TEXT DEFAULT 'to_do',
            is_shared INTEGER DEFAULT 0,
            creator_email TEXT,
            email_sent INTEGER DEFAULT 0,
            alert_shown INTEGER DEFAULT 0,
            FOREIGN KEY (user_email) REFERENCES users (email)
        )
    """)

    try:
        conn.execute("ALTER TABLE assignments ADD COLUMN status TEXT DEFAULT 'to_do'")
    except:
        pass  # prevents error if column already exists


    
    # 3. Jadual Assignment Members
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assignment_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER,
            member_email TEXT,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id),
            FOREIGN KEY (member_email) REFERENCES users(email),
            UNIQUE(assignment_id, member_email)
        )
    """)

    # 4. Jadual Subject Colors
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subject_colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            subject TEXT,
            color_code TEXT,
            UNIQUE(user_email, subject)
        )
    """)

    # 5. Jadual Messages (Chat)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER,
            sender_name TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assignment_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            member_email TEXT NOT NULL
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_title TEXT,
            activity TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS personal_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_email TEXT NOT NULL,
        receiver_email TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
    
    conn.commit()
    conn.close()

# Jalankan fungsi ini untuk setup database semasa Flask bermula
init_all_tables()




@app.route("/")
def home():
    return render_template("landingpage.html")

def send_email(to_email, subject, body):
    sender = "assignmate4u@gmail.com"
    password = "mdom ybrf nwcf hcic"

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
        "SELECT * FROM assignments WHERE email_sent = 0"
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
    error_msg = None

    if request.method == 'POST':
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        subject = request.form.get('subject')
        title = request.form.get('title')
        deadline = request.form.get('deadline')
        assignment_type = request.form.get('assignment_type') # 'personal' atau 'shared'
        friend_input = request.form.get('friend_input', '').strip() # Ambil e-mel/username kawan

        is_shared = 1 if assignment_type == 'shared' else 0
        
        conn = get_db()
        cursor = conn.cursor()

        # JIKA PILIH SHARED: Semak dahulu jika akaun kawan wujud di dalam sistem
        invited_email = None
        if is_shared == 1 and friend_input:
            user_found = conn.execute(
                "SELECT email FROM users WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)", 
                (friend_input, friend_input)
            ).fetchone()
            
            if not user_found:
                error_msg = f"Error: User '{friend_input}' not registered in the system!"
                conn.close()
                return render_template("add_Assignment.html", mmu_data=mmu_data, error_msg=error_msg)
            else:
                invited_email = user_found["email"]

        # 1. Masukkan data tugasan baru ke table assignments
        cursor.execute(
            """INSERT INTO assignments 
               (subject, title, deadline, user_email, status, is_shared, creator_email) 
               VALUES (?, ?, ?, ?, 'to_do', ?, ?)""",
            (subject, title, deadline, user_email, is_shared, user_email)
        )

        
        assignment_id = cursor.lastrowid
        
        # 2. Jika jenis berkumpulan, daftarkan pencipta & kawan ke table assignment_members
        if is_shared == 1:
            # Masukkan pencipta tugasan (anda)
            cursor.execute(
                "INSERT INTO assignment_members (assignment_id, member_email) VALUES (?, ?)",
                (assignment_id, user_email)
            )
            # Masukkan kawan yang dijemput (jika ada input dimasukkan)
            if invited_email:
                try:
                    cursor.execute(
                        "INSERT INTO assignment_members (assignment_id, member_email) VALUES (?, ?)",
                        (assignment_id, invited_email)
                    )
                except sqlite3.IntegrityError:
                    pass # Abaikan ralat jika ter-input email sendiri
            

        conn.commit()
        conn.close()
        
        return redirect(url_for("dashboard"))

    return render_template("add_Assignment.html", mmu_data=mmu_data, error_msg=error_msg)


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
    search_query = request.args.get('search', '').strip()  

    # 1. Ambil senarai subjek tersendiri untuk drop-down filter
    subject_rows = conn.execute("""
        SELECT DISTINCT subject FROM assignments 
        WHERE user_email = ? 
        OR id IN (SELECT assignment_id FROM assignment_members WHERE member_email = ?)
    """, (user_email, user_email)).fetchall()
    user_subjects = [row['subject'] for row in subject_rows]

    # 2. Bina query SQL dinamik bersama fungsi Search
    query = """
        SELECT * FROM assignments 
        WHERE (user_email = ? OR id IN (SELECT assignment_id FROM assignment_members WHERE member_email = ?))
    """
    params = [user_email, user_email]

    # Jika user pilih subjek tertentu di drop-down filter
    if selected_filter != 'All' and selected_filter != '':
        query += " AND subject = ?"
        params.append(selected_filter)

    # Jika user menaip sesuatu di search bar (Cari pada Title atau Subject)
    if search_query:
        query += " AND (title LIKE ? OR subject LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")

    assignments = conn.execute(query, params).fetchall()
    
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
    return render_template('dashboard.html', subjects=user_subjects, assignments=assignments, upcoming=upcoming, user=user_data, search_query=search_query)
    
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
        
        # 1. Ambil fail gambar dari form
        file = request.files.get('profile_pic')
        filename = None

        # 2. Semak jika fail wujud dan dibenarkan
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + "_" + filename
            path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(path) # Simpan gambar ke static/uploads
            filename = unique_filename

        # 3. Kemas kini pangkalan data
        if filename:
            # Jika user muat naik gambar baru, kemas kini sekali kolum profile_pic
            conn.execute('''
                UPDATE users 
                SET full_name = ?, username = ?, bio = ?, gender = ?, profile_pic = ?
                WHERE email = ? OR username = ?
            ''', (full_name, username, bio, gender, filename, user_identifier, user_identifier))
        else:
            # Jika user tak muat naik gambar baru, kekalkan gambar lama
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
    user_email = session.get('user')
    if not user_email:
        return redirect(url_for('login'))

    conn = get_db()
    
    # 1. Ambil input teks dari search bar (jika ada)
    search_query = request.args.get('search', '').strip()  

    # 2. Bina query SQL dinamik - Ditambah "AND subject LIKE ?" untuk tapis subjek yang betul
    query = """
        SELECT * FROM assignments 
        WHERE (user_email = ? OR id IN (SELECT assignment_id FROM assignment_members WHERE member_email = ?))
        AND subject LIKE ?
    """
    # Guna `f"%{code}%"` supaya ia sepadan dengan format nama penuh subjek (contoh: "CMF1114 - Multimedia Fundamentals")
    params = [user_email, user_email, f"%{code}%"]

    # 3. Jika user menaip sesuatu di search bar, tapis berdasarkan Title
    if search_query:
        query += " AND title LIKE ?"
        params.append(f"%{search_query}%")

    assignments = conn.execute(query, params).fetchall()
    
    # Ambil data user untuk paparan
    user_data = conn.execute(
        "SELECT * FROM users WHERE email = ? OR username = ?", 
        (user_email, user_email)
    ).fetchone()

    conn.close()
    
    # Hantar senarai yang telah ditapis dan search_query ke fail HTML subjek
    return render_template('subject.html', code=code, assignments=assignments, user=user_data, search_query=search_query)

@app.route('/assignment/<title>', methods=["GET", "POST"])
def assignment(title):
    user_email = session.get("user")
    if not user_email:
        return redirect(url_for("login"))
    
    if title not in assignment_store:
        assignment_store[title] = {
            "description": "",
            "comments": [],
            "attachment": []
        }

    conn = get_db()

    assignment = conn.execute("""
        SELECT id
        FROM assignments
        WHERE title = ?
    """, (title,)).fetchone()

    assignment_id = assignment["id"]

    data = assignment_store[title]

    if request.method == "POST":
        new_desc = request.form.get("description")
        if new_desc:
            data["description"] = new_desc
            log_activity(
                title,
                f"{session['user']} updated the description."
            )

        new_comment = request.form.get("comment")
        if new_comment:
            data["comments"].append(new_comment)
            log_activity(
                title,
                f"{session['user']} added a comment."
            )

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
            log_activity(
                title,
                f"{session['user']} uploaded '{filename}'."
            )

        status = request.form.get("status")
        log_activity(
            title,
            f"{session['user']} changed the status to '{status}'."
        )
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
    
    # 1. Ambil data user semasa yang login
    user_data = conn.execute("SELECT * FROM users WHERE email = ? OR username = ?", (user_email, user_email)).fetchone()

    # 2. Ambil data assignment berdasarkan tajuk yang betul
    assignment_row = conn.execute("SELECT * FROM assignments WHERE title = ?", (title,)).fetchone()
    
    status = "to_do"
    members_data = []
    
    # 3.Guna ID sebenar daripada tugasan untuk cari ahli kumpulan
    if assignment_row:
        status = assignment_row["status"]
        members_data = conn.execute("""
            SELECT users.username, users.full_name, users.bio, users.profile_pic 
            FROM assignment_members 
            JOIN users ON assignment_members.member_email = users.email
            WHERE assignment_members.assignment_id = ?
        """, (assignment_row["id"],)).fetchall() 

    # 4. Ambil logs bagi assignment ini
    logs = conn.execute("SELECT * FROM activity_logs WHERE assignment_title = ? ORDER BY timestamp DESC", (title,)).fetchall()
    conn.close()

    return render_template(
        "assignment.html",
        title=title,
        description=data["description"],
        comments=data["comments"],
        attachment=data["attachment"],
        status=status,
        logs=logs,
        user=user_data,
        members=members_data 
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

    print('Deleting', filename)

    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    print("Path:", path)
    print("Exists:", os.path.exists(path))

    if os.path.exists(path):
        os.remove(path)
        print("Deleted")

    for assignment in assignment_store.values():
        if filename in assignment["attachment"]:
            assignment["attachment"].remove(filename)

    return redirect(request.referrer or url_for('dashboard'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename
    )

# Route untuk chat

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sender_name,
               message,
               created_at
        FROM messages
        ORDER BY created_at
    """)

    messages = cursor.fetchall()

    conn.close()

    return render_template(
        'chat.html',
        messages=messages
    )

@app.route('/personal_chat') #Route peraonal chat dengan other member
def personal_chat():

    if 'user' not in session:
        return redirect(url_for('login'))

    current_user = session['user']

    conn = get_db()

    users = conn.execute("""
        SELECT username,email
        FROM users
        WHERE email != ?
        ORDER BY username
    """, (current_user,)).fetchall()

    conn.close()

    return render_template(
        "personalChat.html",
        users=users
    )

#Route chat room dengan other member
@app.route('/personal_chat/<email>')
def personal_chat_room(email):

    if 'user' not in session:
        return redirect(url_for('login'))

    current_user = session['user']

    conn = get_db()

    target_user = conn.execute("""
        SELECT *
        FROM users
        WHERE email = ?
    """, (email,)).fetchone()

    messages = conn.execute("""
        SELECT *
        FROM personal_messages
        WHERE
        (
            sender_email = ?
            AND receiver_email = ?
        )
        OR
        (
            sender_email = ?
            AND receiver_email = ?
        )
        ORDER BY created_at
    """, (
        current_user,
        email,
        email,
        current_user
    )).fetchall()

    conn.close()

    return render_template(
        "personalChatRoom.html",
        target_user=target_user,
        messages=messages
    )

#send message untuk personal chat

@app.route('/send_personal_message', methods=['POST'])
def send_personal_message():

    if 'user' not in session:
        return redirect(url_for('login'))

    sender_email = session['user']

    receiver_email = request.form['receiver_email']

    message = request.form['message']

    conn = get_db()

    conn.execute("""
        INSERT INTO personal_messages
        (
            sender_email,
            receiver_email,
            message
        )
        VALUES (?, ?, ?)
    """, (
        sender_email,
        receiver_email,
        message
    ))

    conn.commit()
    conn.close()

    return redirect(
        url_for(
            'personal_chat_room',
            email=receiver_email
        )
    )

@app.route('/send', methods=['POST'])
def send_message():

    user_email = session.get('user')

    if not user_email:
        return redirect(url_for('login'))

    message = request.form['message']

    conn = get_db()

    user = conn.execute(
        "SELECT username FROM users WHERE email = ?",
        (user_email,)
    ).fetchone()

    sender_name = user["username"]

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages
        (assignment_id, sender_name, message)
        VALUES (?, ?, ?)
    """, (1, sender_name, message))

    conn.commit()
    conn.close()

    return redirect(url_for("chat"))

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"].strip().lower()

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if user:

            token = secrets.token_urlsafe(32)

            conn.execute(
                "UPDATE users SET reset_token = ? WHERE email = ?",
                (token, email)
            )

            conn.commit()

            reset_link = url_for(
                "reset_password",
                token=token,
                _external=True
            )

            msg = Message(
                subject="Password Reset",
                sender=app.config["MAIL_USERNAME"],
                recipients=[email]
            )

            msg.body = f"""
            Hello,

            You requested to reset your password.

            Click the link below:

            {reset_link}

            If you did not request this, please ignore this email.
            """

            print("===== About to send email =====")

            try:
                mail.send(msg)
                print("===== Email sent successfully =====")

            except Exception as e:
                print("===== Email failed =====")
                print(type(e))
                print(e)
                raise

        conn.close()

        return render_template("forgot_password.html", show_popup=True)

    return render_template("forgot_password.html", show_popup=False)

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE reset_token = ?",
        (token,)
    ).fetchone()

    if not user:
        conn.close()
        return "Invalid reset link."

    if request.method == "POST":

        new_password = request.form["password"]

        conn.execute(
            """
            UPDATE users
            SET password = ?, reset_token = NULL
            WHERE email = ?
            """,
            (new_password, user["email"])
        )

        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    conn.close()

    return render_template("reset_password.html")



if __name__ == '__main__':
    app.run(debug=True)