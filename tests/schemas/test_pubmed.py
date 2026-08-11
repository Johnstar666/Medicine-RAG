"""Tests for schemas/pubmed.py — PubMed 接口 Pydantic Schema。

测试覆盖:
    - 所有 10 个模型的合法实例化
    - PubMedSearchRequest 入参校验（空 query、超长 query、max_results 越界、空白字符串）
    - IngestBatchRequest pmids 长度边界
    - 各模型默认值
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from schemas.pubmed import (
    ArticleDetailData,
    ArticleListData,
    ArticleSummary,
    DeleteResultData,
    IngestBatchData,
    IngestBatchRequest,
    IngestResultItem,
    PubMedSearchData,
    PubMedSearchRequest,
    SearchDetailItem,
)

# ──────────────────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────────────────


def valid_pubmed_search_request(**overrides):
    """返回一个合法的 PubMedSearchRequest 实例，可覆盖默认字段。"""
    defaults = {
        "query": "COVID-19 mRNA vaccine",
        "max_results": 5,
        "auto_ingest": True,
    }
    defaults.update(overrides)
    return PubMedSearchRequest(**defaults)


def valid_search_detail_item(**overrides):
    """返回一个合法的 SearchDetailItem 实例。"""
    defaults = {
        "pmid": "12345678",
        "status": "ingested",
        "title": "Test Article Title",
        "reason": "",
    }
    defaults.update(overrides)
    return SearchDetailItem(**defaults)


# ──────────────────────────────────────────────────────────────
# T12: 模型合法实例化测试
# ──────────────────────────────────────────────────────────────


class TestPubMedSearchRequest:
    """PubMedSearchRequest 模型测试。"""

    def test_valid_minimal(self):
        """最简合法参数实例化成功。"""
        req = PubMedSearchRequest(query="test")
        assert req.query == "test"
        assert req.max_results == 5
        assert req.auto_ingest is True

    def test_valid_fully_specified(self):
        """完整合法参数实例化成功。"""
        req = PubMedSearchRequest(
            query="COVID-19 mRNA vaccine efficacy",
            max_results=10,
            auto_ingest=False,
        )
        assert req.query == "COVID-19 mRNA vaccine efficacy"
        assert req.max_results == 10
        assert req.auto_ingest is False

    def test_model_dump_success(self):
        """验证 model_dump() 成功返回字典。"""
        req = PubMedSearchRequest(query="heart disease")
        dumped = req.model_dump()
        assert dumped == {
            "query": "heart disease",
            "max_results": 5,
            "auto_ingest": True,
        }

    def test_query_empty_string_rejected(self):
        """空字符串 query 应被拒绝。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest(query="")

    def test_query_whitespace_only_rejected(self):
        """仅含空白的 query 被 field_validator 拒绝。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest(query="   ")

    def test_query_tabs_and_newlines_stripped_then_rejected(self):
        """仅含制表符和换行符的 query 被拒绝。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest(query="\t\n  \t")

    def test_query_too_long_rejected(self):
        """超过 500 字符的 query 被拒绝。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest(query="x" * 501)

    def test_query_exactly_500_chars_accepted(self):
        """恰好 500 字符的 query 通过校验。"""
        query = "a" * 500
        req = PubMedSearchRequest(query=query)
        assert len(req.query) == 500

    def test_max_results_zero_rejected(self):
        """max_results=0 越界被拒绝。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest(query="test", max_results=0)

    def test_max_results_negative_rejected(self):
        """max_results 为负数被拒绝。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest(query="test", max_results=-1)

    def test_max_results_exceeds_30_rejected(self):
        """max_results > 30 被拒绝。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest(query="test", max_results=31)

    def test_max_results_at_boundaries_accepted(self):
        """max_results 边界值 1 和 30 都通过。"""
        req1 = PubMedSearchRequest(query="test", max_results=1)
        assert req1.max_results == 1
        req2 = PubMedSearchRequest(query="test", max_results=30)
        assert req2.max_results == 30

    def test_whitespace_stripped_from_query(self):
        """前后空白被 field_validator 自动 strip。"""
        req = PubMedSearchRequest(query="  hello world  ")
        assert req.query == "hello world"

    def test_missing_query_raises(self):
        """缺少必填字段 query 抛出异常。"""
        with pytest.raises(ValidationError):
            PubMedSearchRequest()


class TestSearchDetailItem:
    """SearchDetailItem 模型测试。"""

    def test_valid_ingested(self):
        item = SearchDetailItem(pmid="123", status="ingested", title="Title")
        assert item.pmid == "123"
        assert item.status == "ingested"
        assert item.title == "Title"
        assert item.reason == ""

    def test_valid_skipped(self):
        item = SearchDetailItem(
            pmid="456", status="skipped", title="", reason="already_exists"
        )
        assert item.status == "skipped"
        assert item.reason == "already_exists"

    def test_valid_failed(self):
        item = SearchDetailItem(
            pmid="789", status="failed", title="Some Title", reason="Network error"
        )
        assert item.status == "failed"
        assert item.reason == "Network error"

    def test_model_dump(self):
        item = SearchDetailItem(pmid="111", status="ingested", title="Test")
        dumped = item.model_dump()
        assert dumped == {
            "pmid": "111",
            "status": "ingested",
            "title": "Test",
            "reason": "",
        }

    def test_defaults(self):
        """验证默认值。"""
        item = SearchDetailItem(pmid="pmid1", status="stored")
        assert item.title == ""
        assert item.reason == ""


class TestPubMedSearchData:
    """PubMedSearchData 模型测试。"""

    def test_valid_empty_details(self):
        data = PubMedSearchData(
            query="test",
            pmids_found=0,
            pmids_new=0,
            pmids_ingested=0,
            pmids_skipped=0,
            pmids_failed=0,
        )
        assert data.details == []
        dumped = data.model_dump()
        assert dumped["query"] == "test"

    def test_valid_with_details(self):
        items = [
            SearchDetailItem(pmid="1", status="ingested", title="A"),
            SearchDetailItem(pmid="2", status="skipped", reason="already_exists"),
        ]
        data = PubMedSearchData(
            query="q",
            pmids_found=2,
            pmids_new=1,
            pmids_ingested=1,
            pmids_skipped=1,
            pmids_failed=0,
            details=items,
        )
        assert len(data.details) == 2
        assert data.details[0].pmid == "1"

    def test_model_dump(self):
        data = PubMedSearchData(
            query="q",
            pmids_found=5,
            pmids_new=3,
            pmids_ingested=3,
            pmids_skipped=2,
            pmids_failed=0,
        )
        dumped = data.model_dump()
        assert "query" in dumped
        assert dumped["pmids_found"] == 5


class TestArticleSummary:
    """ArticleSummary 模型测试。"""

    def test_valid_minimal(self):
        summary = ArticleSummary(pmid="12345678")
        assert summary.pmid == "12345678"
        assert summary.title == ""
        assert summary.authors == []
        assert summary.journal == ""
        assert summary.publish_date == ""
        assert summary.abstract_preview == ""
        assert summary.is_free_download is False
        assert summary.ingestion_status == "uningested"
        assert summary.ingested_at is None
        assert summary.study_groups == []
        assert summary.created_at is None

    def test_valid_full(self):
        now = datetime.now()
        summary = ArticleSummary(
            pmid="12345678",
            title="A Great Study",
            authors=["Smith J", "Doe R"],
            journal="Nature",
            publish_date="2024-01-15",
            abstract_preview="This study investigates...",
            is_free_download=True,
            ingestion_status="ingested",
            ingested_at=now,
            study_groups=["treatment", "control"],
            created_at=now,
        )
        assert summary.title == "A Great Study"
        assert len(summary.authors) == 2
        assert summary.ingested_at == now

    def test_model_dump(self):
        summary = ArticleSummary(pmid="pm1")
        dumped = summary.model_dump()
        assert dumped["pmid"] == "pm1"
        assert dumped["ingested_at"] is None


class TestArticleListData:
    """ArticleListData 模型测试。"""

    def test_valid_empty(self):
        data = ArticleListData(total=0, page=1, page_size=20, articles=[])
        assert data.total == 0
        assert data.page == 1
        assert data.articles == []

    def test_valid_with_articles(self):
        articles = [
            ArticleSummary(pmid="1"),
            ArticleSummary(pmid="2", title="Test Article"),
        ]
        data = ArticleListData(total=47, page=1, page_size=20, articles=articles)
        assert data.total == 47
        assert len(data.articles) == 2
        assert data.articles[1].title == "Test Article"

    def test_model_dump(self):
        data = ArticleListData(
            total=5, page=2, page_size=3,
            articles=[ArticleSummary(pmid="a")],
        )
        dumped = data.model_dump()
        assert dumped["total"] == 5
        assert dumped["articles"][0]["pmid"] == "a"


class TestArticleDetailData:
    """ArticleDetailData 模型测试。"""

    def test_valid_minimal(self):
        detail = ArticleDetailData(pmid="12345678")
        assert detail.pmid == "12345678"
        assert detail.article_info == {}
        assert detail.study_groups == []
        assert detail.results_info == {}
        assert detail.objectives == ""
        assert detail.is_free_download is False
        assert detail.ingestion_status == "uningested"
        assert detail.chunk_count is None
        assert detail.vector_ids is None

    def test_valid_full(self):
        now = datetime.now()
        detail = ArticleDetailData(
            pmid="12345678",
            article_info={
                "title": "Test Article",
                "authors": ["Author A"],
                "abstract": "Long abstract...",
                "journal": "Science",
                "doi": "10.1234/test",
                "publish_date": "2024-12-01",
            },
            study_groups=["group A", "group B"],
            results_info={
                "raw_abstract": "Results...",
                "endpoints": "Primary endpoint",
            },
            objectives="To test the hypothesis",
            is_free_download=True,
            ingestion_status="ingested",
            chunk_count=5,
            vector_ids=["vec_1", "vec_2", "vec_3", "vec_4", "vec_5"],
            ingested_at=now,
            created_at=now,
            updated_at=now,
            search_query="COVID-19 vaccine",
            ingestion_error=None,
        )
        assert detail.article_info["title"] == "Test Article"
        assert len(detail.study_groups) == 2
        assert detail.chunk_count == 5
        assert len(detail.vector_ids) == 5

    def test_model_dump(self):
        detail = ArticleDetailData(pmid="pmid", chunk_count=3)
        dumped = detail.model_dump()
        assert dumped["pmid"] == "pmid"
        assert dumped["chunk_count"] == 3
        assert dumped["ingestion_error"] is None


class TestIngestResultItem:
    """IngestResultItem 模型测试。"""

    def test_valid_ingested(self):
        item = IngestResultItem(pmid="123", status="ingested", chunk_count=4)
        assert item.status == "ingested"
        assert item.chunk_count == 4
        assert item.reason == ""

    def test_valid_failed(self):
        item = IngestResultItem(pmid="456", status="failed", reason="Empty text")
        assert item.status == "failed"
        assert item.chunk_count == 0
        assert item.reason == "Empty text"

    def test_defaults(self):
        item = IngestResultItem(pmid="pmid", status="already_ingested")
        assert item.chunk_count == 0
        assert item.reason == ""

    def test_model_dump(self):
        item = IngestResultItem(pmid="1", status="ingested", chunk_count=2, reason="")
        dumped = item.model_dump()
        assert dumped["chunk_count"] == 2


class TestIngestBatchData:
    """IngestBatchData 模型测试。"""

    def test_valid_empty(self):
        data = IngestBatchData()
        assert data.total_uningested == 0
        assert data.ingested == 0
        assert data.failed == 0
        assert data.details == []

    def test_valid_with_details(self):
        items = [
            IngestResultItem(pmid="1", status="ingested", chunk_count=3),
            IngestResultItem(pmid="2", status="failed", reason="Error"),
        ]
        data = IngestBatchData(total_uningested=2, ingested=1, failed=1, details=items)
        assert data.total_uningested == 2
        assert data.ingested == 1
        assert data.failed == 1
        assert len(data.details) == 2

    def test_model_dump(self):
        data = IngestBatchData(total_uningested=5, ingested=5, failed=0)
        dumped = data.model_dump()
        assert dumped["total_uningested"] == 5
        assert dumped["failed"] == 0


class TestDeleteResultData:
    """DeleteResultData 模型测试。"""

    def test_both_deleted(self):
        result = DeleteResultData(pmid="123", deleted_pg=True, deleted_vector=True)
        assert result.deleted_pg is True
        assert result.deleted_vector is True

    def test_only_pg_deleted(self):
        result = DeleteResultData(pmid="456", deleted_pg=True, deleted_vector=False)
        assert result.deleted_pg is True
        assert result.deleted_vector is False

    def test_none_deleted(self):
        result = DeleteResultData(pmid="789", deleted_pg=False, deleted_vector=False)
        assert result.deleted_pg is False
        assert result.deleted_vector is False

    def test_model_dump(self):
        result = DeleteResultData(pmid="1", deleted_pg=True, deleted_vector=True)
        dumped = result.model_dump()
        assert dumped["pmid"] == "1"
        assert dumped["deleted_pg"] is True


# ──────────────────────────────────────────────────────────────
# T13: IngestBatchRequest pmids 长度边界测试
# ──────────────────────────────────────────────────────────────


class TestIngestBatchRequest:
    """IngestBatchRequest 模型测试（含 pmids 长度边界校验）。"""

    def test_valid_single_pmid(self):
        """单个 PMID 通过校验。"""
        req = IngestBatchRequest(pmids=["12345678"])
        assert len(req.pmids) == 1
        assert req.force is False

    def test_valid_50_pmids(self):
        """恰好 50 个 PMID 通过校验。"""
        pmids = [str(i) for i in range(1, 51)]
        req = IngestBatchRequest(pmids=pmids)
        assert len(req.pmids) == 50

    def test_valid_with_force_true(self):
        """force=True 通过校验。"""
        req = IngestBatchRequest(pmids=["123"], force=True)
        assert req.force is True

    def test_empty_pmids_rejected(self):
        """空列表被拒绝。"""
        with pytest.raises(ValidationError):
            IngestBatchRequest(pmids=[])

    def test_51_pmids_rejected(self):
        """51 个 PMID 被拒绝。"""
        pmids = [str(i) for i in range(1, 52)]
        with pytest.raises(ValidationError):
            IngestBatchRequest(pmids=pmids)

    def test_missing_pmids_raises(self):
        """缺少必填字段 pmids 抛出异常。"""
        with pytest.raises(ValidationError):
            IngestBatchRequest()

    def test_pmids_default_force(self):
        """force 默认值为 False。"""
        req = IngestBatchRequest(pmids=["1", "2"])
        assert req.force is False

    def test_model_dump(self):
        req = IngestBatchRequest(pmids=["111", "222"], force=True)
        dumped = req.model_dump()
        assert dumped == {"pmids": ["111", "222"], "force": True}


# ──────────────────────────────────────────────────────────────
# 综合 / 边界测试
# ──────────────────────────────────────────────────────────────


class TestAllModelsInstantiated:
    """验证所有 10 个模型可用合法数据实例化并通过 model_dump()。"""

    def test_all_models_instantiate_and_dump(self):
        """逐一实例化每个模型并验证 model_dump() 成功。"""

        # 1. PubMedSearchRequest
        m1 = PubMedSearchRequest(query="test query")
        assert isinstance(m1.model_dump(), dict)

        # 2. SearchDetailItem
        m2 = SearchDetailItem(pmid="1", status="ingested")
        assert isinstance(m2.model_dump(), dict)

        # 3. PubMedSearchData
        m3 = PubMedSearchData(
            query="q",
            pmids_found=1,
            pmids_new=0,
            pmids_ingested=1,
            pmids_skipped=0,
            pmids_failed=0,
        )
        assert isinstance(m3.model_dump(), dict)

        # 4. ArticleSummary
        m4 = ArticleSummary(pmid="1")
        assert isinstance(m4.model_dump(), dict)

        # 5. ArticleListData
        m5 = ArticleListData(total=0, page=1, page_size=20, articles=[])
        assert isinstance(m5.model_dump(), dict)

        # 6. ArticleDetailData
        m6 = ArticleDetailData(pmid="1")
        assert isinstance(m6.model_dump(), dict)

        # 7. IngestResultItem
        m7 = IngestResultItem(pmid="1", status="ingested")
        assert isinstance(m7.model_dump(), dict)

        # 8. IngestBatchData
        m8 = IngestBatchData()
        assert isinstance(m8.model_dump(), dict)

        # 9. DeleteResultData
        m9 = DeleteResultData(pmid="1", deleted_pg=True, deleted_vector=True)
        assert isinstance(m9.model_dump(), dict)

        # 10. IngestBatchRequest
        m10 = IngestBatchRequest(pmids=["1"])
        assert isinstance(m10.model_dump(), dict)
