# 状态码 -> 中文名，前端下拉、图表、标签统一从这里取
ASSET_STATUS: dict[str, str] = {
    "IN_STOCK": "在库",
    "BORROWED": "已领用",
    "PENDING_REPAIR": "待维修",
    "REPAIRING": "维修中",
    "PENDING_SCRAP": "待报废",
    "SCRAPPED": "已报废",
}

APPLICATION_STATUS: dict[str, str] = {
    "PENDING": "待审批",
    "APPROVED": "已通过",
    "REJECTED": "已驳回",
    "CANCELLED": "已取消",
}

ASSIGNMENT_STATUS: dict[str, str] = {
    "ACTIVE": "领用中",
    "RETURNED": "已归还",
    "OVERDUE": "已逾期",
}

REPAIR_STATUS: dict[str, str] = {
    "PENDING": "待处理",
    "REPAIRING": "维修中",
    "COMPLETED": "已完成",
    "CANCELLED": "已取消",
}

# 资产生命周期允许的状态流转（业务状态机，写在 Service 里校验，不塞进数据库 CHECK）
ASSET_TRANSITIONS: dict[str, set[str]] = {
    "IN_STOCK": {"BORROWED", "PENDING_REPAIR", "PENDING_SCRAP"},
    "BORROWED": {"IN_STOCK", "PENDING_REPAIR", "PENDING_SCRAP"},
    "PENDING_REPAIR": {"REPAIRING"},
    "REPAIRING": {"IN_STOCK", "BORROWED"},
    "PENDING_SCRAP": {"SCRAPPED"},
    "SCRAPPED": set(),
}

ACTIVE_ASSIGNMENT_STATUS = ("ACTIVE", "OVERDUE")
