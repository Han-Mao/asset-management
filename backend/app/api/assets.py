from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.deps import Page, get_current_user, get_db, require_permission
from ..core.errors import BizError
from ..core.response import EnvelopeRoute
from ..schemas import AssetCreate, AssetUpdate
from ..services import asset as asset_svc
from ..services import import_export
from ..services.common import write_log

router = APIRouter(prefix="/assets", tags=["资产管理"], route_class=EnvelopeRoute)


def _filters(
    keyword: str | None = None,
    category_id: int | None = None,
    status: str | None = None,
    borrower_id: int | None = None,
    borrow_start: datetime | None = None,
    borrow_end: datetime | None = None,
    return_start: datetime | None = None,
    return_end: datetime | None = None,
) -> dict:
    return {
        "keyword": keyword,
        "category_id": category_id,
        "status": status,
        "borrower_id": borrower_id,
        "borrow_start": borrow_start,
        "borrow_end": borrow_end,
        "return_start": return_start,
        "return_end": return_end,
    }


@router.get("")
def list_assets(
    f: dict = Depends(_filters),
    page: Page = Depends(),
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:read")),
):
    return asset_svc.list_assets(db, page, viewer=user, **f)


@router.get("/status-options")
def status_options(_=Depends(get_current_user)):
    return asset_svc.status_options()


@router.post("")
def create_asset(
    data: AssetCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:create")),
):
    return asset_svc.create_asset(db, data, user, request)


@router.get("/export")
def export_assets(
    f: dict = Depends(_filters),
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:export")),
):
    write_log(db, user.id, "ASSET_EXPORT", "ASSET", None, "导出资产清单")
    db.commit()
    content = import_export.export_assets(db, **f)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="assets.xlsx"'},
    )


@router.get("/import/template")
def import_template(_=Depends(require_permission("asset:import"))):
    return StreamingResponse(
        BytesIO(import_export.template_bytes()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="asset-import-template.xlsx"'},
    )


@router.post("/import")
def import_assets(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:import")),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise BizError("请上传 .xlsx 文件")
    try:
        return import_export.import_assets(db, file.file.read(), user, request)
    except ValueError as exc:
        raise BizError(str(exc)) from None


@router.get("/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db), user=Depends(require_permission("asset:read"))):
    return asset_svc.get_asset(db, asset_id, viewer=user)


@router.put("/{asset_id}")
def update_asset(
    asset_id: int,
    data: AssetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:update")),
):
    return asset_svc.update_asset(db, asset_id, data, user, request)


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:delete")),
):
    asset_svc.delete_asset(db, asset_id, user, request)
    return None


@router.get("/{asset_id}/qrcode")
def asset_qrcode(asset_id: int, db: Session = Depends(get_db), user=Depends(require_permission("asset:read"))):
    return Response(content=asset_svc.qrcode_png(db, asset_id, viewer=user), media_type="image/png")


@router.get("/{asset_id}/lifecycle")
def asset_lifecycle(asset_id: int, db: Session = Depends(get_db), user=Depends(require_permission("asset:read"))):
    return asset_svc.lifecycle(db, asset_id, viewer=user)


@router.post("/{asset_id}/pending-scrap")
def pending_scrap(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:update")),
):
    return asset_svc.mark_pending_scrap(db, asset_id, user, request)


@router.post("/{asset_id}/scrap")
def scrap(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_permission("asset:delete")),
):
    return asset_svc.scrap_asset(db, asset_id, user, request)
