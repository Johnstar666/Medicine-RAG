"""PubMed 搜索服务。

PubMed 搜索 -> 逐篇入库 -> 可选自动索引的业务编排服务。
对外暴露 search_and_store() 和 ingest_all_uningested() 两个方法。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from domain.constants import SearchItemStatus
from infrastructure.utils.logger_handler import get_logger
from schemas.pubmed import (
    IngestBatchData,
    IngestResultItem,
    PubMedSearchData,
    SearchDetailItem,
)

logger = get_logger(name="pubmed_search")


@dataclass
class SearchResultItem:
    """单篇文献搜索入库结果（内部使用，最终转为 Pydantic SearchDetailItem）。"""

    pmid: str
    status: str  # "ingested" | "stored" | "skipped" | "failed"
    title: str = ""
    reason: str = ""


class PubMedSearchAppService:
    """PubMed 搜索 -> 入库 -> 索引 业务编排。

    对外暴露：
        search_and_store(query, max_results, auto_ingest) -> PubMedSearchData
        ingest_all_uningested(force) -> IngestBatchData
    """

    # 指数退避重试参数
    _SEARCH_RETRY_DELAYS: tuple[float, ...] = (3.0, 6.0, 12.0)

    def __init__(
        self,
        pubmed_retriever: Any,
        postgres_db: Any,
        pubmed_ingester: Any,
        request_interval: float = 0.15,
    ) -> None:
        """初始化 PubMed 搜索服务。

        Args:
            pubmed_retriever: PubMedRetriever 实例。
            postgres_db: PostgresDB 实例。
            pubmed_ingester: PubMedArticleIngester 实例。
            request_interval: NCBI API 请求间隔（秒）。
        """
        self._retriever = pubmed_retriever
        self._db = postgres_db
        self._ingester = pubmed_ingester
        self._interval = request_interval

    # ------------------------------------------------------------------
    # 核心方法: search_and_store
    # ------------------------------------------------------------------

    def search_and_store(
        self,
        query: str,
        max_results: int = 5,
        auto_ingest: bool = True,
    ) -> PubMedSearchData:
        """PubMed 搜索 -> 逐篇入库 -> 可选自动索引。

        执行流程：
        1. 调用 PubMedRetriever.search_pubmed(query) -> PMID 列表
        2. FOR EACH pmid:
             a. 若已存在 -> skip (status="skipped")
             b. 否则 fetch -> insert -> status="stored"
        3. 若 auto_ingest=True:
             FOR EACH 新入库的 pmid:
               ingest_article(pmid) -> status 更新为 "ingested" 或 "failed"
        4. 汇总统计 -> PubMedSearchData

        Args:
            query: PubMed 查询词。
            max_results: 最大返回条数 (1-30)。
            auto_ingest: 是否自动触发向量索引。

        Returns:
            PubMedSearchData: 聚合统计结果。
        """
        logger.info("Search started: query=%s, max_results=%d", query, max_results)

        # Step 1: PubMed 搜索（含指数退避重试）
        pmids = self._search_with_retry(query, max_results)

        # Step 2: PMID 列表为空时直接返回
        if not pmids:
            logger.info("Search returned empty PMID list for query: %s", query)
            return PubMedSearchData(
                query=query,
                pmids_found=0,
                pmids_new=0,
                pmids_ingested=0,
                pmids_skipped=0,
                pmids_failed=0,
                details=[],
            )

        # Step 3: 逐篇处理（单篇失败不中断整批）
        results: list[SearchResultItem] = []
        for pmid in pmids:
            time.sleep(self._interval)
            result = self._process_single_article(pmid)
            results.append(result)
            logger.info(
                "Article processed: pmid=%s, status=%s, title=%s",
                pmid,
                result.status,
                result.title[:60] if result.title else "",
            )

        # Step 4: 可选自动索引（对 status="stored" 的文献）
        if auto_ingest:
            for result in results:
                if result.status == SearchItemStatus.STORED:
                    time.sleep(self._interval)
                    self._ingest_single_article(result)

        # Step 5: 汇总统计
        details_pydantic = [
            SearchDetailItem(
                pmid=r.pmid,
                status=r.status,
                title=r.title,
                reason=r.reason,
            )
            for r in results
        ]

        pmids_new = sum(
            1
            for r in results
            if r.status in {
                SearchItemStatus.STORED,
                SearchItemStatus.INGESTED,
                SearchItemStatus.FAILED,
            }
        )
        pmids_ingested = sum(
            1 for r in results if r.status == SearchItemStatus.INGESTED
        )
        pmids_skipped = sum(
            1 for r in results if r.status == SearchItemStatus.SKIPPED
        )
        pmids_failed = sum(
            1 for r in results if r.status == SearchItemStatus.FAILED
        )

        logger.info(
            "Search completed: found=%d, new=%d, ingested=%d, skipped=%d, failed=%d",
            len(pmids),
            pmids_new,
            pmids_ingested,
            pmids_skipped,
            pmids_failed,
        )

        return PubMedSearchData(
            query=query,
            pmids_found=len(pmids),
            pmids_new=pmids_new,
            pmids_ingested=pmids_ingested,
            pmids_skipped=pmids_skipped,
            pmids_failed=pmids_failed,
            details=details_pydantic,
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _search_with_retry(self, query: str, max_results: int) -> list[str]:
        """带指数退避的 PubMed 搜索。

        重试 3 次，延迟分别为 3s / 6s / 12s。
        全部失败则向上抛出异常。

        Args:
            query: PubMed 查询词。
            max_results: 传递给 retriever 的最大结果数
                （由 retriever 内部 max_results 控制）。

        Returns:
            PMID 字符串列表。
        """
        # 注意：PubMedRetriever.search_pubmed 不接受 max_results 参数，
        # 其行为由自身 max_results 配置决定。此处保留参数供未来扩展。
        _ = max_results
        last_exc: Exception | None = None

        for attempt, delay in enumerate(self._SEARCH_RETRY_DELAYS, start=1):
            try:
                return self._retriever.search_pubmed(query)
            except Exception as e:
                last_exc = e
                logger.warning(
                    "PubMed search attempt %d failed: %s. Retrying in %.1fs...",
                    attempt,
                    e,
                    delay,
                )
                time.sleep(delay)

        # 全部重试都失败
        logger.error(
            "PubMed search failed after %d attempts",
            len(self._SEARCH_RETRY_DELAYS),
        )
        assert last_exc is not None
        raise last_exc

    def _process_single_article(self, pmid: str) -> SearchResultItem:
        """处理单篇文献：查重 -> fetch -> insert。

        Args:
            pmid: PubMed 唯一标识符。

        Returns:
            SearchResultItem: 处理结果（skipped / stored / failed）。
        """
        # Step 1: 查重
        try:
            if self._db.is_pmid_exist(pmid):
                return SearchResultItem(
                    pmid=pmid,
                    status=SearchItemStatus.SKIPPED,
                    reason="already_exists",
                )
        except Exception as e:
            return SearchResultItem(
                pmid=pmid,
                status=SearchItemStatus.FAILED,
                reason=f"dup_check error: {e}",
            )

        # Step 2: fetch
        try:
            article_data = self._retriever.fetch_article_details(pmid)
        except Exception as e:
            logger.warning("Fetch failed for pmid=%s: %s", pmid, e)
            return SearchResultItem(
                pmid=pmid,
                status=SearchItemStatus.FAILED,
                reason=str(e),
            )

        # Step 3: insert
        title = (
            article_data.get("article_info", {}).get("title", "")
            if isinstance(article_data, dict)
            else ""
        )
        try:
            self._db.insert_article(article_data)
        except Exception as e:
            logger.warning("Insert failed for pmid=%s: %s", pmid, e)
            return SearchResultItem(
                pmid=pmid,
                status=SearchItemStatus.FAILED,
                title=title,
                reason=str(e),
            )

        return SearchResultItem(
            pmid=pmid,
            status=SearchItemStatus.STORED,
            title=title,
        )

    def _ingest_single_article(self, result: SearchResultItem) -> None:
        """对单篇已入库文献执行向量索引。

        成功后更新 result.status 为 "ingested"，
        失败后更新 result.status 为 "failed" 并记录原因。

        Args:
            result: 待索引的 SearchResultItem（status 应为 "stored"）。
        """
        try:
            ingest_result = self._ingester.ingest_article(result.pmid)
            if ingest_result.status in ("ingested", "already_ingested"):
                result.status = SearchItemStatus.INGESTED
            else:
                result.status = SearchItemStatus.FAILED
                result.reason = ingest_result.reason
        except Exception as e:
            logger.warning("Ingest failed for pmid=%s: %s", result.pmid, e)
            result.status = SearchItemStatus.FAILED
            result.reason = str(e)

    # ------------------------------------------------------------------
    # 便捷方法: ingest_all_uningested
    # ------------------------------------------------------------------

    def ingest_all_uningested(self, force: bool = False) -> IngestBatchData:
        """索引所有未索引的文献（uningested + failed）。

        委托 PubMedArticleIngester.ingest_all_uningested() 执行，
        汇总结果后返回 IngestBatchData。

        Args:
            force: 是否强制重索引（覆盖已有向量）。

        Returns:
            IngestBatchData: 批量索引操作结果。
        """
        logger.info("Starting full ingestion: force=%s", force)

        results = self._ingester.ingest_all_uningested(force=force)
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

        total = len(results)
        logger.info(
            "Full ingestion completed: total=%d, ingested=%d, failed=%d",
            total,
            ingested_count,
            failed_count,
        )

        return IngestBatchData(
            total_uningested=total,
            ingested=ingested_count,
            failed=failed_count,
            details=details,
        )
