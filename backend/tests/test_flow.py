from datetime import datetime, timedelta, timezone

from .conftest import data, find_asset, pick_assets

FUTURE = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def _apply(client, headers, asset_id, reason="项目开发需要"):
    return client.post(
        "/api/applications", headers=headers, json={"asset_id": asset_id, "reason": reason, "expected_return_time": FUTURE}
    )


def test_full_application_approval_flow(client, staff, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    created = data(_apply(client, staff, asset["id"]))
    assert created["status"] == "PENDING"
    assert created["asset_code"] == asset["asset_code"]

    # 申请阶段不改资产状态
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "IN_STOCK"

    # 管理员收到待审批提醒
    pending = data(client.get("/api/applications/pending", headers=admin))["items"]
    assert any(a["application_no"] == created["application_no"] for a in pending)

    approved = data(client.post(f"/api/applications/{created['id']}/approve", headers=admin, json={"remark": "同意"}))
    assert approved["status"] == "APPROVED"
    assert approved["approver_name"] == "管理员"

    # 四件事在同一个事务里完成
    asset_after = data(client.get(f"/api/assets/{asset['id']}", headers=admin))
    assert asset_after["status"] == "BORROWED"
    assert asset_after["borrower_id"]

    my_assignments = data(client.get("/api/assignments/my", headers=staff))["items"]
    assignment = [a for a in my_assignments if a["asset_id"] == asset["id"]]
    assert assignment and assignment[0]["application_id"] == created["id"]

    notices = data(client.get("/api/notifications", headers=staff, params={"unread": True}))["items"]
    assert any(n["notification_type"] == "APPLICATION_APPROVED" for n in notices)

    lifecycle = data(client.get(f"/api/assets/{asset['id']}/lifecycle", headers=admin))
    assert any(e["type"] == "ASSIGNED" for e in lifecycle)


def test_approve_twice_rejected(client, staff, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    created = data(_apply(client, staff, asset["id"]))
    data(client.post(f"/api/applications/{created['id']}/approve", headers=admin, json={}))
    again = client.post(f"/api/applications/{created['id']}/approve", headers=admin, json={}).json()
    assert again["code"] != 0 and "已通过" in again["message"]


def test_two_applications_same_asset_only_one_wins(client, staff, staff2, admin):
    """两个用户申请同一台资产：只能审批通过一个（并发/幂等保障）。"""
    asset = find_asset(client, admin, "IN_STOCK")
    a1 = data(_apply(client, staff, asset["id"]))
    a2 = data(_apply(client, staff2, asset["id"]))
    assert data(client.post(f"/api/applications/{a1['id']}/approve", headers=admin, json={}))["status"] == "APPROVED"
    second = client.post(f"/api/applications/{a2['id']}/approve", headers=admin, json={}).json()
    assert second["code"] != 0 and "不可领用" in second["message"]
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["borrower_id"] is not None


def test_duplicate_pending_application_blocked(client, staff, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    data(_apply(client, staff, asset["id"]))
    again = _apply(client, staff, asset["id"]).json()
    assert again["code"] != 0 and "已提交过" in again["message"]


def test_apply_on_unavailable_asset_blocked(client, staff, admin):
    borrowed = find_asset(client, admin, "BORROWED")
    assert _apply(client, staff, borrowed["id"]).json()["code"] != 0
    scrapped = find_asset(client, admin, "SCRAPPED")
    assert _apply(client, staff, scrapped["id"]).json()["code"] != 0


def test_cancel_permission_and_state(client, staff, staff2, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    application = data(_apply(client, staff, asset["id"]))
    assert client.post(f"/api/applications/{application['id']}/cancel", headers=staff2).json()["code"] != 0
    assert data(client.post(f"/api/applications/{application['id']}/cancel", headers=staff))["status"] == "CANCELLED"
    assert client.post(f"/api/applications/{application['id']}/cancel", headers=staff).json()["code"] != 0


def test_reject_flow(client, staff, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    application = data(_apply(client, staff, asset["id"]))
    rejected = data(
        client.post(f"/api/applications/{application['id']}/reject", headers=admin, json={"remark": "库存不足"})
    )
    assert rejected["status"] == "REJECTED"
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "IN_STOCK"
    assert client.post(f"/api/applications/{application['id']}/approve", headers=admin, json={}).json()["code"] != 0


def test_batch_approve(client, staff, staff2, admin):
    assets = pick_assets(client, admin, 2)
    ids = [data(_apply(client, staff, a["id"]))["id"] for a in assets]
    result = data(
        client.post("/api/applications/batch-approve", headers=admin, json={"ids": ids, "remark": "批量通过"})
    )
    assert result["success"] == ids and result["failed"] == []
    for a in assets:
        assert data(client.get(f"/api/assets/{a['id']}", headers=admin))["status"] == "BORROWED"


def test_return_flow(client, staff, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    application = data(_apply(client, staff, asset["id"]))
    data(client.post(f"/api/applications/{application['id']}/approve", headers=admin, json={}))
    assignment = [
        a for a in data(client.get("/api/assignments/my", headers=staff, params={"page_size": 100}))["items"] if a["asset_id"] == asset["id"]
    ][0]

    returned = data(client.post(f"/api/assignments/{assignment['id']}/return", headers=staff, json={"remark": "设备完好"}))
    assert returned["status"] == "RETURNED" and returned["actual_return_time"]
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "IN_STOCK"
    assert client.post(f"/api/assignments/{assignment['id']}/return", headers=staff, json={}).json()["code"] != 0


def test_return_to_repair(client, staff, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    application = data(_apply(client, staff, asset["id"]))
    data(client.post(f"/api/applications/{application['id']}/approve", headers=admin, json={}))
    assignment = [
        a for a in data(client.get("/api/assignments/my", headers=staff, params={"page_size": 100}))["items"] if a["asset_id"] == asset["id"]
    ][0]
    data(client.post(f"/api/assignments/{assignment['id']}/return", headers=staff, json={"to_repair": True}))
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "PENDING_REPAIR"


def test_repair_full_flow(client, staff, admin):
    # 借一台设备出来
    asset = find_asset(client, admin, "IN_STOCK")
    application = data(_apply(client, staff, asset["id"]))
    data(client.post(f"/api/applications/{application['id']}/approve", headers=admin, json={}))

    repair = data(
        client.post("/api/repairs", headers=staff, json={"asset_id": asset["id"], "fault_description": "无法开机"})
    )
    assert repair["status"] == "PENDING"
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "PENDING_REPAIR"
    # 同一台设备不能重复报修
    assert client.post("/api/repairs", headers=staff, json={"asset_id": asset["id"], "fault_description": "x"}).json()["code"] != 0

    started = data(client.post(f"/api/repairs/{repair['id']}/start", headers=admin))
    assert started["status"] == "REPAIRING" and started["start_time"]
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "REPAIRING"

    done = data(
        client.post(
            f"/api/repairs/{repair['id']}/complete",
            headers=admin,
            json={"repair_result": "更换主板", "repair_cost": "800.00", "repair_company": "华强北维修中心"},
        )
    )
    assert done["status"] == "COMPLETED" and done["end_time"]
    # 原用户仍持有该设备 → 回到「已领用」
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "BORROWED"
    assert client.post(f"/api/repairs/{repair['id']}/start", headers=admin).json()["code"] != 0


def test_notification_center(client, staff, admin):
    before = data(client.get("/api/notifications/unread-count", headers=staff))["count"]
    assert before > 0
    items = data(client.get("/api/notifications", headers=staff, params={"page_size": 5}))["items"]
    data(client.post(f"/api/notifications/{items[0]['id']}/read", headers=staff))
    assert data(client.get("/api/notifications/unread-count", headers=staff))["count"] == before - 1
    data(client.post("/api/notifications/read-all", headers=staff))
    assert data(client.get("/api/notifications/unread-count", headers=staff))["count"] == 0


def test_dashboard(client, admin, staff):
    overview = data(client.get("/api/dashboard/overview", headers=admin))
    assert overview["total_assets"] >= 150
    assert overview["in_stock"] > 0 and overview["borrowed"] > 0 and overview["scrapped"] > 0

    statuses = data(client.get("/api/dashboard/asset-status", headers=admin))
    assert sum(s["count"] for s in statuses) == overview["total_assets"]

    cats = data(client.get("/api/dashboard/asset-category", headers=admin))
    assert cats and sum(c["count"] for c in cats) == overview["total_assets"]

    expiry = data(client.get("/api/dashboard/expiry", headers=admin))
    assert expiry

    assert data(client.get("/api/dashboard/borrow-trend", headers=admin))
    assert data(client.get("/api/dashboard/department", headers=admin))
    assert client.get("/api/dashboard/department", headers=staff).status_code == 403
    assert data(client.get("/api/dashboard/application-stats", headers=admin))


def test_reminder_task(client, staff, admin):
    result = data(client.post("/api/system/reminders/test", headers=admin))
    assert set(result) == {"expire", "overdue"}
    notices = data(client.get("/api/notifications", headers=staff, params={"page_size": 100}))["items"]
    types = {n["notification_type"] for n in notices}
    assert {"ASSET_EXPIRE_7D", "ASSET_EXPIRE_1D", "ASSET_OVERDUE"} & types
    # 幂等：同一天重复触发不再重复发个人提醒
    again = data(client.post("/api/system/reminders/test", headers=admin))
    assert again["expire"] == 0 and again["overdue"] == 0
