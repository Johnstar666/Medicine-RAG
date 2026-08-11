"""
PubMed 文献搜索 → 入库的独立管线。

功能: 搜索 PubMed → 逐 PMID 查重 → 提取详情 → 插入 PostgreSQL。

用法:
  from pubmed.paper_search import PubMedSearchPipeline
  pipeline = PubMedSearchPipeline()
  results = pipeline.run("COVID-19 mRNA vaccine", max_results=10)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.persistence.postgres_db import PostgresDB
from infrastructure.utils.config_handler import pubmed_conf
from infrastructure.utils.logger_handler import get_logger
from pubmed.pubmed_retriever import PubMedRetriever

logger = get_logger(name="pubmed_pipeline")


class PubMedSearchPipeline:
    """PubMed 搜索入库管线（独立于 API 服务，可命令行运行）。

    与 PubMedSearchAppService 的关系:
        - PubMedSearchPipeline: 纯搜索+入库，不含向量索引
        - PubMedSearchAppService: 搜索+入库+索引的完整编排，供 API 使用

    管道在内部调用 PostgresDB 的上下文管理器管理连接生命周期。
    """

    def __init__(self) -> None:
        """初始化 PubMedSearchPipeline。

        创建 PubMedRetriever 实例用于后续搜索和文献详情获取。
        """
        self._retriever = PubMedRetriever()

    def run(self, query: str, max_results: int | None = None) -> list[dict]:
        """执行搜索入库管线。

        Args:
            query: PubMed 查询词。
            max_results: 最大结果数，默认从 pubmed_conf 配置读取。

        Returns:
            list of dict: 每条文献的处理结果。
                每项格式: {"pmid": str, "status": str, "title": str}
                status 取值: "inserted" | "skipped" | "failed"
        """
        if max_results is None:
            max_results = pubmed_conf.get("max_results", 5)

        results: list[dict] = []

        logger.info(
            "Starting PubMed search pipeline: query='%s', max_results=%d",
            query,
            max_results,
        )

        with PostgresDB() as db:
            # Step 1: 搜索 PubMed → PMID 列表
            pmids: list[str] = self._retriever.search_pubmed(query)
            if not pmids:
                logger.info("No PMIDs found for query '%s'", query)
                return results

            logger.info("Found %d PMIDs for query '%s'", len(pmids), query)

            # Step 2: 遍历 PMID，查重 → fetch → insert
            inserted_count = 0
            skipped_count = 0
            failed_count = 0
            for pmid in pmids:
                result: dict = {"pmid": pmid, "status": "unknown", "title": ""}
                try:
                    if db.is_pmid_exist(pmid):
                        result["status"] = "skipped"
                        result["reason"] = "already_exists"
                        skipped_count += 1
                        logger.info("PMID %s already exists, skipped", pmid)
                        results.append(result)
                        continue

                    article_data: dict = self._retriever.fetch_article_details(pmid)
                    article_data["search_query"] = query
                    db.insert_article(article_data)

                    result["status"] = "inserted"
                    title = article_data.get("article_info", {}).get("title", "")
                    result["title"] = title
                    inserted_count += 1
                    logger.info(
                        "PMID %s inserted successfully: '%s'", pmid, title
                    )
                except Exception as e:
                    logger.error("Failed to process PMID %s: %s", pmid, e)
                    result["status"] = "failed"
                    result["reason"] = str(e)
                    failed_count += 1

                results.append(result)

            logger.info(
                "Pipeline finished: inserted=%d, skipped=%d, failed=%d, total=%d",
                inserted_count, skipped_count, failed_count, len(pmids),
            )

        return results


if __name__ == "__main__":
    test_query = "heart"
    pipeline = PubMedSearchPipeline()
    results = pipeline.run(test_query)
    for r in results:
        print(f"PMID: {r['pmid']}, Status: {r['status']}")
