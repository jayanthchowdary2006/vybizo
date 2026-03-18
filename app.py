# ─────────────────────────────────────────────────────────────
#  Vybizo — Complete Platform Backend
#  Install : pip install flask werkzeug
#  Run     : python app.py  →  http://127.0.0.1:5500
# ─────────────────────────────────────────────────────────────

from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash, jsonify)
import sqlite3, hashlib, re, os, random, string
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "vybizo_secret_2025"

# ─────────────────────────────────────────────────────────────
# Update: Vercel-friendly database and upload handling
IS_VERCEL = "VERCEL" in os.environ

if IS_VERCEL:
    # Vercel has a read-only filesystem except for /tmp
    DB_PATH = "/tmp/users.db"
    UPLOAD_FOLDER = "/tmp/uploads"
    # Note: SQLite on Vercel is NOT persistent across redeploys or timeouts.
    # For persistent data, use Vercel Postgres or Neon.
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")

ALLOWED_EXT   = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "webm"}
ADMIN_MOBILE  = "9999999999"
ADMIN_PASS    = "admin123"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30

# Safely create folders
try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception as e:
    # Silently handle folder creation errors on read-only systems
    if not IS_VERCEL:
        print(f"Error creating folder: {e}")


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

def generate_key(length=6):
    return ''.join(random.choices(string.digits, k=length))

def login_required(f):
    @wraps(f)
    def decorated(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*a, **kw):
        if not session.get("is_admin"):
            flash("Admin access only.", "error")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return decorated

def init_db():
    with get_db() as c:
        # Check if user_id column exists in users table
        columns = [col[1] for col in c.execute("PRAGMA table_info(users)").fetchall()]
        
        if not columns:
            c.execute("""CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, 
                mobile TEXT NOT NULL UNIQUE,
                user_id TEXT UNIQUE,
                password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        elif "user_id" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN user_id TEXT")

        c.execute("""CREATE TABLE IF NOT EXISTS business_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE, business_name TEXT NOT NULL,
            category TEXT NOT NULL, description TEXT,
            fb_link TEXT, ig_link TEXT, wa_link TEXT, other_link TEXT,
            address TEXT NOT NULL, city TEXT NOT NULL,
            state TEXT NOT NULL, country TEXT NOT NULL,
            pincode TEXT, latitude REAL, longitude REAL,
            contact_number TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT, price REAL NOT NULL,
            category TEXT, media_file TEXT, media_type TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            seller_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            total_price REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            order_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
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
        # Form uses name="user_id" for mobile or username
        uid_input = request.form.get("user_id", "").strip()
        pwd       = request.form.get("password", "").strip()
        
        if not uid_input or not pwd:
            flash("Please fill in all fields.", "error")
            return render_template("login.html")
            
        if uid_input == ADMIN_MOBILE and pwd == ADMIN_PASS:
            session.permanent = True
            session["user_id"]  = ADMIN_MOBILE
            session["name"]     = "Admin"
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
            
        with get_db() as c:
            # Match against user_id OR mobile
            user = c.execute("SELECT * FROM users WHERE user_id=? OR mobile=?", 
                           (uid_input, uid_input)).fetchone()
            
        if user and user["password"] == hash_password(pwd):
            session.permanent = True
            # We keep using mobile as the internal primary key (user_id in session)
            # because existing business_profiles/products use it.
            session["user_id"]  = user["mobile"]
            session["name"]     = user["name"]
            session["is_admin"] = False
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("home"))
            
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))
    if request.method == "POST":
        name    = request.form.get("name", "").strip()
        mobile  = request.form.get("mobile", "").strip()
        user_id = request.form.get("user_id", "").strip()
        pwd     = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()

        if not all([name, mobile, user_id, pwd]):
            flash("All fields are required.", "error")
            return render_template("register.html")
            
        if not valid_mobile(mobile):
            flash("Enter a valid 10-digit mobile number.", "error")
            return render_template("register.html")
            
        if len(pwd) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")
            
        if pwd != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        with get_db() as c:
            exists = c.execute("SELECT id FROM users WHERE mobile=? OR user_id=?", 
                             (mobile, user_id)).fetchone()
            if exists:
                flash("Mobile or Vybizo ID already registered.", "error")
                return render_template("register.html")
            
            try:
                c.execute("INSERT INTO users(name, mobile, user_id, password) VALUES(?,?,?,?)",
                          (name, mobile, user_id, hash_password(pwd)))
                c.commit()
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Registration failed. Please try again.", "error")
                return render_template("register.html")
                
    return render_template("register.html")

# Keep forgot flow if needed, but remove the missing verify/password routes
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        mobile = request.form.get("mobile", "").strip()
        if not valid_mobile(mobile):
            flash("Enter a valid 10-digit mobile number.", "error")
            return render_template("forgot.html")
        with get_db() as c:
            user = c.execute("SELECT id FROM users WHERE mobile=?", (mobile,)).fetchone()
        if not user:
            flash("No account found.", "error")
            return render_template("forgot.html")
        session["fp_mobile"] = mobile
        session["fp_key"]    = generate_key()
        return redirect(url_for("forgot_verify"))
    return render_template("forgot.html")

@app.route("/forgot/verify", methods=["GET", "POST"])
def forgot_verify():
    if "fp_key" not in session:
        return redirect(url_for("forgot"))
    if request.method == "POST":
        if request.form.get("security_key", "").strip() == session.get("fp_key"):
            session["fp_verified"] = True
            return redirect(url_for("forgot_reset"))
        flash("Incorrect security key.", "error")
    return render_template("forgot_verify.html",
                           security_key=session.get("fp_key"),
                           mobile=session.get("fp_mobile"))

@app.route("/forgot/reset", methods=["GET", "POST"])
def forgot_reset():
    if not session.get("fp_verified"):
        return redirect(url_for("forgot"))
    if request.method == "POST":
        pwd     = request.form.get("password", "").strip()
        confirm = request.form.get("confirm",  "").strip()
        if len(pwd) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("forgot_reset.html")
        if pwd != confirm:
            flash("Passwords do not match.", "error")
            return render_template("forgot_reset.html")
        mobile = session.pop("fp_mobile", "")
        session.pop("fp_key", None)
        session.pop("fp_verified", None)
        with get_db() as c:
            c.execute("UPDATE users SET password=? WHERE mobile=?",
                      (hash_password(pwd), mobile))
            c.commit()
        flash("Password updated! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_reset.html")

# ── HOME ──────────────────────────────────────────────────────

@app.route("/home")
@login_required
def home():
    query = request.args.get("q", "").strip()
    with get_db() as c:
        if query:
            products = c.execute("""
                SELECT p.*, b.business_name, b.contact_number, b.city, b.country
                FROM products p JOIN business_profiles b ON p.user_id=b.user_id
                WHERE p.title LIKE ? OR p.description LIKE ?
                   OR b.business_name LIKE ? OR p.category LIKE ?
                ORDER BY p.created_at DESC
            """, (f"%{query}%",)*4).fetchall()
        else:
            products = c.execute("""
                SELECT p.*, b.business_name, b.contact_number, b.city, b.country
                FROM products p JOIN business_profiles b ON p.user_id=b.user_id
                ORDER BY p.created_at DESC
            """).fetchall()
        has_business = c.execute(
            "SELECT id FROM business_profiles WHERE user_id=?",
            (session["user_id"],)).fetchone()
        notif_count = c.execute(
            "SELECT COUNT(*) as n FROM notifications WHERE recipient=? AND is_read=0",
            (session["user_id"],)).fetchone()["n"]
    return render_template("home.html", products=products, query=query,
                           name=session["name"], user_id=session["user_id"],
                           has_business=bool(has_business),
                           notif_count=notif_count)

# ── PRODUCT DETAIL ────────────────────────────────────────────

@app.route("/product/<int:pid>")
@login_required
def product_detail(pid):
    with get_db() as c:
        product = c.execute("""
            SELECT p.*, b.business_name, b.contact_number, b.city,
                   b.country, b.wa_link, b.fb_link, b.ig_link, b.address
            FROM products p JOIN business_profiles b ON p.user_id=b.user_id
            WHERE p.id=?
        """, (pid,)).fetchone()
        if not product:
            flash("Product not found.", "error")
            return redirect(url_for("home"))
        seller = c.execute("SELECT name FROM users WHERE mobile=?",
                           (product["user_id"],)).fetchone()
    return render_template("product_detail.html", product=product,
                           seller=seller, name=session["name"],
                           user_id=session["user_id"])

# ── ORDERS ────────────────────────────────────────────────────

@app.route("/order/place/<int:pid>", methods=["POST"])
@login_required
def place_order(pid):
    with get_db() as c:
        product = c.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if not product:
            flash("Product not found.", "error")
            return redirect(url_for("home"))
        if product["user_id"] == session["user_id"]:
            flash("You cannot order your own product.", "error")
            return redirect(url_for("product_detail", pid=pid))
        qty   = int(request.form.get("quantity", 1))
        note  = request.form.get("note", "").strip()
        total = product["price"] * qty
        cursor = c.execute("""INSERT INTO orders
            (customer_id,product_id,seller_id,quantity,total_price,note)
            VALUES(?,?,?,?,?,?)""",
            (session["user_id"], pid, product["user_id"], qty, total, note))
        order_id = cursor.lastrowid
        c.execute("INSERT INTO notifications(recipient,message,order_id) VALUES(?,?,?)",
            (product["user_id"],
             f"New order from {session['name']}! {product['title']} x{qty} — Rs.{total:.2f}",
             order_id))
        c.execute("INSERT INTO notifications(recipient,message,order_id) VALUES(?,?,?)",
            (ADMIN_MOBILE,
             f"Order #{order_id}: {session['name']} ordered {product['title']} x{qty}",
             order_id))
        c.commit()
    return redirect(url_for("order_confirmation", oid=order_id))

@app.route("/order/confirmation/<int:oid>")
@login_required
def order_confirmation(oid):
    with get_db() as c:
        order = c.execute("""
            SELECT o.*, p.title, p.price, p.media_file, p.media_type,
                   b.business_name, b.contact_number, b.wa_link
            FROM orders o
            JOIN products p ON o.product_id=p.id
            JOIN business_profiles b ON o.seller_id=b.user_id
            WHERE o.id=? AND o.customer_id=?
        """, (oid, session["user_id"])).fetchone()
        if not order:
            flash("Order not found.", "error")
            return redirect(url_for("home"))
    return render_template("order_confirmation.html", order=order,
                           name=session["name"], user_id=session["user_id"])

@app.route("/orders/my")
@login_required
def my_orders():
    with get_db() as c:
        orders = c.execute("""
            SELECT o.*, p.title, p.media_file, p.media_type, b.business_name, b.contact_number
            FROM orders o
            JOIN products p ON o.product_id=p.id
            JOIN business_profiles b ON o.seller_id=b.user_id
            WHERE o.customer_id=? ORDER BY o.created_at DESC
        """, (session["user_id"],)).fetchall()
    return render_template("my_orders.html", orders=orders,
                           name=session["name"], user_id=session["user_id"])

@app.route("/orders/incoming")
@login_required
def incoming_orders():
    with get_db() as c:
        orders = c.execute("""
            SELECT o.*, p.title, p.price, u.name as customer_name, u.mobile as customer_mobile
            FROM orders o
            JOIN products p ON o.product_id=p.id
            JOIN users u ON o.customer_id=u.mobile
            WHERE o.seller_id=? ORDER BY o.created_at DESC
        """, (session["user_id"],)).fetchall()
        c.execute("UPDATE notifications SET is_read=1 WHERE recipient=?", (session["user_id"],))
        c.commit()
    return render_template("incoming_orders.html", orders=orders,
                           name=session["name"], user_id=session["user_id"])

@app.route("/order/status/<int:oid>/<status>", methods=["POST"])
@login_required
def update_order_status(oid, status):
    if status not in ["confirmed","shipped","delivered","cancelled"]:
        return redirect(url_for("incoming_orders"))
    with get_db() as c:
        order = c.execute("SELECT * FROM orders WHERE id=? AND seller_id=?",
                          (oid, session["user_id"])).fetchone()
        if order:
            c.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
            c.execute("INSERT INTO notifications(recipient,message,order_id) VALUES(?,?,?)",
                (order["customer_id"],
                 f"Your order #{oid} is now {status.upper()}!", oid))
            c.commit()
            flash(f"Order #{oid} marked as {status}.", "success")
    return redirect(url_for("incoming_orders"))

# ── NOTIFICATIONS ─────────────────────────────────────────────

@app.route("/notifications")
@login_required
def notifications():
    with get_db() as c:
        notifs = c.execute("""SELECT * FROM notifications WHERE recipient=?
            ORDER BY created_at DESC LIMIT 50""", (session["user_id"],)).fetchall()
        c.execute("UPDATE notifications SET is_read=1 WHERE recipient=?", (session["user_id"],))
        c.commit()
    return render_template("notifications.html", notifs=notifs,
                           name=session["name"], user_id=session["user_id"])

# ── ADMIN ─────────────────────────────────────────────────────

@app.route("/admin")
@admin_required
def admin_dashboard():
    with get_db() as c:
        orders = c.execute("""
            SELECT o.*, p.title, p.price, u.name as customer_name,
                   u.mobile as customer_mobile, b.business_name
            FROM orders o
            JOIN products p ON o.product_id=p.id
            JOIN users u ON o.customer_id=u.mobile
            JOIN business_profiles b ON o.seller_id=b.user_id
            ORDER BY o.created_at DESC
        """).fetchall()
        users    = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        products = c.execute("""SELECT p.*, b.business_name
            FROM products p JOIN business_profiles b ON p.user_id=b.user_id
            ORDER BY p.created_at DESC""").fetchall()
        pending  = sum(1 for o in orders if o["status"] == "pending")
        c.execute("UPDATE notifications SET is_read=1 WHERE recipient=?", (ADMIN_MOBILE,))
        c.commit()
    return render_template("admin_dashboard.html",
                           orders=orders, users=users, products=products,
                           total_orders=len(orders), total_users=len(users),
                           total_products=len(products), pending_orders=pending)

# ── BUSINESS & PRODUCTS (existing) ───────────────────────────

@app.route("/profile")
@login_required
def profile():
    with get_db() as c:
        user     = c.execute("SELECT * FROM users WHERE mobile=?", (session["user_id"],)).fetchone()
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
        orders   = c.execute("SELECT * FROM products WHERE user_id=? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    return render_template("profile.html", user=user, business=business,
                           orders=orders, name=session["name"], user_id=session["user_id"])

@app.route("/business/create", methods=["GET","POST"])
@login_required
def create_business():
    with get_db() as c:
        existing = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
    if existing: return redirect(url_for("edit_business"))
    if request.method == "POST":
        data = {k: request.form.get(k,"").strip() for k in ["business_name","category","description","fb_link","ig_link","wa_link","other_link","address","city","state","country","pincode","contact_number"]}
        data["user_id"] = session["user_id"]
        data["latitude"]  = request.form.get("latitude",  None) or None
        data["longitude"] = request.form.get("longitude", None) or None
        if not all([data["business_name"],data["category"],data["address"],data["city"],data["state"],data["country"]]):
            flash("Please fill all required fields.","error"); return render_template("create_business.html",name=session["name"],user_id=session["user_id"])
        with get_db() as c:
            c.execute("""INSERT INTO business_profiles(user_id,business_name,category,description,fb_link,ig_link,wa_link,other_link,address,city,state,country,pincode,latitude,longitude,contact_number)
                VALUES(:user_id,:business_name,:category,:description,:fb_link,:ig_link,:wa_link,:other_link,:address,:city,:state,:country,:pincode,:latitude,:longitude,:contact_number)""", data)
            c.commit()
        flash("Business profile created!","success"); return redirect(url_for("add_product"))
    return render_template("create_business.html",name=session["name"],user_id=session["user_id"])

@app.route("/business/edit", methods=["GET","POST"])
@login_required
def edit_business():
    with get_db() as c:
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
    if not business: return redirect(url_for("create_business"))
    if request.method == "POST":
        data = {k: request.form.get(k,"").strip() for k in ["business_name","category","description","fb_link","ig_link","wa_link","other_link","address","city","state","country","pincode","contact_number"]}
        data["user_id"] = session["user_id"]
        data["latitude"]  = request.form.get("latitude",  None) or None
        data["longitude"] = request.form.get("longitude", None) or None
        with get_db() as c:
            c.execute("""UPDATE business_profiles SET business_name=:business_name,category=:category,description=:description,fb_link=:fb_link,ig_link=:ig_link,wa_link=:wa_link,other_link=:other_link,address=:address,city=:city,state=:state,country=:country,pincode=:pincode,latitude=:latitude,longitude=:longitude,contact_number=:contact_number WHERE user_id=:user_id""", data)
            c.commit()
        flash("Business updated!","success"); return redirect(url_for("profile"))
    return render_template("create_business.html",business=business,name=session["name"],user_id=session["user_id"])

@app.route("/product/add", methods=["GET","POST"])
@login_required
def add_product():
    with get_db() as c:
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
    if not business: flash("Create a business profile first.","error"); return redirect(url_for("create_business"))
    if request.method == "POST":
        title=request.form.get("title","").strip(); desc=request.form.get("description","").strip()
        price_r=request.form.get("price","0").strip(); category=request.form.get("category","").strip()
        if not title or not price_r: flash("Title and price are required.","error"); return render_template("add_product.html",business=business,name=session["name"],user_id=session["user_id"])
        try: price=float(price_r)
        except: flash("Enter a valid price.","error"); return render_template("add_product.html",business=business,name=session["name"],user_id=session["user_id"])
        media_file=media_type=None
        file=request.files.get("media")
        if file and file.filename and allowed_file(file.filename):
            fname=secure_filename(f"{session['user_id']}_{file.filename}")
            file.save(os.path.join(app.config["UPLOAD_FOLDER"],fname))
            media_file=fname; media_type="video" if fname.rsplit(".",1)[1].lower() in {"mp4","mov","webm"} else "image"
        with get_db() as c:
            c.execute("INSERT INTO products(user_id,title,description,price,category,media_file,media_type)VALUES(?,?,?,?,?,?,?)",(session["user_id"],title,desc,price,category,media_file,media_type)); c.commit()
        flash("Product listed!","success"); return redirect(url_for("my_products"))
    return render_template("add_product.html",business=business,name=session["name"],user_id=session["user_id"])

@app.route("/product/my")
@login_required
def my_products():
    with get_db() as c:
        products=c.execute("SELECT * FROM products WHERE user_id=? ORDER BY created_at DESC",(session["user_id"],)).fetchall()
        business=c.execute("SELECT * FROM business_profiles WHERE user_id=?",(session["user_id"],)).fetchone()
    return render_template("my_products.html",products=products,business=business,name=session["name"],user_id=session["user_id"])

@app.route("/product/delete/<int:pid>", methods=["POST"])
@login_required
def delete_product(pid):
    with get_db() as c:
        p=c.execute("SELECT * FROM products WHERE id=? AND user_id=?",(pid,session["user_id"])).fetchone()
        if p:
            if p["media_file"]:
                try: os.remove(os.path.join(app.config["UPLOAD_FOLDER"],p["media_file"]))
                except: pass
            c.execute("DELETE FROM products WHERE id=?",(pid,)); c.commit(); flash("Product deleted.","success")
    return redirect(url_for("my_products"))

@app.route("/business/<uid>")
@login_required
def view_business(uid):
    with get_db() as c:
        business=c.execute("SELECT * FROM business_profiles WHERE user_id=?",(uid,)).fetchone()
        if not business: flash("Business not found.","error"); return redirect(url_for("home"))
        products=c.execute("SELECT * FROM products WHERE user_id=? ORDER BY created_at DESC",(uid,)).fetchall()
        owner=c.execute("SELECT name FROM users WHERE mobile=?",(uid,)).fetchone()
    return render_template("view_business.html",business=business,products=products,owner=owner,name=session["name"],user_id=session["user_id"])

# ── API ───────────────────────────────────────────────────────

@app.route("/api/search")
@login_required
def api_search():
    q=request.args.get("q","").strip()
    with get_db() as c:
        rows=c.execute("""SELECT p.id,p.title,p.price,p.user_id,b.business_name,b.city
            FROM products p JOIN business_profiles b ON p.user_id=b.user_id
            WHERE p.title LIKE ? OR b.business_name LIKE ? OR p.category LIKE ? OR p.description LIKE ?
            LIMIT 10""",(f"%{q}%",)*4).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/products")
@login_required
def api_products():
    with get_db() as c:
        rows=c.execute("""SELECT p.*,b.business_name,b.contact_number,b.city,b.country
            FROM products p JOIN business_profiles b ON p.user_id=b.user_id
            ORDER BY p.created_at DESC""").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/profile")
@login_required
def api_profile():
    with get_db() as c:
        user = c.execute("SELECT * FROM users WHERE mobile=?", (session["user_id"],)).fetchone()
        business = c.execute("SELECT * FROM business_profiles WHERE user_id=?", (session["user_id"],)).fetchone()
    
    user_data = dict(user) if user else {}
    biz_data = dict(business) if business else None
    return jsonify({**user_data, "business": biz_data})

# Initialize database for both local and serverless environments
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5500)


# This line ensures notif_count API works
@app.route("/api/notif_count")
@login_required
def api_notif_count():
    with get_db() as c:
        n = c.execute("SELECT COUNT(*) as n FROM notifications WHERE recipient=? AND is_read=0",
                      (session["user_id"],)).fetchone()["n"]
    return jsonify({"count": n})