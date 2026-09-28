from io import BytesIO

from openpyxl import load_workbook

from .conftest import data, find_asset


def test_asset_crud_and_status_immutable(client, admin):
    created = data(
        client.post(
            "/api/assets",
            headers=admin,
            json={
                "asset_name": "测试笔记本",
                "category_id": data(client.get("/api/asset-categories", headers=admin))[0]["id"],
                "brand": "Lenovo",
                "purchase_price": "6999.00",
                "purchase_date": "2026-01-01",
            },
        )
    )
    assert created["asset_code"].startswith("IT-")
    assert created["status"] == "IN_STOCK"

    aid = created["id"]
    updated = data(
        client.put(f"/api/assets/{aid}", headers=admin, json={"asset_name": "测试笔记本2", "status": "BORROWED"})
    )
    # status 不在 AssetUpdate 里，传了也不接受
    assert updated["asset_name"] == "测试笔记本2"
    assert updated["status"] == "IN_STOCK"

    assert data(client.delete(f"/api/assets/{aid}", headers=admin)) is None
    assert client.get(f"/api/assets/{aid}", headers=admin).json()["code"] == 40401


def test_asset_query_filters(client, admin):
    page = data(client.get("/api/assets", headers=admin, params={"keyword": "IT-", "page": 1, "page_size": 5}))
    assert page["page"] == 1 and len(page["items"]) == 5 and page["total"] >= 100

    borrowed = data(client.get("/api/assets", headers=admin, params={"status": "BORROWED", "page_size": 100}))["items"]
    assert borrowed and all(a["status"] == "BORROWED" for a in borrowed)
    assert all(a["borrower_name"] for a in borrowed)

    one = borrowed[0]
    same_borrower = data(client.get("/api/assets", headers=admin, params={"borrower_id": one["borrower_id"], "page_size": 100}))
    assert same_borrower["total"] >= 1

    overdue = data(client.get("/api/assets", headers=admin, params={"status": "BORROWED", "return_end": "2020-01-01"}))
    assert overdue["total"] == 0


def test_delete_borrowed_asset_rejected(client, admin):
    borrowed = find_asset(client, admin, "BORROWED")
    assert client.delete(f"/api/assets/{borrowed['id']}", headers=admin).json()["code"] != 0


def test_qrcode_and_lifecycle(client, admin):
    asset = find_asset(client, admin, "BORROWED")
    resp = client.get(f"/api/assets/{asset['id']}/qrcode", headers=admin)
    assert resp.status_code == 200 and resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    events = data(client.get(f"/api/assets/{asset['id']}/lifecycle", headers=admin))
    types = {e["type"] for e in events}
    assert "ASSET_CREATED" in types and "ASSIGNED" in types


def test_scrap_flow(client, admin):
    asset = find_asset(client, admin, "IN_STOCK")
    data(client.post(f"/api/assets/{asset['id']}/pending-scrap", headers=admin))
    assert data(client.get(f"/api/assets/{asset['id']}", headers=admin))["status"] == "PENDING_SCRAP"
    assert data(client.post(f"/api/assets/{asset['id']}/scrap", headers=admin))["status"] == "SCRAPPED"
    assert client.put(f"/api/assets/{asset['id']}", headers=admin, json={"asset_name": "x"}).json()["code"] != 0


def test_export_and_template(client, admin):
    resp = client.get("/api/assets/export", headers=admin, params={"status": "IN_STOCK"})
    assert resp.status_code == 200
    wb = load_workbook(BytesIO(resp.content))
    ws = wb.active
    assert ws.max_row >= 1

    tpl = client.get("/api/assets/import/template", headers=admin)
    assert tpl.status_code == 200
    assert load_workbook(BytesIO(tpl.content)).active[2][0].value == "IT-2026-000001"


def test_import_assets_with_error_report(client, admin):
    from openpyxl import Workbook

    cats = data(client.get("/api/asset-categories", headers=admin))
    notebook = [c["category_name"] for c in cats if c["category_code"] == "NOTEBOOK"][0]
    wb = Workbook()
    ws = wb.active
    ws.append(["资产编号", "设备名称", "设备类型", "品牌", "型号", "序列号", "采购日期", "采购价格", "保修截止", "存放位置", "供应商", "备注"])
    ws.append(["IT-IMPORT-001", "导入测试本", notebook, "Lenovo", "T14", "SN-IMP-1", "2026-01-01", 5000, "2029-01-01", "A栋101", "某供应商", ""])
    ws.append(["IT-IMPORT-001", "重复编号", notebook, "", "", "", "", "", "", "", "", ""])
    ws.append(["IT-IMPORT-002", "类型不存在", "不存在的类型", "", "", "", "", "", "", "", "", ""])
    ws.append(["IT-IMPORT-003", "价格错误", notebook, "", "", "", "2026-01-01", "很贵", "", "", "", ""])
    buf = BytesIO()
    wb.save(buf)

    result = data(
        client.post(
            "/api/assets/import",
            headers=admin,
            files={"file": ("import.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    )
    assert result["total"] == 4 and result["success"] == 1 and result["failed"] == 3
    assert {e["row"] for e in result["errors"]} == {3, 4, 5}

    # 导入的资产可查到
    found = data(client.get("/api/assets", headers=admin, params={"keyword": "IT-IMPORT-001"}))
    assert found["total"] == 1 and found["items"][0]["status"] == "IN_STOCK"


def test_import_bad_header(client, admin):
    wb = __import__("openpyxl").Workbook()
    wb.active.append(["编号", "名称"])
    buf = BytesIO()
    wb.save(buf)
    body = client.post("/api/assets/import", headers=admin, files={"file": ("bad.xlsx", buf.getvalue())}).json()
    assert body["code"] != 0 and "表头" in body["message"]
