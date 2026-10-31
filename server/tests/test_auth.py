import pytest
from starlette.websockets import WebSocketDisconnect

from server.tests.conftest import account, login, user_id


def test_register_login_logout(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/rooms").status_code == 401
    for name, password in (("ab", "matkhau1"), ("có dấu", "matkhau1"), ("binh", "123")):
        res = client.post("/api/register", json={"username": name, "password": password})
        assert res.status_code == 400 and res.json()["detail"]
    account(client, "Binh")
    res = client.post("/api/register", json={"username": "binh", "password": "matkhau1"})
    assert res.json()["detail"] == "Tên đăng nhập đã có người dùng."

    res = client.post("/api/login", json={"username": "binh", "password": "sai-mat-khau"})
    assert res.status_code == 400
    res = client.post("/api/login", json={"username": "binh", "password": "matkhau1"})
    assert res.json() == {"id": 2, "username": "Binh", "isAdmin": False, "elo": 1000}
    assert client.get("/api/me").json()["username"] == "Binh"
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_change_own_password(client):
    phone = account(client, "binh")
    laptop = login(client, "binh", "matkhau1")
    change = lambda current, new: client.post(
        "/api/password", json={"current": current, "new": new}, headers=laptop)
    assert change("sai-mat-khau", "moi12345").json()["detail"] == "Mật khẩu hiện tại không đúng."
    assert change("matkhau1", "123").status_code == 400  # quá ngắn
    assert client.post("/api/password", json={"current": "matkhau1", "new": "moi12345"}).status_code == 401

    assert change("matkhau1", "moi12345").status_code == 200
    assert client.get("/api/me", headers=laptop).status_code == 200  # phiên đang dùng vẫn giữ
    assert client.get("/api/me", headers=phone).status_code == 401   # máy khác bị đăng xuất
    assert client.post("/api/login", json={"username": "binh", "password": "matkhau1"}).status_code == 400
    login(client, "binh", "moi12345")


def test_registration_needs_approval_and_admin_tools(client):
    for name in ("cho_duyet", "bi_tu_choi"):
        assert client.post("/api/register", json={"username": name, "password": "matkhau1"}).json() == {"pending": True}
    res = client.post("/api/login", json={"username": "cho_duyet", "password": "matkhau1"})
    assert res.json()["detail"] == "Tài khoản đang chờ admin phê duyệt."
    assert "session" not in res.cookies

    admin = login(client, "admin", "admin-secret")
    assert client.get("/api/me", headers=admin).json()["isAdmin"] is True
    users = {u["username"]: u for u in client.get("/api/admin/users", headers=admin).json()}
    assert not users["cho_duyet"]["approved"] and users["admin"]["approved"]
    wait_id, reject_id = users["cho_duyet"]["id"], users["bi_tu_choi"]["id"]

    act = lambda uid, action: client.post(f"/api/admin/users/{uid}/{action}", headers=admin)
    assert act(wait_id, "make-admin").status_code == 400  # chưa duyệt thì chưa nâng cấp được
    assert act(reject_id, "reject").status_code == 200
    assert client.post("/api/login", json={"username": "bi_tu_choi", "password": "matkhau1"}).status_code == 400
    assert act(wait_id, "approve").status_code == 200
    assert act(wait_id, "reject").status_code == 400  # đã duyệt thì không xóa bằng "từ chối"
    member = login(client, "cho_duyet", "matkhau1")

    # Người thường không vào được trang quản trị.
    assert client.get("/api/admin/users", headers=member).status_code == 403
    assert client.post(f"/api/admin/users/{wait_id}/make-admin", headers=member).status_code == 403

    new_password = act(wait_id, "reset-password").json()["password"]
    assert client.get("/api/me", headers=member).status_code == 401  # phiên cũ bị đăng xuất
    assert client.post("/api/login", json={"username": "cho_duyet", "password": "matkhau1"}).status_code == 400
    promoted = login(client, "cho_duyet", new_password)
    assert act(wait_id, "make-admin").status_code == 200
    assert client.get("/api/admin/users", headers=promoted).status_code == 200
    assert act(wait_id, "khong-co").status_code == 404

    admin_id = user_id(client, admin, "admin")
    assert act(admin_id, "delete").json()["detail"] == "Không thể tự xóa tài khoản của chính mình."
    assert act(wait_id, "delete").status_code == 200
    assert client.get("/api/me", headers=promoted).status_code == 401  # phiên bị xóa theo
    assert client.post("/api/login", json={"username": "cho_duyet", "password": new_password}).status_code == 400
    assert act(wait_id, "delete").status_code == 400  # đã xóa rồi


def test_websocket_requires_login(client):
    with client.websocket_connect("/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4401

