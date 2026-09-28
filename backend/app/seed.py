"""初始化数据库 + Demo 数据。

    python -m app.seed          # 已有数据则跳过（幂等）
    python -m app.seed --reset  # 清库重建

Demo 数据故意覆盖各种状态与到期场景（逾期/1天/7天/30天），演示时每个功能都有数据。
"""

import random
import sys
from datetime import date, timedelta

from sqlalchemy import func, select

from .core.database import SessionLocal, now
from .core.schema import drop_everything, upgrade_to_head
from .core.security import hash_password
from .models import (
    Asset,
    AssetApplication,
    AssetAssignment,
    AssetCategory,
    AssetRepair,
    Department,
    Notification,
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)

PERMISSIONS: list[tuple[str, str, str, str]] = [
    ("查看资产", "asset:read", "asset", "read"),
    ("新增资产", "asset:create", "asset", "create"),
    ("编辑资产", "asset:update", "asset", "update"),
    ("删除资产", "asset:delete", "asset", "delete"),
    ("导入资产", "asset:import", "asset", "import"),
    ("导出资产", "asset:export", "asset", "export"),
    ("提交领用申请", "application:create", "application", "create"),
    ("审批领用申请", "application:approve", "application", "approve"),
    ("查看领用记录", "assignment:read", "assignment", "read"),
    ("归还设备", "assignment:return", "assignment", "return"),
    ("提交维修", "repair:create", "repair", "create"),
    ("处理维修", "repair:handle", "repair", "handle"),
    ("查看消息", "notification:read", "notification", "read"),
    ("查看统计", "statistics:read", "statistics", "read"),
    ("查看用户", "user:read", "user", "read"),
    ("新增用户", "user:create", "user", "create"),
    ("编辑用户", "user:update", "user", "update"),
    ("删除用户", "user:delete", "user", "delete"),
    ("查看角色", "role:read", "role", "read"),
    ("分配权限", "role:update", "role", "update"),
    ("部门管理", "department:manage", "department", "manage"),
    ("分类管理", "category:manage", "category", "manage"),
    ("查看操作日志", "log:read", "log", "read"),
]
USER_PERMISSIONS = [
    "asset:read",
    "application:create",
    "assignment:read",
    "assignment:return",
    "repair:create",
    "notification:read",
]

DEPARTMENTS = ["信息中心", "AI实验室", "生物研究所", "行政办公室"]
CATEGORIES = [
    ("NOTEBOOK", "笔记本", 8999),
    ("DESKTOP", "台式机", 5499),
    ("MONITOR", "显示器", 1899),
    ("MOUSE", "鼠标", 129),
    ("KEYBOARD", "键盘", 299),
    ("PROJECTOR", "投影仪", 3999),
    ("ADAPTER", "转接头", 199),
    ("PRINTER", "打印机", 2599),
    ("OTHER", "其他", 999),
]
BRANDS = {
    "NOTEBOOK": [("Lenovo", "ThinkPad X1 Carbon"), ("Dell", "XPS 13"), ("Apple", "MacBook Pro 14")],
    "DESKTOP": [("Dell", "OptiPlex 7010"), ("HP", "ProDesk 400")],
    "MONITOR": [("Dell", "U2720Q"), ("AOC", "Q27G2"), ("Philips", "276E8VJSB")],
    "MOUSE": [("Logitech", "MX Master 3S"), ("Razer", "DeathAdder V2")],
    "KEYBOARD": [("Logitech", "K380"), ("HHKB", "Professional 3")],
    "PROJECTOR": [("Epson", "CB-X06"), ("BenQ", "MX560")],
    "ADAPTER": [("Apple", "USB-C Multiport"), ("绿联", "HDMI 转接")],
    "PRINTER": [("HP", "LaserJet M404"), ("Canon", "LBP2900")],
    "OTHER": [("小米", "智能插座"), ("Anker", "扩展坞")],
}


def seed(reset: bool = False) -> None:
    if reset:
        drop_everything()
    upgrade_to_head()
    db = SessionLocal()
    try:
        if db.scalar(select(func.count()).select_from(User)):
            print("数据库已有数据，跳过初始化（需要重建请加 --reset）")
            return

        random.seed(42)

        # 权限 / 角色
        for name, code, res, action in PERMISSIONS:
            db.add(Permission(permission_name=name, permission_code=code, resource=res, action=action))
        db.flush()
        perm_id = {p.permission_code: p.id for p in db.scalars(select(Permission))}
        admin_role = Role(role_name="管理员", role_code="ADMIN", description="系统管理员，拥有全部权限")
        user_role = Role(role_name="普通用户", role_code="USER", description="普通员工，可申请领用与报修")
        db.add_all([admin_role, user_role])
        db.flush()
        for code, pid in perm_id.items():
            db.add(RolePermission(role_id=admin_role.id, permission_id=pid))
        for code in USER_PERMISSIONS:
            db.add(RolePermission(role_id=user_role.id, permission_id=perm_id[code]))
        db.flush()

        # 部门
        root = Department(department_name="研究院")
        db.add(root)
        db.flush()
        depts = {}
        for name in DEPARTMENTS:
            d = Department(department_name=name, parent_id=root.id)
            db.add(d)
            db.flush()
            depts[name] = d.id

        # 用户
        pwd = hash_password("123456")
        users = {}
        for username, real_name, dept, role in [
            ("admin", "管理员", "信息中心", admin_role),
            ("zhangsan", "张三", "AI实验室", user_role),
            ("lisi", "李四", "生物研究所", user_role),
            ("wangwu", "王五", "行政办公室", user_role),
        ]:
            u = User(
                username=username,
                password_hash=pwd,
                real_name=real_name,
                email=f"{username}@example.com",
                phone=f"1380000{random.randint(1000, 9999)}",
                department_id=depts[dept],
                status=1,
            )
            db.add(u)
            db.flush()
            db.add(UserRole(user_id=u.id, role_id=role.id))
            users[username] = u
        db.flush()

        # 资产分类
        cats = {}
        for code, name, price in CATEGORIES:
            c = AssetCategory(category_name=name, category_code=code, description=f"{name}类资产")
            db.add(c)
            db.flush()
            cats[code] = (c.id, price)

        # 资产：状态分布 在库30% 已领用50% 维修中5% 待维修3% 待报废2% 已报废10%
        total = 150
        plan = (
            ["IN_STOCK"] * int(total * 0.30)
            + ["BORROWED"] * int(total * 0.50)
            + ["REPAIRING"] * int(total * 0.05)
            + ["PENDING_REPAIR"] * int(total * 0.03)
            + ["PENDING_SCRAP"] * int(total * 0.02)
            + ["SCRAPPED"] * int(total * 0.10)
        )
        plan += ["IN_STOCK"] * (total - len(plan))
        random.shuffle(plan)

        staff = [users["zhangsan"], users["lisi"], users["wangwu"]]
        # 到期场景：逾期 / 1天 / 7天 / 30天 / 正常
        due_offsets = [-12, -3, 1, 6, 25, 90, 180, 240]
        borrowed_lots: list[tuple[Asset, User, int]] = []
        repair_lots: list[tuple[Asset, User]] = []

        today = now()
        for i, status in enumerate(plan, start=1):
            code_key = random.choice(list(cats))
            cat_id, base_price = cats[code_key]
            brand, model = random.choice(BRANDS[code_key])
            purchase = date.today() - timedelta(days=random.randint(60, 900))
            a = Asset(
                asset_code=f"IT-{today.year}-{i:06d}",
                asset_name=f"{brand} {model}",
                category_id=cat_id,
                brand=brand,
                model=model,
                serial_number=f"SN{random.randint(10**8, 10**9 - 1)}",
                purchase_date=purchase,
                purchase_price=base_price + random.randint(-200, 500),
                warranty_expire_date=purchase + timedelta(days=1095),
                status=status,
                location=f"{random.choice('ABCD')}栋{random.randint(1, 6)}0{random.randint(1, 9)}",
                supplier=random.choice(["某某科技", "联创数码", "恒信办公设备"]),
                remark=None,
            )
            db.add(a)
            db.flush()
            if status in ("BORROWED", "REPAIRING"):
                borrowed_lots.append((a, random.choice(staff), random.choice(due_offsets)))
            if status in ("REPAIRING", "PENDING_REPAIR"):
                repair_lots.append((a, random.choice(staff)))
        db.flush()

        # 已领用资产：申请（APPROVED）+ 领用记录（ACTIVE/OVERDUE）
        for a, u, offset in borrowed_lots:
            apply_time = today - timedelta(days=random.randint(20, 200))
            expect = (today + timedelta(days=offset)).replace(microsecond=0)
            app = AssetApplication(
                application_no=f"AP{apply_time.strftime('%Y%m%d')}{a.id:04d}",
                applicant_id=u.id,
                asset_id=a.id,
                reason=random.choice(["用于项目开发", "日常办公", "外出演示", "实验室数据采集"]),
                apply_time=apply_time,
                expected_return_time=expect,
                status="APPROVED",
                approver_id=users["admin"].id,
                approval_time=apply_time + timedelta(hours=6),
                approval_remark="同意领用",
            )
            db.add(app)
            db.flush()
            db.add(
                AssetAssignment(
                    asset_id=a.id,
                    user_id=u.id,
                    application_id=app.id,
                    assign_time=apply_time + timedelta(hours=6),
                    expected_return_time=expect,
                    status="OVERDUE" if offset < 0 else "ACTIVE",
                )
            )
        db.flush()

        # 维修单
        for a, u in repair_lots:
            started = today - timedelta(days=random.randint(3, 30))
            status = "REPAIRING" if a.status == "REPAIRING" else "PENDING"
            db.add(
                AssetRepair(
                    repair_no=f"RP{started.strftime('%Y%m%d')}{a.id:04d}",
                    asset_id=a.id,
                    reporter_id=u.id,
                    fault_description=random.choice(["无法开机", "屏幕闪烁", "键盘失灵", "风扇异响", "接口接触不良"]),
                    repair_company="华强北维修中心" if status == "REPAIRING" else None,
                    start_time=started if status == "REPAIRING" else None,
                    status=status,
                    created_at=started,
                )
            )

        # 待审批 / 已驳回 / 已取消 申请（挑在库资产）
        free_assets = list(db.scalars(select(Asset).where(Asset.status == "IN_STOCK").limit(14)))
        for i, a in enumerate(free_assets[:8]):
            u = random.choice(staff)
            db.add(
                AssetApplication(
                    application_no=f"AP{today.strftime('%Y%m%d')}{9000 + i}",
                    applicant_id=u.id,
                    asset_id=a.id,
                    reason=random.choice(["新员工入职配机", "项目开发需要", "外出演示使用"]),
                    apply_time=today - timedelta(days=random.randint(0, 5)),
                    expected_return_time=today + timedelta(days=random.choice([30, 60, 90])),
                    status="PENDING",
                )
            )
        for i, a in enumerate(free_assets[8:11]):
            u = random.choice(staff)
            db.add(
                AssetApplication(
                    application_no=f"AP{today.strftime('%Y%m%d')}{9100 + i}",
                    applicant_id=u.id,
                    asset_id=a.id,
                    reason="临时借用",
                    apply_time=today - timedelta(days=random.randint(6, 20)),
                    expected_return_time=today + timedelta(days=30),
                    status="REJECTED",
                    approver_id=users["admin"].id,
                    approval_time=today - timedelta(days=3),
                    approval_remark="库存需保留给新员工",
                )
            )
        for i, a in enumerate(free_assets[11:14]):
            u = random.choice(staff)
            db.add(
                AssetApplication(
                    application_no=f"AP{today.strftime('%Y%m%d')}{9200 + i}",
                    applicant_id=u.id,
                    asset_id=a.id,
                    reason="误提交",
                    apply_time=today - timedelta(days=random.randint(1, 10)),
                    expected_return_time=today + timedelta(days=30),
                    status="CANCELLED",
                )
            )

        # 消息 + 历史日志（让首页/消息中心一打开就有内容）
        db.add(
            Notification(
                receiver_id=users["admin"].id,
                title="资产到期汇总提醒",
                content="今日到期情况：已逾期 2 台、明天到期 1 台、7天内到期 3 台。",
                notification_type="ASSET_EXPIRE_SUMMARY",
                is_read=False,
            )
        )
        db.add(
            Notification(
                receiver_id=users["zhangsan"].id,
                title="设备7天内到期提醒",
                content="您领用的设备将于 7 天内到期，请及时归还。",
                notification_type="ASSET_EXPIRE_7D",
                is_read=False,
            )
        )
        for i in range(30):
            db.add(
                OperationLog(
                    operator_id=random.choice(list(users.values())).id,
                    operation_type=random.choice(["LOGIN", "ASSET_UPDATE", "APPLICATION_CREATE", "ASSET_CREATE"]),
                    target_type=random.choice(["ASSET", "APPLICATION", "USER"]),
                    target_id=random.randint(1, 150),
                    operation_content="演示历史日志",
                    ip_address=f"192.168.1.{random.randint(2, 250)}",
                    created_at=today - timedelta(days=random.randint(0, 15)),
                )
            )
        db.commit()
        counts = {
            "用户": db.scalar(select(func.count()).select_from(User)),
            "资产": db.scalar(select(func.count()).select_from(Asset)),
            "领用记录": db.scalar(select(func.count()).select_from(AssetAssignment)),
            "申请": db.scalar(select(func.count()).select_from(AssetApplication)),
            "维修": db.scalar(select(func.count()).select_from(AssetRepair)),
        }
        print("初始化完成：", counts)
        print("登录账号：admin / zhangsan / lisi / wangwu，密码均为 123456")
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
