"""pytest 共享 fixtures 和工具函数。

为所有测试模块提供:
    - 临时 ChromaDB 目录
    - Mock PostgreSQL 连接参数
    - 通用 mock 工具
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在 Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_chroma_dir():
    """创建一个临时目录用于 ChromaDB 测试，测试后自动清理。"""
    with tempfile.TemporaryDirectory(prefix="chroma_test_") as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_postgres_connection():
    """Mock psycopg2 连接，返回模拟的 cursor 和 connection。"""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.rowcount = 1
    mock_cur.fetchone.return_value = None
    mock_cur.fetchall.return_value = []
    return mock_conn, mock_cur


@pytest.fixture
def sample_pubmed_article():
    """返回一条完整的示例 PubMed 文章 dict，供测试使用。"""
    return {
        "pmid": "12345678",
        "article_info": {
            "title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
            "authors": ["Baden LR", "El Sahly HM", "Essink B"],
            "abstract": (
                "BACKGROUND: Vaccination is critical... METHODS: Randomized... "
                "RESULTS: 94.1% efficacy... "
                "CONCLUSIONS: The vaccine is safe and effective."
            ),
            "journal": "N Engl J Med",
            "doi": "10.1056/NEJMoa2035389",
            "publish_date": "2020-12-31",
            "pmc_id": "PMC7717217",
            "publication_type": "Clinical Trial, Phase III",
        },
        "study_groups": ["vaccine group", "placebo group"],
        "results_info": {
            "raw_abstract": (
                "BACKGROUND: Vaccination is critical... RESULTS: 94.1% efficacy..."
            ),
            "endpoints": "Vaccine efficacy endpoint",
            "stats": "P<0.001, HR=0.67",
        },
        "objectives": "To evaluate the efficacy and safety of mRNA-1273",
        "is_free_download": True,
        "ingestion_status": "uningested",
        "search_query": "COVID-19 mRNA vaccine",
        "raw_response": {},
    }


@pytest.fixture
def sample_article_list():
    """返回示例文献列表。"""
    return [
        {
            "pmid": "12345678",
            "title": "Test Article 1",
            "authors": ["Author A", "Author B"],
            "journal": "Test Journal",
            "publish_date": "2020-01-01",
            "abstract_preview": "Abstract preview 1...",
            "is_free_download": True,
            "ingestion_status": "ingested",
            "ingested_at": None,
            "study_groups": [],
            "created_at": None,
        },
        {
            "pmid": "87654321",
            "title": "Test Article 2",
            "authors": ["Author C"],
            "journal": "Another Journal",
            "publish_date": "2021-06-15",
            "abstract_preview": "Abstract preview 2...",
            "is_free_download": False,
            "ingestion_status": "uningested",
            "ingested_at": None,
            "study_groups": ["treatment group"],
            "created_at": None,
        },
    ]
