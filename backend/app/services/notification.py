import logging
import smtplib
import threading
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import now
from ..core.errors import BizError
from ..models import Notification, Role, User, UserRole

logger = logging.getLogger("asset.notification")


def send_email(to: str, subject: str, body: str) -> None:
    """stdlib smtplib 起线程发，业务事务不等它；SMTP 未配置就只记日志。"""
    if not settings.smtp_host:
        logger.info("[邮件未配置] 发给 %s：%s", to, subject)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.set_content(body)

    def _run():
        try:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as s:
                if settings.smtp_user:
                    s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg)
        except Exception as exc:  # 邮件失败不能影响业务
            logger.warning("邮件发送失败 %s: %s", to, exc)

    threading.Thread(target=_run, daemon=True).start()


def send(
    db: Session,
    receiver_id: int,
    title: str,
    content: str,
    notification_type: str,
    related_type: str | None = None,
    related_id: int | None = None,
    email: bool = False,
) -> Notification:
    """所有业务模块发通知的唯一入口；以后加短信/企微只改这里。"""
    n = Notification(
        receiver_id=receiver_id,
        title=title,
        content=content,
        notification_type=notification_type,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(n)
    if email:
        to = db.scalar(select(User.email).where(User.id == receiver_id))
        if to:
            send_email(to, title, content)
    return n


def send_to_role(db: Session, role_codes: list[str], **kw) -> int:
    """给某角色的所有正常用户发通知（如“有新的领用申请待审批”）。"""
    ids = db.scalars(
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.role_code.in_(role_codes), User.status == 1)
    ).all()
    for uid in set(ids):
        send(db, receiver_id=uid, **kw)
    return len(set(ids))


def already_sent(db: Session, receiver_id: int, notification_type: str, related_id: int, today_only: bool = False) -> bool:
    """提醒去重：同一接收人 + 同一类型 + 同一业务对象是否已发过。

    today_only=False（30/7/1 天里程碑）→ 一辈子只发一次；
    today_only=True（逾期）→ 当天发过就不再发，第二天可以再发。
    """
    cond = [
        Notification.receiver_id == receiver_id,
        Notification.notification_type == notification_type,
        Notification.related_id == related_id,
    ]
    if today_only:
        start = now().replace(hour=0, minute=0, second=0, microsecond=0)
        cond.append(Notification.created_at >= start - timedelta(hours=8))  # 本地日 0 点对应的 UTC
    return bool(db.scalar(select(func.count()).select_from(Notification).where(*cond)))


def list_my(db: Session, user_id: int, only_unread: bool, page) -> dict:
    cond = [Notification.receiver_id == user_id]
    if only_unread:
        cond.append(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(Notification).where(*cond)) or 0
    rows = db.scalars(
        select(Notification)
        .where(*cond)
        .order_by(Notification.created_at.desc())
        .offset(page.offset)
        .limit(page.page_size)
    ).all()
    return page.wrap(list(rows), total)


def unread_count(db: Session, user_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.receiver_id == user_id, Notification.is_read.is_(False))
        )
        or 0
    )


def mark_read(db: Session, user_id: int, notification_id: int) -> None:
    n = db.get(Notification, notification_id)
    if n is None or n.receiver_id != user_id:
        raise BizError("消息不存在")
    n.is_read = True
    n.read_at = now()
    db.commit()


def mark_all_read(db: Session, user_id: int) -> int:
    res = db.execute(
        update(Notification)
        .where(Notification.receiver_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=now())
    )
    db.commit()
    return res.rowcount or 0
