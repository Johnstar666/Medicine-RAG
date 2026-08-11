"""知识库路由模块.

提供知识库统计相关的 API 端点。

Endpoints:
    GET /knowledge/stats — 获取知识库总体统计概览

依赖注入:
    模块级 setter ``set_knowledge_management_service()`` 接收
    ``KnowledgeManagementService`` 实例，由 ``main.py`` 在启动时调用。
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from fastapi import APIRouter, HTTPException

from schemas.common import ApiResponse
from schemas.knowledge import KnowledgeStatsData

if TYPE_CHECKING:
    from application.services.knowledge_management_service import (
        KnowledgeManagementService,
    )

router = APIRouter(prefix="/knowledge")

# ── 模块级服务引用（由 main.py 在启动时注入） ─────────────────
knowledge_management_service: KnowledgeManagementService | None = None


def set_knowledge_management_service(
    service: KnowledgeManagementService,
) -> None:
    """注入知识库管理服务实例.

    由 ``main.py`` 在应用启动时从 ``ServiceFactory`` 获取服务并调用此函数。

    Args:
        service: ``KnowledgeManagementService`` 实例。
    """
    global knowledge_management_service
    knowledge_management_service = service


# ── GET /knowledge/stats ──────────────────────────────────────


@router.get("/stats")
async def get_knowledge_stats() -> ApiResponse:
    """获取知识库总体统计.

    跨 PostgreSQL + ChromaDB + 本地文件系统聚合统计数据，
    返回文献数量、向量块数量、按来源类型分组等信息。

    Returns:
        ``ApiResponse[KnowledgeStatsData]`` 包装的统计概览。

    Raises:
        HTTPException(500): 服务未初始化或内部错误。
    """
    import logging

    logger = logging.getLogger("knowledge_router")
    logger.info("Received knowledge stats request")

    if knowledge_management_service is None:
        raise HTTPException(
            status_code=500, detail="Knowledge management service not initialized"
        )

    try:
        result: KnowledgeStatsData = (
            knowledge_management_service.get_knowledge_stats()
        )
        logger.info(
            "Knowledge stats retrieved: %d local docs, %d pubmed articles, "
            "%d vector chunks",
            result.local_documents,
            result.pubmed_articles_total,
            result.total_vector_chunks,
        )
        return ApiResponse(code=200, message="success", data=result)
    except Exception as e:
        logger.exception("Failed to retrieve knowledge stats")
        raise HTTPException(status_code=500, detail=str(e)) from e
