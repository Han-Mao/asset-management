import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    applications,
    assets,
    assignments,
    auth,
    categories,
    dashboard,
    departments,
    logs,
    notifications,
    repairs,
    roles,
    system,
    users,
)
from .core.config import settings
from .core.errors import register_exception_handlers
from .core.schema import upgrade_to_head

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("asset")


@asynccontextmanager
async def lifespan(app: FastAPI):
    upgrade_to_head()  # 等价于 alembic upgrade head，保证表结构与迁移一致
    if settings.reminder_enabled:
        from .services.reminder import start_scheduler

        start_scheduler()
        logger.info("到期提醒定时器已启动（每天 %s:00）", settings.reminder_hour)
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

router = APIRouter(prefix=settings.api_prefix)
for module in (
    auth,
    users,
    roles,
    departments,
    categories,
    assets,
    applications,
    assignments,
    repairs,
    notifications,
    dashboard,
    logs,
    system,
):
    router.include_router(module.router)
app.include_router(router)


@app.get("/health", tags=["系统"])
def health():
    return {"code": 0, "message": "success", "data": {"status": "ok", "app": settings.app_name}}
