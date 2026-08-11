"""Tests for infrastructure/persistence/document_retriever_impl.py."""

import os
from unittest.mock import MagicMock

import pytest

# Avoid chain import requiring real DASHSCOPE_API_KEY
if "DASHSCOPE_API_KEY" not in os.environ:
    os.environ["DASHSCOPE_API_KEY"] = "test-dummy-key"

from domain.entities.document import Document  # noqa: E402
from infrastructure.persistence.document_retriever_impl import (  # noqa: E402
    VectorDocumentRetriever,
)

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def retriever() -> VectorDocumentRetriever:
    """返回一个 VectorDocumentRetriever 实例，无需真实向量存储。"""
    mock_vs = MagicMock()
    return VectorDocumentRetriever(vector_store_service=mock_vs)


# ── T08: _format_local_citation with file suffix ─────────────────────────────

class TestFormatLocalCitation:
    """测试 _format_local_citation 静态方法。"""

    @pytest.mark.parametrize("source,ext,expected", [
        ("指南.docx", ".docx", "[1] 《指南》."),
        ("临床报告.doc", ".doc", "[2] 《临床报告》."),
        ("研究.pdf", ".pdf", "[3] 《研究》."),
        ("笔记.txt", ".txt", "[1] 《笔记》."),
    ])
    def test_with_file_extension(self, source, ext, expected):
        """T08: 传入带后缀的文件名 -> 输出去后缀的书名号格式。"""
        doc = Document(content="test content", metadata={"source": source})
        result = VectorDocumentRetriever._format_local_citation(
            doc, int(expected[1]),
        )
        assert result == expected

    @pytest.mark.parametrize("source,index,expected", [
        ("指南", 1, "[1] 《指南》."),
        ("Clinical Report 2024", 2, "[2] 《Clinical Report 2024》."),
        ("论文_final_v2", 3, "[3] 《论文_final_v2》."),
    ])
    def test_without_extension(self, source, index, expected):
        """T09: 传入无后缀的文件名 -> 直接放在书名号内。"""
        doc = Document(content="test", metadata={"source": source})
        result = VectorDocumentRetriever._format_local_citation(doc, index)
        assert result == expected

    def test_empty_source_uses_placeholder(self):
        """source 为空字符串时，使用参考资料的占位名。"""
        doc = Document(content="test", metadata={"source": ""})
        result = VectorDocumentRetriever._format_local_citation(doc, 5)
        assert result == "[5] 《参考资料5》."

    def test_no_source_key_uses_placeholder(self):
        """metadata 中没有 source 键时，使用参考资料的占位名。"""
        doc = Document(content="test", metadata={})
        result = VectorDocumentRetriever._format_local_citation(doc, 7)
        assert result == "[7] 《参考资料7》."

    def test_only_known_extensions_removed(self):
        """只移除已知后缀 (.docx/.doc/.pdf/.txt)，其他扩展名保留。"""
        doc = Document(content="test", metadata={"source": "文件.xlsx"})
        result = VectorDocumentRetriever._format_local_citation(doc, 1)
        assert result == "[1] 《文件.xlsx》."

    def test_false_positive_suffix_not_matched(self):
        """确保不会误匹配部分后缀。"""
        doc = Document(content="test", metadata={"source": "research.document"})
        result = VectorDocumentRetriever._format_local_citation(doc, 1)
        assert result == "[1] 《research.document》."


# ── T10-T11: _format_pubmed_citation ─────────────────────────────────────────

class TestFormatPubmedCitation:
    """测试 _format_pubmed_citation 静态方法。"""

    def test_complete_pubmed_metadata(self):
        """T10: 传入完整 pubmed metadata -> 输出温哥华格式引文。"""
        doc = Document(
            content="Abstract text here...",
            metadata={
                "source_type": "pubmed",
                "authors": "Baden LR, El Sahly HM, Essink B",
                "title": (
                    "Efficacy and Safety of the mRNA-1273 "
                    "SARS-CoV-2 Vaccine"
                ),
                "journal": "N Engl J Med",
                "publish_date": "2020-12-31",
                "pmid": "12345678",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 3)

        expected = (
            "[3] Baden LR, El Sahly HM, Essink B. "
            "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine. "
            "N Engl J Med. 2020. PMID: 12345678."
        )
        assert result == expected

    def test_missing_authors(self):
        """T11: 缺少 authors 字段 -> 跳过 authors 部分。"""
        doc = Document(
            content="Abstract...",
            metadata={
                "source_type": "pubmed",
                "title": "Test Title",
                "journal": "Test Journal",
                "publish_date": "2021-06-15",
                "pmid": "87654321",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 1)
        expected = "[1] Test Title. Test Journal. 2021. PMID: 87654321."
        assert result == expected

    def test_missing_journal(self):
        """缺少 journal 字段 -> 跳过 journal 部分。"""
        doc = Document(
            content="Abstract...",
            metadata={
                "source_type": "pubmed",
                "authors": "Author1",
                "title": "Title Only",
                "publish_date": "2022",
                "pmid": "11111",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 2)
        assert "Author1." in result
        assert "Title Only." in result
        assert "2022." in result
        assert "PMID: 11111." in result
        # Verify no standalone "Journal." appears
        assert " Journal. " not in result

    def test_missing_publish_date(self):
        """缺少 publish_date 字段 -> 跳过 year 部分。"""
        doc = Document(
            content="Abstract...",
            metadata={
                "source_type": "pubmed",
                "authors": "Smith J",
                "title": "No Date Paper",
                "journal": "Some Journal",
                "pmid": "22222",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 1)
        assert "Smith J." in result
        assert "No Date Paper." in result
        assert "Some Journal." in result
        assert "PMID: 22222." in result

    def test_missing_pmid(self):
        """缺少 pmid 字段 -> 跳过 PMID 部分。"""
        doc = Document(
            content="Abstract...",
            metadata={
                "source_type": "pubmed",
                "authors": "Lee C",
                "title": "No PMID Paper",
                "journal": "Biology Letters",
                "publish_date": "2019-03-01",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 5)
        assert "PMID:" not in result
        assert result.startswith("[5] Lee C.")

    def test_unknown_title_defaults_to_unknown(self):
        """title 缺失时使用 "Unknown Title"。"""
        doc = Document(
            content="Abstract...",
            metadata={
                "source_type": "pubmed",
                "authors": "Author X",
                "pmid": "99999",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 1)
        assert "Unknown Title." in result

    def test_empty_authors_string_is_skipped(self):
        """authors 为空字符串 -> 跳过 authors 部分。"""
        doc = Document(
            content="test",
            metadata={
                "source_type": "pubmed",
                "authors": "",
                "title": "Title Only",
                "journal": "Journal",
                "publish_date": "2020",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 1)
        assert result == "[1] Title Only. Journal. 2020."

    def test_date_without_year_part(self):
        """publish_date 长度不足 4 -> year 为空，跳过 year 部分。"""
        doc = Document(
            content="test",
            metadata={
                "source_type": "pubmed",
                "title": "Short Date",
                "authors": "Author",
                "journal": "Journal",
                "publish_date": "20",
                "pmid": "33333",
            },
        )
        result = VectorDocumentRetriever._format_pubmed_citation(doc, 1)
        assert "Author." in result
        assert "Short Date." in result
        assert "Journal." in result
        assert "PMID: 33333." in result


# ── T12: format_documents_for_context with mixed document types ───────────────

class TestFormatDocumentsForContext:
    """测试 format_documents_for_context 实例方法。"""

    def test_mixed_local_and_pubmed(self, retriever):
        """T12: 混合文档列表（1 local + 1 pubmed）-> 输出两种引文格式。"""
        local_doc = Document(
            content="Local file content.",
            metadata={
                "source": "临床指南.docx",
                "source_type": "local_file",
            },
        )
        pubmed_doc = Document(
            content="PubMed article content.",
            metadata={
                "source_type": "pubmed",
                "authors": "Smith J",
                "title": "Test Pubmed Article",
                "journal": "Test Journal",
                "publish_date": "2022-01-01",
                "pmid": "11111",
            },
        )
        docs = [local_doc, pubmed_doc]
        context = retriever.format_documents_for_context(docs)

        assert "[1] 《临床指南》." in context
        assert "Local file content." in context
        assert "Smith J." in context
        assert "Test Pubmed Article." in context
        assert "Test Journal." in context
        assert "2022." in context
        assert "PMID: 11111." in context
        assert "PubMed article content." in context

    def test_all_local_documents(self, retriever):
        """全部 local_file 文档 -> 全部用书名号格式。"""
        doc_a = Document(
            content="c1",
            metadata={"source": "a.pdf", "source_type": "local_file"},
        )
        doc_b = Document(
            content="c2",
            metadata={"source": "b.docx", "source_type": "local_file"},
        )
        context = retriever.format_documents_for_context([doc_a, doc_b])
        assert "[1] 《a》." in context
        assert "[2] 《b》." in context

    def test_all_pubmed_documents(self, retriever):
        """全部 pubmed 文档 -> 全部用温哥华格式。"""
        docs = [
            Document(
                content="c1",
                metadata={
                    "source_type": "pubmed",
                    "authors": "A1",
                    "title": "T1",
                    "pmid": "1",
                },
            ),
            Document(
                content="c2",
                metadata={
                    "source_type": "pubmed",
                    "authors": "A2",
                    "title": "T2",
                    "pmid": "2",
                },
            ),
        ]
        context = retriever.format_documents_for_context(docs)
        assert "[1] A1. T1. PMID: 1." in context
        assert "[2] A2. T2. PMID: 2." in context

    def test_backward_compat_no_source_type(self, retriever):
        """T06: source_type 不存在于 metadata -> 默认走 local_file 格式。"""
        doc = Document(
            content="old data content",
            metadata={"source": "旧文件.pdf"},
        )
        context = retriever.format_documents_for_context([doc])
        assert "[1] 《旧文件》." in context
        assert "old data content" in context

    def test_unknown_source_type_uses_local_format(self, retriever):
        """未知 source_type 值 -> 走 local_file 格式（向后兼容）。"""
        doc = Document(
            content="content",
            metadata={"source": "data.txt", "source_type": "unknown_type"},
        )
        context = retriever.format_documents_for_context([doc])
        assert "[1] 《data》." in context

    def test_preserves_document_content(self, retriever):
        """验证文档 content 被正确拼接到上下文中。"""
        docs = [
            Document(
                content="段落一：关键发现",
                metadata={"source": "report.docx"},
            ),
            Document(
                content="段落二：补充说明",
                metadata={"source": "notes.doc"},
            ),
        ]
        context = retriever.format_documents_for_context(docs)
        assert "段落一：关键发现" in context
        assert "段落二：补充说明" in context

    def test_sequential_numbering(self, retriever):
        """验证索引序号从 1 开始递增。"""
        docs = [
            Document(content="c1", metadata={"source": "f1.pdf"}),
            Document(content="c2", metadata={"source": "f2.pdf"}),
            Document(content="c3", metadata={"source": "f3.pdf"}),
        ]
        context = retriever.format_documents_for_context(docs)
        assert "[1] 《f1》." in context
        assert "[2] 《f2》." in context
        assert "[3] 《f3》." in context
