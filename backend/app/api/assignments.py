from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import Page, get_current_user, get_db, require_permission
from ..core.errors import BizError
from ..core.response import EnvelopeRoute
from ..schemas import ReturnIn
from ..services import assignment as asg_svc
from ..services.asset import viewer_is_admin

router = APIRouter(prefix="/assignments", tags=["领用记录"], route_class=EnvelopeRoute)


@router.get("")
def list_assignments(
    status: str | None = None,
    keyword: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(require_permission("assignment:read")),
):
    return asg_svc.list_assignments(db, page, status=status, keyword=keyword)


@router.get("/my")
def my_assignments(
    status: str | None = None,
    current: bool = False,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return asg_svc.my_assignments(db, page, user.id, status, current=current)


@router.get("/{assignment_id}")
def get_assignment(assignment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    data = asg_svc.get_assignment(db, assignment_id)
    if data["user_id"] != user.id and not viewer_is_admin(db, user):
        raise BizError("无权查看该领用记录", 40301)
    return data


@router.post("/{assignment_id}/return")
def return_asset(
    assignment_id: int,
    data: ReturnIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return asg_svc.return_asset(db, assignment_id, data, user, request)
