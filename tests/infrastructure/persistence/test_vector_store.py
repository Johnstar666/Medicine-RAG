"""Tests for VectorStoreService new methods: add_documents_direct,
delete_by_metadata_filter, get_collection_stats, get_splitter."""
import os
from unittest.mock import MagicMock, patch

# Ensure a dummy DashScope API key is set before module-level imports that
# instantiate the embedding model.
os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

import pytest
from langchain_core.documents import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from infrastructure.persistence.vector_store import VectorStoreService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_chroma():
    """Return a MagicMock configured as a fake Chroma instance."""
    mock = MagicMock()
    mock._collection.count.return_value = 100
    mock.get.return_value = {"ids": [], "metadatas": []}
    mock.add_documents.return_value = ["id_1", "id_2"]
    mock.delete.return_value = None
    return mock


@pytest.fixture
def vector_store_with_mock(mock_chroma):
    """Build a VectorStoreService whose vector_store is the mock Chroma."""
    with patch(
        "infrastructure.persistence.vector_store.Chroma",
        return_value=mock_chroma,
    ), patch(
        "infrastructure.persistence.vector_store.embed_model",
        MagicMock(),
    ):
        return VectorStoreService()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_docs(n: int = 2) -> list[LangchainDocument]:
    """Return *n* simple LangchainDocument instances."""
    docs: list[LangchainDocument] = []
    for i in range(n):
        docs.append(
            LangchainDocument(
                page_content=f"test content {i}",
                metadata={"pmid": f"pmid_{i}", "source_type": "test"},
            )
        )
    return docs


# ===================================================================
# add_documents_direct
# ===================================================================

class TestAddDocumentsDirect:
    def test_returns_ids_on_success(self, vector_store_with_mock, mock_chroma):
        docs = _make_docs(3)
        mock_chroma.add_documents.return_value = ["a", "b", "c"]

        result = vector_store_with_mock.add_documents_direct(docs)

        assert result == ["a", "b", "c"]
        mock_chroma.add_documents.assert_called_once_with(docs)

    def test_raises_on_chromadb_write_failure(
        self, vector_store_with_mock, mock_chroma
    ):
        docs = _make_docs()
        mock_chroma.add_documents.side_effect = RuntimeError("chroma down")

        with pytest.raises(RuntimeError, match="chroma down"):
            vector_store_with_mock.add_documents_direct(docs)


# ===================================================================
# delete_by_metadata_filter
# ===================================================================

class TestDeleteByMetadataFilter:
    def test_deletes_and_returns_count(self, vector_store_with_mock, mock_chroma):
        mock_chroma.get.return_value = {"ids": ["id_a", "id_b"], "metadatas": [{}, {}]}

        result = vector_store_with_mock.delete_by_metadata_filter(
            {"pmid": "test123"}
        )

        assert result == 2
        mock_chroma.get.assert_called_once_with(where={"pmid": "test123"})
        mock_chroma.delete.assert_called_once_with(ids=["id_a", "id_b"])

    def test_returns_zero_when_no_match(
        self, vector_store_with_mock, mock_chroma
    ):
        mock_chroma.get.return_value = {"ids": [], "metadatas": []}

        result = vector_store_with_mock.delete_by_metadata_filter(
            {"pmid": "nonexistent"}
        )

        assert result == 0
        mock_chroma.delete.assert_not_called()

    def test_raises_on_chromadb_get_failure(
        self, vector_store_with_mock, mock_chroma
    ):
        mock_chroma.get.side_effect = RuntimeError("get error")

        with pytest.raises(RuntimeError, match="get error"):
            vector_store_with_mock.delete_by_metadata_filter({"pmid": "123"})


# ===================================================================
# get_collection_stats
# ===================================================================

class TestGetCollectionStats:
    def test_returns_stats_normal_path(self, vector_store_with_mock, mock_chroma):
        mock_chroma._collection.count.return_value = 42
        mock_chroma.get.return_value = {
            "ids": ["1", "2", "3"],
            "metadatas": [
                {"source_type": "local_file"},
                {"source_type": "pubmed"},
                {"source_type": "local_file"},
            ],
        }

        result = vector_store_with_mock.get_collection_stats()

        assert result["total_chunks"] == 42
        assert result["by_source_type"] == {"local_file": 2, "pubmed": 1}

    def test_fallback_when_get_raises(self, vector_store_with_mock, mock_chroma):
        mock_chroma._collection.count.return_value = 200
        mock_chroma.get.side_effect = RuntimeError("too many docs")

        result = vector_store_with_mock.get_collection_stats()

        assert result["total_chunks"] == 200
        assert result["by_source_type"] == {"local_file": -1, "pubmed": -1}

    def test_returns_zero_when_count_raises(
        self, vector_store_with_mock, mock_chroma
    ):
        mock_chroma._collection.count.side_effect = RuntimeError("count error")

        result = vector_store_with_mock.get_collection_stats()

        assert result == {"total_chunks": 0, "by_source_type": {}}

    def test_defaults_missing_source_type_to_local_file(
        self, vector_store_with_mock, mock_chroma
    ):
        mock_chroma._collection.count.return_value = 1
        mock_chroma.get.return_value = {
            "ids": ["1"],
            "metadatas": [{}],  # no source_type key
        }

        result = vector_store_with_mock.get_collection_stats()

        assert result["by_source_type"]["local_file"] == 1
        assert result["by_source_type"]["pubmed"] == 0


# ===================================================================
# get_splitter
# ===================================================================

class TestGetSplitter:
    def test_pubmed_returns_recursive_splitter(self, vector_store_with_mock):
        splitter = vector_store_with_mock.get_splitter(source_type="pubmed")

        assert isinstance(splitter, RecursiveCharacterTextSplitter)
        # The splitter should use pubmed-specific config values
        assert splitter._chunk_size is not None
        assert splitter._chunk_overlap is not None

    def test_local_file_returns_recursive_splitter(self, vector_store_with_mock):
        splitter = vector_store_with_mock.get_splitter(source_type="local_file")

        assert isinstance(splitter, RecursiveCharacterTextSplitter)
        assert splitter._chunk_size is not None
        assert splitter._chunk_overlap is not None

    def test_default_source_type_is_local_file(self, vector_store_with_mock):
        splitter = vector_store_with_mock.get_splitter()

        assert isinstance(splitter, RecursiveCharacterTextSplitter)

    def test_pubmed_splitter_can_split_text(self, vector_store_with_mock):
        splitter = vector_store_with_mock.get_splitter(source_type="pubmed")
        text = "Sentence one. Sentence two. Sentence three."

        chunks = splitter.split_text(text)

        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)


# ===================================================================
# Existing methods remain unchanged
# ===================================================================

class TestExistingMethodsUnchanged:
    """Sanity checks that __init__ / get_retriever / load_document are intact."""

    def test_init_still_sets_spliter(self, vector_store_with_mock):
        assert vector_store_with_mock.spliter is not None
        assert isinstance(
            vector_store_with_mock.spliter, RecursiveCharacterTextSplitter
        )

    def test_get_retriever_works(self, vector_store_with_mock, mock_chroma):
        mock_retriever = MagicMock()
        mock_chroma.as_retriever.return_value = mock_retriever

        retriever = vector_store_with_mock.get_retriever()

        assert retriever is mock_retriever
