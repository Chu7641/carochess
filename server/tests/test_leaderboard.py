"""Kiểm tra API bảng xếp hạng Elo (/api/leaderboard)."""

import sqlite3
import pytest
from server import auth
from server.tests.conftest import account, login


def test_leaderboard_requires_auth(client):
    res = client.get("/api/leaderboard")
    assert res.status_code == 401


def test_leaderboard_sorting_and_unapproved_filtered(client, tmp_path, monkeypatch):
    # Tạo các tài khoản qua API
    h_a = account(client, "alice")
    h_b = account(client, "bob")
    h_c = account(client, "charlie")

    # Tạo một tài khoản chưa được duyệt
    client.post("/api/register", json={"username": "unapproved_user", "password": "matkhau1"})

    # Điều chỉnh trực tiếp elo trong db
    with sqlite3.connect(auth.Path(auth.os.environ["CARO_DB"])) as db:
        db.execute("UPDATE users SET elo = 1200 WHERE username = 'alice'")
        db.execute("UPDATE users SET elo = 1100 WHERE username = 'bob'")
        db.execute("UPDATE users SET elo = 1100 WHERE username = 'charlie'")
        # unapproved có elo cao hơn nhưng chưa được duyệt
        db.execute("UPDATE users SET elo = 2000 WHERE username = 'unapproved_user'")
        db.commit()

    # Kiểm tra leaderboard khi đăng nhập bằng bob
    res = client.get("/api/leaderboard", headers=h_b)
    assert res.status_code == 200
    data = res.json()

    # unapproved_user không được xuất hiện
    usernames = [u["username"] for u in data["elo"]]
    assert "unapproved_user" not in usernames

    # Thứ tự: admin (1000), alice (1200), bob (1100), charlie (1100)
    # Hạng 1: alice (1200)
    # Hạng 2: bob (1100) - xếp trước charlie vì 'bob' < 'charlie'
    # Hạng 3: charlie (1100)
    assert data["elo"][0]["username"] == "alice" and data["elo"][0]["elo"] == 1200 and data["elo"][0]["rank"] == 1
    assert data["elo"][1]["username"] == "bob" and data["elo"][1]["elo"] == 1100 and data["elo"][1]["rank"] == 2
    assert data["elo"][2]["username"] == "charlie" and data["elo"][2]["elo"] == 1100 and data["elo"][2]["rank"] == 3

    # me của bob
    assert data["me"] == {"rank": 2, "elo": 1100}


def test_leaderboard_me_outside_top(client):
    admin = login(client, "admin", "admin-secret")
    # Tạo nhiều user để kiểm tra limit
    for i in range(1, 15):
        u_name = f"user_{i:02d}"
        account(client, u_name)

    # Đăng nhập vào user_14
    h_14 = login(client, "user_14", "matkhau1")
    # Gọi hàm auth.elo_leaderboard trực tiếp với limit=5 để kiểm tra trường hợp me ngoài top
    with sqlite3.connect(auth.Path(auth.os.environ["CARO_DB"])) as db:
        db.row_factory = sqlite3.Row
        uid_14 = db.execute("SELECT id FROM users WHERE username = 'user_14'").fetchone()["id"]

    res = auth.elo_leaderboard(uid_14, limit=5)
    assert len(res["elo"]) == 5
    # user_14 không nằm trong top 5 nhưng me vẫn có rank và elo đầy đủ
    assert res["me"] is not None
    assert res["me"]["rank"] > 5

