"""权限收敛与流程边界测试（对应 doc/审查建议1.md 第十五节的 8 个用例）。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.database import SessionLocal, now
from app.models import AssetAssignment, AssetRepair, Notification

from .conftest import data, find_asset, pick_assets

FUTURE = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


def _borrow(client, admin, staff, asset_id, reason="权限测试"):
    """走完整流程把设备借到手，返回领用记录。"""
    application = data(
        client.post(
            "/api/applications",
            headers=staff,
            json={"asset_id": asset_id, "reason": reason, "expected_return_time": FUTURE},
        )
    )
    data(client.post(f"/api/applications/{application['id']}/approve", headers=admin, json={}))
    items = data(client.get("/api/assignments/my", headers=staff, params={"current": True, "page_size": 200}))["items"]
    return [a for a in items if a["asset_id"] == asset_id][0]


def test_1_user_cannot_read_others_borrowed_asset(client, admin, staff, staff2):
    asset = pick_assets(client, admin, 1)[0]
    _borrow(client, admin, staff, asset["id"])

    assert data(client.get(f"/api/assets/{asset['id']}", headers=staff))["borrower_name"] == "张三"
    denied = client.get(f"/api/assets/{asset['id']}", headers=staff2).json()
    assert denied["code"] == 40301
    assert client.get(f"/api/assets/{asset['id']}/qrcode", headers=staff2).json()["code"] == 40301


def test_2_user_can_read_in_stock_asset(client, admin, staff):
    asset = pick_assets(client, admin, 1)[0]
    assert data(client.get(f"/api/assets/{asset['id']}", headers=staff))["status"] == "IN_STOCK"
    assert client.get(f"/api/assets/{asset['id']}/qrcode", headers=staff).status_code == 200


def test_3_user_cannot_read_others_lifecycle(client, admin, staff, staff2):
    asset = pick_assets(client, admin, 1)[0]
    _borrow(client, admin, staff, asset["id"])

    assert data(client.get(f"/api/assets/{asset['id']}/lifecycle", headers=staff))
    assert client.get(f"/api/assets/{asset['id']}/lifecycle", headers=staff2).json()["code"] == 40301


def test_4_user_cannot_repair_others_asset(client, admin, staff, staff2):
    borrowed = pick_assets(client, admin, 1)[0]
    _borrow(client, admin, staff, borrowed["id"])
    denied = client.post("/api/repairs", headers=staff2, json={"asset_id": borrowed["id"], "fault_description": "坏了"})
    assert denied.json()["code"] == 40301
    # 在库资产也不允许普通用户报修（业务定义：报修 = 自己领用的设备出问题）
    in_stock = pick_assets(client, admin, 1)[0]
    assert client.post("/api/repairs", headers=staff2, json={"asset_id": in_stock["id"], "fault_description": "x"}).json()["code"] == 40301
    # 自己的设备可以报修
    assert data(client.post("/api/repairs", headers=staff, json={"asset_id": borrowed["id"], "fault_description": "无法开机"}))["status"] == "PENDING"


def test_5_user_cannot_read_others_repair(client, admin, staff, staff2):
    asset = pick_assets(client, admin, 1)[0]
    _borrow(client, admin, staff, asset["id"])
    repair = data(client.post("/api/repairs", headers=staff, json={"asset_id": asset["id"], "fault_description": "屏幕闪烁"}))

    assert data(client.get(f"/api/repairs/{repair['id']}", headers=staff))["repair_no"] == repair["repair_no"]
    assert client.get(f"/api/repairs/{repair['id']}", headers=staff2).json()["code"] == 40301
    assert data(client.get(f"/api/repairs/{repair['id']}", headers=admin))["reporter_name"] == "张三"
    # 普通用户的维修列表也只含自己的
    rows = data(client.get("/api/repairs", headers=staff2, params={"page_size": 100}))["items"]
    assert all(r["reporter_id"] == 3 for r in rows)  # lisi


def test_6_scrap_needs_two_steps(client, admin):
    asset = pick_assets(client, admin, 1)[0]
    # 直接确认报废 → 拒绝（必须先在库 → 待报废）
    assert client.post(f"/api/assets/{asset['id']}/scrap", headers=admin).json()["code"] == 40001
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "IN_STOCK"

    assert data(client.post(f"/api/assets/{asset['id']}/pending-scrap", headers=admin))["status"] == "PENDING_SCRAP"
    assert data(client.post(f"/api/assets/{asset['id']}/scrap", headers=admin))["status"] == "SCRAPPED"
    # 已报废不能重复报废
    assert client.post(f"/api/assets/{asset['id']}/scrap", headers=admin).json()["code"] == 40001


def _count_notifications(notification_type: str, related_id: int) -> int:
    with SessionLocal() as db:
        return db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.notification_type == notification_type, Notification.related_id == related_id)
        )


def _borrow_with_due_days(client, admin, staff, days: int) -> int:
    """借一台设备，并把应归还时间改成 now+days 天，用来精确制造到期场景。"""
    asset = pick_assets(client, admin, 1)[0]
    assignment = _borrow(client, admin, staff, asset["id"], reason="到期提醒测试")
    with SessionLocal() as db:
        row = db.get(AssetAssignment, assignment["id"])
        row.expected_return_time = now() + timedelta(days=days)
        db.commit()
    return assignment["id"]


def test_7_reminder_milestone_once_and_overdue_daily(client, admin, staff):
    a30 = _borrow_with_due_days(client, admin, staff, 30)
    a_overdue = _borrow_with_due_days(client, admin, staff, -3)

    first = data(client.post("/api/system/reminders/test", headers=admin))
    assert first["expire"] >= 1 and first["overdue"] >= 1  # 逾期提醒必须真的发出去
    assert _count_notifications("ASSET_EXPIRE_30D", a30) == 1
    assert _count_notifications("ASSET_OVERDUE", a_overdue) == 1

    # 里程碑（30/7/1 天）只发一次：再跑一次不再新增
    data(client.post("/api/system/reminders/test", headers=admin))
    assert _count_notifications("ASSET_EXPIRE_30D", a30) == 1

    # 逾期每天一次：把已有提醒挪到昨天，再跑就应该再发一条
    with SessionLocal() as db:
        row = db.scalar(
            select(Notification).where(
                Notification.notification_type == "ASSET_OVERDUE", Notification.related_id == a_overdue
            )
        )
        row.created_at = row.created_at - timedelta(days=1)
        db.commit()
    third = data(client.post("/api/system/reminders/test", headers=admin))
    assert third["overdue"] >= 1
    assert _count_notifications("ASSET_OVERDUE", a_overdue) == 2


def test_8_two_managers_approve_same_asset(client, admin, staff, staff2):
    asset = pick_assets(client, admin, 1)[0]
    a1 = data(
        client.post(
            "/api/applications",
            headers=staff,
            json={"asset_id": asset["id"], "reason": "项目开发", "expected_return_time": FUTURE},
        )
    )
    a2 = data(
        client.post(
            "/api/applications",
            headers=staff2,
            json={"asset_id": asset["id"], "reason": "日常办公", "expected_return_time": FUTURE},
        )
    )
    assert data(client.post(f"/api/applications/{a1['id']}/approve", headers=admin, json={}))["status"] == "APPROVED"
    assert client.post(f"/api/applications/{a2['id']}/approve", headers=admin, json={}).json()["code"] != 0

    with SessionLocal() as db:
        active = db.scalar(
            select(func.count())
            .select_from(AssetAssignment)
            .where(AssetAssignment.asset_id == asset["id"], AssetAssignment.status.in_(("ACTIVE", "OVERDUE")))
        )
    assert active == 1
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "BORROWED"


def test_9_current_assignments_only(client, admin, staff):
    asset = pick_assets(client, admin, 1)[0]
    assignment = _borrow(client, admin, staff, asset["id"])
    current = data(client.get("/api/assignments/my", headers=staff, params={"current": True, "page_size": 200}))["items"]
    assert any(a["id"] == assignment["id"] for a in current)

    data(client.post(f"/api/assignments/{assignment['id']}/return", headers=staff, json={"remark": "归还"}))
    after = data(client.get("/api/assignments/my", headers=staff, params={"current": True, "page_size": 200}))["items"]
    assert all(a["id"] != assignment["id"] for a in after)
    # 不加 current 时仍能看到历史记录
    all_rows = data(client.get("/api/assignments/my", headers=staff, params={"page_size": 200}))["items"]
    assert any(a["id"] == assignment["id"] and a["status"] == "RETURNED" for a in all_rows)


def test_10_department_cycle_blocked(client, admin):
    depts = data(client.get("/api/departments", headers=admin))
    root = [d for d in depts if d["parent_id"] is None][0]
    child = [d for d in depts if d["parent_id"] == root["id"]][0]
    # 父 ← 子 反过来会成环，必须拦住
    assert client.put(f"/api/departments/{root['id']}", headers=admin, json={"parent_id": child["id"]}).json()["code"] == 40001
    assert client.put(f"/api/departments/{root['id']}", headers=admin, json={"parent_id": root["id"]}).json()["code"] == 40001


def test_11_import_only_xlsx(client, admin):
    body = client.post("/api/assets/import", headers=admin, files={"file": ("assets.xlsm", b"whatever")}).json()
    assert body["code"] != 0 and ".xlsx" in body["message"]


def test_12_repair_records_of_others_hidden(client, admin, staff):
    """维修列表对普通用户只返回自己的，且不会把别人的资产信息带出去。"""
    rows = data(client.get("/api/repairs", headers=staff, params={"page_size": 100}))["items"]
    assert all(r["reporter_id"] == 2 for r in rows)  # zhangsan
    assert all(r["fault_description"] for r in rows)
    assert db_repair_count() >= len(rows)


def db_repair_count() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(AssetRepair)) or 0
