from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

# Khởi tạo ứng dụng Flask
app = Flask(__name__)
app.secret_key = "123456"

def get_db():
    conn = sqlite3.connect('bio_database.db')
    return conn

# Hàm tạo database nếu chưa có
def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE, password TEXT, fullname TEXT,
                  bio TEXT, avatar_url TEXT, banner_url TEXT, theme TEXT,
                  address TEXT, phone TEXT, social_ig TEXT, social_tiktok TEXT,
                  social_fb TEXT, social_yt TEXT, zalo TEXT)''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN bank_name TEXT")
        c.execute("ALTER TABLE users ADD COLUMN bank_account TEXT")
        c.execute("ALTER TABLE users ADD COLUMN bank_owner TEXT")
    except:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT, title TEXT, url TEXT, clicks INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS services
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT, name TEXT, price TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def index():
    return render_template("index.html")
    
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            session["user"] = username
            return redirect(url_for("admin"))
        except sqlite3.IntegrityError:
            return "Tên đăng nhập đã tồn tại!"
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip().lower()
        password = request.form.get("password")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session["user"] = username
            return redirect(url_for("admin"))
        return "Sai tài khoản hoặc mật khẩu!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "user" not in session:
        return redirect(url_for("login"))
    
    current_user = session["user"]
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        if "add_link" in request.form:
            title = request.form.get("title", "").strip()
            url = request.form.get("url", "").strip()
            if title and url:
                cursor.execute("INSERT INTO links (username, title, url, clicks) VALUES (?, ?, ?, 0)", 
                               (current_user, title, url))
                conn.commit()

        if "update_bank" in request.form:
            bank_name = request.form.get("bank_name", "").strip()
            bank_account = request.form.get("bank_account", "").strip()
            bank_owner = request.form.get("bank_owner", "").strip()
            cursor.execute("UPDATE users SET bank_name=?, bank_account=?, bank_owner=? WHERE username=?", 
                           (bank_name, bank_account, bank_owner, current_user))
            conn.commit()

        if "add_service" in request.form:
            name = request.form.get("name", "").strip()
            price = request.form.get("price", "").strip()
            if name and price:
                cursor.execute("INSERT INTO services (username, name, price) VALUES (?, ?, ?)", 
                               (current_user, name, price))
                conn.commit()

        cursor.close()
        conn.close()
        return redirect(url_for("admin"))

    cursor.execute("SELECT * FROM users WHERE username = ?", (current_user,))
    user_row = cursor.fetchone()

    cursor.execute("SELECT id, title, url, clicks FROM links WHERE username = ? ORDER BY id DESC", (current_user,))
    links = [{"id": r[0], "title": r[1], "url": r[2], "clicks": r[3]} for r in cursor.fetchall()]

    cursor.execute("SELECT id, name, price FROM services WHERE username = ? ORDER BY id DESC", (current_user,))
    services = [{"id": r[0], "name": r[1], "price": r[2]} for r in cursor.fetchall()]

    cursor.close()
    conn.close()
    return render_template("admin.html", user=user_row, links=links, services=services)

@app.route("/delete_service/<int:service_id>")
def delete_service(service_id):
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM services WHERE id = ? AND username = ?", (service_id, session["user"]))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/<username>")
def user_bio(username):
    username = username.strip().lower()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fullname, bio, avatar_url, banner_url, theme, address, phone,
               social_ig, social_tiktok, social_fb, social_yt, zalo,
               bank_name, bank_account, bank_owner
        FROM users WHERE username = ?
    """, (username,))
    user_data = cursor.fetchone()

    if not user_data:
        cursor.close()
        conn.close()
        return "<h3>Không tìm thấy trang cá nhân này!</h3>", 404

    cursor.execute("SELECT id, title, url FROM links WHERE username = ? ORDER BY id ASC", (username,))
    my_links = [{"id": row[0], "title": row[1], "url": row[2]} for row in cursor.fetchall()]

    cursor.execute("SELECT id, name, price FROM services WHERE username = ? ORDER BY id ASC", (username,))
    my_services = [{"id": row[0], "name": row[1], "price": row[2]} for row in cursor.fetchall()]

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
        "zalo": user_data[11] if len(user_data) > 11 and user_data[11] else "",
        "bank_name": user_data[12] if len(user_data) > 12 and user_data[12] else "",
        "bank_account": user_data[13] if len(user_data) > 13 and user_data[13] else "",
        "bank_owner": user_data[14] if len(user_data) > 14 and user_data[14] else ""
    }

    return render_template("bio.html", user=user_info, links=my_links, services=my_services)

if __name__ == "__main__":
    app.run(debug=True)