# ─────────────────────────────────────────────────────────────
#  Vybizo — Flask Backend
#  Install : pip install flask werkzeug
#  Run     : python app.py
#  Open    : http://127.0.0.1:5000
# ─────────────────────────────────────────────────────────────

from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash, jsonify)
import sqlite3, hashlib, re, os
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "vybizo_secret_2025"

DB_PATH       = "users.db"
UPLOAD_FOLDER = os.path.join("static", "uploads")
ALLOWED_EXT   = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "webm"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def valid_mobile(m):
    return bool(re.fullmatch(r"[6-9]\d{9}", m))

def allowed_file(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXT

def login_required(f):
    @wraps(f)
    def decorated(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return decorated

def init_db():
    with get_db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, mobile TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL UNIQUE, password TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS business_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE, business_name TEXT NOT NULL,
            category TEXT NOT NULL, description TEXT,
            fb_link TEXT, ig_link TEXT, wa_link TEXT, other_link TEXT,
            address TEXT NOT NULL, city TEXT NOT NULL,
            state TEXT NOT NULL, country TEXT NOT NULL,
            pincode TEXT, latitude REAL, longitude REAL,
            contact_number TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT, price REAL NOT NULL,
            category TEXT, media_file TEXT, media_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id))""")
        c.commit()

# ── AUTH ──────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("home") if "user_id" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))
    if request.method == "POST":
        uid = request.form.get("user_id", "").strip()
        pwd = request.form.get("password", "").strip()
        if not uid or not pwd:
            flash("Please fill in all fields.", "error")
            return render_template("login.html")
        with get_db() as c:
            user = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if user and user["password"] == hash_password(pwd):
            session["user_id"] = user["user_id"]
            session["name"]    = user["name"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("home"))
        flash("Invalid User ID or password.", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))
    if request.method == "POST":
        name    = request.form.get("name",    "").strip()
        mobile  = request.form.get("mobile",  "").strip()
        uid     = request.form.get("user_id", "").strip()
        pwd     = request.form.get("password","").strip()
        confirm = request.form.get("confirm", "").strip()
        if not all([name, mobile, uid, pwd, confirm]):
            flash("All fields are required.", "error"); return render_template("register.html")
        if not valid_mobile(mobile):
            flash("Enter a valid 10-digit Indian mobile number.", "error"); return render_template("register.html")
        if len(uid) < 4:
            flash("User ID must be at least 4 characters.", "error"); return render_template("register.html")
        if len(pwd) < 6:
            flash("Password must be at least 6 characters.", "error"); return render_template("register.html")
        if pwd != confirm:
            flash("Passwords do not match.", "error"); return render_template("register.html")
        try:
            with get_db() as c:
                c.execute("INSERT INTO users(name,mobile,user_id,password)VALUES(?,?,?,?)",
                          (name, mobile, uid, hash_password(pwd)))
                c.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError as e:
            flash("Mobile or User ID already taken.", "error")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── HOME / MARKETPLACE ────────────────────────────────────────

@app.route("/home")
@login_required
def home():
    query = request.args.get("q", "").strip()
    with get_db() as c:
        if query:
            products = c.execute("""
                SELECT p.*, b.business_name, b.contact_number, b.city, b.country
                FROM products p JOIN business_profiles b ON p.user_id=b.user_id
                WHERE p.title LIKE ? OR p.description LIKE ? OR b.business_name LIKE ?
                ORDER BY p.created_at DESC
            """, (f"%{query}%",)*3).fetchall()
        else:
            products = c.execute("""
                SELECT p.*, b.business_name, b.contact_number, b.city, b.country
                FROM products p JOIN business_profiles b ON p.user_id=b.user_id
                ORDER BY p.created_at DESC
            """).fetchall()
        has_business = c.execute(
            "SELECT id FROM business_profiles WHERE user_id=?",
            (session["user_id"],)).fetchone()
    return render_template("home.html", products=products, query=query,
                           name=session["name"], user_id=session["user_id"],
                           has_business=bool(has_business))

@app.route("/api/search")
@login_required
def api_search():
    q = request.args.get("q", "").strip()
    with get_db() as c:
        rows = c.execute("""
            SELECT p.*, b.business_name, b.contact_number, b.city, b.country
            FROM products p JOIN business_profiles b ON p.user_id=b.user_id
            WHERE p.title LIKE ? OR b.business_name LIKE ? OR p.category LIKE ?
            ORDER BY p.created_at DESC LIMIT 20
        """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    return jsonify([dict(r) for r in rows])

# ── PROFILE ───────────────────────────────────────────────────

@app.route("/profile")
@login_required
def profile():
    with get_db() as c:
        user     = c.execute("SELECT * FROM users WHERE user_id=?", (session["user_id"],)).fetchone()
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
        orders   = c.execute("SELECT * FROM products WHERE user_id=? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    return render_template("profile.html", user=user, business=business,
                           orders=orders, name=session["name"], user_id=session["user_id"])

# ── BUSINESS PROFILE ──────────────────────────────────────────

@app.route("/business/create", methods=["GET", "POST"])
@login_required
def create_business():
    with get_db() as c:
        existing = c.execute("SELECT * FROM business_profiles WHERE user_id=?",
                              (session["user_id"],)).fetchone()
    if existing:
        return redirect(url_for("edit_business"))
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in [
            "business_name","category","description","fb_link","ig_link",
            "wa_link","other_link","address","city","state","country","pincode","contact_number"]}
        data["user_id"]   = session["user_id"]
        data["latitude"]  = request.form.get("latitude",  None) or None
        data["longitude"] = request.form.get("longitude", None) or None
        if not all([data["business_name"], data["category"],
                    data["address"], data["city"], data["state"], data["country"]]):
            flash("Please fill all required fields.", "error")
            return render_template("create_business.html", name=session["name"], user_id=session["user_id"])
        with get_db() as c:
            c.execute("""INSERT INTO business_profiles
                (user_id,business_name,category,description,fb_link,ig_link,wa_link,other_link,
                 address,city,state,country,pincode,latitude,longitude,contact_number)
                VALUES(:user_id,:business_name,:category,:description,:fb_link,:ig_link,:wa_link,
                       :other_link,:address,:city,:state,:country,:pincode,:latitude,:longitude,:contact_number)""", data)
            c.commit()
        flash("Business profile created! Now add your products.", "success")
        return redirect(url_for("add_product"))
    return render_template("create_business.html", name=session["name"], user_id=session["user_id"])

@app.route("/business/edit", methods=["GET", "POST"])
@login_required
def edit_business():
    with get_db() as c:
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?",
                              (session["user_id"],)).fetchone()
    if not business:
        return redirect(url_for("create_business"))
    if request.method == "POST":
        data = {k: request.form.get(k, "").strip() for k in [
            "business_name","category","description","fb_link","ig_link",
            "wa_link","other_link","address","city","state","country","pincode","contact_number"]}
        data["user_id"]   = session["user_id"]
        data["latitude"]  = request.form.get("latitude",  None) or None
        data["longitude"] = request.form.get("longitude", None) or None
        with get_db() as c:
            c.execute("""UPDATE business_profiles SET
                business_name=:business_name, category=:category, description=:description,
                fb_link=:fb_link, ig_link=:ig_link, wa_link=:wa_link, other_link=:other_link,
                address=:address, city=:city, state=:state, country=:country, pincode=:pincode,
                latitude=:latitude, longitude=:longitude, contact_number=:contact_number
                WHERE user_id=:user_id""", data)
            c.commit()
        flash("Business profile updated!", "success")
        return redirect(url_for("profile"))
    return render_template("create_business.html", business=business,
                           name=session["name"], user_id=session["user_id"])

# ── PRODUCTS ──────────────────────────────────────────────────

@app.route("/product/add", methods=["GET", "POST"])
@login_required
def add_product():
    with get_db() as c:
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?",
                              (session["user_id"],)).fetchone()
    if not business:
        flash("Create a business profile first.", "error")
        return redirect(url_for("create_business"))
    if request.method == "POST":
        title    = request.form.get("title",       "").strip()
        desc     = request.form.get("description", "").strip()
        price_r  = request.form.get("price",       "0").strip()
        category = request.form.get("category",    "").strip()
        if not title or not price_r:
            flash("Title and price are required.", "error")
            return render_template("add_product.html", business=business,
                                   name=session["name"], user_id=session["user_id"])
        try:    price = float(price_r)
        except: flash("Enter a valid price.", "error"); return render_template("add_product.html", business=business, name=session["name"], user_id=session["user_id"])
        media_file = media_type = None
        file = request.files.get("media")
        if file and file.filename and allowed_file(file.filename):
            fname = secure_filename(f"{session['user_id']}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            media_file = fname
            media_type = "video" if fname.rsplit(".",1)[1].lower() in {"mp4","mov","webm"} else "image"
        with get_db() as c:
            c.execute("""INSERT INTO products
                (user_id,title,description,price,category,media_file,media_type)
                VALUES(?,?,?,?,?,?,?)""",
                (session["user_id"], title, desc, price, category, media_file, media_type))
            c.commit()
        flash("Product listed successfully!", "success")
        return redirect(url_for("my_products"))
    return render_template("add_product.html", business=business,
                           name=session["name"], user_id=session["user_id"])

@app.route("/product/my")
@login_required
def my_products():
    with get_db() as c:
        products = c.execute("SELECT * FROM products WHERE user_id=? ORDER BY created_at DESC",
                              (session["user_id"],)).fetchall()
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?",
                              (session["user_id"],)).fetchone()
    return render_template("my_products.html", products=products, business=business,
                           name=session["name"], user_id=session["user_id"])

@app.route("/product/delete/<int:pid>", methods=["POST"])
@login_required
def delete_product(pid):
    with get_db() as c:
        p = c.execute("SELECT * FROM products WHERE id=? AND user_id=?",
                      (pid, session["user_id"])).fetchone()
        if p:
            if p["media_file"]:
                try: os.remove(os.path.join(app.config["UPLOAD_FOLDER"], p["media_file"]))
                except FileNotFoundError: pass
            c.execute("DELETE FROM products WHERE id=?", (pid,))
            c.commit()
            flash("Product deleted.", "success")
    return redirect(url_for("my_products"))

# ── VIEW BUSINESS ─────────────────────────────────────────────

@app.route("/business/<uid>")
@login_required
def view_business(uid):
    with get_db() as c:
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (uid,)).fetchone()
        if not business:
            flash("Business not found.", "error")
            return redirect(url_for("home"))
        products = c.execute("SELECT * FROM products WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()
        owner    = c.execute("SELECT name FROM users WHERE user_id=?", (uid,)).fetchone()
    return render_template("view_business.html", business=business, products=products,
                           owner=owner, name=session["name"], user_id=session["user_id"])

# ── RUN ───────────────────────────────────────────────────────



@app.route("/api/profile")
@login_required
def api_profile():
    with get_db() as c:
        user     = c.execute("SELECT * FROM users WHERE user_id=?", (session["user_id"],)).fetchone()
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
    data = dict(user) if user else {}
    data["business"] = dict(business) if business else None
    return jsonify(data)

@app.route("/api/products")
@login_required
def api_products():
    with get_db() as c:
        rows = c.execute("""
            SELECT p.*, b.business_name, b.contact_number, b.city, b.country
            FROM products p JOIN business_profiles b ON p.user_id=b.user_id
            ORDER BY p.created_at DESC
        """).fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    init_db()
    app.run(debug=True)