"""PubMed 文章向量化模块.

将 PostgreSQL 中的 PubMed 文章数据转换为结构化文本，经分块处理后写入
ChromaDB 向量存储。提供单篇索引、批量索引、全量索引和向量清理功能。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.documents import Document as LangchainDocument

from infrastructure.utils.logger_handler import get_logger

logger = get_logger(name="pubmed_ingester")


@dataclass
class IngestResult:
    """单篇摄入结果.

    Attributes:
        pmid: PubMed 唯一标识符
        status: 结果状态 ("ingested" | "already_ingested" | "failed")
        chunk_count: 生成的 chunk 数量
        reason: 失败原因（成功时为空字符串）
        vector_ids: ChromaDB 分配的 chunk ID 列表
    """

    pmid: str
    status: str
    chunk_count: int = 0
    reason: str = ""
    vector_ids: list[str] = field(default_factory=list)


class PubMedArticleIngester:
    """PubMed 文章 -> 结构化文本 -> 分块 -> ChromaDB 向量索引.

    核心管线:
        1. 从 PG 获取 JSONB 文章数据
        2. _build_article_text() 按模板拼接结构化文本
        3. RecursiveCharacterTextSplitter 分块
        4. 为每个 chunk 构建 metadata（含 source_type="pubmed"）
        5. VectorStoreService.add_documents_direct() 写入 ChromaDB
        6. 更新 PG ingestion_status
    """

    def __init__(self, postgres_db, vector_store_service) -> None:
        """初始化 Ingester.

        Args:
            postgres_db: PostgresDB 实例
            vector_store_service: VectorStoreService 实例
        """
        self._db = postgres_db
        self._vs = vector_store_service

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def ingest_article(self, pmid: str, force: bool = False) -> IngestResult:
        """将单篇 PubMed 文章向量化并写入 ChromaDB.

        幂等性:
            - 已 ingested + force=False -> 直接返回 (status="already_ingested")
            - 已 ingested + force=True  -> 先删旧 chunks 再重索引

        Args:
            pmid: PubMed 唯一标识符
            force: 是否强制重索引（覆盖已有向量）

        Returns:
            IngestResult 包含状态、chunk 数量、失败原因和向量 ID。
        """
        try:
            # Step 1: 从 PG 获取文章
            article = self._db.get_article_by_pmid(pmid)
            if article is None:
                return IngestResult(
                    pmid,
                    "failed",
                    reason=f"PMID {pmid} not found in database",
                )

            current_status = article.get("ingestion_status", "uningested")

            # Step 2: 幂等检查 —— 已索引且非强制，直接返回
            if current_status == "ingested" and not force:
                return IngestResult(
                    pmid,
                    "already_ingested",
                    chunk_count=article.get("chunk_count") or 0,
                )

            # Step 3: force=True 时先清理旧向量
            if force and current_status == "ingested":
                self.remove_from_vector_store(pmid)

            # Step 4: 标记为 ingesting
            self._db.update_ingestion_status(pmid, "ingesting")

            # Step 5: 构建结构化文本
            article_text = self._build_article_text(article)
            if not article_text or not article_text.strip():
                self._db.update_ingestion_status(
                    pmid,
                    "failed",
                    error="Empty article text after building template",
                )
                return IngestResult(
                    pmid, "failed", reason="Empty article text"
                )

            # Step 6: 分块
            splitter = self._vs.get_splitter(source_type="pubmed")
            chunks = splitter.split_text(article_text)
            if not chunks:
                self._db.update_ingestion_status(
                    pmid, "failed", error="No chunks produced"
                )
                return IngestResult(
                    pmid, "failed", reason="No chunks produced"
                )

            # Step 7: 为每个 chunk 构建 LangchainDocument + metadata
            langchain_docs: list[LangchainDocument] = []
            for i, chunk_text in enumerate(chunks):
                metadata = self._build_chunk_metadata(
                    article, i, len(chunks)
                )
                langchain_docs.append(
                    LangchainDocument(
                        page_content=chunk_text, metadata=metadata
                    )
                )

            # Step 8: 写入 ChromaDB
            vector_ids = self._vs.add_documents_direct(langchain_docs)

            # Step 9: 更新状态为 ingested
            self._db.update_ingestion_status(
                pmid,
                "ingested",
                chunk_count=len(chunks),
                vector_ids=vector_ids,
            )

            logger.info(
                "文献索引成功 (pmid=%s, chunks=%d)", pmid, len(chunks)
            )
            return IngestResult(
                pmid,
                "ingested",
                chunk_count=len(chunks),
                vector_ids=vector_ids,
            )

        except Exception as e:
            logger.error(
                "文献索引失败 (pmid=%s): %s", pmid, e, exc_info=True
            )
            # 尝试将状态标记为 failed
            try:
                self._db.update_ingestion_status(
                    pmid, "failed", error=str(e)
                )
            except Exception as db_err:
                logger.error(
                    "更新失败状态时再次出错 (pmid=%s): %s",
                    pmid,
                    db_err,
                )
            return IngestResult(pmid, "failed", reason=str(e))

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _build_article_text(self, article: dict[str, Any]) -> str:
        """将 PostgreSQL JSONB 文章数据按模板拼接为结构化文本.

        模板:
            [PubMed Article]
            Title: {title}
            Authors: {authors}
            Journal: {journal}
            Publication Date: {date}
            DOI: {doi}
            PMID: {pmid}

            Research Objectives:
            {objectives}

            Study Groups:
            {study_groups}

            Key Results:
            {results_summary}

            Abstract:
            {abstract}

        Args:
            article: PG 返回的文章 dict (RealDictRow 或普通 dict).

        Returns:
            结构化文本字符串，可能为空字符串。
        """
        info = article.get("article_info") or {}
        title = info.get("title", "")
        authors_list = info.get("authors", [])
        authors_str = ", ".join(authors_list) if authors_list else "N/A"
        journal = info.get("journal", "")
        pub_date = info.get("publish_date", "")
        doi = info.get("doi", "")
        abstract = info.get("abstract", "")

        objectives = article.get("objectives") or ""
        study_groups = article.get("study_groups") or []
        groups_str = ", ".join(study_groups) if study_groups else "N/A"

        results_info = article.get("results_info") or {}
        results_summary = results_info.get("raw_abstract", "")

        text = f"""[PubMed Article]
Title: {title}
Authors: {authors_str}
Journal: {journal}
Publication Date: {pub_date}
DOI: {doi}
PMID: {article.get('pmid', '')}

Research Objectives:
{objectives}

Study Groups:
{groups_str}

Key Results:
{results_summary}

Abstract:
{abstract}"""

        return text.strip()

    def _build_chunk_metadata(
        self,
        article: dict[str, Any],
        chunk_index: int,
        total_chunks: int,
    ) -> dict[str, Any]:
        """为单个 chunk 构建 ChromaDB metadata.

        metadata 字段（与概要设计 5.6 一致）:
            source, source_type, pmid, title, authors,
            journal, publish_date, doi, is_free_download,
            chunk_index, total_chunks

        Args:
            article: PG 返回的文章 dict.
            chunk_index: 当前 chunk 索引 (从 0 开始).
            total_chunks: 总 chunk 数.

        Returns:
            metadata 字典。
        """
        info = article.get("article_info") or {}
        title = info.get("title", "")
        authors_list: list[str] = info.get("authors", [])
        # 最多 5 位作者 + et al.
        authors_str = ", ".join(authors_list[:5])
        if len(authors_list) > 5:
            authors_str += ", et al."

        pmid = article.get("pmid", "")

        return {
            "source": f"PMID:{pmid}: {title[:80]}",
            "source_type": "pubmed",
            "pmid": pmid,
            "title": title,
            "authors": authors_str,
            "journal": info.get("journal", ""),
            "publish_date": info.get("publish_date", ""),
            "doi": info.get("doi", ""),
            "is_free_download": article.get("is_free_download", False),
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
        }

    # ------------------------------------------------------------------
    # 批量方法
    # ------------------------------------------------------------------

    def batch_ingest(
        self, pmids: list[str], force: bool = False
    ) -> list[IngestResult]:
        """批量索引.

        逐篇调用 ingest_article()，单篇失败不影响其他篇。

        Args:
            pmids: 要索引的 PMID 列表。
            force: 是否强制重索引。

        Returns:
            每篇的 IngestResult 列表。
        """
        results: list[IngestResult] = []
        for pmid in pmids:
            result = self.ingest_article(pmid, force=force)
            results.append(result)
            logger.debug(
                "Batch ingest progress: %s -> %s", pmid, result.status
            )
        return results

    def ingest_all_uningested(
        self, force: bool = False
    ) -> list[IngestResult]:
        """索引所有 ingestion_status 为 'uningested' 或 'failed' 的文献.

        内部调用 PostgresDB.list_articles() 获取列表，
        然后逐篇调用 ingest_article()。

        Args:
            force: 是否强制重索引。

        Returns:
            每篇的 IngestResult 列表。
        """
        rows, _total = self._db.list_articles(
            page=1, page_size=9999, ingestion_status="uningested"
        )
        pmids: list[str] = [row["pmid"] for row in rows]

        # 同时包含 failed 的文章
        failed_rows, _ = self._db.list_articles(
            page=1, page_size=9999, ingestion_status="failed"
        )
        pmids.extend([row["pmid"] for row in failed_rows])

        logger.info(
            "开始全量索引: %d 篇待处理 (uningested + failed)", len(pmids)
        )
        return self.batch_ingest(pmids, force=force)

    # ------------------------------------------------------------------
    # 删除方法
    # ------------------------------------------------------------------

    def remove_from_vector_store(self, pmid: str) -> int:
        """从 ChromaDB 中删除指定 PMID 的所有向量块.

        Args:
            pmid: PubMed 唯一标识符。

        Returns:
            实际删除的 chunk 数量。
        """
        try:
            n = self._vs.delete_by_metadata_filter({"pmid": pmid})
            logger.info(
                "从向量存储中删除 PMID %s: %d 个 chunks", pmid, n
            )
            return n
        except Exception as e:
            logger.error("删除向量块失败 (pmid=%s): %s", pmid, e)
            raise
