"""Pydantic Schema 统一放这里（一个文件，够用了）；数据库 Model 不直接做入参出参。"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- auth ----------------
class LoginIn(BaseModel):
    username: str
    password: str


class UserBrief(ORMModel):
    id: int
    username: str
    real_name: str
    roles: list[str] = []
    permissions: list[str] = []


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief


# ---------------- 用户 / 角色 / 部门 ----------------
class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=64)
    real_name: str
    email: EmailStr | None = None
    phone: str | None = None
    department_id: int | None = None
    role_codes: list[str] = ["USER"]


class UserUpdate(BaseModel):
    real_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    department_id: int | None = None
    role_codes: list[str] | None = None


class StatusIn(BaseModel):
    status: int = Field(ge=0, le=1)


class PasswordIn(BaseModel):
    password: str = Field(min_length=6, max_length=64)


class UserOut(ORMModel):
    id: int
    username: str
    real_name: str
    email: str | None = None
    phone: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    status: int
    roles: list[str] = []
    last_login_at: datetime | None = None
    created_at: datetime


class RoleIn(BaseModel):
    role_name: str
    role_code: str
    description: str | None = None
    permission_codes: list[str] | None = None


class RoleUpdate(BaseModel):
    role_name: str | None = None
    description: str | None = None
    permission_codes: list[str] | None = None


class RoleOut(ORMModel):
    id: int
    role_name: str
    role_code: str
    description: str | None = None
    permission_codes: list[str] = []


class PermissionOut(ORMModel):
    id: int
    permission_name: str
    permission_code: str
    resource: str | None = None
    action: str | None = None


class DepartmentIn(BaseModel):
    department_name: str
    parent_id: int | None = None


class DepartmentUpdate(BaseModel):
    """PUT 时字段都可选：只改上级部门不该被迫带部门名。"""

    department_name: str | None = None
    parent_id: int | None = None


class DepartmentOut(ORMModel):
    id: int
    department_name: str
    parent_id: int | None = None
    asset_count: int = 0
    user_count: int = 0


class CategoryIn(BaseModel):
    category_name: str
    category_code: str
    description: str | None = None


class CategoryOut(ORMModel):
    id: int
    category_name: str
    category_code: str
    description: str | None = None
    asset_count: int = 0


# ---------------- 资产 ----------------
class AssetCreate(BaseModel):
    asset_name: str
    category_id: int
    asset_code: str | None = None  # 留空自动生成 IT-YYYY-000123
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    purchase_date: date | None = None
    purchase_price: Decimal | None = None
    warranty_expire_date: date | None = None
    location: str | None = None
    supplier: str | None = None
    remark: str | None = None


class AssetUpdate(BaseModel):
    """故意不含 status：资产状态必须由业务动作（审批/维修/报废）驱动。"""

    asset_name: str | None = None
    category_id: int | None = None
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    purchase_date: date | None = None
    purchase_price: Decimal | None = None
    warranty_expire_date: date | None = None
    location: str | None = None
    supplier: str | None = None
    remark: str | None = None


class AssetOut(ORMModel):
    id: int
    asset_code: str
    asset_name: str
    category_id: int
    category_name: str | None = None
    brand: str | None = None
    model: str | None = None
    serial_number: str | None = None
    purchase_date: date | None = None
    purchase_price: Decimal | None = None
    warranty_expire_date: date | None = None
    status: str
    location: str | None = None
    supplier: str | None = None
    remark: str | None = None
    created_at: datetime


# ---------------- 申请 / 领用 ----------------
class ApplicationCreate(BaseModel):
    asset_id: int
    reason: str = Field(min_length=1)
    expected_return_time: datetime


class ApprovalIn(BaseModel):
    remark: str | None = None


class BatchApproveIn(BaseModel):
    ids: list[int] = Field(min_length=1)
    remark: str | None = None


class ApplicationOut(ORMModel):
    id: int
    application_no: str
    applicant_id: int
    applicant_name: str | None = None
    department_name: str | None = None
    asset_id: int
    asset_code: str | None = None
    asset_name: str | None = None
    reason: str
    apply_time: datetime
    expected_return_time: datetime
    status: str
    approver_id: int | None = None
    approver_name: str | None = None
    approval_time: datetime | None = None
    approval_remark: str | None = None


class ReturnIn(BaseModel):
    remark: str | None = None
    to_repair: bool = False  # 归还时发现故障，直接转待维修


class AssignmentOut(ORMModel):
    id: int
    asset_id: int
    asset_code: str | None = None
    asset_name: str | None = None
    user_id: int
    user_name: str | None = None
    application_id: int
    assign_time: datetime
    expected_return_time: datetime
    actual_return_time: datetime | None = None
    status: str
    remark: str | None = None
    days_left: int | None = None


# ---------------- 维修 ----------------
class RepairCreate(BaseModel):
    asset_id: int
    fault_description: str
    repair_company: str | None = None


class RepairUpdate(BaseModel):
    repair_company: str | None = None
    repair_cost: Decimal | None = None
    repair_result: str | None = None


class RepairOut(ORMModel):
    id: int
    repair_no: str
    asset_id: int
    asset_code: str | None = None
    asset_name: str | None = None
    reporter_id: int
    reporter_name: str | None = None
    fault_description: str
    repair_company: str | None = None
    repair_cost: Decimal | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    repair_result: str | None = None
    status: str
    created_at: datetime


# ---------------- 消息 / 日志 ----------------
class NotificationOut(ORMModel):
    id: int
    title: str
    content: str
    notification_type: str
    related_type: str | None = None
    related_id: int | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class LogOut(ORMModel):
    id: int
    operator_id: int | None = None
    operator_name: str | None = None
    operation_type: str
    target_type: str | None = None
    target_id: int | None = None
    operation_content: str | None = None
    ip_address: str | None = None
    created_at: datetime
