"""PubMed 路由模块.

提供 PubMed 文献搜索、浏览、索引和删除的 REST API 端点。
所有端点通过模块级 setter 接收服务实例（由 main.py 在启动时注入）。

Endpoints:
    POST   /pubmed/search                — 触发 PubMed 搜索并入库
    GET    /pubmed/articles              — 分页浏览本地 PubMed 文献
    GET    /pubmed/articles/{pmid}       — 获取单篇文献完整详情
    POST   /pubmed/ingest/batch          — 批量索引指定 PMID 列表
    POST   /pubmed/ingest/all-uningested — 一键索引所有未入库文献
    POST   /pubmed/ingest/{pmid}         — 手动索引单篇文献
    DELETE /pubmed/articles/{pmid}       — 删除文献（PG + ChromaDB）
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from fastapi import APIRouter, HTTPException, Path, Query

from application.services.knowledge_management_service import (
    KnowledgeManagementService,
)
from application.services.pubmed_search_service import PubMedSearchAppService
from infrastructure.utils.logger_handler import get_logger
from schemas.common import ApiResponse
from schemas.pubmed import (
    DeleteResultData,
    IngestBatchData,
    IngestBatchRequest,
    IngestResultItem,
    PubMedSearchRequest,
)

logger = get_logger(name="pubmed_router")

# ── 模块级服务引用（由 main.py 在启动时注入） ─────────────────
pubmed_search_service: PubMedSearchAppService | None = None
knowledge_management_service: KnowledgeManagementService | None = None


def set_pubmed_search_service(service: PubMedSearchAppService) -> None:
    """注入 PubMed 搜索服务实例.

    Args:
        service: PubMedSearchAppService 实例.
    """
    global pubmed_search_service
    pubmed_search_service = service


def set_knowledge_management_service(service: KnowledgeManagementService) -> None:
    """注入知识库管理服务实例.

    Args:
        service: KnowledgeManagementService 实例.
    """
    global knowledge_management_service
    knowledge_management_service = service


router = APIRouter(prefix="/pubmed")

# ── 内部辅助 ──────────────────────────────────────────────────


def _check_pubmed_service() -> PubMedSearchAppService:
    """校验 pubmed_search_service 已注入，否则抛出 HTTP 500.

    Returns:
        PubMedSearchAppService 实例.

    Raises:
        HTTPException(500): 服务未初始化.
    """
    if pubmed_search_service is None:
        raise HTTPException(status_code=500, detail="Service not initialized")
    return pubmed_search_service


def _check_km_service() -> KnowledgeManagementService:
    """校验 knowledge_management_service 已注入，否则抛出 HTTP 500.

    Returns:
        KnowledgeManagementService 实例.

    Raises:
        HTTPException(500): 服务未初始化.
    """
    if knowledge_management_service is None:
        raise HTTPException(status_code=500, detail="Service not initialized")
    return knowledge_management_service


# ── POST /pubmed/search ────────────────────────────────────────


@router.post("/search")
async def search_pubmed(request: PubMedSearchRequest):
    """触发 PubMed 搜索，结果自动入库并（默认）向量索引.

    Args:
        request: 包含 query、max_results、auto_ingest 的请求体.

    Returns:
        ApiResponse[PubMedSearchData]

    Raises:
        HTTPException(500): 服务未初始化.
        HTTPException(503): PubMed API 暂时不可用.
    """
    service = _check_pubmed_service()

    logger.info(
        "PubMed search request: query='%s', max_results=%d",
        request.query,
        request.max_results,
    )

    try:
        result = service.search_and_store(
            query=request.query,
            max_results=request.max_results,
            auto_ingest=request.auto_ingest,
        )
    except RuntimeError as e:
        logger.error("PubMed search RuntimeError: %s", e)
        raise HTTPException(
            status_code=503,
            detail="PubMed API 暂时不可用，请稍后重试",
        ) from e
    except Exception as e:
        logger.exception("PubMed search unexpected error")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return ApiResponse(code=200, message="success", data=result)


# ── GET /pubmed/articles ───────────────────────────────────────


@router.get("/articles")
async def list_articles(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    search: str | None = Query(default=None, max_length=200, description="搜索关键词"),
    ingestion_status: str = Query(
        default="all",
        pattern=r"^(all|ingested|uningested|failed)$",
        description="过滤状态",
    ),
    sort_by: str = Query(
        default="created_at",
        pattern=r"^(created_at|updated_at|pmid)$",
        description="排序字段",
    ),
    order: str = Query(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="排序方向",
    ),
):
    """分页浏览/搜索本地 PubMed 文献库.

    Args:
        page: 页码，>= 1.
        page_size: 每页条数，1-100.
        search: 搜索关键词（标题/摘要 ILIKE 模糊匹配）.
        ingestion_status: 过滤状态 (all / ingested / uningested / failed).
        sort_by: 排序字段 (created_at / updated_at / pmid).
        order: 排序方向 (asc / desc).

    Returns:
        ApiResponse[ArticleListData]

    Raises:
        HTTPException(400): 参数非法.
        HTTPException(500): 服务端内部错误.
    """
    km = _check_km_service()

    try:
        result = km.list_articles(
            page=page,
            page_size=page_size,
            search=search,
            ingestion_status=ingestion_status,
            sort_by=sort_by,
            order=order,
        )
    except ValueError as e:
        logger.warning("list_articles ValueError: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("list_articles unexpected error")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return ApiResponse(code=200, message="success", data=result)


# ── GET /pubmed/articles/{pmid} ─────────────────────────────────


@router.get("/articles/{pmid}")
async def get_article_detail(
    pmid: str = Path(..., min_length=1, description="PubMed 唯一标识符"),
):
    """获取单篇文献完整详情.

    Args:
        pmid: PubMed 唯一标识符.

    Returns:
        ApiResponse[ArticleDetailData]

    Raises:
        HTTPException(404): PMID 不存在.
        HTTPException(500): 服务端内部错误.
    """
    km = _check_km_service()

    try:
        result = km.get_article_detail(pmid)
    except Exception as e:
        logger.exception("get_article_detail error for pmid=%s", pmid)
        raise HTTPException(status_code=500, detail=str(e)) from e

    if result is None:
        raise HTTPException(status_code=404, detail=f"PMID {pmid} not found")

    return ApiResponse(code=200, message="success", data=result)


# ── POST /pubmed/ingest/batch ─────────────────────────────────


@router.post("/ingest/batch")
async def ingest_batch(request: IngestBatchRequest):
    """批量索引指定 PMID 列表.

    Args:
        request: 包含 pmids 列表和 force 标志的请求体.

    Returns:
        ApiResponse[IngestBatchData]

    Raises:
        HTTPException(500): 服务未初始化或索引失败.
    """
    service = _check_pubmed_service()
    ingester = service._ingester

    try:
        results = ingester.batch_ingest(request.pmids, force=request.force)
    except Exception as e:
        logger.exception("ingest_batch error")
        raise HTTPException(status_code=500, detail=str(e)) from e

    details: list[IngestResultItem] = []
    ingested_count = 0
    failed_count = 0

    for r in results:
        details.append(
            IngestResultItem(
                pmid=r.pmid,
                status=r.status,
                chunk_count=r.chunk_count,
                reason=r.reason,
            )
        )
        if r.status in ("ingested", "already_ingested"):
            ingested_count += 1
        else:
            failed_count += 1

    data = IngestBatchData(
        total_uningested=len(results),
        ingested=ingested_count,
        failed=failed_count,
        details=details,
    )

    return ApiResponse(code=200, message="success", data=data)


# ── POST /pubmed/ingest/all-uningested ─────────────────────────


@router.post("/ingest/all-uningested")
async def ingest_all_uningested():
    """一键索引所有未入库文献.

    对 ingestion_status 为 uningested 或 failed 的文献执行向量索引.

    Returns:
        ApiResponse[IngestBatchData]

    Raises:
        HTTPException(500): 服务未初始化或索引失败.
    """
    service = _check_pubmed_service()

    try:
        result = service.ingest_all_uningested()
    except Exception as e:
        logger.exception("ingest_all_uningested error")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return ApiResponse(code=200, message="success", data=result)


# ── POST /pubmed/ingest/{pmid} ─────────────────────────────────


@router.post("/ingest/{pmid}")
async def ingest_single_article(
    pmid: str = Path(..., min_length=1, description="PubMed 唯一标识符"),
    force: bool = Query(default=False, description="是否强制重索引"),
):
    """手动触发单篇文献向量索引.

    Args:
        pmid: PubMed 唯一标识符.
        force: 是否强制重索引（覆盖已有向量）.

    Returns:
        ApiResponse[IngestBatchData] 包含单条 detail.

    Raises:
        HTTPException(500): 服务未初始化或索引失败.
    """
    service = _check_pubmed_service()
    ingester = service._ingester

    try:
        ingest_result = ingester.ingest_article(pmid, force=force)
    except Exception as e:
        logger.exception("ingest_single_article error for pmid=%s", pmid)
        raise HTTPException(status_code=500, detail=str(e)) from e

    detail = IngestResultItem(
        pmid=ingest_result.pmid,
        status=ingest_result.status,
        chunk_count=ingest_result.chunk_count,
        reason=ingest_result.reason,
    )

    ingested_count = (
        1 if ingest_result.status in ("ingested", "already_ingested") else 0
    )
    failed_count = 1 if ingest_result.status == "failed" else 0

    data = IngestBatchData(
        total_uningested=1,
        ingested=ingested_count,
        failed=failed_count,
        details=[detail],
    )

    return ApiResponse(code=200, message="success", data=data)


# ── DELETE /pubmed/articles/{pmid} ─────────────────────────────


@router.delete("/articles/{pmid}")
async def delete_article(
    pmid: str = Path(..., min_length=1, description="PubMed 唯一标识符"),
):
    """删除文献（PostgreSQL 记录 + ChromaDB 向量块）.

    Args:
        pmid: PubMed 唯一标识符.

    Returns:
        ApiResponse[DeleteResultData]

    Raises:
        HTTPException(404): PMID 在 PG 和 ChromaDB 中均不存在.
        HTTPException(500): 服务端内部错误.
    """
    km = _check_km_service()

    try:
        result: DeleteResultData = km.delete_article(pmid)
    except Exception as e:
        logger.exception("delete_article error for pmid=%s", pmid)
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not result.deleted_pg and not result.deleted_vector:
        raise HTTPException(
            status_code=404,
            detail="PMID not found in both PG and ChromaDB",
        )

    return ApiResponse(code=200, message="success", data=result)
