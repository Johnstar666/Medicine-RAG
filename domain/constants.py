"""domain/constants.py --- 全局枚举与错误码.

项目: Medicine_RAG_Project
日期: 2026-08-11
用途: 定义项目中所有模块共用的枚举类型，包括摄入状态、错误码、
      摄入结果状态和搜索条目状态。
"""

from enum import Enum


class IngestionStatus(str, Enum):
    """PubMed 文献向量索引状态。

    与数据库 pubmed_articles.ingestion_status 字段的可选值完全一致:
        - uningested: 未索引
        - ingesting:  索引中
        - ingested:   已索引
        - failed:     索引失败
    """

    UNINGESTED = "uningested"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    FAILED = "failed"


class ErrorCode(int, Enum):
    """业务错误码。与 HTTP 状态码配合使用，放在 ApiResponse.code 中。

    约定:
        - 200-299: 成功
        - 400-499: 客户端错误
        - 500-599: 服务端错误
        - 1000-1999: 业务逻辑错误（用于 HTTP 200 下的部分失败）

    注: 部分成员共享相同的整数值（如 INTERNAL_ERROR 和
    SERVICE_NOT_INITIALIZED 均为 500），这在 Python Enum 中自动成为别名，
    符合语义（均映射到 HTTP 500）。
    """

    # 成功
    SUCCESS = 200

    # 客户端错误 (400-499)
    BAD_REQUEST = 400
    PMID_NOT_FOUND = 404

    # 服务端错误 (500-599)
    INTERNAL_ERROR = 500
    SERVICE_NOT_INITIALIZED = 500
    PUBMED_API_UNAVAILABLE = 503
    PG_UNAVAILABLE = 503
    CHROMADB_UNAVAILABLE = 503

    # 业务级部分失败 (1000+)
    INGESTION_PARTIAL_FAILURE = 1001
    SEARCH_PARTIAL_FAILURE = 1002


class IngestResultStatus(str, Enum):
    """单篇摄入操作的结果状态。

    用于 PubMedArticleIngester.ingest_article() 返回值中的 status 字段:
        - ingested:         本次摄入成功
        - already_ingested: 文献已索引（幂等，跳过）
        - failed:           摄入失败
    """

    INGESTED = "ingested"
    ALREADY_INGESTED = "already_ingested"
    FAILED = "failed"


class SearchItemStatus(str, Enum):
    """单篇文献搜索入库结果状态。

    用于 PubMedSearchAppService.search_and_store() 返回的 details 列表中
    每条 SearchResultItem 的 status 字段:
        - ingested: 入库并索引成功
        - stored:   仅入库（auto_ingest=false 时）
        - skipped:  PMID 已存在，跳过
        - failed:   入库或索引失败
    """

    INGESTED = "ingested"
    STORED = "stored"
    SKIPPED = "skipped"
    FAILED = "failed"


def _run_self_test() -> None:
    """自测: 遍历每个枚举的成员并打印 name/value，确认所有值正确。"""
    print("=== IngestionStatus ===")
    for status in IngestionStatus:
        print(f"  {status.name:<15} = {status.value!r}")

    print("\n=== ErrorCode ===")
    for code in ErrorCode:
        print(f"  {code.name:<30} = {code.value}")

    print("\n=== IngestResultStatus ===")
    for result in IngestResultStatus:
        print(f"  {result.name:<20} = {result.value!r}")

    print("\n=== SearchItemStatus ===")
    for item in SearchItemStatus:
        print(f"  {item.name:<12} = {item.value!r}")


if __name__ == "__main__":
    _run_self_test()
