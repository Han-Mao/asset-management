# IT资产全生命周期管理系统

按 `doc/` 下的三份设计文档（项目设计 / 数据库设计 / 项目设计2）实现的完整项目：
**FastAPI + SQLAlchemy 2 + Alembic + JWT/RBAC + Vue3 + Element Plus + ECharts**。

核心业务闭环：

```
用户登录 → 查看资产 → 申请领用 → 管理员审批 → 资产变「已领用」+ 生成领用记录
        → 到期提醒（30/7/1天/逾期）→ 归还 / 维修 → 重新入库 → 报废
```

## 快速开始

### 本地跑（零外部依赖，SQLite）

```bash
# 1. 后端：装依赖 + 建库 + 灌 Demo 数据（150 台资产，覆盖各种状态与到期场景）
cd backend
pip install -r requirements.txt
python -m app.seed            # 幂等；要清库重建加 --reset
uvicorn app.main:app --reload # http://127.0.0.1:8000/docs

# 2. 前端
cd ../frontend
npm install
npm run dev                   # http://127.0.0.1:5173
```

### Docker 跑（PostgreSQL）

```bash
cd deploy && docker compose up --build
# 前端 http://localhost:8080 ，后端 http://localhost:8000/docs
```

### 演示账号（密码都是 `123456`）

| 账号 | 姓名 | 角色 | 能做什么 |
| --- | --- | --- | --- |
| admin | 管理员 | ADMIN | 全部：资产增删改、审批、维修处理、用户/角色/部门、统计、日志、导入导出 |
| zhangsan / lisi / wangwu | 张三/李四/王五 | USER | 看资产、申请领用、看自己的申请与设备、报修、看消息 |

### 5 分钟演示脚本

1. `zhangsan` 登录 → 资产管理 → 找一台「在库」设备 → **申请领用**（填原因/预计归还）
2. 退出，`admin` 登录 → 审批中心 → **通过**（也可以勾选多条**批量通过**）
3. 回 `zhangsan` → 我的设备：设备已到手，显示剩余天数；消息中心有「申请已通过」
4. 管理员首页 → **手动触发到期提醒**：普通用户收到 30/7/1 天与逾期提醒（站内信+邮件），管理员收到汇总
5. 资产详情 → **生命周期**时间轴：入库 → 申请 → 审批 → 领用 → 报修 → 归还
6. 资产管理 → 导出 Excel / 下载模板并导入（带错误行报告） / 打印二维码

## 已实现功能

| 模块 | 说明 |
| --- | --- |
| 认证与权限 | JWT 登录、`require_permission(...)` 依赖式 RBAC、角色-权限可在线分配 |
| 资产 | CRUD、按编号/名称/类型/状态/领用人/领用时间/应归还时间筛选分页、二维码、生命周期、删除保护、报废流转 |
| 领用 | 一申请一台资产、重复申请与不可用资产拦截、取消、我的申请 |
| 审批 | **单事务 + 行锁**：改申请状态、改资产状态、建领用记录、发站内信、写日志；批量审批 |
| 领用记录 | 历史领用关系、归还（可转待维修）、逾期自动置 `OVERDUE` |
| 维修 | 报修 → 接单 → 完成 / 取消，资产状态机联动，完成后按是否仍被领用决定回「已领用」还是「在库」 |
| 消息 | 站内信 + stdlib smtplib 异步邮件（SMTP 未配置时只记日志，演示不阻塞） |
| 到期提醒 | 进程内每日定时任务（30/7/1 天/逾期）+ 管理员手动触发接口；用「当天是否发过同类型通知」去重 |
| 统计 | 资产状态/类型/部门分布、月度领用趋势、申请状态分布、未来 30 天到期 |
| 系统管理 | 用户（启停、重置密码、分配角色）、角色权限、部门树、资产分类 |
| 其他 | Excel 导入（逐行校验 + 错误行报告）/ 导出、操作日志、统一响应体 |

## 目录结构

```
asset-management/
├── backend/
│   ├── app/
│   │   ├── api/            # 13 个 Router：auth/users/roles/departments/categories/assets/
│   │   │                   #   applications/assignments/repairs/notifications/dashboard/logs/system
│   │   ├── core/           # config/database/security/constants/deps/errors/response/schema
│   │   ├── models/         # 13 张表：system.py(8) + asset.py(2) + workflow.py(3)
│   │   ├── services/       # 业务逻辑（含审批事务、提醒任务、导入导出、统计）
│   │   ├── schemas.py      # Pydantic 出入参（数据库 Model 不直接当接口用）
│   │   ├── seed.py         # 建库 + Demo 数据
│   │   └── main.py
│   ├── alembic/            # 表结构唯一事实来源
│   └── tests/              # 34 个端到端用例（TestClient 打真实接口）
├── frontend/src/           # Vue3 + Element Plus + ECharts，13 个页面
└── deploy/                 # docker-compose(PG) + nginx + 前端镜像
```

## 设计要点（面试可讲）

- **资产状态只由业务动作驱动**：`AssetUpdate` 里根本没有 `status` 字段，前端传了也会被忽略；状态流转由 `ASSET_TRANSITIONS` 状态机在 Service 层校验。
- **`asset` 不存 `borrower_id`**：`asset` 只记当前状态，`asset_assignment` 记历史领用关系，资产详情页才能看到完整交接历史。
- **审批并发三层保障**：`SELECT ... FOR UPDATE` 锁资产行 + Service 校验 `IN_STOCK` + 数据库部分唯一索引 `uq_active_asset_assignment`（一台资产只能有一条 ACTIVE/OVERDUE 领用记录）。
- **申请阶段不锁库存**：申请不代表获得资产，抢占库存只发生在审批。
- **逾期不改资产状态**：`asset.status=BORROWED` 表示设备在别人手上，`assignment.status=OVERDUE` 表示领用关系逾期，两者语义分开，首页统计才能同时展示「已领用 75 / 逾期 19」。
- **不建的**：提醒记录表（查 `asset_assignment` 即可）、生命周期表（5 张表组合出来）、Dashboard 统计表（SQL 聚合）。

## 与设计文档的有意差异

为控制复杂度做了 4 处替换，功能等价：

| 文档方案 | 本项目 | 原因 |
| --- | --- | --- |
| Celery + Redis（定时 + 去重） | 进程内每日定时线程 + 查通知表去重 | 少两个中间件；多实例部署时再换 Celery Beat（已隔离在 `services/reminder.py`） |
| Repository / Service 双层 | 只保留 Service（直接 `select()`） | 查询没被 3 个以上模块复用，多一层只是搬运 |
| `models/` 10 个文件、`schemas/` 7 个文件 | `models/` 3 个文件、`schemas.py` 1 个文件 | 每个文件几十行，拆开只增加跳转成本 |
| 独立 `reminder` 表 / `asset_lifecycle` 表 | 不建 | 需求本身就是查询结果，不是业务实体 |

## 测试

```bash
cd backend && pytest -q     # 34 passed
```

覆盖：登录与禁用账号、RBAC 403、普通用户资产可见范围、资产 CRUD 与「status 不可改」、
条件筛选、删除保护、二维码、生命周期、报废流转、Excel 导入错误报告、完整领用审批事务、
重复审批、**两个用户申请同一台资产只有一个成功**、取消/驳回、归还（含转维修）、
维修全流程、消息中心、统计接口、到期提醒幂等。
