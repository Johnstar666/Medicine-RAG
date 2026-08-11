"""通用 API 响应信封。

为所有 API 端点提供统一的外层响应结构，确保一致的接口返回格式。
各端点根据自身业务需求定义 data 字段的具体类型。
"""

from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一 API 响应信封。

    所有端点均通过此结构返回 JSON 响应，data 字段类型由各端点自行定义。

    Attributes:
        code: HTTP 状态码（如 200, 400, 404, 500, 503）。
        message: 人类可读的状态描述，成功时为 "success"，失败时为具体错误信息。
        data: 业务载荷数据，成功时填充对应模型，失败或无数据时为 None。

    使用约定:
        - 成功 (200): 填充 code=200, message="success", data=业务数据。
        - 资源不存在 (404): 填充 code=404, message="Resource not found", data=None。
        - 服务端错误 (500): 填充 code=500, message=错误详情, data=None。

    说明:
        原 ``schemas/rag_query.py`` 中的 ``ApiResponse`` 保留不动，
        新增代码统一使用本文件中的版本，避免修改已有路由。
    """

    code: int
    """HTTP 状态码。"""

    message: str
    """人类可读的状态描述。"""

    data: Any | None = None
    """业务载荷，可为任意 Pydantic 模型或 None。"""
