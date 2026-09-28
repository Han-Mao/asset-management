from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.deps import Page, get_current_user, get_db, require_permission
from ..core.errors import BizError
from ..core.response import EnvelopeRoute
from ..schemas import ApprovalIn, ApplicationCreate, BatchApproveIn
from ..services import application as app_svc
from ..services.asset import viewer_is_admin

router = APIRouter(prefix="/applications", tags=["领用申请"], route_class=EnvelopeRoute)


@router.post("")
def create_application(
    data: ApplicationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("application:create")),
):
    return app_svc.create_application(db, data, user, request)


@router.get("")
def list_applications(
    status: str | None = None,
    keyword: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user=Depends(require_permission("application:approve")),
):
    return app_svc.list_applications(db, page, status=status, keyword=keyword)


@router.get("/my")
def my_applications(
    status: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return app_svc.list_applications(db, page, status=status, applicant_id=user.id)


@router.get("/pending")
def pending_applications(
    keyword: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user=Depends(require_permission("application:approve")),
):
    return app_svc.list_applications(db, page, status="PENDING", keyword=keyword)


@router.post("/batch-approve")
def batch_approve(
    data: BatchApproveIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("application:approve")),
):
    return app_svc.batch_approve(db, data.ids, user, data.remark, request)


@router.get("/{application_id}")
def get_application(application_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    data = app_svc.get_application(db, application_id)
    if not viewer_is_admin(db, user) and data["applicant_id"] != user.id:
        raise BizError("无权查看该申请", 40301)
    return data


@router.post("/{application_id}/cancel")
def cancel_application(
    application_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    return app_svc.cancel_application(db, application_id, user, request)


@router.post("/{application_id}/approve")
def approve(
    application_id: int,
    data: ApprovalIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("application:approve")),
):
    return app_svc.approve_application(db, application_id, user, data.remark, request)


@router.post("/{application_id}/reject")
def reject(
    application_id: int,
    data: ApprovalIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("application:approve")),
):
    return app_svc.reject_application(db, application_id, user, data.remark, request)
