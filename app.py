# --- QUẢN TRỊ ADMIN ---
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "user" not in session:
        return redirect(url_for("login"))
    
    current_user = session["user"]
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        # 1. Thêm link
        if "add_link" in request.form:
            title = request.form.get("title", "").strip()
            url = request.form.get("url", "").strip()
            if title and url and (url.startswith("http://") or url.startswith("https://")):
                cursor.execute("INSERT INTO links (username, title, url, clicks) VALUES (%s, %s, %s, 0)", 
                               (current_user, title, url))
                conn.commit()

        # 2. Cập nhật VietQR
        if "update_bank" in request.form:
            bank_name = request.form.get("bank_name", "").strip()
            bank_account = request.form.get("bank_account", "").strip()
            bank_owner = request.form.get("bank_owner", "").strip()
            cursor.execute("UPDATE users SET bank_name=%s, bank_account=%s, bank_owner=%s WHERE username=%s", 
                           (bank_name, bank_account, bank_owner, current_user))
            conn.commit()

        # 3. Thêm gói Bảng giá / Dịch vụ
        if "add_service" in request.form:
            name = request.form.get("name", "").strip()
            price = request.form.get("price", "").strip()
            if name and price:
                cursor.execute("INSERT INTO services (username, name, price) VALUES (%s, %s, %s)", 
                               (current_user, name, price))
                conn.commit()

        cursor.close()
        conn.close()
        return redirect(url_for("admin"))

    # Lấy dữ liệu hiển thị
    cursor.execute("SELECT * FROM users WHERE username = %s", (current_user,))
    user_row = cursor.fetchone()

    cursor.execute("SELECT id, title, url, clicks FROM links WHERE username = %s ORDER BY id DESC", (current_user,))
    links = [{"id": r[0], "title": r[1], "url": r[2], "clicks": r[3]} for r in cursor.fetchall()]

    cursor.execute("SELECT id, name, price FROM services WHERE username = %s ORDER BY id DESC", (current_user,))
    services = [{"id": r[0], "name": r[1], "price": r[2]} for r in cursor.fetchall()]

    cursor.close()
    conn.close()

    return render_template("admin.html", user=user_row, links=links, services=services)


# --- ROUTE XÓA DỊCH VỤ ---
@app.route("/delete_service/<int:service_id>")
def delete_service(service_id):
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM services WHERE id = %s AND username = %s", (service_id, session["user"]))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("admin"))


# --- XEM TRANG BIO CÔNG KHAI ---
@app.route("/<username>")
def user_bio(username):
    username = username.strip().lower()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fullname, bio, avatar_url, banner_url, theme, address, phone,
               social_ig, social_tiktok, social_fb, social_yt, zalo,
               bank_name, bank_account, bank_owner
        FROM users WHERE username = %s
    """, (username,))
    user_data = cursor.fetchone()

    if not user_data:
        cursor.close()
        conn.close()
        return "<h3>Không tìm thấy trang cá nhân này!</h3>", 404

    cursor.execute("SELECT id, title, url FROM links WHERE username = %s ORDER BY id ASC", (username,))
    my_links = [{"id": row[0], "title": row[1], "url": row[2]} for row in cursor.fetchall()]

    cursor.execute("SELECT id, name, price FROM services WHERE username = %s ORDER BY id ASC", (username,))
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