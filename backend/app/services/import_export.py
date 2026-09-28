"""Excel 导入导出：解析/校验逻辑都在这里，Router 只负责收文件、发流。"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.constants import ASSET_STATUS
from ..models import Asset, AssetCategory
from .asset import build_query
from .common import write_log

HEADERS = [
    "资产编号",
    "设备名称",
    "设备类型",
    "品牌",
    "型号",
    "序列号",
    "采购日期",
    "采购价格",
    "保修截止",
    "存放位置",
    "供应商",
    "备注",
]
EXPORT_HEADERS = HEADERS[:2] + ["设备类型", "状态", "当前领用人", "应归还时间"] + HEADERS[3:]


def template_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "资产导入模板"
    ws.append(HEADERS)
    ws.append(
        ["IT-2026-000001", "ThinkPad X1 Carbon", "笔记本", "Lenovo", "X1 Carbon", "SN12345",
         "2026-03-01", 8999, "2029-03-01", "A栋301", "某某科技", "示例行，导入前请删除"]
    )
    ws2 = wb.create_sheet("资产类型参考")
    ws2.append(["类型名称"])
    for name in ["笔记本", "台式机", "显示器", "鼠标", "键盘", "投影仪", "转接头", "打印机", "其他"]:
        ws2.append([name])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _parse_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"日期格式错误：{v}")


def import_assets(db: Session, content: bytes, operator=None, request=None) -> dict:
    try:
        wb = load_workbook(BytesIO(content), data_only=True)
    except Exception:
        raise ValueError("文件无法解析，请使用 .xlsx 格式") from None
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("文件内容为空")
    if [str(c).strip() if c else "" for c in rows[0][: len(HEADERS)]] != HEADERS:
        raise ValueError("表头不匹配，请先下载导入模板")

    cat_by_name = {c.category_name: c.id for c in db.scalars(select(AssetCategory))}
    cat_by_code = {c.category_code: c.id for c in db.scalars(select(AssetCategory))}
    existing = set(db.scalars(select(Asset.asset_code)))
    seen: set[str] = set()

    success, errors = 0, []
    for idx, raw in enumerate(rows[1:], start=2):
        cells = [("" if c is None else c) for c in raw]
        if not any(str(c).strip() for c in cells):
            continue
        vals = (cells + [""] * len(HEADERS))[: len(HEADERS)]
        code = str(vals[0]).strip()
        name = str(vals[1]).strip()
        ctype = str(vals[2]).strip()
        if not code:
            errors.append({"row": idx, "asset_code": "", "message": "资产编号为空"})
            continue
        if code in existing or code in seen:
            errors.append({"row": idx, "asset_code": code, "message": "资产编号已存在"})
            continue
        if not name:
            errors.append({"row": idx, "asset_code": code, "message": "设备名称为空"})
            continue
        category_id = cat_by_name.get(ctype) or cat_by_code.get(ctype)
        if not category_id:
            errors.append({"row": idx, "asset_code": code, "message": f"设备类型不存在：{ctype}"})
            continue
        try:
            purchase_date = _parse_date(vals[6])
            warranty = _parse_date(vals[8])
        except ValueError as exc:
            errors.append({"row": idx, "asset_code": code, "message": str(exc)})
            continue
        price = None
        if str(vals[7]).strip():
            try:
                price = Decimal(str(vals[7]).strip())
            except InvalidOperation:
                errors.append({"row": idx, "asset_code": code, "message": f"采购价格不是数字：{vals[7]}"})
                continue
        db.add(
            Asset(
                asset_code=code,
                asset_name=name,
                category_id=category_id,
                brand=str(vals[3]).strip() or None,
                model=str(vals[4]).strip() or None,
                serial_number=str(vals[5]).strip() or None,
                purchase_date=purchase_date,
                purchase_price=price,
                warranty_expire_date=warranty,
                status="IN_STOCK",
                location=str(vals[9]).strip() or None,
                supplier=str(vals[10]).strip() or None,
                remark=str(vals[11]).strip() or None,
            )
        )
        seen.add(code)
        success += 1

    write_log(db, operator.id if operator else None, "ASSET_IMPORT", "ASSET", None, f"导入资产 {success} 条", request)
    db.commit()
    return {"total": success + len(errors), "success": success, "failed": len(errors), "errors": errors}


def export_assets(db: Session, **filters) -> bytes:
    stmt = build_query(db, **filters).order_by(Asset.id.desc())
    wb = Workbook()
    ws = wb.active
    ws.title = "资产清单"
    ws.append(EXPORT_HEADERS)
    for asset, cname, cur, uname in db.execute(stmt).all():
        ws.append(
            [
                asset.asset_code,
                asset.asset_name,
                cname,
                ASSET_STATUS.get(asset.status, asset.status),
                uname or "",
                cur.expected_return_time.strftime("%Y-%m-%d") if cur else "",
                asset.brand,
                asset.model,
                asset.serial_number,
                asset.purchase_date.strftime("%Y-%m-%d") if asset.purchase_date else "",
                float(asset.purchase_price) if asset.purchase_price is not None else "",
                asset.warranty_expire_date.strftime("%Y-%m-%d") if asset.warranty_expire_date else "",
                asset.location,
                asset.supplier,
                asset.remark,
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
