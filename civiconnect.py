from flask import Flask, request, redirect, url_for, session
import sqlite3
import re
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

app = Flask(__name__)
app.secret_key = "civiconnect_demo_secret"
DB = "civiconnect.db"

# AI training examples
training_texts = [
    "road is damaged and full of potholes",
    "street road has many holes",
    "water pipe is leaking",
    "no water supply in our area",
    "garbage is not collected",
    "dustbin is overflowing",
    "street light is not working",
    "no lights on the road at night",
    "drainage water is overflowing",
    "sewage water on the street"
]

training_labels = [
    "Road Damage", "Road Damage",
    "Water Leakage", "Water Leakage",
    "Garbage", "Garbage",
    "Streetlight", "Streetlight",
    "Drainage", "Drainage"
]

# Train AI text classification model
ai_model = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("classifier", MultinomialNB())
])

ai_model.fit(training_texts, training_labels)


def connect_db():
    return sqlite3.connect(DB)


def setup_database():
    con = connect_db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS complaints(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            description TEXT,
            category TEXT,
            priority TEXT,
            status TEXT
        )
    """)
    con.commit()
    con.close()


def analyze_issue(description):
    category = ai_model.predict([description])[0]

    urgent_words = [
        "emergency", "danger", "accident",
        "overflowing", "urgent", "severe"
    ]

    if any(word in description.lower() for word in urgent_words):
        priority = "High"
    elif category in ["Road Damage", "Drainage", "Water Leakage"]:
        priority = "Medium"
    else:
        priority = "Low"

    return category, priority


PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>CiviConnect AI</title>
<style>
body {
    font-family: Arial;
    background: #eef3f8;
    margin: 0;
    text-align: center;
}
header {
    background: #123b63;
    color: white;
    padding: 22px;
}
.box {
    background: white;
    width: 85%;
    max-width: 650px;
    margin: 25px auto;
    padding: 25px;
    border-radius: 12px;
    box-shadow: 0 2px 10px #bbb;
}
input, textarea {
    width: 90%;
    padding: 12px;
    margin: 9px;
}
button, .btn {
    background: #1266a5;
    color: white;
    border: 0;
    padding: 12px 20px;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    margin: 6px;
}
a { color: #1266a5; }
.item {
    background: #f1f5fa;
    margin: 12px;
    padding: 12px;
    text-align: left;
}
</style>
</head>
<body>
<header>
<h1>CiviConnect AI</h1>
<p>Smart Community Issue Reporting System</p>
</header>
<div class="box">
{{ content|safe }}
</div>
</body>
</html>
"""


def page(content):
    from flask import render_template_string
    return render_template_string(PAGE, content=content)


@app.route("/")
def home():
    return page("""
    <h2>Welcome to CiviConnect AI</h2>
    <p>Report community problems and track their progress.</p>
    <a class="btn" href="/register">Register</a>
    <a class="btn" href="/login">Login</a>
    <a class="btn" href="/admin">Admin</a>
    """)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])

        try:
            con = connect_db()
            con.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (name, email, password)
            )
            con.commit()
            con.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return page("<h3>Email already registered.</h3><a href='/register'>Try again</a>")

    return page("""
    <h2>User Registration</h2>
    <form method="POST">
    <input name="name" placeholder="Full Name" required>
    <input name="email" type="email" placeholder="Email" required>
    <input name="password" type="password" placeholder="Password" required>
    <button>Register</button>
    </form>
    <a href="/">Home</a>
    """)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        con = connect_db()
        user = con.execute(
            "SELECT * FROM users WHERE email=?", (email,)
        ).fetchone()
        con.close()

        if user and check_password_hash(user[3], password):
            session["user"] = email
            return redirect(url_for("dashboard"))

        return page("<h3>Invalid email or password.</h3><a href='/login'>Try again</a>")

    return page("""
    <h2>User Login</h2>
    <form method="POST">
    <input name="email" type="email" placeholder="Email" required>
    <input name="password" type="password" placeholder="Password" required>
    <button>Login</button>
    </form>
    <a href="/">Home</a>
    """)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    return page("""
    <h2>User Dashboard</h2>
    <p>Welcome, """ + session["user"] + """</p>
    <a class="btn" href="/report">Report an Issue</a>
    <a class="btn" href="/mycomplaints">My Complaints</a>
    <a class="btn" href="/logout">Logout</a>
    """)


@app.route("/report", methods=["GET", "POST"])
def report():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        description = request.form["description"].strip()

        if not description:
            return page("<h3>Please enter an issue description.</h3>")

        category, priority = analyze_issue(description)

        con = connect_db()
        cur = con.execute("""
            INSERT INTO complaints
            (user_email,description,category,priority,status)
            VALUES(?,?,?,?,?)
        """, (
            session["user"], description,
            category, priority, "Pending"
        ))
        complaint_id = cur.lastrowid
        con.commit()
        con.close()

        return page(f"""
        <h2>Complaint Submitted!</h2>
        <h3>Complaint ID: {complaint_id}</h3>
        <p>AI Category: {category}</p>
        <p>Priority: {priority}</p>
        <p>Status: Pending</p>
        <a href="/dashboard">Dashboard</a>
        """)

    return page("""
    <h2>Report Community Issue</h2>
    <form method="POST">
    <textarea name="description" rows="5"
    placeholder="Describe your community problem..." required></textarea>
    <br><button>Submit Complaint</button>
    </form>
    <a href="/dashboard">Back</a>
    """)


@app.route("/mycomplaints")
def mycomplaints():
    if "user" not in session:
        return redirect(url_for("login"))

    con = connect_db()
    rows = con.execute(
        "SELECT * FROM complaints WHERE user_email=?",
        (session["user"],)
    ).fetchall()
    con.close()

    content = "<h2>My Complaints</h2>"

    for row in rows:
        content += f"""
        <div class='item'>
        <b>Complaint ID:</b> {row[0]}<br>
        <b>Issue:</b> {row[2]}<br>
        <b>Category:</b> {row[3]}<br>
        <b>Priority:</b> {row[4]}<br>
        <b>Status:</b> {row[5]}
        </div>
        """

    return page(content + "<a href='/dashboard'>Back</a>")


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if (request.form["username"] == "admin"
                and request.form["password"] == "admin123"):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))

        return page("<h3>Invalid admin login.</h3><a href='/admin'>Try again</a>")

    return page("""
    <h2>Administrator Login</h2>
    <form method="POST">
    <input name="username" placeholder="Username" required>
    <input name="password" type="password" placeholder="Password" required>
    <button>Login</button>
    </form>
    <a href="/">Home</a>
    """)


@app.route("/admin-dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin"))

    con = connect_db()
    rows = con.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()
    con.close()

    content = "<h2>Admin Dashboard</h2>"

    for row in rows:
        content += f"""
        <div class='item'>
        <b>ID:</b> {row[0]} |
        <b>User:</b> {row[1]}<br>
        <b>Issue:</b> {row[2]}<br>
        <b>Category:</b> {row[3]} |
        <b>Priority:</b> {row[4]} |
        <b>Status:</b> {row[5]}
        <form method='POST' action='/update/{row[0]}'>
        <select name='status'>
        <option>Pending</option>
        <option>In Progress</option>
        <option>Resolved</option>
        </select>
        <button>Update Status</button>
        </form>
        </div>
        """

    return page(content + "<a href='/logout'>Logout</a>")


@app.route("/update/<int:complaint_id>", methods=["POST"])
def update(complaint_id):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    status = request.form["status"]
    if status not in ["Pending", "In Progress", "Resolved"]:
        return "Invalid status", 400

    con = connect_db()
    con.execute(
        "UPDATE complaints SET status=? WHERE id=?",
        (status, complaint_id)
    )
    con.commit()
    con.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    setup_database()
    print("CiviConnect AI server starting...")
    app.run(debug=True)