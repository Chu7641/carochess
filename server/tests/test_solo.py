"""Kiểm tra chức năng solo: chuyển dữ liệu cũ, bảng điểm solo_scores, SoloSession và SoloManager."""

import sqlite3
import time
from pathlib import Path

import pytest

from server import auth
from server.solo import SoloManager, SoloSession


def test_migration_from_old_tables(tmp_path, monkeypatch):
    db_path = str(tmp_path / "legacy.db")
    monkeypatch.setenv("CARO_DB", db_path)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")

    # Tạo database kiểu cũ với bảng users, mines_scores, sudoku_scores
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created REAL NOT NULL,
            approved INTEGER NOT NULL DEFAULT 1,
            elo INTEGER NOT NULL DEFAULT 1000
        );
        CREATE TABLE mines_scores (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            level TEXT NOT NULL,
            ms INTEGER NOT NULL,
            finished REAL NOT NULL
        );
        CREATE TABLE sudoku_scores (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            level TEXT NOT NULL,
            ms INTEGER NOT NULL,
            finished REAL NOT NULL
        );
        INSERT INTO users (id, username, password, created) VALUES
            (1, 'alice', 'hash1', 1.0),
            (2, 'bob', 'hash2', 2.0),
            (3, 'charlie', 'hash3', 3.0);

        -- Điểm mìn: alice chơi 2 lần (lần 2 nhanh hơn), bob cùng thời gian với lần 2 nhưng xong muộn hơn
        INSERT INTO mines_scores (user_id, level, ms, finished) VALUES
            (1, 'easy', 15000, 100.0),
            (1, 'easy', 12000, 200.0),
            (2, 'easy', 12000, 205.0),
            (3, 'easy', 18000, 150.0),
            (1, 'medium', 50000, 300.0);

        -- Điểm sudoku
        INSERT INTO sudoku_scores (user_id, level, ms, finished) VALUES
            (1, 'easy', 40000, 100.0),
            (2, 'easy', 35000, 120.0),
            (2, 'medium', 90000, 130.0);
    """)
    conn.commit()
    conn.close()

    # Gọi auth.init() để kích hoạt di chuyển dữ liệu
    auth.init()

    # Kiểm tra bảng cũ đã bị xóa và bảng mới solo_scores đã có
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "mines_scores" not in tables
    assert "sudoku_scores" not in tables
    assert "solo_scores" in tables

    # Kiểm tra số dòng được di chuyển: 5 mines + 3 sudoku = 8
    total_scores = conn.execute("SELECT COUNT(*) FROM solo_scores").fetchone()[0]
    assert total_scores == 8

    # Kiểm tra leaderboard và best của mìn
    lb_mines = auth.solo_leaderboard("minesweeper", "easy")
    assert len(lb_mines) == 3
    assert lb_mines[0]["username"] == "alice" and lb_mines[0]["ms"] == 12000 and lb_mines[0]["rank"] == 1
    assert lb_mines[1]["username"] == "bob" and lb_mines[1]["ms"] == 12000 and lb_mines[1]["rank"] == 2
    assert lb_mines[2]["username"] == "charlie" and lb_mines[2]["ms"] == 18000 and lb_mines[2]["rank"] == 3

    best_alice = auth.solo_best("minesweeper", 1, "easy")
    assert best_alice == {"ms": 12000, "rank": 1}
    best_bob = auth.solo_best("minesweeper", 2, "easy")
    assert best_bob == {"ms": 12000, "rank": 2}

    # Kiểm tra leaderboard và best của sudoku
    lb_sudoku = auth.solo_leaderboard("sudoku", "easy")
    assert len(lb_sudoku) == 2
    assert lb_sudoku[0]["username"] == "bob" and lb_sudoku[0]["ms"] == 35000
    assert lb_sudoku[1]["username"] == "alice" and lb_sudoku[1]["ms"] == 40000

    best_bob_sudoku = auth.solo_best("sudoku", 2, "easy")
    assert best_bob_sudoku == {"ms": 35000, "rank": 1}

    # Gọi auth.init() lần 2: không được nhân đôi dữ liệu
    conn.close()
    auth.init()
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM solo_scores").fetchone()[0] == 8
    conn.close()


def test_record_solo_leaderboard_and_best(tmp_path, monkeypatch):
    db_path = str(tmp_path / "solo_test.db")
    monkeypatch.setenv("CARO_DB", db_path)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")
    auth.init()

    # Tạo 2 người dùng
    auth.register("user_one", "matkhau1")
    auth.register("user_two", "matkhau2")
    u1 = next(u["id"] for u in auth.list_users() if u["username"] == "user_one")
    u2 = next(u["id"] for u in auth.list_users() if u["username"] == "user_two")
    auth.approve(u1)
    auth.approve(u2)

    # Ghi điểm mìn easy
    auth.record_solo("minesweeper", u1, "easy", 20000)
    time.sleep(0.01)
    auth.record_solo("minesweeper", u1, "easy", 10000)  # Lập kỷ lục mới cho u1
    auth.record_solo("minesweeper", u2, "easy", 15000)

    # Ghi điểm mìn hard và sudoku easy
    auth.record_solo("minesweeper", u1, "hard", 60000)
    auth.record_solo("sudoku", u1, "easy", 50000)

    # Kiểm tra leaderboard mìn easy chỉ giữ thời gian tốt nhất mỗi người
    lb = auth.solo_leaderboard("minesweeper", "easy")
    assert len(lb) == 2
    assert lb[0]["username"] == "user_one" and lb[0]["ms"] == 10000 and lb[0]["rank"] == 1
    assert lb[1]["username"] == "user_two" and lb[1]["ms"] == 15000 and lb[1]["rank"] == 2

    # Không lẫn giữa các cấp độ
    lb_hard = auth.solo_leaderboard("minesweeper", "hard")
    assert len(lb_hard) == 1
    assert lb_hard[0]["username"] == "user_one" and lb_hard[0]["ms"] == 60000

    # Không lẫn giữa các trò
    lb_sudoku = auth.solo_leaderboard("sudoku", "easy")
    assert len(lb_sudoku) == 1
    assert lb_sudoku[0]["username"] == "user_one" and lb_sudoku[0]["ms"] == 50000

    # Thứ hạng và thành tích cá nhân
    assert auth.solo_best("minesweeper", u1, "easy") == {"ms": 10000, "rank": 1}
    assert auth.solo_best("minesweeper", u2, "easy") == {"ms": 15000, "rank": 2}
    assert auth.solo_best("minesweeper", u2, "hard") is None


def test_delete_user_clears_solo_scores(tmp_path, monkeypatch):
    db_path = str(tmp_path / "delete_test.db")
    monkeypatch.setenv("CARO_DB", db_path)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")
    auth.init()

    auth.register("to_delete", "matkhau1")
    u = next(u["id"] for u in auth.list_users() if u["username"] == "to_delete")
    auth.approve(u)

    auth.record_solo("minesweeper", u, "easy", 12345)
    auth.record_solo("sudoku", u, "easy", 54321)

    assert auth.solo_best("minesweeper", u, "easy") is not None
    assert auth.solo_best("sudoku", u, "easy") is not None

    # Xóa tài khoản
    auth.delete_user(u)

    assert auth.solo_best("minesweeper", u, "easy") is None
    assert auth.solo_best("sudoku", u, "easy") is None


def test_solo_session_and_manager(tmp_path, monkeypatch):
    db_path = str(tmp_path / "mgr_test.db")
    monkeypatch.setenv("CARO_DB", db_path)
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")
    auth.init()

    auth.register("session_user", "matkhau1")
    u = next(u["id"] for u in auth.list_users() if u["username"] == "session_user")
    auth.approve(u)

    class MockSoloSession(SoloSession):
        GAME = "minesweeper"

    manager = SoloManager(ttl=1)  # TTL 1 giây
    s1 = MockSoloSession(u, "easy", start_timer=True)
    manager.new(u, s1)
    assert manager.get(u) is s1

    # Thắng ván
    s1.finish(won=True, ms=1500)
    assert s1.final_ms == 1500
    assert s1.score_recorded
    assert s1.new_record

    # Thắng lần 2 với thời gian chậm hơn -> new_record = False
    s2 = MockSoloSession(u, "easy", start_timer=True)
    s2.finish(won=True, ms=2000)
    assert not s2.new_record

    # Kiểm tra TTL hết hạn
    s1.last_active = time.time() - 2
    manager.cleanup()
    assert manager.get(u) is None
