import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import re

app = Flask(__name__)
load_dotenv()

# Đọc khóa bí mật từ biến môi trường
app.secret_key = os.environ.get("SECRET_KEY")

# Đọc link Database từ biến môi trường
DB_URL = os.environ.get("DATABASE_URL")
RESERVED_USERNAMES = {
    "admin", "login", "register", "logout", "delete",
    "click", "static", "api", "index", "home", "about",
    "contact", "help", "settings", "dashboard", "assets", "book"
}

def get_db():
    return psycopg2.connect(DB_URL)

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            fullname TEXT,
            bio TEXT,
            avatar_url TEXT DEFAULT '',
            banner_url TEXT DEFAULT '',
            theme TEXT DEFAULT 'dark',
            address TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            zalo TEXT DEFAULT '',
            social_ig TEXT DEFAULT '',
            social_tiktok TEXT DEFAULT '',
            social_fb TEXT DEFAULT '',
            social_yt TEXT DEFAULT ''
        );
    ''')
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS theme TEXT DEFAULT 'dark';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS banner_url TEXT DEFAULT '';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS address TEXT DEFAULT '';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT DEFAULT '';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS zalo TEXT DEFAULT '';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS social_ig TEXT DEFAULT '';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS social_tiktok TEXT DEFAULT '';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS social_fb TEXT DEFAULT '';")
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS social_yt TEXT DEFAULT '';")
   
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS links (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            clicks INTEGER DEFAULT 0
        );
    ''')
    
    # Bảng khách đặt lịch tư vấn
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            service_note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        );
    ''')
    conn.commit()
    cursor.close()
    conn.close()

init_db()

# 1. Trang chủ Landing Page
@app.route("/")
def index():
    is_logged_in = "user" in session
    username = session.get("user")
    return render_template("index.html", is_logged_in=is_logged_in, username=username)

# 2. Đăng Ký
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    suggested_username = request.args.get("username", "")

    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")
        fullname = request.form.get("fullname")
        bio = request.form.get("bio")

        # --- Validate username ---
        if not re.match(r"^[a-z0-9_]{3,20}$", username):
            error = "Tên đăng nhập chỉ được chứa chữ thường, số, dấu gạch dưới, từ 3-20 ký tự."
            return render_template("register.html", error=error, suggested_username=suggested_username)

        if username in RESERVED_USERNAMES:
            error = "Tên đăng nhập này không thể sử dụng, vui lòng chọn tên khác."
            return render_template("register.html", error=error, suggested_username=suggested_username)

        # --- Validate password ---
        if not password or len(password) < 6:
            error = "Mật khẩu phải có ít nhất 6 ký tự."
            return render_template("register.html", error=error, suggested_username=suggested_username)

        hashed_password = generate_password_hash(password)

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, fullname, bio, avatar_url, banner_url, theme) VALUES (%s, %s, %s, %s, '', '', 'dark')",
                           (username, hashed_password, fullname, bio))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect("/login")
        except Exception:
            error = "Tên đăng nhập này đã tồn tại!"

    return render_template("register.html", error=error, suggested_username=suggested_username)

# 3. Đăng Nhập
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT username, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user[1], password):
            session["user"] = user[0]
            return redirect("/admin")
        else:
            error = "Sai tên đăng nhập hoặc mật khẩu!"

    return render_template("login.html", error=error)

# 4. Đăng Xuất
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

# 5. Trang Quản Trị Admin
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "user" not in session:
        return redirect("/login")

    current_user = session["user"]
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        if "add_link" in request.form:
            title = request.form.get("title", "").strip()
            url = request.form.get("url", "").strip()

            if title and url and (url.startswith("http://") or url.startswith("https://")):
                cursor.execute("INSERT INTO links (username, title, url, clicks) VALUES (%s, %s, %s, 0)", (current_user, title, url))
                conn.commit()

        elif "update_profile" in request.form:
            fullname = request.form.get("fullname")
            bio = request.form.get("bio")
            avatar_url = request.form.get("avatar_url")
            banner_url = request.form.get("banner_url")
            theme = request.form.get("theme", "dark")
            address = request.form.get("address", "").strip()
            phone = request.form.get("phone", "").strip()
            zalo = request.form.get("zalo", "").strip()
            social_ig = request.form.get("social_ig", "").strip()
            social_tiktok = request.form.get("social_tiktok", "").strip()
            social_fb = request.form.get("social_fb", "").strip()
            social_yt = request.form.get("social_yt", "").strip()

            cursor.execute("""
                UPDATE users SET
                fullname = %s, bio = %s, avatar_url = %s, banner_url = %s,
                theme = %s, address = %s, phone = %s, zalo = %s, social_ig = %s,
                social_tiktok = %s, social_fb = %s, social_yt = %s
                WHERE username = %s
            """, (fullname, bio, avatar_url, banner_url, theme, address, phone, zalo, social_ig, social_tiktok, social_fb, social_yt, current_user))
            conn.commit()

        elif "update_appointment_status" in request.form:
            app_id = request.form.get("appointment_id")
            new_status = request.form.get("status", "done")
            cursor.execute("UPDATE appointments SET status=%s WHERE id=%s AND username=%s", (new_status, app_id, current_user))
            conn.commit()

        return redirect("/admin")

    cursor.execute("""
        SELECT fullname, bio, avatar_url, banner_url, theme, address, phone,
        social_ig, social_tiktok, social_fb, social_yt, zalo
        FROM users WHERE username = %s
    """, (current_user,))
    user_data = cursor.fetchone()

    cursor.execute("SELECT id, title, url, clicks FROM links WHERE username = %s ORDER BY id ASC", (current_user,))
    links = cursor.fetchall()

    cursor.execute("""
        SELECT id, customer_name, customer_phone, service_note, TO_CHAR(created_at, 'HH24:MI DD/MM/YYYY'), status 
        FROM appointments WHERE username = %s ORDER BY id DESC
    """, (current_user,))
    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    user_info = {
        "username": current_user,
        "fullname": user_data[0] if user_data and user_data[0] else current_user,
        "bio": user_data[1] if user_data and user_data[1] else "",
        "avatar_url": user_data[2] if user_data and user_data[2] else "",
        "banner_url": user_data[3] if user_data and user_data[3] else "",
        "theme": user_data[4] if user_data and user_data[4] else "dark",
        "address": user_data[5] if user_data and user_data[5] else "",
        "phone": user_data[6] if user_data and user_data[6] else "",
        "social_ig": user_data[7] if user_data and user_data[7] else "",
        "social_tiktok": user_data[8] if user_data and user_data[8] else "",
        "social_fb": user_data[9] if user_data and user_data[9] else "",
        "social_yt": user_data[10] if user_data and user_data[10] else "",
        "zalo": user_data[11] if user_data and len(user_data) > 11 and user_data[11] else ""
    }

    return render_template("admin.html", links=links, user=user_info, appointments=appointments)

# 6. Xóa link
@app.route("/delete/<int:link_id>")
def delete_link(link_id):
    if "user" not in session:
        return redirect("/login")

    current_user = session["user"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM links WHERE id = %s AND username = %s", (link_id, current_user))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect("/admin")

# Xóa lịch hẹn
@app.route("/delete_appointment/<int:app_id>")
def delete_appointment(app_id):
    if "user" not in session:
        return redirect("/login")
    
    current_user = session["user"]
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE id = %s AND username = %s", (app_id, current_user))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect("/admin")

# 7. Click link
@app.route("/click/<int:link_id>")
def track_click(link_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE links SET clicks = clicks + 1 WHERE id = %s", (link_id,))
    conn.commit()
    cursor.execute("SELECT url FROM links WHERE id = %s", (link_id,))
    target_url = cursor.fetchone()
    cursor.close()
    conn.close()

    if target_url:
        return redirect(target_url[0])
    return redirect("/")

# 8. Gửi yêu cầu đặt lịch (AJAX)
@app.route("/book/<username>", methods=["POST"])
def book_appointment(username):
    target_username = username.strip().lower()
    name = (request.form.get("customer_name") or "").strip()
    phone = (request.form.get("customer_phone") or "").strip()
    note = (request.form.get("service_note") or "").strip()

    if not name or not phone:
        return jsonify({"success": False, "message": "Vui lòng nhập tên và số điện thoại!"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (target_username,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"success": False, "message": "Tài khoản không tồn tại!"}), 404

    cursor.execute("""
        INSERT INTO appointments (username, customer_name, customer_phone, service_note)
        VALUES (%s, %s, %s, %s)
    """, (target_username, name, phone, note))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True, "message": "Gửi thông tin thành công! Cơ sở sẽ liên hệ lại sớm nhất."})

# 9. Xem Bio công khai
@app.route("/<username>")
def user_bio(username):
    username = username.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT fullname, bio, avatar_url, banner_url, theme, address, phone,
               social_ig, social_tiktok, social_fb, social_yt, zalo
        FROM users WHERE username = %s
    """, (username,))
    user_data = cursor.fetchone()

    if not user_data:
        cursor.close()
        conn.close()
        return "<h3>Không tìm thấy trang cá nhân này!</h3>", 404

    cursor.execute("SELECT id, title, url FROM links WHERE username = %s ORDER BY id ASC", (username,))
    my_links = [{"id": row[0], "title": row[1], "url": row[2]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    user_info = {
        "username": username,
        "name": user_data[0] if user_data[0] else username,
        "bio": user_data[1] if user_data[1] else "",
        "avatar": user_data[2] if user_data[2] else "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150",
        "banner": user_data[3] if user_data[3] else "",
        "theme": user_data[4] if user_data[4] else "dark",
        "address": user_data[5] if user_data[5] else "",
        "phone": user_data[6] if user_data[6] else "",
        "social_ig": user_data[7] if user_data[7] else "",
        "social_tiktok": user_data[8] if user_data[8] else "",
        "social_fb": user_data[9] if user_data[9] else "",
        "social_yt": user_data[10] if user_data[10] else "",
        "zalo": user_data[11] if user_data and len(user_data) > 11 and user_data[11] else ""
    }
    return render_template("bio.html", user=user_info, links=my_links)

if __name__ == "__main__":
    app.run(debug=True)