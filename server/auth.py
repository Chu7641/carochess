"""Tài khoản người dùng trong SQLite. Mật khẩu băm bằng scrypt, phiên đăng nhập lưu bằng token."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION_SECONDS = 30 * 24 * 3600
USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,20}")


class AuthError(Exception):
    """Lỗi đăng nhập/đăng ký; câu tiếng Việt gửi nguyên văn cho client."""


def load_env(path=ROOT / ".env"):
    """Đọc KEY=VALUE từ .env; biến đã có trong môi trường được ưu tiên."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _db():
    path = Path(os.environ.get("CARO_DB", ROOT / "data" / "caro.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def _hash(password, salt=None):
    salt = salt or os.urandom(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return f"scrypt${salt.hex()}${key.hex()}"


def _verify(password, stored):
    _, salt, _ = stored.split("$")
    return hmac.compare_digest(_hash(password, bytes.fromhex(salt)), stored)


START_ELO = 1000
ELO_K = 32  # điểm tối đa một ván; hai người ngang elo: thắng +16, thua -16


def _public(row):
    return {"id": row["id"], "username": row["username"], "isAdmin": bool(row["is_admin"]),
            "elo": row["elo"]}


def _write(sql, *args):
    """Chạy một câu lệnh ghi; trả số dòng bị ảnh hưởng."""
    with closing(_db()) as db, db:
        return db.execute(sql, args).rowcount


def init():
    """Tạo bảng và tài khoản admin khai báo trong .env (nếu chưa có)."""
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not username or not password:
        raise RuntimeError("Thiếu ADMIN_USERNAME / ADMIN_PASSWORD trong file .env (xem .env.example).")
    with closing(_db()) as db, db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created REAL NOT NULL,
                approved INTEGER NOT NULL DEFAULT 1,
                elo INTEGER NOT NULL DEFAULT 1000
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires REAL NOT NULL
            );
        """)
        # Database từ bản cũ: thêm cột mới. Người dùng cũ coi như đã duyệt, elo khởi điểm.
        existing = [col["name"] for col in db.execute("PRAGMA table_info(users)")]
        for column, ddl in (("approved", "INTEGER NOT NULL DEFAULT 1"),
                            ("elo", f"INTEGER NOT NULL DEFAULT {START_ELO}")):
            if column not in existing:
                db.execute(f"ALTER TABLE users ADD COLUMN {column} {ddl}")
        if not db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            db.execute("INSERT INTO users (username, password, is_admin, created) VALUES (?, ?, 1, ?)",
                       (username, _hash(password), time.time()))


def register(username, password):
    """Tạo tài khoản chờ duyệt; chỉ đăng nhập được sau khi admin phê duyệt."""
    username = str(username or "").strip()
    password = str(password or "")
    if not USERNAME_RE.fullmatch(username):
        raise AuthError("Tên đăng nhập gồm 3–20 ký tự: chữ không dấu, số hoặc dấu _.")
    if not 6 <= len(password) <= 128:
        raise AuthError("Mật khẩu phải từ 6 đến 128 ký tự.")
    try:
        with closing(_db()) as db, db:
            db.execute("INSERT INTO users (username, password, created, approved) VALUES (?, ?, ?, 0)",
                       (username, _hash(password), time.time()))
    except sqlite3.IntegrityError as exc:
        raise AuthError("Tên đăng nhập đã có người dùng.") from exc


def login(username, password):
    """Trả (token, user). Sai tên hoặc mật khẩu đều báo cùng một câu."""
    with closing(_db()) as db, db:
        row = db.execute("SELECT * FROM users WHERE username = ?",
                         (str(username or "").strip(),)).fetchone()
        if row is None or not _verify(str(password or ""), row["password"]):
            raise AuthError("Sai tên đăng nhập hoặc mật khẩu.")
        if not row["approved"]:
            raise AuthError("Tài khoản đang chờ admin phê duyệt.")
        token = secrets.token_urlsafe(32)
        now = time.time()
        db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
        db.execute("INSERT INTO sessions VALUES (?, ?, ?)", (token, row["id"], now + SESSION_SECONDS))
    return token, _public(row)


def user_for(token):
    if not token:
        return None
    with closing(_db()) as db:
        row = db.execute("SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id "
                         "WHERE token = ? AND expires > ?", (token, time.time())).fetchone()
    return _public(row) if row else None


def logout(token):
    _write("DELETE FROM sessions WHERE token = ?", token)


def elo_of(username):
    with closing(_db()) as db:
        row = db.execute("SELECT elo FROM users WHERE username = ?", (username,)).fetchone()
    return row["elo"] if row else START_ELO


def record_game(name_a, name_b, score_a):
    """Cập nhật elo sau một ván; score_a: 1 a thắng, 0 a thua, 0.5 hòa. Trả (elo_a, elo_b, delta_a)."""
    with closing(_db()) as db, db:
        elo = {row["username"]: row["elo"] for row in db.execute(
            "SELECT username, elo FROM users WHERE username IN (?, ?)", (name_a, name_b))}
        if len(elo) < 2:
            return None  # một bên đã bị xóa tài khoản: không tính
        a, b = elo[name_a], elo[name_b]
        delta = round(ELO_K * (score_a - 1 / (1 + 10 ** ((b - a) / 400))))
        db.execute("UPDATE users SET elo = ? WHERE username = ?", (a + delta, name_a))
        db.execute("UPDATE users SET elo = ? WHERE username = ?", (b - delta, name_b))
    return a + delta, b - delta, delta


# ---------- quản trị (chỉ gọi sau khi đã kiểm tra quyền admin) ----------
def list_users():
    with closing(_db()) as db:
        rows = db.execute("SELECT * FROM users ORDER BY approved, created").fetchall()
    return [{**_public(row), "approved": bool(row["approved"]), "created": row["created"]}
            for row in rows]


def approve(user_id):
    if not _write("UPDATE users SET approved = 1 WHERE id = ?", user_id):
        raise AuthError("Không tìm thấy tài khoản.")


def reject(user_id):
    """Từ chối = xóa đăng ký đang chờ; không xóa tài khoản đã duyệt."""
    if not _write("DELETE FROM users WHERE id = ? AND approved = 0", user_id):
        raise AuthError("Chỉ từ chối được tài khoản đang chờ duyệt.")


def delete_user(user_id):
    _write("DELETE FROM sessions WHERE user_id = ?", user_id)  # SQLite không tự xóa theo khóa ngoại
    if not _write("DELETE FROM users WHERE id = ?", user_id):
        raise AuthError("Không tìm thấy tài khoản.")


def reset_elo(user_id):
    if not _write("UPDATE users SET elo = ? WHERE id = ?", START_ELO, user_id):
        raise AuthError("Không tìm thấy tài khoản.")


def make_admin(user_id):
    if not _write("UPDATE users SET is_admin = 1 WHERE id = ? AND approved = 1", user_id):
        raise AuthError("Chỉ nâng cấp được tài khoản đã duyệt.")


def reset_password(user_id):
    """Đặt mật khẩu ngẫu nhiên, đăng xuất mọi phiên cũ; trả mật khẩu mới cho admin."""
    password = secrets.token_urlsafe(8)
    if not _write("UPDATE users SET password = ? WHERE id = ?", _hash(password), user_id):
        raise AuthError("Không tìm thấy tài khoản.")
    _write("DELETE FROM sessions WHERE user_id = ?", user_id)
    return password
