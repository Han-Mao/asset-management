"""每日到期提醒。

懒版替代 Celery + Redis：进程内一个后台线程按天跑；去重不引入 Redis/新表，
直接查 sys_notification：
  30/7/1 天里程碑 —— 同一领用记录 + 同一提醒类型，**一辈子只发一次**
  逾期          —— 同一领用记录，**每天发一次**
ponytail: 单进程定时器，多实例部署会重复触发，那时再换 Celery Beat。
"""

import logging
import threading
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.constants import ACTIVE_ASSIGNMENT_STATUS
from ..core.database import SessionLocal, now
from ..models import Asset, AssetAssignment, User
from . import assignment as assignment_svc
from . import notification as notif

logger = logging.getLogger("asset.reminder")

# 剩余天数 == 以下值时才触发（里程碑式，不是「小于等于」）
MILESTONES = {
    30: ("ASSET_EXPIRE_30D", "30天内到期"),
    7: ("ASSET_EXPIRE_7D", "7天内到期"),
    1: ("ASSET_EXPIRE_1D", "明天到期"),
}


def _milestone(days: int) -> tuple[str, str] | None:
    if days < 0:
        return "ASSET_OVERDUE", "已逾期"
    return MILESTONES.get(days)


def run_reminders(db: Session) -> dict:
    """扫描领用中的记录：30/7/1 天各提醒一次，逾期每天提醒一次。"""
    assignment_svc.overdue_status_sync(db)
    rows = db.execute(
        select(AssetAssignment, Asset, User)
        .join(Asset, Asset.id == AssetAssignment.asset_id)
        .join(User, User.id == AssetAssignment.user_id)
        .where(AssetAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUS))
    ).all()

    sent = {"expire": 0, "overdue": 0}
    admin_buckets: dict[str, int] = {}
    for s, asset, user in rows:
        # 按自然日算剩余天数：今天到应归还日差 1 天 = 明天到期
        days = (s.expected_return_time.date() - now().date()).days
        hit = _milestone(days)
        if hit is None:
            continue
        kind, label = hit
        admin_buckets[label] = admin_buckets.get(label, 0) + 1

        overdue = kind == "ASSET_OVERDUE"
        if notif.already_sent(db, user.id, kind, s.id, today_only=overdue):
            continue
        if overdue:
            notif.send(
                db,
                receiver_id=user.id,
                title="设备已逾期未归还",
                content=f"您领用的 {asset.asset_name}（{asset.asset_code}）已逾期 {-days} 天，请尽快归还。",
                notification_type=kind,
                related_type="ASSIGNMENT",
                related_id=s.id,
                email=True,  # 逾期邮件追一下
            )
            sent["overdue"] += 1
        else:
            notif.send(
                db,
                receiver_id=user.id,
                title=f"设备{label}提醒",
                content=(
                    f"您领用的 {asset.asset_name}（{asset.asset_code}）将于 {s.expected_return_time:%Y-%m-%d} 到期，"
                    f"剩余 {days} 天，请及时归还。"
                ),
                notification_type=kind,
                related_type="ASSIGNMENT",
                related_id=s.id,
                email=True,  # 到期提醒：普通用户站内信 + 邮件
            )
            sent["expire"] += 1

    # 管理员只收站内信汇总
    if admin_buckets:
        summary = "、".join(f"{k} {v} 台" for k, v in admin_buckets.items())
        notif.send_to_role(
            db,
            ["ADMIN"],
            title="资产到期汇总提醒",
            content=f"今日到期情况：{summary}。",
            notification_type="ASSET_EXPIRE_SUMMARY",
        )
    db.commit()
    logger.info("到期提醒完成：%s", sent)
    return sent


def _loop():
    while True:
        now_ = now()
        target = now_.replace(hour=settings.reminder_hour, minute=0, second=0, microsecond=0)
        if target <= now_:
            target = target + timedelta(days=1)
        time.sleep(max(60, (target - now_).total_seconds()))
        db = SessionLocal()
        try:
            run_reminders(db)
        except Exception:  # 定时任务挂了不能拖垮服务
            logger.exception("到期提醒任务执行失败")
        finally:
            db.close()


def start_scheduler() -> threading.Thread:
    t = threading.Thread(target=_loop, name="reminder-scheduler", daemon=True)
    t.start()
    return t
