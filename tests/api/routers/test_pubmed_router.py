"""Tests for pubmed_router.py.

Uses FastAPI TestClient with mocked services injected via module-level setter
functions.  Covers all 7 endpoints — happy paths, service-not-initialized,
validation errors, and exception-to-HTTPException mappings.

Test mapping to docs/tasks/pubmed-router.md:
    T15 — POST /pubmed/search success (mock service)
    T16 — POST /pubmed/search service not injected → 500
    T17 — GET /pubmed/articles default params
    T18 — GET /pubmed/articles?page=0 → 422
    T19 — GET /pubmed/articles/{pmid} not found → 404
    T20 — DELETE /pubmed/articles/{pmid} verify response fields
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

# Ensure project root is on path
sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    ),
)

# ── Force early logging / config init if needed ────────────────
# Some modules import config at module level which may fail without env.
os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

# Import router module via its module path to allow patching globals
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routers.pubmed_router as pubmed_router_module
from schemas.pubmed import (
    ArticleDetailData,
    ArticleListData,
    ArticleSummary,
    DeleteResultData,
    IngestBatchData,
    IngestResultItem,
    PubMedSearchData,
    SearchDetailItem,
)

# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    """Build a standalone FastAPI app with only the pubmed router."""
    app = FastAPI()
    app.include_router(pubmed_router_module.router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Service-reset fixture (autouse) — clean module state per test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_services() -> None:
    """Reset module-level services before / after each test."""
    pubmed_router_module.pubmed_search_service = None
    pubmed_router_module.knowledge_management_service = None
    yield
    pubmed_router_module.pubmed_search_service = None
    pubmed_router_module.knowledge_management_service = None


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _inject_pubmed_service(mock: MagicMock) -> None:
    """Inject a mock PubMedSearchAppService into the router module."""
    pubmed_router_module.set_pubmed_search_service(mock)


def _inject_km_service(mock: MagicMock) -> None:
    """Inject a mock KnowledgeManagementService into the router module."""
    pubmed_router_module.set_knowledge_management_service(mock)


def _make_search_data(query: str = "test") -> PubMedSearchData:
    """Build a minimal PubMedSearchData for assertions."""
    return PubMedSearchData(
        query=query,
        pmids_found=3,
        pmids_new=2,
        pmids_ingested=2,
        pmids_skipped=1,
        pmids_failed=0,
        details=[
            SearchDetailItem(
                pmid="111", status="ingested", title="Article 1", reason=""
            ),
            SearchDetailItem(
                pmid="222", status="ingested", title="Article 2", reason=""
            ),
            SearchDetailItem(
                pmid="333",
                status="skipped",
                title="",
                reason="already_exists",
            ),
        ],
    )


def _make_article_list() -> ArticleListData:
    """Build a minimal ArticleListData for assertions."""
    return ArticleListData(
        total=10,
        page=1,
        page_size=20,
        articles=[
            ArticleSummary(
                pmid="111",
                title="Test Article",
                ingestion_status="ingested",
            ),
        ],
    )


def _make_article_detail() -> ArticleDetailData:
    """Build a minimal ArticleDetailData for assertions."""
    return ArticleDetailData(
        pmid="111",
        article_info={"title": "Test Article", "abstract": "Test abstract"},
    )


def _make_ingest_batch_data(
    total: int = 3, ingested: int = 2, failed: int = 1
) -> IngestBatchData:
    """Build a minimal IngestBatchData for assertions."""
    return IngestBatchData(
        total_uningested=total,
        ingested=ingested,
        failed=failed,
        details=[
            IngestResultItem(
                pmid="111", status="ingested", chunk_count=5, reason=""
            ),
            IngestResultItem(
                pmid="222", status="ingested", chunk_count=3, reason=""
            ),
            IngestResultItem(
                pmid="333",
                status="failed",
                chunk_count=0,
                reason="Empty article text",
            ),
        ],
    )


# ===================================================================
# POST /pubmed/search
# ===================================================================


class TestSearchPubmed:
    """Tests for POST /pubmed/search."""

    def test_success_returns_200(self, client: TestClient) -> None:
        """T15: mock service returns data → HTTP 200 with correct structure."""
        mock_svc = MagicMock()
        mock_svc.search_and_store.return_value = _make_search_data("COVID-19")
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/search",
            json={"query": "COVID-19", "max_results": 5, "auto_ingest": True},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["message"] == "success"
        data = body["data"]
        assert data["query"] == "COVID-19"
        assert data["pmids_found"] == 3
        assert data["pmids_new"] == 2
        assert data["pmids_ingested"] == 2
        assert data["pmids_skipped"] == 1
        assert data["pmids_failed"] == 0
        assert len(data["details"]) == 3
        assert data["details"][0]["status"] == "ingested"

        mock_svc.search_and_store.assert_called_once_with(
            query="COVID-19", max_results=5, auto_ingest=True
        )

    def test_service_not_injected_returns_500(self, client: TestClient) -> None:
        """T16: service not injected → HTTP 500."""
        resp = client.post(
            "/pubmed/search",
            json={"query": "test", "max_results": 5},
        )
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Service not initialized"

    def test_runtime_error_returns_503(self, client: TestClient) -> None:
        """search_and_store raises RuntimeError → HTTP 503."""
        mock_svc = MagicMock()
        mock_svc.search_and_store.side_effect = RuntimeError(
            "NCBI unreachable"
        )
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/search",
            json={"query": "test", "max_results": 5},
        )
        assert resp.status_code == 503
        assert "PubMed API" in resp.json()["detail"]

    def test_generic_exception_returns_500(self, client: TestClient) -> None:
        """search_and_store raises generic Exception → HTTP 500."""
        mock_svc = MagicMock()
        mock_svc.search_and_store.side_effect = Exception("Unexpected error")
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/search",
            json={"query": "test", "max_results": 5},
        )
        assert resp.status_code == 500
        assert "Unexpected error" in resp.json()["detail"]

    def test_empty_query_rejected_by_pydantic(self, client: TestClient) -> None:
        """Empty query → 422 (Pydantic validation)."""
        mock_svc = MagicMock()
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/search",
            json={"query": "   ", "max_results": 5},
        )
        assert resp.status_code == 422

    def test_max_results_out_of_range(self, client: TestClient) -> None:
        """max_results > 30 → 422."""
        mock_svc = MagicMock()
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/search",
            json={"query": "test", "max_results": 50},
        )
        assert resp.status_code == 422

    def test_auto_ingest_false_passed_through(self, client: TestClient) -> None:
        """auto_ingest=False is forwarded to the service."""
        mock_svc = MagicMock()
        mock_svc.search_and_store.return_value = _make_search_data()
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/search",
            json={"query": "test", "max_results": 5, "auto_ingest": False},
        )

        assert resp.status_code == 200
        mock_svc.search_and_store.assert_called_once_with(
            query="test", max_results=5, auto_ingest=False
        )


# ===================================================================
# GET /pubmed/articles
# ===================================================================


class TestListArticles:
    """Tests for GET /pubmed/articles."""

    def test_default_params_returns_200(self, client: TestClient) -> None:
        """T17: default pagination → HTTP 200 with correct structure."""
        mock_km = MagicMock()
        mock_km.list_articles.return_value = _make_article_list()
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total"] == 10
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["articles"]) == 1
        assert data["articles"][0]["pmid"] == "111"

        mock_km.list_articles.assert_called_once_with(
            page=1,
            page_size=20,
            search=None,
            ingestion_status="all",
            sort_by="created_at",
            order="desc",
        )

    def test_page_zero_returns_422(self, client: TestClient) -> None:
        """T18: page=0 → HTTP 422 (FastAPI Query validation)."""
        mock_km = MagicMock()
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles?page=0")
        assert resp.status_code == 422

    def test_page_size_out_of_range_returns_422(self, client: TestClient) -> None:
        """page_size=101 → HTTP 422."""
        mock_km = MagicMock()
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles?page_size=101")
        assert resp.status_code == 422

    def test_invalid_ingestion_status_returns_422(self, client: TestClient) -> None:
        """Invalid ingestion_status → HTTP 422 (pattern validation)."""
        mock_km = MagicMock()
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles?ingestion_status=invalid")
        assert resp.status_code == 422

    def test_invalid_sort_by_returns_422(self, client: TestClient) -> None:
        """Invalid sort_by → HTTP 422."""
        mock_km = MagicMock()
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles?sort_by=invalid")
        assert resp.status_code == 422

    def test_custom_params_passed_through(self, client: TestClient) -> None:
        """All custom query params are forwarded."""
        mock_km = MagicMock()
        mock_km.list_articles.return_value = _make_article_list()
        _inject_km_service(mock_km)

        resp = client.get(
            "/pubmed/articles?page=3&page_size=50&search=vaccine"
            "&ingestion_status=ingested&sort_by=pmid&order=asc"
        )

        assert resp.status_code == 200
        mock_km.list_articles.assert_called_once_with(
            page=3,
            page_size=50,
            search="vaccine",
            ingestion_status="ingested",
            sort_by="pmid",
            order="asc",
        )

    def test_service_not_injected_returns_500(self, client: TestClient) -> None:
        """km service not injected → HTTP 500."""
        resp = client.get("/pubmed/articles")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Service not initialized"

    def test_value_error_returns_400(self, client: TestClient) -> None:
        """km.list_articles raises ValueError → HTTP 400."""
        mock_km = MagicMock()
        mock_km.list_articles.side_effect = ValueError("page must be >= 1")
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles")
        assert resp.status_code == 400
        assert "page must be >= 1" in resp.json()["detail"]

    def test_generic_exception_returns_500(self, client: TestClient) -> None:
        """km.list_articles raises generic Exception → HTTP 500."""
        mock_km = MagicMock()
        mock_km.list_articles.side_effect = RuntimeError("DB down")
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles")
        assert resp.status_code == 500
        assert "DB down" in resp.json()["detail"]


# ===================================================================
# GET /pubmed/articles/{pmid}
# ===================================================================


class TestGetArticleDetail:
    """Tests for GET /pubmed/articles/{pmid}."""

    def test_success_returns_200(self, client: TestClient) -> None:
        """Valid PMID → HTTP 200 with article detail."""
        mock_km = MagicMock()
        mock_km.get_article_detail.return_value = _make_article_detail()
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles/111")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["pmid"] == "111"
        mock_km.get_article_detail.assert_called_once_with("111")

    def test_not_found_returns_404(self, client: TestClient) -> None:
        """T19: PMID not found → HTTP 404."""
        mock_km = MagicMock()
        mock_km.get_article_detail.return_value = None
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles/999")
        assert resp.status_code == 404
        assert "PMID 999 not found" in resp.json()["detail"]

    def test_service_not_injected_returns_500(self, client: TestClient) -> None:
        """km service not injected → HTTP 500."""
        resp = client.get("/pubmed/articles/111")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Service not initialized"

    def test_service_raises_exception_returns_500(self, client: TestClient) -> None:
        """km.get_article_detail raises exception → HTTP 500."""
        mock_km = MagicMock()
        mock_km.get_article_detail.side_effect = RuntimeError("DB error")
        _inject_km_service(mock_km)

        resp = client.get("/pubmed/articles/111")
        assert resp.status_code == 500
        assert "DB error" in resp.json()["detail"]


# ===================================================================
# POST /pubmed/ingest/{pmid}
# ===================================================================


class TestIngestSingleArticle:
    """Tests for POST /pubmed/ingest/{pmid}."""

    def test_success_returns_200(self, client: TestClient) -> None:
        """Valid ingest → HTTP 200 with IngestBatchData wrapping single result."""
        mock_svc = MagicMock()
        # Simulate an IngestResult from PubMedArticleIngester
        from infrastructure.persistence.pubmed_ingester import IngestResult

        mock_ingester = MagicMock()
        mock_ingester.ingest_article.return_value = IngestResult(
            pmid="111",
            status="ingested",
            chunk_count=5,
            reason="",
        )
        mock_svc._ingester = mock_ingester
        _inject_pubmed_service(mock_svc)

        resp = client.post("/pubmed/ingest/111")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total_uningested"] == 1
        assert data["ingested"] == 1
        assert data["failed"] == 0
        assert len(data["details"]) == 1
        assert data["details"][0]["pmid"] == "111"
        assert data["details"][0]["status"] == "ingested"
        assert data["details"][0]["chunk_count"] == 5

        mock_ingester.ingest_article.assert_called_once_with(
            "111", force=False
        )

    def test_force_flag_passed_through(self, client: TestClient) -> None:
        """force=True → forwarded to ingester."""
        mock_svc = MagicMock()
        from infrastructure.persistence.pubmed_ingester import IngestResult

        mock_ingester = MagicMock()
        mock_ingester.ingest_article.return_value = IngestResult(
            pmid="111", status="ingested", chunk_count=5, reason=""
        )
        mock_svc._ingester = mock_ingester
        _inject_pubmed_service(mock_svc)

        resp = client.post("/pubmed/ingest/111?force=true")

        assert resp.status_code == 200
        mock_ingester.ingest_article.assert_called_once_with(
            "111", force=True
        )

    def test_failed_ingest_returns_200_with_failed_status(
        self, client: TestClient
    ) -> None:
        """Ingest returns failed status → HTTP 200 with failed count."""
        mock_svc = MagicMock()
        from infrastructure.persistence.pubmed_ingester import IngestResult

        mock_ingester = MagicMock()
        mock_ingester.ingest_article.return_value = IngestResult(
            pmid="111", status="failed", chunk_count=0, reason="Empty text"
        )
        mock_svc._ingester = mock_ingester
        _inject_pubmed_service(mock_svc)

        resp = client.post("/pubmed/ingest/111")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["ingested"] == 0
        assert data["failed"] == 1
        assert data["details"][0]["status"] == "failed"

    def test_service_not_injected_returns_500(self, client: TestClient) -> None:
        """pubmed service not injected → HTTP 500."""
        resp = client.post("/pubmed/ingest/111")
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Service not initialized"

    def test_ingester_raises_exception_returns_500(self, client: TestClient) -> None:
        """ingester.ingest_article raises exception → HTTP 500."""
        mock_svc = MagicMock()
        mock_ingester = MagicMock()
        mock_ingester.ingest_article.side_effect = RuntimeError("DB down")
        mock_svc._ingester = mock_ingester
        _inject_pubmed_service(mock_svc)

        resp = client.post("/pubmed/ingest/111")
        assert resp.status_code == 500
        assert "DB down" in resp.json()["detail"]


# ===================================================================
# POST /pubmed/ingest/batch
# ===================================================================


class TestIngestBatch:
    """Tests for POST /pubmed/ingest/batch."""

    def test_success_returns_200(self, client: TestClient) -> None:
        """Valid batch → HTTP 200 with IngestBatchData."""
        mock_svc = MagicMock()
        from infrastructure.persistence.pubmed_ingester import IngestResult

        mock_ingester = MagicMock()
        mock_ingester.batch_ingest.return_value = [
            IngestResult(pmid="111", status="ingested", chunk_count=5, reason=""),
            IngestResult(pmid="222", status="failed", chunk_count=0, reason="Empty"),
            IngestResult(
                pmid="333",
                status="already_ingested",
                chunk_count=3,
                reason="",
            ),
        ]
        mock_svc._ingester = mock_ingester
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/ingest/batch",
            json={"pmids": ["111", "222", "333"], "force": False},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_uningested"] == 3
        assert data["ingested"] == 2
        assert data["failed"] == 1
        assert len(data["details"]) == 3

        mock_ingester.batch_ingest.assert_called_once_with(
            ["111", "222", "333"], force=False
        )

    def test_empty_pmids_returns_422(self, client: TestClient) -> None:
        """Empty pmids list → HTTP 422."""
        mock_svc = MagicMock()
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/ingest/batch",
            json={"pmids": [], "force": False},
        )
        assert resp.status_code == 422

    def test_service_not_injected_returns_500(self, client: TestClient) -> None:
        """pubmed service not injected → HTTP 500."""
        resp = client.post(
            "/pubmed/ingest/batch",
            json={"pmids": ["111"], "force": False},
        )
        assert resp.status_code == 500

    def test_ingester_raises_exception_returns_500(self, client: TestClient) -> None:
        """ingester.batch_ingest raises exception → HTTP 500."""
        mock_svc = MagicMock()
        mock_ingester = MagicMock()
        mock_ingester.batch_ingest.side_effect = RuntimeError("Batch failed")
        mock_svc._ingester = mock_ingester
        _inject_pubmed_service(mock_svc)

        resp = client.post(
            "/pubmed/ingest/batch",
            json={"pmids": ["111"], "force": False},
        )
        assert resp.status_code == 500
        assert "Batch failed" in resp.json()["detail"]


# ===================================================================
# POST /pubmed/ingest/all-uningested
# ===================================================================


class TestIngestAllUningested:
    """Tests for POST /pubmed/ingest/all-uningested."""

    def test_success_returns_200(self, client: TestClient) -> None:
        """Valid call → HTTP 200 with IngestBatchData."""
        mock_svc = MagicMock()
        mock_svc.ingest_all_uningested.return_value = _make_ingest_batch_data()
        _inject_pubmed_service(mock_svc)

        resp = client.post("/pubmed/ingest/all-uningested")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["total_uningested"] == 3
        assert data["ingested"] == 2
        assert data["failed"] == 1

        mock_svc.ingest_all_uningested.assert_called_once()

    def test_service_not_injected_returns_500(self, client: TestClient) -> None:
        """pubmed service not injected → HTTP 500."""
        resp = client.post("/pubmed/ingest/all-uningested")
        assert resp.status_code == 500

    def test_service_raises_exception_returns_500(self, client: TestClient) -> None:
        """Service raises exception → HTTP 500."""
        mock_svc = MagicMock()
        mock_svc.ingest_all_uningested.side_effect = RuntimeError("DB error")
        _inject_pubmed_service(mock_svc)

        resp = client.post("/pubmed/ingest/all-uningested")
        assert resp.status_code == 500
        assert "DB error" in resp.json()["detail"]


# ===================================================================
# DELETE /pubmed/articles/{pmid}
# ===================================================================


class TestDeleteArticle:
    """Tests for DELETE /pubmed/articles/{pmid}."""

    def test_success_returns_200_with_delete_result(self, client: TestClient) -> None:
        """T20: Valid delete → HTTP 200 with deleted_pg and deleted_vector."""
        mock_km = MagicMock()
        mock_km.delete_article.return_value = DeleteResultData(
            pmid="111", deleted_pg=True, deleted_vector=True
        )
        _inject_km_service(mock_km)

        resp = client.delete("/pubmed/articles/111")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["pmid"] == "111"
        assert data["deleted_pg"] is True
        assert data["deleted_vector"] is True

        mock_km.delete_article.assert_called_once_with("111")

    def test_partial_delete_pg_only(self, client: TestClient) -> None:
        """PG deleted, ChromaDB not → HTTP 200 (not found -> partial still 200)."""
        mock_km = MagicMock()
        mock_km.delete_article.return_value = DeleteResultData(
            pmid="111", deleted_pg=True, deleted_vector=False
        )
        _inject_km_service(mock_km)

        resp = client.delete("/pubmed/articles/111")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["deleted_pg"] is True
        assert data["deleted_vector"] is False

    def test_both_not_found_returns_404(self, client: TestClient) -> None:
        """Neither PG nor ChromaDB has the PMID → HTTP 404."""
        mock_km = MagicMock()
        mock_km.delete_article.return_value = DeleteResultData(
            pmid="999", deleted_pg=False, deleted_vector=False
        )
        _inject_km_service(mock_km)

        resp = client.delete("/pubmed/articles/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_service_not_injected_returns_500(self, client: TestClient) -> None:
        """km service not injected → HTTP 500."""
        resp = client.delete("/pubmed/articles/111")
        assert resp.status_code == 500

    def test_service_raises_exception_returns_500(self, client: TestClient) -> None:
        """km.delete_article raises exception → HTTP 500."""
        mock_km = MagicMock()
        mock_km.delete_article.side_effect = RuntimeError("DB error")
        _inject_km_service(mock_km)

        resp = client.delete("/pubmed/articles/111")
        assert resp.status_code == 500
        assert "DB error" in resp.json()["detail"]
