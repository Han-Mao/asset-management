from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.deps import Page, get_current_user, get_db
from ..core.response import EnvelopeRoute
from ..schemas import NotificationOut
from ..services import notification as notif

router = APIRouter(prefix="/notifications", tags=["消息中心"], route_class=EnvelopeRoute)


@router.get("")
def list_notifications(
    unread: bool = False,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    data = notif.list_my(db, user.id, unread, page)
    data["items"] = [NotificationOut.model_validate(n) for n in data["items"]]
    return data


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"count": notif.unread_count(db, user.id)}


@router.post("/read-all")
def read_all(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"count": notif.mark_all_read(db, user.id)}


@router.post("/{notification_id}/read")
def read(notification_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    notif.mark_read(db, user.id, notification_id)
    return None
