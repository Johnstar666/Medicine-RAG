"""Tests for KnowledgeManagementService."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from application.services.knowledge_management_service import (
    KnowledgeManagementService,
)
from schemas.knowledge import KnowledgeStatsData, VectorStoreInfo
from schemas.pubmed import (
    ArticleDetailData,
    ArticleListData,
    DeleteResultData,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    """Return a MagicMock configured as a fake PostgresDB."""
    return MagicMock()


@pytest.fixture
def mock_vs() -> MagicMock:
    """Return a MagicMock configured as a fake VectorStoreService."""
    mock = MagicMock()
    mock.get_collection_stats.return_value = {
        "total_chunks": 100,
        "by_source_type": {"local_file": 60, "pubmed": 40},
    }
    return mock


@pytest.fixture
def mock_ingester() -> MagicMock:
    """Return a MagicMock configured as a fake PubMedArticleIngester."""
    mock = MagicMock()
    mock.remove_from_vector_store.return_value = 3
    return mock


@pytest.fixture
def service(
    mock_db: MagicMock,
    mock_vs: MagicMock,
    mock_ingester: MagicMock,
) -> KnowledgeManagementService:
    """Build a KnowledgeManagementService with mocked dependencies."""
    return KnowledgeManagementService(mock_db, mock_vs, mock_ingester)


@pytest.fixture
def sample_pg_rows() -> list[dict]:
    """Return sample rows mimicking PostgresDB.list_articles() output."""
    return [
        {
            "pmid": "11111111",
            "article_info": {
                "title": "Test Vaccine Efficacy",
                "authors": ["Doe J", "Smith A"],
                "journal": "N Engl J Med",
                "publish_date": "2021-03-15",
                "abstract": "This is a long abstract " + "X " * 40,
            },
            "study_groups": ["vaccine", "placebo"],
            "objectives": "Evaluate efficacy",
            "is_free_download": True,
            "ingestion_status": "ingested",
            "ingested_at": None,
            "created_at": None,
        },
        {
            "pmid": "22222222",
            "article_info": {
                "title": "Another Drug Study",
                "authors": ["Lee C"],
                "journal": "Lancet",
                "publish_date": "2022-06-01",
                "abstract": "Short abstract.",
            },
            "study_groups": [],
            "objectives": "",
            "is_free_download": False,
            "ingestion_status": "uningested",
            "ingested_at": None,
            "created_at": None,
        },
    ]


@pytest.fixture
def sample_detail_row() -> dict:
    """Return a sample row mimicking PostgresDB.get_article_by_pmid() output."""
    return {
        "pmid": "11111111",
        "article_info": {
            "title": "Test Vaccine Efficacy",
            "authors": ["Doe J", "Smith A"],
            "journal": "N Engl J Med",
            "publish_date": "2021-03-15",
            "abstract": "This is a long abstract about vaccine efficacy.",
            "doi": "10.1234/test",
        },
        "study_groups": ["vaccine", "placebo"],
        "results_info": {
            "raw_abstract": "Vaccine efficacy 94.1%",
            "endpoints": "Efficacy",
        },
        "objectives": "Evaluate efficacy of mRNA vaccine",
        "is_free_download": True,
        "ingestion_status": "ingested",
        "chunk_count": 5,
        "vector_ids": ["id_a", "id_b"],
        "ingested_at": None,
        "created_at": None,
        "updated_at": None,
        "search_query": "COVID vaccine",
        "ingestion_error": None,
    }


# ===================================================================
# list_articles
# ===================================================================


class TestListArticles:
    """Tests for list_articles()."""

    def test_returns_correct_article_list_data(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        sample_pg_rows: list[dict],
    ) -> None:
        """T13: Mock DB returns prefab rows -> ArticleListData built correctly."""
        mock_db.list_articles.return_value = (sample_pg_rows, 2)

        result = service.list_articles(page=1, page_size=20)

        assert isinstance(result, ArticleListData)
        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 20
        assert len(result.articles) == 2

        # Verify first article mapping
        a0 = result.articles[0]
        assert a0.pmid == "11111111"
        assert a0.title == "Test Vaccine Efficacy"
        assert a0.authors == ["Doe J", "Smith A"]
        assert a0.journal == "N Engl J Med"
        assert a0.publish_date == "2021-03-15"
        assert len(a0.abstract_preview) <= 200
        assert a0.is_free_download is True
        assert a0.ingestion_status == "ingested"
        assert a0.study_groups == ["vaccine", "placebo"]

        # Verify second article mapping
        a1 = result.articles[1]
        assert a1.pmid == "22222222"
        assert a1.title == "Another Drug Study"
        assert a1.is_free_download is False
        assert a1.ingestion_status == "uningested"

    def test_page_zero_raises_value_error(
        self, service: KnowledgeManagementService
    ) -> None:
        """T14: page=0 raises ValueError."""
        with pytest.raises(ValueError, match="page must be >= 1"):
            service.list_articles(page=0)

    def test_negative_page_raises_value_error(
        self, service: KnowledgeManagementService
    ) -> None:
        """page < 1 raises ValueError."""
        with pytest.raises(ValueError, match="page must be >= 1"):
            service.list_articles(page=-1)

    def test_page_size_zero_raises_value_error(
        self, service: KnowledgeManagementService
    ) -> None:
        """page_size=0 raises ValueError."""
        with pytest.raises(
            ValueError, match="page_size must be between 1 and 100"
        ):
            service.list_articles(page_size=0)

    def test_page_size_over_100_raises_value_error(
        self, service: KnowledgeManagementService
    ) -> None:
        """page_size > 100 raises ValueError."""
        with pytest.raises(
            ValueError, match="page_size must be between 1 and 100"
        ):
            service.list_articles(page_size=101)

    def test_invalid_ingestion_status_raises_value_error(
        self, service: KnowledgeManagementService
    ) -> None:
        """invalid ingestion_status raises ValueError."""
        with pytest.raises(
            ValueError, match="invalid ingestion_status: unknown"
        ):
            service.list_articles(ingestion_status="unknown")

    def test_invalid_sort_by_raises_value_error(
        self, service: KnowledgeManagementService
    ) -> None:
        """invalid sort_by raises ValueError."""
        with pytest.raises(ValueError, match="invalid sort_by: invalid_col"):
            service.list_articles(sort_by="invalid_col")

    def test_invalid_order_raises_value_error(
        self, service: KnowledgeManagementService
    ) -> None:
        """invalid order raises ValueError."""
        with pytest.raises(ValueError, match="invalid order: unknown"):
            service.list_articles(order="unknown")

    def test_passes_search_to_db(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        sample_pg_rows: list[dict],
    ) -> None:
        """search parameter is forwarded to DB layer."""
        mock_db.list_articles.return_value = (sample_pg_rows[:1], 1)

        result = service.list_articles(search="vaccine")

        mock_db.list_articles.assert_called_once_with(
            page=1,
            page_size=20,
            search="vaccine",
            ingestion_status="all",
            sort_by="created_at",
            order="desc",
        )
        assert result.total == 1

    def test_passes_ingestion_status_to_db(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        sample_pg_rows: list[dict],
    ) -> None:
        """ingestion_status filter is forwarded to DB layer."""
        mock_db.list_articles.return_value = (sample_pg_rows[:1], 1)

        service.list_articles(ingestion_status="uningested")

        call_kwargs = mock_db.list_articles.call_args[1]
        assert call_kwargs["ingestion_status"] == "uningested"

    def test_passes_sort_and_order_to_db(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        sample_pg_rows: list[dict],
    ) -> None:
        """sort_by and order are forwarded to DB layer."""
        mock_db.list_articles.return_value = (sample_pg_rows, 2)

        service.list_articles(sort_by="pmid", order="asc")

        call_kwargs = mock_db.list_articles.call_args[1]
        assert call_kwargs["sort_by"] == "pmid"
        assert call_kwargs["order"] == "asc"

    def test_handler_non_existent_authors(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
    ) -> None:
        """Row missing authors field doesn't crash."""
        row = [
            {
                "pmid": "33333333",
                "article_info": {
                    "title": "Minimal Article",
                    "abstract": "Short abstract.",
                },
                "study_groups": [],
                "objectives": "",
                "is_free_download": False,
                "ingestion_status": "uningested",
                "ingested_at": None,
                "created_at": None,
            }
        ]
        mock_db.list_articles.return_value = (row, 1)

        result = service.list_articles()

        assert len(result.articles) == 1
        assert result.articles[0].authors == []

    def test_empty_result_set(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
    ) -> None:
        """Empty result set returns ArticleListData with zero total."""
        mock_db.list_articles.return_value = ([], 0)

        result = service.list_articles()

        assert result.total == 0
        assert result.articles == []
        assert result.page == 1


# ===================================================================
# get_article_detail
# ===================================================================


class TestGetArticleDetail:
    """Tests for get_article_detail()."""

    def test_existing_pmid_returns_article_detail(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        sample_detail_row: dict,
    ) -> None:
        """T15: Existing PMID returns correctly mapped ArticleDetailData."""
        mock_db.get_article_by_pmid.return_value = sample_detail_row

        result = service.get_article_detail("11111111")

        assert result is not None
        assert isinstance(result, ArticleDetailData)
        assert result.pmid == "11111111"
        assert result.article_info["title"] == "Test Vaccine Efficacy"
        assert result.study_groups == ["vaccine", "placebo"]
        assert result.results_info["raw_abstract"] == "Vaccine efficacy 94.1%"
        assert result.objectives == "Evaluate efficacy of mRNA vaccine"
        assert result.is_free_download is True
        assert result.ingestion_status == "ingested"
        assert result.chunk_count == 5
        assert result.vector_ids == ["id_a", "id_b"]
        assert result.search_query == "COVID vaccine"

    def test_nonexistent_pmid_returns_none(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
    ) -> None:
        """T16: Non-existing PMID returns None."""
        mock_db.get_article_by_pmid.return_value = None

        result = service.get_article_detail("nonexistent")

        assert result is None

    def test_article_info_none_defaults_to_empty_dict(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
    ) -> None:
        """T08: article_info=None defaults to {}."""
        row = {
            "pmid": "12345678",
            "article_info": None,
            "study_groups": None,
            "results_info": None,
            "objectives": None,
            "is_free_download": None,
            "ingestion_status": None,
        }
        mock_db.get_article_by_pmid.return_value = row

        result = service.get_article_detail("12345678")

        assert result is not None
        assert result.article_info == {}
        assert result.study_groups == []
        assert result.results_info == {}
        assert result.objectives == ""

    def test_results_info_none_defaults_to_empty_dict(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
    ) -> None:
        """T08: results_info=None defaults to {}."""
        row = {
            "pmid": "12345678",
            "article_info": {"title": "Test"},
            "study_groups": [],
            "results_info": None,
            "objectives": "Test objectives",
            "is_free_download": True,
            "ingestion_status": "ingested",
        }
        mock_db.get_article_by_pmid.return_value = row

        result = service.get_article_detail("12345678")

        assert result is not None
        assert result.results_info == {}

    def test_partial_fields_filled_correctly(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
    ) -> None:
        """Minimal row with only pmid and a few fields still works."""
        row = {
            "pmid": "minimal",
            "article_info": {"title": "Minimal"},
            "study_groups": [],
            "results_info": {},
            "objectives": "",
            "is_free_download": False,
            "ingestion_status": "uningested",
        }
        mock_db.get_article_by_pmid.return_value = row

        result = service.get_article_detail("minimal")

        assert result is not None
        assert result.pmid == "minimal"
        assert result.chunk_count is None
        assert result.vector_ids is None
        assert result.ingested_at is None
        assert result.ingestion_error is None


# ===================================================================
# delete_article
# ===================================================================


class TestDeleteArticle:
    """Tests for delete_article()."""

    def test_both_succeed(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_ingester: MagicMock,
    ) -> None:
        """T17: Both PG and vector deletion succeed."""
        mock_db.delete_article.return_value = True
        mock_ingester.remove_from_vector_store.return_value = 3

        result = service.delete_article("11111111")

        assert isinstance(result, DeleteResultData)
        assert result.pmid == "11111111"
        assert result.deleted_pg is True
        assert result.deleted_vector is True
        mock_ingester.remove_from_vector_store.assert_called_once_with(
            "11111111"
        )
        mock_db.delete_article.assert_called_once_with("11111111")

    def test_pg_fails_vector_succeeds(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_ingester: MagicMock,
    ) -> None:
        """T18: PG exception -> deleted_pg=False, deleted_vector=True."""
        mock_db.delete_article.side_effect = RuntimeError("PG down")
        mock_ingester.remove_from_vector_store.return_value = 5

        result = service.delete_article("11111111")

        assert result.deleted_pg is False
        assert result.deleted_vector is True
        # PG was attempted
        mock_db.delete_article.assert_called_once_with("11111111")

    def test_vector_fails_pg_succeeds(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_ingester: MagicMock,
    ) -> None:
        """Vector deletion raises exception -> deleted_vector=False, deleted_pg=True."""
        mock_db.delete_article.return_value = True
        mock_ingester.remove_from_vector_store.side_effect = RuntimeError(
            "ChromaDB down"
        )

        result = service.delete_article("11111111")

        assert result.deleted_vector is False
        assert result.deleted_pg is True
        mock_db.delete_article.assert_called_once_with("11111111")

    def test_both_fail(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_ingester: MagicMock,
    ) -> None:
        """Both PG and vector deletion raise exceptions."""
        mock_db.delete_article.side_effect = RuntimeError("PG down")
        mock_ingester.remove_from_vector_store.side_effect = RuntimeError(
            "VS down"
        )

        result = service.delete_article("11111111")

        assert result.deleted_pg is False
        assert result.deleted_vector is False

    def test_vector_delete_zero_chunks_still_false(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_ingester: MagicMock,
    ) -> None:
        """remove_from_vector_store returns 0 -> deleted_vector=False."""
        mock_db.delete_article.return_value = True
        mock_ingester.remove_from_vector_store.return_value = 0

        result = service.delete_article("11111111")

        assert result.deleted_vector is False
        assert result.deleted_pg is True

    def test_pg_delete_returns_false(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_ingester: MagicMock,
    ) -> None:
        """delete_article returns False (PMID not found) -> deleted_pg=False."""
        mock_db.delete_article.return_value = False
        mock_ingester.remove_from_vector_store.return_value = 3

        result = service.delete_article("nonexistent")

        assert result.deleted_pg is False
        assert result.deleted_vector is True


# ===================================================================
# get_knowledge_stats
# ===================================================================


class TestGetKnowledgeStats:
    """Tests for get_knowledge_stats()."""

    def test_aggregates_all_data_sources(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_vs: MagicMock,
    ) -> None:
        """T19: Mock all data sources -> verify KnowledgeStatsData aggregation."""
        mock_db.count_articles_by_status.return_value = {
            "total": 50,
            "ingested": 40,
            "uningested": 8,
            "failed": 2,
        }
        mock_vs.get_collection_stats.return_value = {
            "total_chunks": 200,
            "by_source_type": {"local_file": 120, "pubmed": 80},
        }

        # Patch local document count to avoid filesystem dependency
        with patch.object(
            service,
            "_get_local_document_count",
            return_value=15,
        ):
            result = service.get_knowledge_stats()

        assert isinstance(result, KnowledgeStatsData)
        assert result.local_documents == 15
        assert result.pubmed_articles_total == 50
        assert result.pubmed_articles_ingested == 40
        assert result.pubmed_articles_uningested == 8
        assert result.total_vector_chunks == 200
        assert result.by_source_type == {"local_file": 120, "pubmed": 80}
        assert isinstance(result.vector_store, VectorStoreInfo)

    def test_vector_store_info_uses_config_values(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_vs: MagicMock,
    ) -> None:
        """VectorStoreInfo is built from config values."""
        mock_db.count_articles_by_status.return_value = {
            "total": 0,
            "ingested": 0,
            "uningested": 0,
            "failed": 0,
        }
        mock_vs.get_collection_stats.return_value = {
            "total_chunks": 0,
            "by_source_type": {},
        }

        with patch.object(service, "_get_local_document_count", return_value=0):
            result = service.get_knowledge_stats()

        assert result.vector_store.collection_name != ""
        assert result.vector_store.storage_path != ""
        assert result.vector_store.embedding_model != ""

    def test_empty_stats_default_to_zero(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_vs: MagicMock,
    ) -> None:
        """Empty stats from all sources default to zero."""
        mock_db.count_articles_by_status.return_value = {
            "total": 0,
            "ingested": 0,
            "uningested": 0,
            "failed": 0,
        }
        mock_vs.get_collection_stats.return_value = {
            "total_chunks": 0,
            "by_source_type": {},
        }

        with patch.object(service, "_get_local_document_count", return_value=0):
            result = service.get_knowledge_stats()

        assert result.local_documents == 0
        assert result.pubmed_articles_total == 0
        assert result.pubmed_articles_ingested == 0
        assert result.total_vector_chunks == 0
        assert result.by_source_type == {}

    def test_counts_by_status_map(
        self,
        service: KnowledgeManagementService,
        mock_db: MagicMock,
        mock_vs: MagicMock,
    ) -> None:
        """count_articles_by_status values map correctly to KnowledgeStatsData."""
        mock_db.count_articles_by_status.return_value = {
            "total": 15,
            "ingested": 12,
            "uningested": 2,
            "failed": 1,
        }
        mock_vs.get_collection_stats.return_value = {
            "total_chunks": 55,
            "by_source_type": {"local_file": 30, "pubmed": 25},
        }

        with patch.object(service, "_get_local_document_count", return_value=99):
            result = service.get_knowledge_stats()

        assert result.pubmed_articles_total == 15
        assert result.pubmed_articles_ingested == 12
        assert result.pubmed_articles_uningested == 2
        # total_vector_chunks is 55, not from PG total
        assert result.total_vector_chunks == 55


# ===================================================================
# _get_local_document_count
# ===================================================================


class TestGetLocalDocumentCount:
    """Tests for _get_local_document_count()."""

    def test_counts_files_in_directory(
        self,
        service: KnowledgeManagementService,
    ) -> None:
        """Files with allowed extensions are counted correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            allowed_files = ["doc1.pdf", "doc2.txt", "doc3.docx"]
            disallowed_files = ["image.png", "data.csv"]

            for f in allowed_files + disallowed_files:
                path = os.path.join(tmpdir, f)
                with open(path, "w") as fh:
                    fh.write("test")

            with patch(
                "application.services.knowledge_management_service.get_abs_path",
                return_value=tmpdir,
            ):
                with patch.dict(
                    "application.services.knowledge_management_service.chroma_conf",
                    {
                        "data_path": tmpdir,
                        "allow_knowledge_file_type": ["pdf", "txt", "docx", "doc"],
                    },
                ):
                    count = service._get_local_document_count()
                    assert count == 3

    def test_directory_not_exists_returns_zero(
        self,
        service: KnowledgeManagementService,
    ) -> None:
        """Non-existing directory returns 0 with a WARNING log."""
        with patch(
            "application.services.knowledge_management_service.get_abs_path",
            return_value="/nonexistent/path/12345",
        ):
            count = service._get_local_document_count()
            assert count == 0

    def test_empty_directory_returns_zero(
        self,
        service: KnowledgeManagementService,
    ) -> None:
        """Empty directory returns 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "application.services.knowledge_management_service.get_abs_path",
                return_value=tmpdir,
            ):
                with patch.dict(
                    "application.services.knowledge_management_service.chroma_conf",
                    {
                        "data_path": tmpdir,
                        "allow_knowledge_file_type": ["pdf", "txt"],
                    },
                ):
                    count = service._get_local_document_count()
                    assert count == 0

    def test_no_matching_extensions_returns_zero(
        self,
        service: KnowledgeManagementService,
    ) -> None:
        """Directory with only disallowed file types returns 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for f in ["image.png", "data.csv"]:
                path = os.path.join(tmpdir, f)
                with open(path, "w") as fh:
                    fh.write("test")

            with patch(
                "application.services.knowledge_management_service.get_abs_path",
                return_value=tmpdir,
            ):
                with patch.dict(
                    "application.services.knowledge_management_service.chroma_conf",
                    {
                        "data_path": tmpdir,
                        "allow_knowledge_file_type": ["pdf", "txt"],
                    },
                ):
                    count = service._get_local_document_count()
                    assert count == 0

    def test_empty_allow_list_counts_nothing(
        self,
        service: KnowledgeManagementService,
    ) -> None:
        """Empty allow_knowledge_file_type list results in 0 count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.pdf")
            with open(path, "w") as fh:
                fh.write("test")

            with patch(
                "application.services.knowledge_management_service.get_abs_path",
                return_value=tmpdir,
            ):
                with patch.dict(
                    "application.services.knowledge_management_service.chroma_conf",
                    {
                        "data_path": tmpdir,
                        "allow_knowledge_file_type": [],
                    },
                ):
                    count = service._get_local_document_count()
                    assert count == 0

    def test_files_without_extension_ignored(
        self,
        service: KnowledgeManagementService,
    ) -> None:
        """Files without an extension are not counted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "noextension")
            with open(path, "w") as fh:
                fh.write("test")

            with patch(
                "application.services.knowledge_management_service.get_abs_path",
                return_value=tmpdir,
            ):
                with patch.dict(
                    "application.services.knowledge_management_service.chroma_conf",
                    {
                        "data_path": tmpdir,
                        "allow_knowledge_file_type": ["pdf", "txt"],
                    },
                ):
                    count = service._get_local_document_count()
                    assert count == 0
