from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.deps import get_db, require_permission
from ..core.response import EnvelopeRoute
from ..services import assignment as asg_svc
from ..services import reminder

router = APIRouter(prefix="/system", tags=["系统"], route_class=EnvelopeRoute)


@router.post("/reminders/test")
def trigger_reminder(db: Session = Depends(get_db), _=Depends(require_permission("statistics:read"))):
    """开发/演示用：手动触发一次到期提醒（生产由进程内定时器每天自动执行）。"""
    return reminder.run_reminders(db)


@router.post("/overdue-sync")
def overdue_sync(db: Session = Depends(get_db), _=Depends(require_permission("statistics:read"))):
    return {"updated": asg_svc.overdue_status_sync(db)}
