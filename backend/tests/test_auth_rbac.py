from .conftest import data, find_asset


def test_login_ok(client):
    body = client.post("/api/auth/login", json={"username": "admin", "password": "123456"}).json()
    assert body["code"] == 0
    assert "ADMIN" in body["data"]["user"]["roles"]
    assert "asset:create" in body["data"]["user"]["permissions"]


def test_login_wrong_password(client):
    body = client.post("/api/auth/login", json={"username": "admin", "password": "bad"}).json()
    assert body["code"] == 40002


def test_me(client, admin):
    me = data(client.get("/api/auth/me", headers=admin))
    assert me["username"] == "admin"
    assert me["roles"] == ["ADMIN"]


def test_no_token_401(client):
    assert client.get("/api/assets").status_code == 401


def test_normal_user_cannot_create_asset(client, staff):
    assert client.post("/api/assets", headers=staff, json={"asset_name": "x", "category_id": 1}).status_code == 403


def test_normal_user_cannot_read_logs(client, staff, admin):
    assert client.get("/api/operation-logs", headers=staff).status_code == 403
    assert data(client.get("/api/operation-logs", headers=admin))["total"] > 0


def test_user_asset_scope(client, staff, admin):
    """普通用户只看到可申请资产 + 自己的资产，管理员看全部。"""
    mine = data(client.get("/api/assets", headers=staff, params={"page_size": 200}))["items"]
    all_assets = data(client.get("/api/assets", headers=admin, params={"page_size": 200}))["items"]
    assert len(mine) < len(all_assets)
    for a in mine:
        assert a["status"] == "IN_STOCK" or a["borrower_id"] is not None


def test_user_management(client, admin):
    created = data(
        client.post(
            "/api/users",
            headers=admin,
            json={
                "username": "zhaoliu",
                "password": "123456",
                "real_name": "赵六",
                "department_id": 2,
                "role_codes": ["USER"],
            },
        )
    )
    uid = created["id"]
    assert created["roles"] == ["USER"]
    assert created["department_name"]

    # 禁用后不能登录
    assert data(client.patch(f"/api/users/{uid}/status", headers=admin, json={"status": 0})) is None
    assert client.post("/api/auth/login", json={"username": "zhaoliu", "password": "123456"}).json()["code"] == 40003
    client.patch(f"/api/users/{uid}/status", headers=admin, json={"status": 1})
    assert client.post("/api/auth/login", json={"username": "zhaoliu", "password": "123456"}).json()["code"] == 0

    client.post(f"/api/users/{uid}/reset-password", headers=admin, json={"password": "abcdef"})
    assert client.post("/api/auth/login", json={"username": "zhaoliu", "password": "abcdef"}).json()["code"] == 0

    client.put(f"/api/users/{uid}", headers=admin, json={"real_name": "赵六六"})
    assert data(client.get(f"/api/users/{uid}", headers=admin))["real_name"] == "赵六六"


def test_cannot_remove_own_admin_role(client, admin):
    me = data(client.get("/api/auth/me", headers=admin))
    body = client.put(f"/api/users/{me['id']}", headers=admin, json={"role_codes": ["USER"]}).json()
    assert body["code"] == 40001


def test_role_and_permission_management(client, admin):
    perms = data(client.get("/api/roles/permissions", headers=admin))
    assert {"asset:read", "application:approve"} <= {p["permission_code"] for p in perms}

    created = data(
        client.post(
            "/api/roles",
            headers=admin,
            json={"role_name": "审计人员", "role_code": "AUDITOR", "permission_codes": ["asset:read", "log:read"]},
        )
    )
    assert set(created["permission_codes"]) == {"asset:read", "log:read"}
    updated = data(
        client.put(f"/api/roles/{created['id']}", headers=admin, json={"role_name": "审计员", "permission_codes": ["asset:read"]})
    )
    assert updated["role_name"] == "审计员"
    assert updated["permission_codes"] == ["asset:read"]
    assert data(client.delete(f"/api/roles/{created['id']}", headers=admin)) is None


def test_department_and_category(client, admin):
    depts = data(client.get("/api/departments", headers=admin))
    assert any(d["department_name"] == "AI实验室" for d in depts)
    created = data(client.post("/api/departments", headers=admin, json={"department_name": "测试部门"}))
    assert data(client.put(f"/api/departments/{created['id']}", headers=admin, json={"department_name": "测试部"}))
    assert data(client.delete(f"/api/departments/{created['id']}", headers=admin)) is None

    cats = data(client.get("/api/asset-categories", headers=admin))
    assert len(cats) == 9
    assert all(c["asset_count"] >= 0 for c in cats)
    used = find_asset(client, admin, "IN_STOCK")["category_id"]
    assert client.delete(f"/api/asset-categories/{used}", headers=admin).json()["code"] != 0


def test_department_rename_hierarchy_guard(client, admin):
    root = [d for d in data(client.get("/api/departments", headers=admin)) if d["parent_id"] is None][0]
    assert client.put(f"/api/departments/{root['id']}", headers=admin, json={"parent_id": root["id"]}).json()["code"] != 0
