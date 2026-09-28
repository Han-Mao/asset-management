from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class BizError(Exception):
    """业务异常：返回 HTTP 200 + 统一响应体里的非 0 code，前端直接弹 message。"""

    def __init__(self, message: str, code: int = 40001):
        self.message = message
        self.code = code
        super().__init__(message)


def envelope(data: Any = None, message: str = "success", code: int = 0) -> dict:
    return {"code": code, "message": message, "data": data}


def register_exception_handlers(app):
    @app.exception_handler(BizError)
    async def _biz(request: Request, exc: BizError):
        return JSONResponse(status_code=200, content=envelope(None, exc.message, exc.code))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:])
        msg = f"参数校验失败：{field} {first.get('msg', '')}".strip()
        return JSONResponse(status_code=200, content=envelope(None, msg, 40000))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        # 401/403 保留真实状态码，前端据此跳登录页
        return JSONResponse(
            status_code=exc.status_code, content=envelope(None, str(exc.detail), exc.status_code * 100)
        )
