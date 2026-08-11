"""Tests for PubMedArticleIngester."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

import pytest

from infrastructure.persistence.pubmed_ingester import (
    IngestResult,
    PubMedArticleIngester,
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
    mock_splitter = MagicMock()
    mock_splitter.split_text.return_value = ["chunk 1", "chunk 2", "chunk 3"]
    mock.get_splitter.return_value = mock_splitter
    mock.add_documents_direct.return_value = ["id_1", "id_2", "id_3"]
    mock.delete_by_metadata_filter.return_value = 3
    return mock


@pytest.fixture
def ingester(mock_db: MagicMock, mock_vs: MagicMock) -> PubMedArticleIngester:
    """Build a PubMedArticleIngester with mocked dependencies."""
    return PubMedArticleIngester(mock_db, mock_vs)


@pytest.fixture
def complete_article() -> dict:
    """Return a complete article dict matching the PG schema."""
    return {
        "pmid": "12345678",
        "article_info": {
            "title": "Efficacy and Safety of mRNA-1273 SARS-CoV-2 Vaccine",
            "authors": ["Baden LR", "El Sahly HM", "Essink B"],
            "abstract": (
                "BACKGROUND: Vaccination is critical. "
                "METHODS: Randomized trial. "
                "RESULTS: 94.1% efficacy. "
                "CONCLUSIONS: Safe and effective."
            ),
            "journal": "N Engl J Med",
            "doi": "10.1056/NEJMoa2035389",
            "publish_date": "2020-12-31",
        },
        "study_groups": ["vaccine group", "placebo group"],
        "results_info": {
            "raw_abstract": (
                "BACKGROUND: Vaccination is critical. "
                "RESULTS: 94.1% efficacy."
            ),
        },
        "objectives": "To evaluate efficacy and safety of mRNA-1273",
        "is_free_download": True,
        "ingestion_status": "uningested",
    }


@pytest.fixture
def ingested_article(complete_article: dict) -> dict:
    """Return an article that is already marked as ingested."""
    article = dict(complete_article)
    article["ingestion_status"] = "ingested"
    article["chunk_count"] = 5
    return article


# ===================================================================
# IngestResult dataclass
# ===================================================================


class TestIngestResult:
    """Tests for the IngestResult dataclass."""

    def test_default_values(self) -> None:
        result = IngestResult(pmid="1", status="ingested")
        assert result.pmid == "1"
        assert result.status == "ingested"
        assert result.chunk_count == 0
        assert result.reason == ""
        assert result.vector_ids == []

    def test_full_construction(self) -> None:
        result = IngestResult(
            pmid="2",
            status="failed",
            chunk_count=0,
            reason="something went wrong",
            vector_ids=[],
        )
        assert result.pmid == "2"
        assert result.status == "failed"
        assert result.reason == "something went wrong"

    def test_vector_ids_default_is_distinct_per_instance(self) -> None:
        r1 = IngestResult(pmid="a", status="ingested")
        r2 = IngestResult(pmid="b", status="ingested")
        r1.vector_ids.append("id_x")
        assert r2.vector_ids == []


# ===================================================================
# _build_article_text
# ===================================================================


class TestBuildArticleText:
    """Tests for _build_article_text()."""

    def test_complete_article_produces_all_sections(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        text = ingester._build_article_text(complete_article)

        assert "[PubMed Article]" in text
        assert "Title: Efficacy and Safety of mRNA-1273 SARS-CoV-2 Vaccine" in text
        assert "Authors: Baden LR, El Sahly HM, Essink B" in text
        assert "Journal: N Engl J Med" in text
        assert "Publication Date: 2020-12-31" in text
        assert "DOI: 10.1056/NEJMoa2035389" in text
        assert "PMID: 12345678" in text
        assert "Research Objectives:" in text
        assert "To evaluate efficacy and safety of mRNA-1273" in text
        assert "Study Groups:" in text
        assert "vaccine group, placebo group" in text
        assert "Key Results:" in text
        assert "Abstract:" in text
        assert "BACKGROUND: Vaccination is critical." in text

    def test_authors_empty_shows_na(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        article = dict(complete_article)
        article["article_info"]["authors"] = []  # type: ignore[index]

        text = ingester._build_article_text(article)

        assert "Authors: N/A" in text

    def test_study_groups_empty_shows_na(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        article = dict(complete_article)
        article["study_groups"] = []

        text = ingester._build_article_text(article)

        assert "Study Groups:\nN/A" in text

    def test_minimal_article_does_not_crash(
        self, ingester: PubMedArticleIngester
    ) -> None:
        article: dict = {"pmid": "99"}
        text = ingester._build_article_text(article)
        assert isinstance(text, str)
        assert "PMID: 99" in text
        assert "Authors: N/A" in text

    def test_missing_article_info_does_not_crash(
        self, ingester: PubMedArticleIngester
    ) -> None:
        article: dict = {"pmid": "100", "article_info": None}
        text = ingester._build_article_text(article)
        assert isinstance(text, str)

    def test_returns_stripped_text(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        text = ingester._build_article_text(complete_article)
        assert text == text.strip()


# ===================================================================
# _build_chunk_metadata
# ===================================================================


class TestBuildChunkMetadata:
    """Tests for _build_chunk_metadata()."""

    def test_metadata_has_all_required_fields(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        meta = ingester._build_chunk_metadata(complete_article, 0, 5)

        assert meta["source"] == (
            "PMID:12345678: "
            "Efficacy and Safety of mRNA-1273 SARS-CoV-2 Vaccine"
        )
        assert meta["source_type"] == "pubmed"
        assert meta["pmid"] == "12345678"
        assert meta["title"] == (
            "Efficacy and Safety of mRNA-1273 SARS-CoV-2 Vaccine"
        )
        assert meta["authors"] == "Baden LR, El Sahly HM, Essink B"
        assert meta["journal"] == "N Engl J Med"
        assert meta["publish_date"] == "2020-12-31"
        assert meta["doi"] == "10.1056/NEJMoa2035389"
        assert meta["is_free_download"] is True
        assert meta["chunk_index"] == 0
        assert meta["total_chunks"] == 5

    def test_source_truncates_title_at_80_chars(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        article = dict(complete_article)
        article["article_info"]["title"] = "A" * 120  # type: ignore[index]

        meta = ingester._build_chunk_metadata(article, 0, 1)

        expected_source = f"PMID:12345678: {'A' * 80}"
        assert meta["source"] == expected_source
        assert len(meta["source"]) <= 80 + len("PMID:12345678: ")

    def test_authors_truncated_at_5_plus_et_al(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        article = dict(complete_article)
        article["article_info"]["authors"] = [  # type: ignore[index]
            "A1", "A2", "A3", "A4", "A5", "A6", "A7"
        ]

        meta = ingester._build_chunk_metadata(article, 2, 10)

        assert meta["authors"] == "A1, A2, A3, A4, A5, et al."

    def test_chunk_index_and_total_correct(
        self, ingester: PubMedArticleIngester, complete_article: dict
    ) -> None:
        meta = ingester._build_chunk_metadata(complete_article, 3, 10)

        assert meta["chunk_index"] == 3
        assert meta["total_chunks"] == 10


# ===================================================================
# ingest_article
# ===================================================================


class TestIngestArticle:
    """Tests for ingest_article()."""

    def test_normal_path_produces_ingested_result(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        mock_vs: MagicMock,
        complete_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = complete_article

        result = ingester.ingest_article("12345678")

        assert result.status == "ingested"
        assert result.chunk_count == 3  # 3 chunks from mock splitter
        assert result.vector_ids == ["id_1", "id_2", "id_3"]
        assert result.reason == ""

        # Verify PG status updates
        mock_db.update_ingestion_status.assert_any_call(
            "12345678", "ingesting"
        )
        mock_db.update_ingestion_status.assert_any_call(
            "12345678",
            "ingested",
            chunk_count=3,
            vector_ids=["id_1", "id_2", "id_3"],
        )

    def test_idempotent_already_ingested(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        ingested_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = ingested_article

        result = ingester.ingest_article("12345678")

        assert result.status == "already_ingested"
        assert result.chunk_count == 5  # from the article's chunk_count
        # Should NOT have called update_ingestion_status or add_documents
        mock_db.update_ingestion_status.assert_not_called()

    def test_force_reindex_removes_old_then_indexes(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        mock_vs: MagicMock,
        ingested_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = ingested_article

        result = ingester.ingest_article("12345678", force=True)

        assert result.status == "ingested"
        # Verify old vectors were removed
        mock_vs.delete_by_metadata_filter.assert_called_once_with(
            {"pmid": "12345678"}
        )
        # Then normal ingest proceeds
        mock_db.update_ingestion_status.assert_any_call(
            "12345678", "ingesting"
        )

    def test_force_on_uningested_skips_remove(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        mock_vs: MagicMock,
        complete_article: dict,
    ) -> None:
        """force=True on an uningested article should NOT call remove."""
        mock_db.get_article_by_pmid.return_value = complete_article

        result = ingester.ingest_article("12345678", force=True)

        assert result.status == "ingested"
        mock_vs.delete_by_metadata_filter.assert_not_called()

    def test_pmid_not_found_returns_failed(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = None

        result = ingester.ingest_article("nonexistent")

        assert result.status == "failed"
        assert "not found" in result.reason
        assert result.chunk_count == 0

    def test_empty_text_returns_failed(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        complete_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = complete_article
        # Make _build_article_text return empty
        ingester._build_article_text = MagicMock(return_value="")  # type: ignore[method-assign]

        result = ingester.ingest_article("12345678")

        assert result.status == "failed"
        assert "Empty" in result.reason
        mock_db.update_ingestion_status.assert_any_call(
            "12345678",
            "failed",
            error="Empty article text after building template",
        )

    def test_no_chunks_returns_failed(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        mock_vs: MagicMock,
        complete_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = complete_article
        mock_vs.get_splitter.return_value.split_text.return_value = []

        result = ingester.ingest_article("12345678")

        assert result.status == "failed"
        assert "No chunks" in result.reason
        mock_db.update_ingestion_status.assert_any_call(
            "12345678",
            "failed",
            error="No chunks produced",
        )

    def test_chromadb_write_failure_updates_pg_to_failed(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        mock_vs: MagicMock,
        complete_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = complete_article
        mock_vs.add_documents_direct.side_effect = RuntimeError(
            "ChromaDB connection lost"
        )

        result = ingester.ingest_article("12345678")

        assert result.status == "failed"
        assert "ChromaDB connection lost" in result.reason
        # PG should have been updated to failed
        mock_db.update_ingestion_status.assert_any_call(
            "12345678", "failed", error="ChromaDB connection lost"
        )

    def test_exception_during_pg_fallback_is_handled(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        mock_vs: MagicMock,
        complete_article: dict,
    ) -> None:
        """When the main operation fails AND the PG fallback also fails,
        the method still returns a failed IngestResult."""
        mock_db.get_article_by_pmid.return_value = complete_article
        mock_vs.add_documents_direct.side_effect = RuntimeError("boom")

        # Allow the "ingesting" update to succeed, but fail the
        # subsequent fallback update (which carries an "error" kwarg).
        def side_effect(*args: object, **kwargs: object) -> None:
            if kwargs.get("error"):
                raise RuntimeError("pg also down")
            return None

        mock_db.update_ingestion_status.side_effect = side_effect

        result = ingester.ingest_article("12345678")

        assert result.status == "failed"
        assert "boom" in result.reason


# ===================================================================
# batch_ingest
# ===================================================================


class TestBatchIngest:
    """Tests for batch_ingest()."""

    def test_all_succeed(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        complete_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = complete_article

        results = ingester.batch_ingest(["1", "2", "3"])

        assert len(results) == 3
        assert all(r.status == "ingested" for r in results)

    def test_second_fails_does_not_affect_others(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        complete_article: dict,
    ) -> None:
        """The 2nd article fails; the 1st and 3rd still succeed."""
        responses = {
            "1": complete_article,
            "2": None,  # not found -> failed
            "3": complete_article,
        }
        mock_db.get_article_by_pmid.side_effect = (
            lambda pmid: responses.get(pmid)
        )

        results = ingester.batch_ingest(["1", "2", "3"])

        assert len(results) == 3
        assert results[0].status == "ingested"
        assert results[1].status == "failed"
        assert results[2].status == "ingested"

    def test_force_flag_passed_through(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        mock_vs: MagicMock,
        ingested_article: dict,
    ) -> None:
        mock_db.get_article_by_pmid.return_value = ingested_article

        results = ingester.batch_ingest(["1"], force=True)

        assert results[0].status == "ingested"
        # remove should have been called because force=True
        mock_vs.delete_by_metadata_filter.assert_called_once_with(
            {"pmid": "1"}
        )

    def test_empty_list_returns_empty(
        self, ingester: PubMedArticleIngester
    ) -> None:
        results = ingester.batch_ingest([])
        assert results == []


# ===================================================================
# ingest_all_uningested
# ===================================================================


class TestIngestAllUnigested:
    """Tests for ingest_all_uningested()."""

    def test_queries_uningested_and_failed(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
        complete_article: dict,
    ) -> None:
        mock_db.list_articles.side_effect = [
            (
                [{"pmid": "1"}, {"pmid": "2"}],  # uningested
                2,
            ),
            (
                [{"pmid": "3"}],  # failed
                1,
            ),
        ]
        mock_db.get_article_by_pmid.return_value = complete_article

        results = ingester.ingest_all_uningested()

        assert len(results) == 3
        # Verify list_articles was called for both statuses
        assert mock_db.list_articles.call_count == 2
        mock_db.list_articles.assert_any_call(
            page=1, page_size=9999, ingestion_status="uningested"
        )
        mock_db.list_articles.assert_any_call(
            page=1, page_size=9999, ingestion_status="failed"
        )

    def test_no_articles_returns_empty(
        self,
        ingester: PubMedArticleIngester,
        mock_db: MagicMock,
    ) -> None:
        mock_db.list_articles.return_value = ([], 0)

        results = ingester.ingest_all_uningested()

        assert results == []


# ===================================================================
# remove_from_vector_store
# ===================================================================


class TestRemoveFromVectorStore:
    """Tests for remove_from_vector_store()."""

    def test_deletes_and_returns_count(
        self,
        ingester: PubMedArticleIngester,
        mock_vs: MagicMock,
    ) -> None:
        mock_vs.delete_by_metadata_filter.return_value = 5

        result = ingester.remove_from_vector_store("12345678")

        assert result == 5
        mock_vs.delete_by_metadata_filter.assert_called_once_with(
            {"pmid": "12345678"}
        )

    def test_returns_zero_when_nothing_deleted(
        self,
        ingester: PubMedArticleIngester,
        mock_vs: MagicMock,
    ) -> None:
        mock_vs.delete_by_metadata_filter.return_value = 0

        result = ingester.remove_from_vector_store("nonexistent")

        assert result == 0

    def test_raises_on_vs_error(
        self,
        ingester: PubMedArticleIngester,
        mock_vs: MagicMock,
    ) -> None:
        mock_vs.delete_by_metadata_filter.side_effect = RuntimeError(
            "vector store down"
        )

        with pytest.raises(RuntimeError, match="vector store down"):
            ingester.remove_from_vector_store("12345678")
