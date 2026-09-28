import os
import tempfile
from pathlib import Path

# 必须在 import app 之前设置，settings 在导入时读取
_tmp = Path(tempfile.mkdtemp(prefix="asset-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["REMINDER_ENABLED"] = "false"
os.environ["SMTP_HOST"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="session")
def client():
    seed(reset=True)
    with TestClient(app) as c:
        yield c


def _login(client, username: str, password: str = "123456") -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    body = resp.json()
    assert body["code"] == 0, body
    return {"Authorization": f"Bearer {body['data']['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin")


@pytest.fixture(scope="session")
def staff(client):
    return _login(client, "zhangsan")


@pytest.fixture(scope="session")
def staff2(client):
    return _login(client, "lisi")


def data(resp) -> object:
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


# 测试之间不重复用同一台资产（否则会撞上“已提交过申请”这类业务规则）
_used: set[int] = set()


def pick_assets(client, headers, n: int = 1, status: str = "IN_STOCK") -> list[dict]:
    items = data(client.get("/api/assets", headers=headers, params={"status": status, "page_size": 200}))["items"]
    fresh = [a for a in items if a["id"] not in _used][:n]
    assert len(fresh) == n, f"可用资产不足（需要 {n} 台状态为 {status} 且未被占用的资产）"
    _used.update(a["id"] for a in fresh)
    return fresh


def find_asset(client, headers, status: str, **extra) -> dict:
    return pick_assets(client, headers, 1, status)[0]
