"""13 张表统一出口：Alembic / seed / 业务代码都从这里 import。"""

from .asset import Asset, AssetCategory
from .system import (
    Department,
    Notification,
    OperationLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from .workflow import AssetApplication, AssetAssignment, AssetRepair

__all__ = [
    "Asset",
    "AssetApplication",
    "AssetAssignment",
    "AssetCategory",
    "AssetRepair",
    "Department",
    "Notification",
    "OperationLog",
    "Permission",
    "Role",
    "RolePermission",
    "User",
    "UserRole",
]
