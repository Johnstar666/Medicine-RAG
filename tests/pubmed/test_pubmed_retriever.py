"""Tests for pubmed/pubmed_retriever.py — PubMed 检索器。

测试覆盖:
    - 所有 9 个静态辅助方法（含新增 _get_pmc_id）
    - fetch_article_details() 重构后的完整返回结构
    - search_pubmed() 搜索功能
    - 边界和异常情况
"""

from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────────
# Mock helpers for Bio.Entrez StringElement
# ──────────────────────────────────────────────────────────────


class MockStringElement(str):
    """Mock Bio.Entrez StringElement with .attributes dict."""

    def __new__(cls, value, attributes=None):
        obj = str.__new__(cls, value)
        obj.attributes = attributes or {}
        return obj


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_article_ids():
    """返回一个模拟的 ArticleIdList，含 DOI 和 PMC ID。"""
    return [
        MockStringElement("10.1056/NEJMoa2035389", {"IdType": "doi"}),
        MockStringElement("PMC7717217", {"IdType": "pmc"}),
        MockStringElement("33301246", {"IdType": "pubmed"}),
    ]


@pytest.fixture
def mock_article_ids_no_pmc():
    """返回没有 PMC ID 的 ArticleIdList。"""
    return [
        MockStringElement("10.1234/example", {"IdType": "doi"}),
        MockStringElement("12345678", {"IdType": "pubmed"}),
    ]


@pytest.fixture
def mock_author_list():
    """返回一个模拟的 AuthorList。"""
    return [
        {"LastName": "Baden", "ForeName": "LR"},
        {"LastName": "El Sahly", "ForeName": "HM"},
        {"LastName": "Essink", "ForeName": "B"},
    ]


@pytest.fixture
def mock_abstract_data_structured():
    """返回结构化摘要（AbstractText 为列表）。"""
    return {
        "AbstractText": [
            "BACKGROUND: Vaccination is critical.",
            "METHODS: Randomized controlled trial.",
            "RESULTS: 94.1% efficacy demonstrated.",
            "CONCLUSIONS: The vaccine is safe and effective.",
        ]
    }


@pytest.fixture
def mock_abstract_data_simple():
    """返回简单摘要（AbstractText 为字符串）。"""
    return {"AbstractText": "A simple abstract text without sections."}


@pytest.fixture
def mock_abstract_data_empty():
    """返回空摘要。"""
    return {}


@pytest.fixture
def mock_pub_date_full():
    """返回完整的发布日期数据。"""
    return {"Year": "2020", "Month": "12", "Day": "31"}


@pytest.fixture
def mock_pub_date_year_only():
    """返回仅含年份的日期数据。"""
    return {"Year": "2021", "Month": "01", "Day": "01"}


@pytest.fixture
def mock_pub_date_empty():
    """返回空的日期数据。"""
    return {}


@pytest.fixture
def mock_pubmed_records():
    """返回完整的模拟 PubMed records 结构。"""
    return {
        "PubmedArticle": [
            {
                "MedlineCitation": {
                    "Article": {
                        "ArticleTitle": (
                            "Efficacy and Safety of the mRNA-1273 "
                            "SARS-CoV-2 Vaccine"
                        ),
                        "Abstract": {
                            "AbstractText": [
                                "BACKGROUND: Vaccination is critical.",
                                "METHODS: Randomized controlled trial.",
                                "RESULTS: 94.1% efficacy.",
                                "CONCLUSIONS: Safe and effective.",
                            ]
                        },
                        "AuthorList": [
                            {"LastName": "Baden", "ForeName": "LR"},
                            {"LastName": "El Sahly", "ForeName": "HM"},
                            {"LastName": "Essink", "ForeName": "B"},
                        ],
                        "Journal": {
                            "Title": "The New England Journal of Medicine",
                            "ISOAbbreviation": "N Engl J Med",
                            "JournalIssue": {
                                "PubDate": {"Year": "2020", "Month": "12", "Day": "31"}
                            },
                        },
                    },
                    "PublicationTypeList": [
                        "Clinical Trial, Phase III",
                        "Randomized Controlled Trial",
                    ],
                },
                "PubmedData": {
                    "ArticleIdList": [
                        MockStringElement("10.1056/NEJMoa2035389", {"IdType": "doi"}),
                        MockStringElement("PMC7717217", {"IdType": "pmc"}),
                        MockStringElement("33301246", {"IdType": "pubmed"}),
                    ]
                },
            }
        ]
    }


@pytest.fixture
def mock_pubmed_records_minimal():
    """返回最小化的 PubMed records（无 PMC，无 PublicationType）。"""
    return {
        "PubmedArticle": [
            {
                "MedlineCitation": {
                    "Article": {
                        "ArticleTitle": "A Minimal Study",
                        "Abstract": {},
                        "AuthorList": [],
                        "Journal": {
                            "Title": "Minimal Journal",
                            "JournalIssue": {"PubDate": {}},
                        },
                    },
                    "PublicationTypeList": [],
                },
                "PubmedData": {"ArticleIdList": []},
            }
        ]
    }


@pytest.fixture
def retriever():
    """返回 PubMedRetriever 实例，mock Entrez 配置。"""
    with patch("pubmed.pubmed_retriever.pubmed_conf", {
        "email": "test@example.com",
        "api_key": "test_key",
        "max_tries": 3,
        "max_results": 5,
    }):
        from pubmed.pubmed_retriever import PubMedRetriever

        return PubMedRetriever()


# ──────────────────────────────────────────────────────────────
# T02: 静态辅助方法测试
# ──────────────────────────────────────────────────────────────


class TestParseAuthors:
    """_parse_authors() 静态方法测试。"""

    def test_normal_author_list(self, mock_author_list):
        """正常多作者列表解析。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_authors(mock_author_list)
        assert len(result) == 3
        assert result[0] == {"last_name": "Baden", "first_name": "LR"}
        assert result[1] == {"last_name": "El Sahly", "first_name": "HM"}
        assert result[2] == {"last_name": "Essink", "first_name": "B"}

    def test_empty_author_list(self):
        """空作者列表返回空列表。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_authors([])
        assert result == []

    def test_author_missing_forename(self):
        """作者缺少 ForeName 时被跳过。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        authors = [{"LastName": "Smith"}]
        result = PubMedRetriever._parse_authors(authors)
        assert result == []

    def test_author_missing_lastname(self):
        """作者缺少 LastName 时被跳过。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        authors = [{"ForeName": "John"}]
        result = PubMedRetriever._parse_authors(authors)
        assert result == []


class TestParseAbstract:
    """_parse_abstract() 静态方法测试。"""

    def test_structured_abstract(self, mock_abstract_data_structured):
        """结构化摘要（列表格式）正确拼接。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_abstract(mock_abstract_data_structured)
        assert "BACKGROUND" in result
        assert "METHODS" in result
        assert "RESULTS" in result
        assert "CONCLUSIONS" in result

    def test_simple_abstract(self, mock_abstract_data_simple):
        """简单摘要（字符串格式）正确返回。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_abstract(mock_abstract_data_simple)
        assert result == "A simple abstract text without sections."

    def test_empty_abstract(self, mock_abstract_data_empty):
        """空摘要返回空字符串。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_abstract(mock_abstract_data_empty)
        assert result == ""


class TestParsePublishDate:
    """_parse_publish_date() 静态方法测试。"""

    def test_full_date(self, mock_pub_date_full):
        """完整日期返回 YYYY-MM-DD 格式。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_publish_date(mock_pub_date_full)
        assert result == "2020-12-31"

    def test_year_only(self, mock_pub_date_year_only):
        """仅年份时 Month/Day 默认为 01。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_publish_date(mock_pub_date_year_only)
        assert result == "2021-01-01"

    def test_empty_date(self, mock_pub_date_empty):
        """无年份返回空字符串。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_publish_date(mock_pub_date_empty)
        assert result == ""

    def test_single_digit_month_day_padded(self):
        """单位数月份和日期补零。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_publish_date(
            {"Year": "2023", "Month": "3", "Day": "5"}
        )
        assert result == "2023-03-05"


class TestParseDoi:
    """_parse_doi() 静态方法测试。"""

    def test_doi_found(self, mock_article_ids):
        """找到 DOI 时正确返回。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_doi(mock_article_ids)
        assert result == "10.1056/NEJMoa2035389"

    def test_doi_not_found(self, mock_article_ids_no_pmc):
        """无 DOI 时返回空字符串。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        ids_without_doi = [
            MockStringElement("PMC12345", {"IdType": "pmc"}),
            MockStringElement("12345678", {"IdType": "pubmed"}),
        ]
        result = PubMedRetriever._parse_doi(ids_without_doi)
        assert result == ""

    def test_empty_list(self):
        """空列表返回空字符串。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_doi([])
        assert result == ""


class TestGetPmcId:
    """_get_pmc_id() 新增静态方法测试。"""

    def test_pmc_found(self, mock_article_ids):
        """找到 PMC ID 时正确返回。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._get_pmc_id(mock_article_ids)
        assert result == "PMC7717217"

    def test_pmc_not_found(self, mock_article_ids_no_pmc):
        """无 PMC ID 时返回空字符串。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._get_pmc_id(mock_article_ids_no_pmc)
        assert result == ""

    def test_empty_list(self):
        """空列表返回空字符串。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._get_pmc_id([])
        assert result == ""


class TestParseStudyGroups:
    """_parse_study_groups() 静态方法测试。"""

    def test_groups_found(self):
        """从中文摘要中提取研究分组关键词。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        abstract = "将患者随机分为试验组和对照组，试验组给予新药治疗。"
        result = PubMedRetriever._parse_study_groups(abstract)
        assert "试验组" in result
        assert "对照组" in result

    def test_no_groups(self):
        """无匹配关键词时返回空列表。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_study_groups("本研究探讨了新药的疗效。")
        assert result == []

    def test_empty_abstract(self):
        """空摘要返回空列表。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_study_groups("")
        assert result == []


class TestParseResultsInfo:
    """_parse_results_info() 静态方法测试。"""

    def test_with_abstract(self):
        """有摘要时返回完整 results_info 结构。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        abstract = "The primary endpoint was met with P<0.001."
        result = PubMedRetriever._parse_results_info(abstract)
        assert result is not None
        assert "endpoints" in result
        assert "stats" in result
        assert "raw_abstract" in result
        assert result["raw_abstract"] == abstract

    def test_with_long_abstract(self):
        """长摘要时 raw_abstract 截断。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        abstract = "A" * 300
        result = PubMedRetriever._parse_results_info(abstract)
        assert result is not None
        assert len(result["raw_abstract"]) == 203  # 200 + "..."
        assert result["raw_abstract"].endswith("...")

    def test_empty_abstract(self):
        """空摘要返回 None。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_results_info("")
        assert result is None


class TestParseObjectives:
    """_parse_objectives() 静态方法测试。"""

    def test_objective_found_by_keyword(self):
        """通过关键词「旨在」提取研究目标。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        abstract = "本研究旨在评估新药在治疗高血压中的疗效和安全性。方法：..."
        result = PubMedRetriever._parse_objectives(abstract)
        assert result is not None
        assert "旨在" in result

    def test_objective_found_by_tanjui(self):
        """通过关键词「探究」提取研究目标。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        abstract = "本研究探究了mRNA疫苗在老年人群中的免疫原性。"
        result = PubMedRetriever._parse_objectives(abstract)
        assert result is not None
        assert "探究" in result

    def test_no_objective_keyword(self):
        """无目标关键词时返回 None。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        abstract = "This study presents novel findings in immunology."
        result = PubMedRetriever._parse_objectives(abstract)
        assert result is None

    def test_empty_abstract(self):
        """空摘要返回 None。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._parse_objectives("")
        assert result is None


class TestIsFreeDownload:
    """_is_free_download() 静态方法测试。"""

    def test_with_pmc(self, mock_article_ids):
        """有 PMC ID 时返回 True。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._is_free_download(mock_article_ids)
        assert result is True

    def test_without_pmc(self, mock_article_ids_no_pmc):
        """无 PMC ID 时返回 False。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._is_free_download(mock_article_ids_no_pmc)
        assert result is False

    def test_empty_list(self):
        """空列表返回 False。"""
        from pubmed.pubmed_retriever import PubMedRetriever

        result = PubMedRetriever._is_free_download([])
        assert result is False


# ──────────────────────────────────────────────────────────────
# T11-T16: fetch_article_details() 测试
# ──────────────────────────────────────────────────────────────


class TestFetchArticleDetails:
    """fetch_article_details() 方法测试（含重构后完整结构验证）。"""

    def test_valid_pmid_returns_complete_structure(
        self, retriever, mock_pubmed_records
    ):
        """T11: 验证返回 dict 结构完整性。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")

            # 根级字段
            assert "pmid" in result
            assert "article_info" in result
            assert "study_groups" in result
            assert "results_info" in result
            assert "objectives" in result
            assert "is_free_download" in result
            assert "search_query" in result
            assert "raw_response" in result
            assert result["pmid"] == "33301246"

            # article_info 字段
            info = result["article_info"]
            assert "title" in info
            assert "authors" in info
            assert "abstract" in info
            assert "journal" in info
            assert "doi" in info
            assert "publish_date" in info
            assert "pmc_id" in info
            assert "publication_type" in info

    def test_authors_format(self, retriever, mock_pubmed_records):
        """T12: 验证 authors 格式为 ["LastName ForeName", ...]。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            authors = result["article_info"]["authors"]

            assert isinstance(authors, list)
            assert len(authors) == 3
            assert authors[0] == "Baden LR"
            assert authors[1] == "El Sahly HM"
            assert authors[2] == "Essink B"

    def test_publish_date_format(self, retriever, mock_pubmed_records):
        """T13: 验证 publish_date 格式为 YYYY-MM-DD。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            pub_date = result["article_info"]["publish_date"]

            assert pub_date == "2020-12-31"
            # 验证格式: YYYY-MM-DD
            parts = pub_date.split("-")
            assert len(parts) == 3
            assert len(parts[0]) == 4  # YYYY
            assert len(parts[1]) == 2  # MM
            assert len(parts[2]) == 2  # DD

    def test_is_free_download_with_pmc(self, retriever, mock_pubmed_records):
        """T14: 有 PMC ID 的文章 is_free_download 返回 True。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            assert result["is_free_download"] is True

    def test_is_free_download_without_pmc(
        self, retriever, mock_pubmed_records_minimal
    ):
        """无 PMC ID 的文章 is_free_download 返回 False。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records_minimal), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("12345678")
            assert result["is_free_download"] is False

    def test_raw_response_contains_complete_data(
        self, retriever, mock_pubmed_records
    ):
        """T15: raw_response 包含完整的 PubMed 数据。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            raw = result["raw_response"]

            assert isinstance(raw, dict)
            assert "PubmedArticle" in raw
            assert raw is not mock_pubmed_records  # deepcopy, not same reference

    def test_invalid_pmid_raises_exception(self, retriever):
        """T16: 无效 PMID 抛出异常。"""
        with patch("Bio.Entrez.read", side_effect=RuntimeError("Invalid PMID")), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            with pytest.raises(Exception):
                retriever.fetch_article_details("invalid_pmid")

    def test_search_query_is_empty_string(self, retriever, mock_pubmed_records):
        """验证 search_query 默认值为空字符串。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            assert result["search_query"] == ""

    def test_doi_field_extracted(self, retriever, mock_pubmed_records):
        """验证 doi 字段被正确提取。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            assert result["article_info"]["doi"] == "10.1056/NEJMoa2035389"

    def test_pmc_id_field_extracted(self, retriever, mock_pubmed_records):
        """验证 pmc_id 字段被正确提取。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            assert result["article_info"]["pmc_id"] == "PMC7717217"

    def test_publication_type_extracted(self, retriever, mock_pubmed_records):
        """验证 publication_type 字段被正确提取并以逗号分隔。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("33301246")
            pub_type = result["article_info"]["publication_type"]
            assert "Clinical Trial, Phase III" in pub_type
            assert "Randomized Controlled Trial" in pub_type

    def test_minimal_article_no_crash(self, retriever, mock_pubmed_records_minimal):
        """最小化文章数据不崩溃，返回默认值。"""
        with patch("Bio.Entrez.read", return_value=mock_pubmed_records_minimal), \
             patch("Bio.Entrez.efetch") as mock_efetch:
            mock_efetch.return_value = MagicMock()

            result = retriever.fetch_article_details("12345678")
            assert result["pmid"] == "12345678"
            assert result["article_info"]["title"] == "A Minimal Study"
            assert result["article_info"]["authors"] == []
            assert result["article_info"]["abstract"] == ""
            assert result["article_info"]["doi"] == ""
            assert result["article_info"]["publish_date"] == ""
            assert result["article_info"]["pmc_id"] == ""
            assert result["article_info"]["publication_type"] == ""
            assert result["is_free_download"] is False


class TestFetchArticleDetailsStaticMethodCalls:
    """验证 fetch_article_details() 内部调用了静态辅助方法。"""

    @staticmethod
    def _mock_entrez(records):
        """Helper: mock both Entrez.read and Entrez.efetch."""
        return (
            patch("Bio.Entrez.read", return_value=records),
            patch("Bio.Entrez.efetch"),
        )

    def test_calls_parse_abstract(self, retriever, mock_pubmed_records):
        """验证调用了 _parse_abstract。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_parse_abstract", wraps=retriever._parse_abstract
        ) as mock_pa:
            retriever.fetch_article_details("33301246")
            mock_pa.assert_called_once()

    def test_calls_parse_authors(self, retriever, mock_pubmed_records):
        """验证调用了 _parse_authors。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_parse_authors", wraps=retriever._parse_authors
        ) as mock_pa:
            retriever.fetch_article_details("33301246")
            mock_pa.assert_called_once()

    def test_calls_parse_publish_date(self, retriever, mock_pubmed_records):
        """验证调用了 _parse_publish_date。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_parse_publish_date",
            wraps=retriever._parse_publish_date,
        ) as mock_ppd:
            retriever.fetch_article_details("33301246")
            mock_ppd.assert_called_once()

    def test_calls_parse_doi(self, retriever, mock_pubmed_records):
        """验证调用了 _parse_doi。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_parse_doi", wraps=retriever._parse_doi
        ) as mock_pd:
            retriever.fetch_article_details("33301246")
            mock_pd.assert_called_once()

    def test_calls_get_pmc_id(self, retriever, mock_pubmed_records):
        """验证调用了 _get_pmc_id。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_get_pmc_id", wraps=retriever._get_pmc_id
        ) as mock_gpi:
            retriever.fetch_article_details("33301246")
            mock_gpi.assert_called_once()

    def test_calls_is_free_download(self, retriever, mock_pubmed_records):
        """验证调用了 _is_free_download。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_is_free_download",
            wraps=retriever._is_free_download,
        ) as mock_ifd:
            retriever.fetch_article_details("33301246")
            mock_ifd.assert_called_once()

    def test_calls_parse_study_groups(self, retriever, mock_pubmed_records):
        """验证调用了 _parse_study_groups。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_parse_study_groups",
            wraps=retriever._parse_study_groups,
        ) as mock_psg:
            retriever.fetch_article_details("33301246")
            mock_psg.assert_called_once()

    def test_calls_parse_results_info(self, retriever, mock_pubmed_records):
        """验证调用了 _parse_results_info。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_parse_results_info",
            wraps=retriever._parse_results_info,
        ) as mock_pri:
            retriever.fetch_article_details("33301246")
            mock_pri.assert_called_once()

    def test_calls_parse_objectives(self, retriever, mock_pubmed_records):
        """验证调用了 _parse_objectives。"""
        mr, me = self._mock_entrez(mock_pubmed_records)
        with mr, me, patch.object(
            retriever, "_parse_objectives",
            wraps=retriever._parse_objectives,
        ) as mock_po:
            retriever.fetch_article_details("33301246")
            mock_po.assert_called_once()


# ──────────────────────────────────────────────────────────────
# T09-T10: search_pubmed() 保持不变
# ──────────────────────────────────────────────────────────────


class TestSearchPubmed:
    """search_pubmed() 方法测试。"""

    def test_returns_pmid_list(self, retriever):
        """正常返回 PMID 列表。"""
        mock_result = {"IdList": ["33301246", "33301247", "33301248"]}
        with patch("Bio.Entrez.read", return_value=mock_result), \
             patch("Bio.Entrez.esearch") as mock_esearch:
            mock_esearch.return_value = MagicMock()

            result = retriever.search_pubmed("COVID-19 vaccine")
            assert isinstance(result, list)
            assert len(result) == 3
            assert result == ["33301246", "33301247", "33301248"]

    def test_empty_results(self, retriever):
        """无结果时返回空列表。"""
        mock_result = {"IdList": []}
        with patch("Bio.Entrez.read", return_value=mock_result), \
             patch("Bio.Entrez.esearch") as mock_esearch:
            mock_esearch.return_value = MagicMock()

            result = retriever.search_pubmed("xyznonexistentquery")
            assert result == []

    def test_retry_on_failure(self, retriever):
        """首次失败后重试成功。"""
        mock_result = {"IdList": ["12345678"]}
        with patch("Bio.Entrez.read") as mock_read, \
             patch("Bio.Entrez.esearch") as mock_esearch, \
             patch("time.sleep") as mock_sleep:
            mock_esearch.return_value = MagicMock()
            # 第一次调用失败，第二次成功
            mock_read.side_effect = [RuntimeError("Network error"), mock_result]

            result = retriever.search_pubmed("test query")
            assert result == ["12345678"]
            assert mock_read.call_count == 2
            mock_sleep.assert_called_once_with(3)

    def test_retry_exhausted_raises(self, retriever):
        """重试仍失败则抛出异常。"""
        with patch("Bio.Entrez.read", side_effect=RuntimeError("Persistent error")), \
             patch("Bio.Entrez.esearch") as mock_esearch, \
             patch("time.sleep"):
            mock_esearch.return_value = MagicMock()

            with pytest.raises(Exception):
                retriever.search_pubmed("test query")
