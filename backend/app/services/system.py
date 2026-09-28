"""系统管理：用户 / 角色 / 权限 / 部门 / 资产分类。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.constants import ACTIVE_ASSIGNMENT_STATUS
from ..core.errors import BizError
from ..core.security import hash_password
from ..models import (
    Asset,
    AssetApplication,
    AssetAssignment,
    AssetCategory,
    Department,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from .common import write_log


# ---------------- 用户 ----------------
def user_roles(db: Session, user_id: int) -> list[str]:
    return list(
        db.scalars(
            select(Role.role_code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        )
    )


def _role_ids(db: Session, codes: list[str]) -> list[int]:
    if not codes:
        return []
    found = dict(db.execute(select(Role.role_code, Role.id).where(Role.role_code.in_(codes))).all())
    missing = set(codes) - set(found)
    if missing:
        raise BizError(f"角色不存在：{','.join(missing)}")
    return list(found.values())


def set_roles(db: Session, user_id: int, codes: list[str]) -> None:
    ids = _role_ids(db, codes)
    db.query(UserRole).filter(UserRole.user_id == user_id).delete()
    for rid in ids:
        db.add(UserRole(user_id=user_id, role_id=rid))


def _user_out(db: Session, u: User) -> dict:
    dept = db.scalar(select(Department.department_name).where(Department.id == u.department_id))
    return {
        "id": u.id,
        "username": u.username,
        "real_name": u.real_name,
        "email": u.email,
        "phone": u.phone,
        "department_id": u.department_id,
        "department_name": dept,
        "status": u.status,
        "roles": user_roles(db, u.id),
        "last_login_at": u.last_login_at,
        "created_at": u.created_at,
    }


def list_users(db: Session, keyword: str | None, department_id: int | None, status: int | None, page) -> dict:
    cond = []
    if keyword:
        like = f"%{keyword}%"
        cond.append(User.username.like(like) | User.real_name.like(like))
    if department_id:
        cond.append(User.department_id == department_id)
    if status is not None:
        cond.append(User.status == status)
    total = db.scalar(select(func.count()).select_from(User).where(*cond)) or 0
    rows = db.scalars(
        select(User).where(*cond).order_by(User.id).offset(page.offset).limit(page.page_size)
    ).all()
    return page.wrap([_user_out(db, u) for u in rows], total)


def get_user(db: Session, user_id: int) -> dict:
    u = db.get(User, user_id)
    if u is None:
        raise BizError("用户不存在", 40401)
    return _user_out(db, u)


def create_user(db: Session, data, operator=None, request=None) -> dict:
    if db.scalar(select(func.count()).select_from(User).where(User.username == data.username)):
        raise BizError("账号已存在")
    u = User(
        username=data.username,
        password_hash=hash_password(data.password),
        real_name=data.real_name,
        email=data.email,
        phone=data.phone,
        department_id=data.department_id,
        status=1,
    )
    db.add(u)
    db.flush()
    set_roles(db, u.id, data.role_codes or ["USER"])
    write_log(db, operator.id if operator else None, "USER_CREATE", "USER", u.id, f"新增用户 {u.username}", request)
    db.commit()
    return _user_out(db, u)


def update_user(db: Session, user_id: int, data, operator=None, request=None) -> dict:
    u = db.get(User, user_id)
    if u is None:
        raise BizError("用户不存在", 40401)
    payload = data.model_dump(exclude_unset=True)
    role_codes = payload.pop("role_codes", None)
    for k, v in payload.items():
        setattr(u, k, v)
    if role_codes is not None:
        if u.id == operator.id and "ADMIN" not in role_codes:
            raise BizError("不能取消自己的管理员角色")
        set_roles(db, u.id, role_codes)
    write_log(db, operator.id if operator else None, "USER_UPDATE", "USER", u.id, f"修改用户 {u.username}", request)
    db.commit()
    return _user_out(db, u)


def delete_user(db: Session, user_id: int, operator=None, request=None) -> None:
    u = db.get(User, user_id)
    if u is None:
        raise BizError("用户不存在", 40401)
    if operator and u.id == operator.id:
        raise BizError("不能删除当前登录账号")
    if db.scalar(select(func.count()).select_from(AssetApplication).where(AssetApplication.applicant_id == user_id)):
        raise BizError("该用户已有业务记录，请改为「禁用」而不是删除")
    username = u.username
    db.delete(u)
    write_log(db, operator.id if operator else None, "USER_DELETE", "USER", user_id, f"删除用户 {username}", request)
    db.commit()


def set_status(db: Session, user_id: int, status: int, operator=None, request=None) -> None:
    u = db.get(User, user_id)
    if u is None:
        raise BizError("用户不存在", 40401)
    if operator and u.id == operator.id:
        raise BizError("不能禁用当前登录账号")
    u.status = status
    write_log(
        db,
        operator.id if operator else None,
        "USER_STATUS",
        "USER",
        u.id,
        f"{'启用' if status == 1 else '禁用'}用户 {u.username}",
        request,
    )
    db.commit()


def reset_password(db: Session, user_id: int, password: str, operator=None, request=None) -> None:
    u = db.get(User, user_id)
    if u is None:
        raise BizError("用户不存在", 40401)
    u.password_hash = hash_password(password)
    write_log(db, operator.id if operator else None, "USER_RESET_PWD", "USER", u.id, f"重置 {u.username} 密码", request)
    db.commit()


# ---------------- 角色 / 权限 ----------------
def _role_out(db: Session, r: Role) -> dict:
    codes = list(
        db.scalars(
            select(Permission.permission_code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == r.id)
        )
    )
    return {
        "id": r.id,
        "role_name": r.role_name,
        "role_code": r.role_code,
        "description": r.description,
        "permission_codes": codes,
    }


def list_roles(db: Session) -> list[dict]:
    return [_role_out(db, r) for r in db.scalars(select(Role).order_by(Role.id))]


def list_permissions(db: Session) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.resource, Permission.action)))


def _set_permissions(db: Session, role_id: int, codes: list[str]) -> None:
    ids = db.scalars(select(Permission.id).where(Permission.permission_code.in_(codes or []))).all()
    db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
    for pid in ids:
        db.add(RolePermission(role_id=role_id, permission_id=pid))


def create_role(db: Session, data, operator=None, request=None) -> dict:
    if db.scalar(select(func.count()).select_from(Role).where(Role.role_code == data.role_code)):
        raise BizError("角色编码已存在")
    r = Role(role_name=data.role_name, role_code=data.role_code, description=data.description)
    db.add(r)
    db.flush()
    _set_permissions(db, r.id, data.permission_codes or [])
    write_log(db, operator.id if operator else None, "ROLE_CREATE", "ROLE", r.id, f"新增角色 {r.role_code}", request)
    db.commit()
    return _role_out(db, r)


def update_role(db: Session, role_id: int, data, operator=None, request=None) -> dict:
    r = db.get(Role, role_id)
    if r is None:
        raise BizError("角色不存在", 40401)
    if data.role_name:
        r.role_name = data.role_name
    if data.description is not None:
        r.description = data.description
    if data.permission_codes is not None:
        _set_permissions(db, r.id, data.permission_codes)
    write_log(db, operator.id if operator else None, "ROLE_UPDATE", "ROLE", r.id, f"修改角色 {r.role_code}", request)
    db.commit()
    return _role_out(db, r)


def delete_role(db: Session, role_id: int, operator=None, request=None) -> None:
    r = db.get(Role, role_id)
    if r is None:
        raise BizError("角色不存在", 40401)
    if db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)):
        raise BizError("该角色下还有用户，不能删除")
    db.delete(r)
    write_log(db, operator.id if operator else None, "ROLE_DELETE", "ROLE", role_id, f"删除角色 {r.role_code}", request)
    db.commit()


# ---------------- 部门 ----------------
def list_departments(db: Session) -> list[dict]:
    # 部门资产数 = 该部门用户当前领用中的资产数（在库资产没有归属部门）
    asset_rows = db.execute(
        select(User.department_id, func.count(AssetAssignment.id))
        .join(AssetAssignment, AssetAssignment.user_id == User.id)
        .where(AssetAssignment.status.in_(ACTIVE_ASSIGNMENT_STATUS))
        .group_by(User.department_id)
    ).all()
    asset_cnt = {d: c for d, c in asset_rows if d}
    user_cnt = dict(db.execute(select(User.department_id, func.count()).group_by(User.department_id)).all())

    out = []
    for d in db.scalars(select(Department).order_by(Department.id)):
        out.append(
            {
                "id": d.id,
                "department_name": d.department_name,
                "parent_id": d.parent_id,
                "asset_count": asset_cnt.get(d.id, 0),
                "user_count": user_cnt.get(d.id, 0),
            }
        )
    return out


def create_department(db: Session, data, operator=None, request=None) -> Department:
    d = Department(department_name=data.department_name, parent_id=data.parent_id)
    db.add(d)
    db.flush()
    write_log(db, operator.id if operator else None, "DEPT_CREATE", "DEPARTMENT", d.id, f"新增部门 {d.department_name}", request)
    db.commit()
    return d


def update_department(db: Session, dept_id: int, data, operator=None, request=None) -> Department:
    d = db.get(Department, dept_id)
    if d is None:
        raise BizError("部门不存在", 40401)
    if data.parent_id == dept_id:
        raise BizError("上级部门不能是自己")
    if data.department_name:
        d.department_name = data.department_name
    if data.parent_id is not None:
        d.parent_id = data.parent_id
    write_log(db, operator.id if operator else None, "DEPT_UPDATE", "DEPARTMENT", d.id, f"修改部门 {d.department_name}", request)
    db.commit()
    return d


def delete_department(db: Session, dept_id: int, operator=None, request=None) -> None:
    d = db.get(Department, dept_id)
    if d is None:
        raise BizError("部门不存在", 40401)
    if db.scalar(select(func.count()).select_from(User).where(User.department_id == dept_id)):
        raise BizError("部门下还有用户，不能删除")
    if db.scalar(select(func.count()).select_from(Department).where(Department.parent_id == dept_id)):
        raise BizError("请先删除下级部门")
    db.delete(d)
    write_log(db, operator.id if operator else None, "DEPT_DELETE", "DEPARTMENT", dept_id, f"删除部门 {d.department_name}", request)
    db.commit()


# ---------------- 资产分类 ----------------
def list_categories(db: Session) -> list[dict]:
    cnt = dict(db.execute(select(Asset.category_id, func.count()).group_by(Asset.category_id)).all())
    return [
        {
            "id": c.id,
            "category_name": c.category_name,
            "category_code": c.category_code,
            "description": c.description,
            "asset_count": cnt.get(c.id, 0),
        }
        for c in db.scalars(select(AssetCategory).order_by(AssetCategory.id))
    ]


def create_category(db: Session, data, operator=None, request=None) -> AssetCategory:
    if db.scalar(select(func.count()).select_from(AssetCategory).where(AssetCategory.category_code == data.category_code)):
        raise BizError("分类编码已存在")
    c = AssetCategory(**data.model_dump())
    db.add(c)
    db.flush()
    write_log(db, operator.id if operator else None, "CATEGORY_CREATE", "CATEGORY", c.id, f"新增分类 {c.category_name}", request)
    db.commit()
    return c


def update_category(db: Session, category_id: int, data, operator=None, request=None) -> AssetCategory:
    c = db.get(AssetCategory, category_id)
    if c is None:
        raise BizError("分类不存在", 40401)
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    write_log(db, operator.id if operator else None, "CATEGORY_UPDATE", "CATEGORY", c.id, f"修改分类 {c.category_name}", request)
    db.commit()
    return c


def delete_category(db: Session, category_id: int, operator=None, request=None) -> None:
    c = db.get(AssetCategory, category_id)
    if c is None:
        raise BizError("分类不存在", 40401)
    if db.scalar(select(func.count()).select_from(Asset).where(Asset.category_id == category_id)):
        raise BizError("该分类下还有资产，不能删除")
    db.delete(c)
    write_log(db, operator.id if operator else None, "CATEGORY_DELETE", "CATEGORY", category_id, f"删除分类 {c.category_name}", request)
    db.commit()
