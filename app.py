import hmac
import os
import re
import secrets
from functools import wraps
from urllib.parse import urlencode, urlparse

import psycopg2
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


load_dotenv()

app = Flask(__name__)

# A missing key is acceptable for a temporary local run, but never for production.
secret_key = os.environ.get("SECRET_KEY")
if not secret_key and os.environ.get("FLASK_ENV") == "production":
    raise RuntimeError("SECRET_KEY must be configured in production.")

app.config.update(
    SECRET_KEY=secret_key or secrets.token_urlsafe(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production",
)

DB_URL = os.environ.get("DATABASE_URL")

RESERVED_USERNAMES = {
    "admin", "login", "register", "logout", "delete", "delete_service",
    "click", "static", "api", "index", "home", "about", "contact",
    "help", "settings", "dashboard", "assets",
}


def get_db():
    if not DB_URL:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg2.connect(DB_URL)


def close_db(conn, cursor):
    cursor.close()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = get_csrf_token


@app.before_request
def protect_post_requests():
    if request.method != "POST":
        return
    supplied_token = request.form.get("csrf_token", "")
    # Add the hidden field to the existing login/register templates when they
    # are updated. Until then, keep those two public forms compatible while
    # strictly protecting every authenticated admin action.
    if request.endpoint in {"login", "register"} and not supplied_token:
        return
    if not supplied_token or not hmac.compare_digest(supplied_token, get_csrf_token()):
        abort(400, description="Yêu cầu không hợp lệ. Vui lòng tải lại trang và thử lại.")


def is_http_url(value):
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def form_text(name, limit, strip=True):
    value = request.form.get(name, "")
    value = value.strip() if strip else value
    return value[:limit]


def valid_phone(value):
    return not value or bool(re.fullmatch(r"\+?[0-9][0-9 ()-]{5,24}", value))


def valid_zalo(value):
    return not value or bool(re.fullmatch(r"[0-9]{6,20}", value))


def valid_bank(bank_name, bank_account):
    return (
        (not bank_name and not bank_account)
        or (
            bool(re.fullmatch(r"[A-Za-z0-9]{2,12}", bank_name))
            and bool(re.fullmatch(r"[0-9]{6,25}", bank_account))
        )
    )


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                fullname TEXT,
                bio TEXT,
                avatar_url TEXT DEFAULT '',
                banner_url TEXT DEFAULT '',
                theme TEXT DEFAULT 'light',
                address TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                social_ig TEXT DEFAULT '',
                social_tiktok TEXT DEFAULT '',
                social_fb TEXT DEFAULT '',
                social_yt TEXT DEFAULT '',
                zalo TEXT DEFAULT '',
                bank_name TEXT DEFAULT '',
                bank_account TEXT DEFAULT '',
                bank_owner TEXT DEFAULT ''
            );
        ''')
        for statement in (
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS theme TEXT DEFAULT 'light'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS banner_url TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS address TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS social_ig TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS social_tiktok TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS social_fb TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS social_yt TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS zalo TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_name TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_account TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bank_owner TEXT DEFAULT ''",
        ):
            cursor.execute(statement)

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                position INTEGER NOT NULL DEFAULT 0
            );
        ''')
        cursor.execute("ALTER TABLE links ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0")
        cursor.execute("UPDATE links SET position = id WHERE position = 0")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                name TEXT NOT NULL,
                price TEXT NOT NULL
            );
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_username_position ON links (username, position)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_services_username ON services (username)")
        conn.commit()
    finally:
        close_db(conn, cursor)


init_db()


@app.route("/")
def index():
    return render_template(
        "index.html",
        is_logged_in="user" in session,
        username=session.get("user"),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    suggested_username = request.args.get("username", "")[:20]

    if request.method == "POST":
        username = form_text("username", 20).lower()
        password = request.form.get("password", "")
        fullname = form_text("fullname", 80)
        bio = form_text("bio", 300)

        if not re.fullmatch(r"[a-z0-9_]{3,20}", username):
            error = "Tên đăng nhập chỉ gồm chữ thường, số hoặc dấu gạch dưới (3–20 ký tự)."
        elif username in RESERVED_USERNAMES:
            error = "Tên đăng nhập này không thể sử dụng."
        elif len(password) < 8:
            error = "Mật khẩu cần có ít nhất 8 ký tự."
        else:
            conn = get_db()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """INSERT INTO users (username, password, fullname, bio, theme)
                       VALUES (%s, %s, %s, %s, 'light')""",
                    (username, generate_password_hash(password), fullname, bio),
                )
                conn.commit()
                return redirect(url_for("login"))
            except psycopg2.IntegrityError:
                conn.rollback()
                error = "Tên đăng nhập này đã tồn tại."
            finally:
                close_db(conn, cursor)

    return render_template("register.html", error=error, suggested_username=suggested_username)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = form_text("username", 20).lower()
        password = request.form.get("password", "")
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username, password FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
        finally:
            close_db(conn, cursor)

        if user and check_password_hash(user[1], password):
            session.clear()
            session["user"] = user[0]
            get_csrf_token()
            return redirect(url_for("admin"))
        error = "Sai tên đăng nhập hoặc mật khẩu."

    return render_template("login.html", error=error)


@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("index"))


def profile_from_row(username, row):
    fields = (
        "fullname", "bio", "avatar_url", "banner_url", "theme", "address", "phone",
        "social_ig", "social_tiktok", "social_fb", "social_yt", "zalo", "bank_name",
        "bank_account", "bank_owner",
    )
    profile = dict(zip(fields, row))
    # Existing database records may predate the input validation below.
    for url_field in ("avatar_url", "banner_url", "social_ig", "social_tiktok", "social_fb", "social_yt"):
        if profile[url_field] and not is_http_url(profile[url_field]):
            profile[url_field] = ""
    profile["username"] = username
    profile["name"] = profile["fullname"] or username
    profile["avatar"] = profile["avatar_url"] or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150"
    profile["banner"] = profile["banner_url"]
    profile["theme"] = profile["theme"] if profile["theme"] in {"light", "dark"} else "light"
    profile["vietqr_url"] = ""
    if profile["bank_name"] and profile["bank_account"]:
        profile["vietqr_url"] = (
            f"https://img.vietqr.io/image/{profile['bank_name']}-{profile['bank_account']}-compact2.png?"
            + urlencode({"accountName": profile["bank_owner"]})
        )
    return profile


def update_profile(current_user):
    fullname = form_text("fullname", 80)
    bio = form_text("bio", 300)
    avatar_url = form_text("avatar_url", 2048)
    banner_url = form_text("banner_url", 2048)
    theme = request.form.get("theme", "light")
    address = form_text("address", 160)
    phone = form_text("phone", 25)
    zalo = form_text("zalo", 20)
    social_links = {name: form_text(name, 2048) for name in ("social_ig", "social_tiktok", "social_fb", "social_yt")}

    if theme not in {"light", "dark"}:
        abort(400, description="Giao diện không hợp lệ.")
    if any(value and not is_http_url(value) for value in [avatar_url, banner_url, *social_links.values()]):
        abort(400, description="Ảnh và mạng xã hội phải là URL bắt đầu bằng http:// hoặc https://.")
    if not valid_phone(phone) or not valid_zalo(zalo):
        abort(400, description="Số điện thoại hoặc số Zalo không hợp lệ.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE users SET fullname = %s, bio = %s, avatar_url = %s, banner_url = %s,
                   theme = %s, address = %s, phone = %s, social_ig = %s,
                   social_tiktok = %s, social_fb = %s, social_yt = %s, zalo = %s
               WHERE username = %s""",
            (fullname, bio, avatar_url, banner_url, theme, address, phone,
             social_links["social_ig"], social_links["social_tiktok"], social_links["social_fb"],
             social_links["social_yt"], zalo, current_user),
        )
        conn.commit()
    finally:
        close_db(conn, cursor)


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    current_user = session["user"]

    if request.method == "POST":
        if "update_profile" in request.form:
            update_profile(current_user)
        elif "update_bank" in request.form:
            bank_name = form_text("bank_name", 12).upper()
            bank_account = form_text("bank_account", 25)
            bank_owner = form_text("bank_owner", 80).upper()
            if not valid_bank(bank_name, bank_account):
                abort(400, description="Mã ngân hàng hoặc số tài khoản không hợp lệ.")
            conn = get_db()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE users SET bank_name = %s, bank_account = %s, bank_owner = %s WHERE username = %s",
                    (bank_name, bank_account, bank_owner, current_user),
                )
                conn.commit()
            finally:
                close_db(conn, cursor)
        elif "add_service" in request.form:
            name = form_text("name", 100)
            price = form_text("price", 60)
            if name and price:
                conn = get_db()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO services (username, name, price) VALUES (%s, %s, %s)", (current_user, name, price))
                    conn.commit()
                finally:
                    close_db(conn, cursor)
        elif "add_link" in request.form:
            title = form_text("title", 100)
            target_url = form_text("url", 2048)
            if not title or not is_http_url(target_url):
                abort(400, description="Tiêu đề và URL hợp lệ là bắt buộc.")
            conn = get_db()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM links WHERE username = %s", (current_user,))
                next_position = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO links (username, title, url, clicks, position) VALUES (%s, %s, %s, 0, %s)",
                    (current_user, title, target_url, next_position),
                )
                conn.commit()
            finally:
                close_db(conn, cursor)
        return redirect(url_for("admin"))

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT fullname, bio, avatar_url, banner_url, theme, address, phone, social_ig,
                      social_tiktok, social_fb, social_yt, zalo, bank_name, bank_account, bank_owner
               FROM users WHERE username = %s""",
            (current_user,),
        )
        row = cursor.fetchone()
        cursor.execute("SELECT id, title, url, clicks FROM links WHERE username = %s ORDER BY position, id", (current_user,))
        links = [{"id": item[0], "title": item[1], "url": item[2], "clicks": item[3]} for item in cursor.fetchall()]
        cursor.execute("SELECT id, name, price FROM services WHERE username = %s ORDER BY id", (current_user,))
        services = [{"id": item[0], "name": item[1], "price": item[2]} for item in cursor.fetchall()]
    finally:
        close_db(conn, cursor)

    return render_template("admin.html", user=profile_from_row(current_user, row), links=links, services=services)


@app.post("/delete/<int:link_id>")
@login_required
def delete_link(link_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM links WHERE id = %s AND username = %s", (link_id, session["user"]))
        conn.commit()
    finally:
        close_db(conn, cursor)
    return redirect(url_for("admin"))


@app.post("/delete_service/<int:service_id>")
@login_required
def delete_service(service_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM services WHERE id = %s AND username = %s", (service_id, session["user"]))
        conn.commit()
    finally:
        close_db(conn, cursor)
    return redirect(url_for("admin"))


@app.route("/click/<int:link_id>")
def track_click(link_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE links SET clicks = clicks + 1 WHERE id = %s RETURNING url", (link_id,))
        target = cursor.fetchone()
        conn.commit()
    finally:
        close_db(conn, cursor)
    return redirect(target[0] if target and is_http_url(target[0]) else url_for("index"))


@app.route("/<username>")
def user_bio(username):
    username = username.strip().lower()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT fullname, bio, avatar_url, banner_url, theme, address, phone, social_ig,
                      social_tiktok, social_fb, social_yt, zalo, bank_name, bank_account, bank_owner
               FROM users WHERE username = %s""",
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            abort(404)
        cursor.execute("SELECT id, title FROM links WHERE username = %s ORDER BY position, id", (username,))
        links = [{"id": item[0], "title": item[1]} for item in cursor.fetchall()]
        cursor.execute("SELECT id, name, price FROM services WHERE username = %s ORDER BY id", (username,))
        services = [{"id": item[0], "name": item[1], "price": item[2]} for item in cursor.fetchall()]
    finally:
        close_db(conn, cursor)
    return render_template("bio.html", user=profile_from_row(username, row), links=links, services=services)


@app.errorhandler(404)
def not_found(_error):
    return "<h3>Không tìm thấy trang cá nhân này.</h3>", 404


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
