"""PubMed 接口 Pydantic Schema 定义。

定义 PubMed 搜索、文献管理、向量索引等所有请求/响应数据模型。

Models:
    PubMedSearchRequest: POST /pubmed/search 请求体
    SearchDetailItem:    单篇文献搜索结果明细
    PubMedSearchData:    POST /pubmed/search 响应 data
    ArticleSummary:      文献列表中的摘要项
    ArticleListData:     GET /pubmed/articles 响应 data
    ArticleDetailData:   GET /pubmed/articles/{pmid} 响应 data
    IngestResultItem:    单篇索引结果明细
    IngestBatchData:     批量索引响应 data
    DeleteResultData:    DELETE 响应 data
    IngestBatchRequest:  POST /pubmed/ingest/batch 请求体
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PubMedSearchRequest(BaseModel):
    """PubMed 搜索请求。

    Attributes:
        query: PubMed 查询词，支持 PubMed 高级检索语法。
        max_results: 最大返回文献数，范围 1-30。
        auto_ingest: 是否在入库后自动触发向量索引。
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="PubMed 查询词，支持 PubMed 高级检索语法",
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=30,
        description="最大返回文献数",
    )
    auto_ingest: bool = Field(
        default=True,
        description="是否在入库后自动触发向量索引",
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        """校验 query 不能为空白字符串。"""
        stripped = v.strip()
        if not stripped:
            raise ValueError("query 不能为空或仅包含空白字符")
        return stripped


class SearchDetailItem(BaseModel):
    """单篇文献的搜索/入库结果明细。

    Attributes:
        pmid: PubMed 唯一标识符。
        status: 处理状态 ("ingested" | "skipped" | "failed")。
        title: 文献标题。
        reason: 当 status="skipped" 时为 "already_exists"；
                当 status="failed" 时为具体错误信息。
    """

    pmid: str
    status: str
    title: str = ""
    reason: str = ""


class PubMedSearchData(BaseModel):
    """搜索入库操作的聚合结果。

    Attributes:
        query: 原始查询词。
        pmids_found: Entrez 返回的 PMID 总数。
        pmids_new: 实际新增入库的篇数。
        pmids_ingested: 成功向量索引的篇数。
        pmids_skipped: 因已存在而跳过的篇数。
        pmids_failed: 入库或索引失败的篇数。
        details: 每篇文献的处理明细。
    """

    query: str
    pmids_found: int
    pmids_new: int
    pmids_ingested: int
    pmids_skipped: int
    pmids_failed: int
    details: list[SearchDetailItem] = []


class ArticleSummary(BaseModel):
    """文献列表中的单条摘要。

    Attributes:
        pmid: PubMed 唯一标识符。
        title: 文献标题。
        authors: 作者列表。
        journal: 期刊名称。
        publish_date: 出版日期字符串。
        abstract_preview: 摘要前 200 字符。
        is_free_download: 是否可免费获取。
        ingestion_status: 向量索引状态。
        ingested_at: 索引完成时间。
        study_groups: 研究分组标签。
        created_at: 入库时间。
    """

    pmid: str
    title: str = ""
    authors: list[str] = []
    journal: str = ""
    publish_date: str = ""
    abstract_preview: str = ""
    is_free_download: bool = False
    ingestion_status: str = "uningested"
    ingested_at: datetime | None = None
    study_groups: list[str] = []
    created_at: datetime | None = None


class ArticleListData(BaseModel):
    """文献分页列表。

    Attributes:
        total: 符合条件的文献总数。
        page: 当前页码。
        page_size: 每页条数。
        articles: 当前页文献摘要列表。
    """

    total: int
    page: int
    page_size: int
    articles: list[ArticleSummary]


class ArticleDetailData(BaseModel):
    """单篇文献完整详情。

    Attributes:
        pmid: PubMed 唯一标识符。
        article_info: 文章基本信息 (title, authors, abstract, journal 等)。
        study_groups: 研究分组标签。
        results_info: 结构化结果信息。
        objectives: 研究目标摘要。
        is_free_download: 是否可免费获取。
        ingestion_status: 向量索引状态。
        chunk_count: 生成的向量块数量。
        vector_ids: ChromaDB 分配的 chunk ID 列表。
        ingested_at: 索引完成时间。
        created_at: 入库时间。
        updated_at: 最后更新时间。
        search_query: 原始搜索查询词。
        ingestion_error: 索引失败原因。
    """

    pmid: str
    article_info: dict[str, Any] = {}
    study_groups: list[str] = []
    results_info: dict[str, Any] = {}
    objectives: str = ""
    is_free_download: bool = False
    ingestion_status: str = "uningested"
    chunk_count: int | None = None
    vector_ids: list[str] | None = None
    ingested_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    search_query: str | None = None
    ingestion_error: str | None = None


class IngestResultItem(BaseModel):
    """单篇索引结果。

    Attributes:
        pmid: PubMed 唯一标识符。
        status: 索引状态 ("ingested" | "already_ingested" | "failed")。
        chunk_count: 生成的向量块数量。
        reason: 失败原因（status="failed" 时填写）。
    """

    pmid: str
    status: str
    chunk_count: int = 0
    reason: str = ""


class IngestBatchData(BaseModel):
    """批量索引操作结果。

    Attributes:
        total_uningested: 待索引的文献总数。
        ingested: 成功索引的篇数。
        failed: 索引失败的篇数。
        details: 每篇索引结果明细。
    """

    total_uningested: int = 0
    ingested: int = 0
    failed: int = 0
    details: list[IngestResultItem] = []


class DeleteResultData(BaseModel):
    """文献删除结果。

    Attributes:
        pmid: PubMed 唯一标识符。
        deleted_pg: PostgreSQL 中是否删除成功。
        deleted_vector: ChromaDB 中是否删除成功。
    """

    pmid: str
    deleted_pg: bool
    deleted_vector: bool


class IngestBatchRequest(BaseModel):
    """批量索引请求体（用于 POST /pubmed/ingest/batch）。

    Attributes:
        pmids: 待索引的 PMID 列表，长度 1-50。
        force: 是否强制重索引（覆盖已有向量）。
    """

    pmids: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="待索引的 PMID 列表",
    )
    force: bool = Field(
        default=False,
        description="是否强制重索引",
    )
