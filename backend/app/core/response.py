from functools import wraps

from fastapi import Response
from fastapi.routing import APIRoute

from .errors import envelope


class EnvelopeRoute(APIRoute):
    """统一把处理函数返回值包成 {code, message, data}；Response/文件流原样返回。"""

    def __init__(self, path, endpoint, **kwargs):
        kwargs.setdefault("response_model", None)

        @wraps(endpoint)
        def wrapped(*args, **kw):
            out = endpoint(*args, **kw)
            return out if isinstance(out, Response) else envelope(out)

        super().__init__(path, wrapped, **kwargs)
