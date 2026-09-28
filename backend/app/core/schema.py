"""表结构的唯一事实来源：Alembic 迁移。

启动 / 初始化脚本都调 upgrade_to_head()，不再用 create_all，
避免「alembic 建的库」和「create_all 建的库」两套结构漂移。
"""

from alembic import command
from alembic.config import Config

from .config import BACKEND_DIR, settings
from .database import engine


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def upgrade_to_head() -> None:
    command.upgrade(alembic_config(), "head")


def drop_everything() -> None:
    """重建库用：删掉 alembic_version（drop_all 删不到它，否则下次会误判已迁移）。"""
    from sqlalchemy import text

    from .database import Base

    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
