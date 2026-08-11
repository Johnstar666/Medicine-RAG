"""Tests for PubMedSearchAppService.

Covers: T11-T16 from docs/tasks/pubmed-search-service.md plus additional
edge-case tests to reach >=70% coverage.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

import pytest

from application.services.pubmed_search_service import (
    PubMedSearchAppService,
    SearchResultItem,
)
from infrastructure.persistence.pubmed_ingester import (
    IngestResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_retriever() -> MagicMock:
    """Return a MagicMock configured as a fake PubMedRetriever."""
    return MagicMock()


@pytest.fixture
def mock_db() -> MagicMock:
    """Return a MagicMock configured as a fake PostgresDB."""
    return MagicMock()


@pytest.fixture
def mock_ingester() -> MagicMock:
    """Return a MagicMock configured as a fake PubMedArticleIngester."""
    return MagicMock()


@pytest.fixture
def service(
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
) -> PubMedSearchAppService:
    """Build a PubMedSearchAppService with mocked dependencies."""
    return PubMedSearchAppService(
        pubmed_retriever=mock_retriever,
        postgres_db=mock_db,
        pubmed_ingester=mock_ingester,
        request_interval=0.0,  # no delay in tests
    )


@pytest.fixture
def sample_article_data() -> dict:
    """Return a sample article dict as returned by fetch_article_details."""
    return {
        "pmid": "12345678",
        "article_info": {
            "title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
            "authors": ["Baden LR", "El Sahly HM"],
            "abstract": "Vaccination is critical...",
            "journal": "N Engl J Med",
            "doi": "10.1056/NEJMoa2035389",
            "publish_date": "2020-12-31",
            "pmc_id": "PMC7717217",
            "publication_type": "Clinical Trial",
        },
        "study_groups": ["vaccine group", "placebo group"],
        "results_info": {"raw_abstract": "..."},
        "objectives": "To evaluate efficacy and safety",
        "is_free_download": True,
        "search_query": "",
        "raw_response": {},
    }


# ---------------------------------------------------------------------------
# T11: Normal path - all articles succeed
# ---------------------------------------------------------------------------


def test_search_and_store_all_success(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """T11: 正常路径 — mock retriever 返回 3 个 PMID, 全部成功.

    Expect: pmids_found=3, pmids_new=3, pmids_ingested=3.
    """
    pmids = ["11111111", "22222222", "33333333"]
    mock_retriever.search_pubmed.return_value = pmids

    # None of these PMIDs exist yet
    mock_db.is_pmid_exist.return_value = False

    # Mock fetch returns unique article data per PMID
    def make_article(pmid: str) -> dict:
        data = dict(sample_article_data)
        data["pmid"] = pmid
        return data

    mock_retriever.fetch_article_details.side_effect = lambda pmid: make_article(pmid)

    # Mock ingest returns ingested
    mock_ingester.ingest_article.return_value = IngestResult(
        pmid="", status="ingested", chunk_count=3
    )

    result = service.search_and_store(
        query="test query", max_results=3, auto_ingest=True
    )

    assert result.pmids_found == 3
    assert result.pmids_new == 3
    assert result.pmids_ingested == 3
    assert result.pmids_skipped == 0
    assert result.pmids_failed == 0
    assert result.query == "test query"

    statuses = [d.status for d in result.details]
    assert all(s == "ingested" for s in statuses)
    assert mock_retriever.search_pubmed.call_count == 1
    assert mock_db.is_pmid_exist.call_count == 3
    assert mock_retriever.fetch_article_details.call_count == 3
    assert mock_db.insert_article.call_count == 3
    assert mock_ingester.ingest_article.call_count == 3


# ---------------------------------------------------------------------------
# T12: All articles already exist
# ---------------------------------------------------------------------------


def test_search_and_store_all_exist(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
) -> None:
    """T12: 全部已存在 — mock is_pmid_exist 全部返回 True.

    Expect: pmids_new=0, pmids_skipped=3.
    """
    pmids = ["11111111", "22222222", "33333333"]
    mock_retriever.search_pubmed.return_value = pmids
    mock_db.is_pmid_exist.return_value = True

    result = service.search_and_store(
        query="test query", max_results=3, auto_ingest=True
    )

    assert result.pmids_found == 3
    assert result.pmids_new == 0
    assert result.pmids_ingested == 0
    assert result.pmids_skipped == 3
    assert result.pmids_failed == 0

    for detail in result.details:
        assert detail.status == "skipped"
        assert detail.reason == "already_exists"

    # fetch / insert / ingest should never be called
    mock_retriever.fetch_article_details.assert_not_called()
    mock_db.insert_article.assert_not_called()
    mock_ingester.ingest_article.assert_not_called()


# ---------------------------------------------------------------------------
# T13: Partial failure - 2nd article fetch fails
# ---------------------------------------------------------------------------


def test_search_and_store_partial_failure(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """T13: 部分失败 — 第 2 篇 fetch 抛异常.

    Expect: 该篇 status="failed", 其余正常.
    """
    pmids = ["11111111", "22222222", "33333333"]
    mock_retriever.search_pubmed.return_value = pmids
    mock_db.is_pmid_exist.return_value = False

    def fetch_side_effect(pmid: str) -> dict:
        if pmid == "22222222":
            raise ConnectionError("Network error fetching 22222222")
        data = dict(sample_article_data)
        data["pmid"] = pmid
        return data

    mock_retriever.fetch_article_details.side_effect = fetch_side_effect
    mock_ingester.ingest_article.return_value = IngestResult(
        pmid="", status="ingested", chunk_count=3
    )

    result = service.search_and_store(
        query="test query", max_results=3, auto_ingest=True
    )

    assert result.pmids_found == 3
    assert result.pmids_new == 3  # 2 篇入库 + 1 篇 fetch 失败也算 new (attempted)
    assert result.pmids_ingested == 2
    assert result.pmids_skipped == 0
    assert result.pmids_failed == 1

    # Verify the failed article
    failed = [d for d in result.details if d.status == "failed"]
    assert len(failed) == 1
    assert failed[0].pmid == "22222222"
    assert "Network error" in failed[0].reason

    # Other two should be ingested
    ingested = [d for d in result.details if d.status == "ingested"]
    assert len(ingested) == 2


# ---------------------------------------------------------------------------
# T14: auto_ingest=False
# ---------------------------------------------------------------------------


def test_search_and_store_no_auto_ingest(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """T14: 不自动索引 — auto_ingest=False.

    Expect: pmids_ingested=0, details 中 status 均为 "stored".
    """
    pmids = ["11111111", "22222222"]
    mock_retriever.search_pubmed.return_value = pmids
    mock_db.is_pmid_exist.return_value = False

    def make_article(pmid: str) -> dict:
        data = dict(sample_article_data)
        data["pmid"] = pmid
        return data

    mock_retriever.fetch_article_details.side_effect = make_article

    result = service.search_and_store(
        query="test query", max_results=2, auto_ingest=False
    )

    assert result.pmids_found == 2
    assert result.pmids_new == 2
    assert result.pmids_ingested == 0
    assert result.pmids_skipped == 0
    assert result.pmids_failed == 0

    for detail in result.details:
        assert detail.status == "stored"

    # Ingest should never be called
    mock_ingester.ingest_article.assert_not_called()


# ---------------------------------------------------------------------------
# T15: PubMed API completely unavailable
# ---------------------------------------------------------------------------


def test_search_and_store_pubmed_api_unavailable(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
) -> None:
    """T15: PubMed API 完全不可用 — mock search_pubmed 抛异常.

    Expect: 异常向上抛出 (after 3 retries).
    """
    mock_retriever.search_pubmed.side_effect = ConnectionError("API unavailable")

    with pytest.raises(ConnectionError, match="API unavailable"):
        service.search_and_store(query="test query", max_results=3)

    # search_pubmed should have been called 3 times (retries)
    assert mock_retriever.search_pubmed.call_count == 3


# ---------------------------------------------------------------------------
# T16: ingest_all_uningested
# ---------------------------------------------------------------------------


def test_ingest_all_uningested_mixed_results(
    service: PubMedSearchAppService,
    mock_ingester: MagicMock,
) -> None:
    """T16: ingest_all_uningested — mock ingester 返回混合结果.

    Expect: IngestBatchData 统计正确.
    """
    mock_results = [
        IngestResult(pmid="111", status="ingested", chunk_count=5),
        IngestResult(pmid="222", status="failed", reason="Empty article text"),
        IngestResult(pmid="333", status="already_ingested", chunk_count=3),
        IngestResult(pmid="444", status="ingested", chunk_count=7),
        IngestResult(pmid="555", status="failed", reason="Chunk error"),
    ]
    mock_ingester.ingest_all_uningested.return_value = mock_results

    result = service.ingest_all_uningested(force=False)

    assert result.total_uningested == 5
    assert result.ingested == 3  # 2 ingested + 1 already_ingested
    assert result.failed == 2
    assert len(result.details) == 5

    statuses = [d.status for d in result.details]
    assert statuses == ["ingested", "failed", "already_ingested", "ingested", "failed"]

    mock_ingester.ingest_all_uningested.assert_called_once_with(force=False)


def test_ingest_all_uningested_force(
    service: PubMedSearchAppService,
    mock_ingester: MagicMock,
) -> None:
    """ingest_all_uningested with force=True passes the flag through."""
    mock_ingester.ingest_all_uningested.return_value = []

    service.ingest_all_uningested(force=True)

    mock_ingester.ingest_all_uningested.assert_called_once_with(force=True)


# ---------------------------------------------------------------------------
# Additional edge-case tests for coverage
# ---------------------------------------------------------------------------


def test_search_and_store_empty_pmid_list(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
) -> None:
    """search_pubmed returns empty list -> early return with zeros."""
    mock_retriever.search_pubmed.return_value = []

    result = service.search_and_store(query="obscure query", max_results=5)

    assert result.pmids_found == 0
    assert result.pmids_new == 0
    assert result.pmids_ingested == 0
    assert result.pmids_skipped == 0
    assert result.pmids_failed == 0
    assert result.details == []
    assert result.query == "obscure query"


def test_search_and_store_insert_failure(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """Insert fails for an article -> status=failed, others unaffected."""
    pmids = ["11111111", "22222222"]
    mock_retriever.search_pubmed.return_value = pmids
    mock_db.is_pmid_exist.return_value = False

    def make_article(pmid: str) -> dict:
        data = dict(sample_article_data)
        data["pmid"] = pmid
        return data

    mock_retriever.fetch_article_details.side_effect = make_article

    # First insert works, second fails
    mock_db.insert_article.side_effect = [
        None,
        RuntimeError("Unique constraint violation"),
    ]
    mock_ingester.ingest_article.return_value = IngestResult(
        pmid="", status="ingested", chunk_count=3
    )

    result = service.search_and_store(query="test", max_results=2, auto_ingest=True)

    assert result.pmids_new == 2
    assert result.pmids_ingested == 1
    assert result.pmids_failed == 1

    failed = [d for d in result.details if d.status == "failed"]
    assert len(failed) == 1
    assert failed[0].pmid == "22222222"
    assert "Unique constraint" in failed[0].reason


def test_search_and_store_ingest_failure(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """Ingest fails for one article -> status becomes failed, batch continues."""
    pmids = ["11111111", "22222222"]
    mock_retriever.search_pubmed.return_value = pmids
    mock_db.is_pmid_exist.return_value = False

    def make_article(pmid: str) -> dict:
        data = dict(sample_article_data)
        data["pmid"] = pmid
        return data

    mock_retriever.fetch_article_details.side_effect = make_article

    # First ingest works, second fails
    mock_ingester.ingest_article.side_effect = [
        IngestResult(pmid="11111111", status="ingested", chunk_count=3),
        RuntimeError("ChromaDB unavailable"),
    ]

    result = service.search_and_store(query="test", max_results=2, auto_ingest=True)

    assert result.pmids_new == 2
    assert result.pmids_ingested == 1
    assert result.pmids_failed == 1

    ingested = [d for d in result.details if d.status == "ingested"]
    failed = [d for d in result.details if d.status == "failed"]
    assert len(ingested) == 1
    assert len(failed) == 1
    assert failed[0].pmid == "22222222"


def test_search_and_store_duplicate_check_failure(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
) -> None:
    """is_pmid_exist raises -> article marked as failed, batch continues."""
    pmids = ["11111111", "22222222"]
    mock_retriever.search_pubmed.return_value = pmids
    mock_db.is_pmid_exist.side_effect = [
        RuntimeError("DB connection lost"),
        False,  # second succeeds
    ]

    # second article data
    mock_retriever.fetch_article_details.return_value = {
        "pmid": "22222222",
        "article_info": {
            "title": "Test Title",
            "authors": [],
            "abstract": "",
            "journal": "",
            "doi": "",
            "publish_date": "",
            "pmc_id": "",
            "publication_type": "",
        },
        "study_groups": [],
        "results_info": None,
        "objectives": "",
        "is_free_download": False,
        "search_query": "",
        "raw_response": None,
    }
    mock_ingester = service._ingester
    mock_ingester.ingest_article.return_value = IngestResult(
        pmid="22222222", status="ingested", chunk_count=3
    )

    result = service.search_and_store(query="test", max_results=2, auto_ingest=True)

    failed = [d for d in result.details if d.status == "failed"]
    assert len(failed) == 1
    assert failed[0].pmid == "11111111"
    assert "DB connection lost" in failed[0].reason

    assert result.pmids_ingested == 1


def test_search_and_store_ingest_result_failed_status(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """ingest_article returns status='failed' (not exception) -> properly counted."""
    pmids = ["11111111"]
    mock_retriever.search_pubmed.return_value = pmids
    mock_db.is_pmid_exist.return_value = False

    data = dict(sample_article_data)
    data["pmid"] = "11111111"
    mock_retriever.fetch_article_details.return_value = data

    mock_ingester.ingest_article.return_value = IngestResult(
        pmid="11111111", status="failed", reason="Empty article text"
    )

    result = service.search_and_store(query="test", max_results=1, auto_ingest=True)

    assert result.pmids_ingested == 0
    assert result.pmids_failed == 1
    assert result.pmids_new == 1


def test_search_and_store_mixed_skip_and_new(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """Mix of skipped (already exist) and new articles."""
    pmids = ["11111111", "22222222", "33333333"]
    mock_retriever.search_pubmed.return_value = pmids

    # PMID 1 already exists, PMID 2 and 3 are new
    mock_db.is_pmid_exist.side_effect = [True, False, False]

    def make_article(pmid: str) -> dict:
        data = dict(sample_article_data)
        data["pmid"] = pmid
        return data

    mock_retriever.fetch_article_details.side_effect = make_article
    mock_ingester.ingest_article.return_value = IngestResult(
        pmid="", status="ingested", chunk_count=3
    )

    result = service.search_and_store(query="test", max_results=3, auto_ingest=True)

    assert result.pmids_found == 3
    assert result.pmids_new == 2
    assert result.pmids_ingested == 2
    assert result.pmids_skipped == 1
    assert result.pmids_failed == 0

    # is_pmid_exist called for each pmid — first returns True, others attempted
    assert mock_db.is_pmid_exist.call_count == 3


def test_search_and_store_retry_succeeds_second_attempt(
    service: PubMedSearchAppService,
    mock_retriever: MagicMock,
    mock_db: MagicMock,
    mock_ingester: MagicMock,
    sample_article_data: dict,
) -> None:
    """search_pubmed fails once, succeeds on second attempt -> no exception."""
    pmids = ["11111111"]
    mock_retriever.search_pubmed.side_effect = [
        RuntimeError("Temporary network error"),
        pmids,
    ]
    mock_db.is_pmid_exist.return_value = False

    data = dict(sample_article_data)
    data["pmid"] = "11111111"
    mock_retriever.fetch_article_details.return_value = data
    mock_ingester.ingest_article.return_value = IngestResult(
        pmid="11111111", status="ingested", chunk_count=3
    )

    result = service.search_and_store(query="test", max_results=1, auto_ingest=True)

    assert result.pmids_found == 1
    assert result.pmids_ingested == 1
    assert mock_retriever.search_pubmed.call_count == 2


# ---------------------------------------------------------------------------
# SearchResultItem dataclass tests
# ---------------------------------------------------------------------------


def test_search_result_item_defaults() -> None:
    """SearchResultItem has correct defaults."""
    item = SearchResultItem(pmid="123", status="stored")
    assert item.pmid == "123"
    assert item.status == "stored"
    assert item.title == ""
    assert item.reason == ""


def test_search_result_item_with_fields() -> None:
    """SearchResultItem accepts all fields."""
    item = SearchResultItem(
        pmid="456",
        status="failed",
        title="Test Article",
        reason="Network error",
    )
    assert item.pmid == "456"
    assert item.status == "failed"
    assert item.title == "Test Article"
    assert item.reason == "Network error"


# ---------------------------------------------------------------------------
# Service constructor
# ---------------------------------------------------------------------------


def test_service_constructor_default_interval() -> None:
    """PubMedSearchAppService uses default request_interval=0.15."""
    svc = PubMedSearchAppService(
        pubmed_retriever=MagicMock(),
        postgres_db=MagicMock(),
        pubmed_ingester=MagicMock(),
    )
    assert svc._interval == 0.15
