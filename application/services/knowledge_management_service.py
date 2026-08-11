"""知识库管理服务模块.

提供知识库文献的查询、删除和跨数据源（PostgreSQL + ChromaDB）统计聚合功能。

Classes:
    KnowledgeManagementService: 知识库文献查询与统计服务.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from infrastructure.utils.config_handler import chroma_conf, rag_conf
from infrastructure.utils.logger_handler import get_logger
from infrastructure.utils.path_tool import get_abs_path
from schemas.knowledge import KnowledgeStatsData, VectorStoreInfo
from schemas.pubmed import (
    ArticleDetailData,
    ArticleListData,
    ArticleSummary,
    DeleteResultData,
)

if TYPE_CHECKING:
    from infrastructure.persistence.postgres_db import PostgresDB
    from infrastructure.persistence.pubmed_ingester import PubMedArticleIngester
    from infrastructure.persistence.vector_store import VectorStoreService

logger = get_logger(name="knowledge_mgmt")

# ── 参数白名单（防御性校验） ─────────────────────────────────
_ALLOWED_STATUS: set[str] = {"all", "ingested", "uningested", "failed"}
_ALLOWED_SORT: set[str] = {"created_at", "updated_at", "pmid"}
_ALLOWED_ORDER: set[str] = {"asc", "desc"}


class KnowledgeManagementService:
    """知识库文献查询与统计，跨 PostgreSQL + ChromaDB 聚合.

    对外暴露:
        list_articles()        — 分页浏览本地 PubMed 文献
        get_article_detail()   — 获取单篇文献完整详情
        delete_article()       — 级联删除文献 (PG + ChromaDB)
        get_knowledge_stats()  — 跨数据源聚合统计

    Args:
        postgres_db: PostgresDB 实例
        vector_store_service: VectorStoreService 实例
        pubmed_ingester: PubMedArticleIngester 实例
    """

    def __init__(
        self,
        postgres_db: PostgresDB,
        vector_store_service: VectorStoreService,
        pubmed_ingester: PubMedArticleIngester,
    ) -> None:
        """初始化知识库管理服务.

        Args:
            postgres_db: PostgreSQL 数据库访问实例.
            vector_store_service: ChromaDB 向量存储实例.
            pubmed_ingester: PubMed 文章向量化实例.
        """
        self._db = postgres_db
        self._vs = vector_store_service
        self._ingester = pubmed_ingester

    # ------------------------------------------------------------------
    # list_articles
    # ------------------------------------------------------------------

    def list_articles(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        ingestion_status: str = "all",
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> ArticleListData:
        """分页查询本地 PubMed 文献.

        内部委托 PostgresDB.list_articles() 执行 SQL 查询.
        search 参数使用 ILIKE 模糊匹配 title 和 abstract.

        Args:
            page: 页码，必须 >= 1.
            page_size: 每页条数，范围 1-100.
            search: 搜索关键词，在标题和摘要中 ILIKE 模糊匹配.
            ingestion_status: 过滤状态，可选 all / ingested / uningested / failed.
            sort_by: 排序字段，可选 created_at / updated_at / pmid.
            order: 排序方向，可选 asc / desc.

        Returns:
            ArticleListData 包含分页信息和当前页文献摘要列表.

        Raises:
            ValueError: 参数校验不通过.
        """
        # ── 防御性参数校验 ──
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")
        if ingestion_status not in _ALLOWED_STATUS:
            raise ValueError(f"invalid ingestion_status: {ingestion_status}")
        if sort_by not in _ALLOWED_SORT:
            raise ValueError(f"invalid sort_by: {sort_by}")
        if order not in _ALLOWED_ORDER:
            raise ValueError(f"invalid order: {order}")

        logger.debug(
            "list_articles query: page=%d, page_size=%d, search=%s, "
            "status=%s, sort_by=%s, order=%s",
            page,
            page_size,
            search,
            ingestion_status,
            sort_by,
            order,
        )

        # ── 委托 DB 层查询 ──
        rows, total = self._db.list_articles(
            page=page,
            page_size=page_size,
            search=search,
            ingestion_status=ingestion_status,
            sort_by=sort_by,
            order=order,
        )

        # ── 将原始 dict 转换为 ArticleSummary ──
        articles: list[ArticleSummary] = []
        for row in rows:
            info = row.get("article_info") or {}
            abstract = info.get("abstract", "")
            abstract_preview = (
                abstract[:200] if abstract else ""
            )
            title = info.get("title", "")

            # authors 可能存储在 article_info 内，也可能在顶层
            authors = info.get("authors", row.get("authors", []))

            articles.append(
                ArticleSummary(
                    pmid=row["pmid"],
                    title=title,
                    authors=authors if authors else [],
                    journal=info.get("journal", ""),
                    publish_date=info.get("publish_date", ""),
                    abstract_preview=abstract_preview,
                    is_free_download=row.get("is_free_download", False),
                    ingestion_status=row.get("ingestion_status", "uningested"),
                    ingested_at=row.get("ingested_at"),
                    study_groups=row.get("study_groups", []),
                    created_at=row.get("created_at"),
                )
            )

        return ArticleListData(
            total=total,
            page=page,
            page_size=page_size,
            articles=articles,
        )

    # ------------------------------------------------------------------
    # get_article_detail
    # ------------------------------------------------------------------

    def get_article_detail(self, pmid: str) -> ArticleDetailData | None:
        """获取单篇文献完整详情.

        直接从 PostgreSQL 获取 JSONB 全量数据.
        PMID 不存在时返回 None（由调用方 Router 转为 404）.

        Args:
            pmid: PubMed 唯一标识符.

        Returns:
            ArticleDetailData 文献完整详情，PMID 不存在时返回 None.
        """
        row = self._db.get_article_by_pmid(pmid)
        if row is None:
            return None

        return ArticleDetailData(
            pmid=row["pmid"],
            article_info=row.get("article_info") or {},
            study_groups=row.get("study_groups") or [],
            results_info=row.get("results_info") or {},
            objectives=row.get("objectives") or "",
            is_free_download=row.get("is_free_download") or False,
            ingestion_status=row.get("ingestion_status") or "uningested",
            chunk_count=row.get("chunk_count"),
            vector_ids=row.get("vector_ids"),
            ingested_at=row.get("ingested_at"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            search_query=row.get("search_query"),
            ingestion_error=row.get("ingestion_error"),
        )

    # ------------------------------------------------------------------
    # delete_article
    # ------------------------------------------------------------------

    def delete_article(self, pmid: str) -> DeleteResultData:
        """级联删除文献：先 ChromaDB 向量，再 PostgreSQL 记录.

        容错设计：两步操作各自独立 try/except，即使一步失败也继续执行另一步.

        Args:
            pmid: PubMed 唯一标识符.

        Returns:
            DeleteResultData 包含 PG 和 ChromaDB 两端的删除结果.
        """
        deleted_vector: bool = False
        deleted_pg: bool = False

        # Step 1: 删除 ChromaDB 中的向量块
        try:
            n = self._ingester.remove_from_vector_store(pmid)
            deleted_vector = n > 0
            logger.info(
                "Deleted %d vector chunks for PMID %s", n, pmid
            )
        except Exception as e:
            logger.error(
                "Failed to delete vectors for PMID %s: %s", pmid, e
            )

        # Step 2: 删除 PostgreSQL 中的文献记录
        try:
            deleted_pg = self._db.delete_article(pmid)
            logger.info(
                "Deleted PG record for PMID %s: %s", pmid, deleted_pg
            )
        except Exception as e:
            logger.error(
                "Failed to delete PG record for PMID %s: %s", pmid, e
            )

        return DeleteResultData(
            pmid=pmid,
            deleted_pg=deleted_pg,
            deleted_vector=deleted_vector,
        )

    # ------------------------------------------------------------------
    # get_knowledge_stats
    # ------------------------------------------------------------------

    def get_knowledge_stats(self) -> KnowledgeStatsData:
        """跨数据源聚合统计.

        数据来源:
            - PostgreSQL: 文献总数、已索引数、未索引数
            - ChromaDB: 总 chunk 数、按 source_type 分组统计
            - 本地文件: ./data/ 目录中文档数

        Returns:
            KnowledgeStatsData 知识库统计概览.
        """
        # 1. PostgreSQL 统计
        status_counts = self._db.count_articles_by_status()
        # 返回格式如 {"total": 47, "ingested": 42, "uningested": 5, "failed": 0}

        # 2. ChromaDB 统计
        vs_stats = self._vs.get_collection_stats()
        # 返回格式示例: {"total_chunks": N, "by_source_type": {...}}

        # 3. 本地文档数
        local_count = self._get_local_document_count()

        # 4. 向量存储信息
        vs_info = VectorStoreInfo(
            collection_name=chroma_conf["collection_name"],
            storage_path=chroma_conf["persist_directory"],
            embedding_model=rag_conf["embedding_model_name"],
        )

        return KnowledgeStatsData(
            local_documents=local_count,
            pubmed_articles_total=status_counts.get("total", 0),
            pubmed_articles_ingested=status_counts.get("ingested", 0),
            pubmed_articles_uningested=status_counts.get("uningested", 0),
            total_vector_chunks=vs_stats.get("total_chunks", 0),
            by_source_type=vs_stats.get("by_source_type", {}),
            vector_store=vs_info,
        )

    # ------------------------------------------------------------------
    # _get_local_document_count
    # ------------------------------------------------------------------

    def _get_local_document_count(self) -> int:
        """统计 ./data/ 目录中允许扩展名的文件数量.

        扫描 chroma_conf["data_path"] 目录，
        统计其扩展名在 chroma_conf["allow_knowledge_file_type"] 中的文件数量。
        目录不存在时返回 0。

        Returns:
            本地文档数量.
        """
        data_path = get_abs_path(chroma_conf["data_path"])
        if not os.path.isdir(data_path):
            logger.warning(
                "Local document directory does not exist: %s", data_path
            )
            return 0

        allowed_exts: list[str] = chroma_conf.get(
            "allow_knowledge_file_type", []
        )
        count = 0
        for f in os.listdir(data_path):
            ext = f.rsplit(".", 1)[-1] if "." in f else ""
            if ext in allowed_exts:
                count += 1
        return count
