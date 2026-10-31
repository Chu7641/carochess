import pytest
from fastapi.testclient import TestClient

from server.app import app, hub


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CARO_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-secret")
    with TestClient(app) as test_client:
        yield test_client
    for code in list(hub.rooms):
        hub.remove(code)


def login(client, name, password):
    """Đăng nhập rồi trả header cookie; mỗi kết nối tự mang cookie của mình."""
    res = client.post("/api/login", json={"username": name, "password": password})
    assert res.status_code == 200, res.text
    client.cookies.clear()
    return {"cookie": f"session={res.cookies['session']}"}


def user_id(client, admin, name):
    return next(u["id"] for u in client.get("/api/admin/users", headers=admin).json()
                if u["username"] == name)


def account(client, name):
    """Đăng ký, admin duyệt, đăng nhập."""
    res = client.post("/api/register", json={"username": name, "password": "matkhau1"})
    assert res.status_code == 200, res.text
    admin = login(client, "admin", "admin-secret")
    client.post(f"/api/admin/users/{user_id(client, admin, name)}/approve", headers=admin)
    return login(client, name, "matkhau1")


def receive_until(ws, predicate, limit=200):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("Không nhận được tin nhắn mong đợi")


def state_where(ws, predicate):
    return receive_until(ws, lambda m: m["type"] == "state" and predicate(m["room"]))["room"]


def start(a, b):
    """Hai người cùng bấm Sẵn sàng; trả trạng thái phòng lúc ván bắt đầu."""
    a.send_json({"type": "ready"})
    b.send_json({"type": "ready"})
    state_where(b, lambda r: r["started"])
    return state_where(a, lambda r: r["started"])

