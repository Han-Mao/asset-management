from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_db, require_permission
from ..core.response import EnvelopeRoute
from ..services import dashboard as dash_svc

router = APIRouter(prefix="/dashboard", tags=["统计"], route_class=EnvelopeRoute)


@router.get("/overview")
def overview(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return dash_svc.overview(db)


@router.get("/asset-status")
def asset_status(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return dash_svc.asset_status(db)


@router.get("/asset-category")
def asset_category(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return dash_svc.asset_category(db)


@router.get("/department")
def department(db: Session = Depends(get_db), _=Depends(require_permission("statistics:read"))):
    return dash_svc.department(db)


@router.get("/expiry")
def expiry(days: int = 30, db: Session = Depends(get_db), _=Depends(get_current_user)):
    return dash_svc.expiry(db, days)


@router.get("/borrow-trend")
def borrow_trend(months: int = 6, db: Session = Depends(get_db), _=Depends(require_permission("statistics:read"))):
    return dash_svc.borrow_trend(db, months)


@router.get("/application-stats")
def application_stats(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return dash_svc.application_stats(db)
