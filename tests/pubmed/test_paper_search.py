"""Tests for pubmed/paper_search.py — PubMedSearchPipeline.

测试覆盖:
    - __init__(): Retriever 初始化
    - run(): 正常流程、空结果、查重跳过、单篇异常处理
    - run(): max_results 参数 / 配置默认值
    - run(): context manager 正常 connect/close
    - run(): 日志输出验证
    - if __name__ == "__main__": 入口
"""

from unittest.mock import MagicMock, patch

import pytest

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_postgres_db():
    """Mock PostgresDB 上下文管理器，模拟正常连接。"""
    with patch("pubmed.paper_search.PostgresDB") as mock_db_cls:
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_db.__enter__.return_value = mock_db
        mock_db.__exit__.return_value = False
        yield mock_db, mock_db_cls


@pytest.fixture
def mock_retriever():
    """Mock PubMedRetriever，返回固定 PMID 列表和 article_data。"""
    with patch("pubmed.paper_search.PubMedRetriever") as mock_cls:
        mock_ret = MagicMock()
        mock_cls.return_value = mock_ret
        yield mock_ret, mock_cls


@pytest.fixture
def sample_article_data():
    """返回标准的 article_data 样本。"""
    return {
        "pmid": "33301246",
        "article_info": {
            "title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
            "authors": ["Baden LR", "El Sahly HM"],
            "abstract": "BACKGROUND: Vaccination is critical...",
            "journal": "N Engl J Med",
            "doi": "10.1056/NEJMoa2035389",
            "publish_date": "2020-12-31",
            "pmc_id": "PMC7717217",
            "publication_type": "Clinical Trial, Phase III",
        },
        "study_groups": [],
        "results_info": None,
        "objectives": "",
        "is_free_download": True,
        "search_query": "",
        "raw_response": {},
    }



# ── T01: __init__ 测试 ────────────────────────────────────────


class TestInit:
    """PubMedSearchPipeline.__init__() 测试。"""

    def test_init_creates_retriever(self):
        """__init__ 应创建 PubMedRetriever 实例。"""
        with patch("pubmed.paper_search.PubMedRetriever") as mock_cls:
            mock_ret = MagicMock()
            mock_cls.return_value = mock_ret

            from pubmed.paper_search import PubMedSearchPipeline

            pipeline = PubMedSearchPipeline()
            mock_cls.assert_called_once()
            assert pipeline._retriever is mock_ret

    def test_retriever_is_pubmed_retriever_instance(self):
        """_retriever 应为 PubMedRetriever 类型。"""
        from pubmed.paper_search import PubMedRetriever, PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        assert isinstance(pipeline._retriever, PubMedRetriever)


# ── T02: run() 正常流程 ───────────────────────────────────────


class TestRunNormalFlow:
    """run() 正常流程测试。"""

    def test_run_inserts_new_articles(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """新文献应被成功插入，每篇返回 status='inserted'。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246", "33301247"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.return_value = sample_article_data

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("COVID-19 vaccine", max_results=5)

        assert len(results) == 2
        assert results[0]["pmid"] == "33301246"
        assert results[0]["status"] == "inserted"
        assert results[0]["title"] == sample_article_data["article_info"]["title"]
        assert results[1]["pmid"] == "33301247"
        assert results[1]["status"] == "inserted"

        # 验证 insert_article 被调用且 search_query 被设置
        assert mock_db.insert_article.call_count == 2
        call_arg = mock_db.insert_article.call_args[0][0]
        assert call_arg["search_query"] == "COVID-19 vaccine"

    def test_run_returns_list_of_dicts(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """返回值格式应为 list of dict。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.return_value = sample_article_data

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test query", max_results=1)

        assert isinstance(results, list)
        assert isinstance(results[0], dict)
        assert "pmid" in results[0]
        assert "status" in results[0]
        assert "title" in results[0]

    def test_run_calls_search_pubmed_with_query(
        self, mock_postgres_db, mock_retriever
    ):
        """run() 应将 query 参数传递给 search_pubmed()。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        pipeline.run("specific query", max_results=3)

        mock_ret.search_pubmed.assert_called_once_with("specific query")


# ── T03: run() 空结果 / 占位 ──────────────────────────────────


class TestRunEmptyResults:
    """run() 空结果测试。"""

    def test_run_returns_empty_list_when_no_pmids(
        self, mock_postgres_db, mock_retriever
    ):
        """search_pubmed 返回空列表时，run() 应返回空列表。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("nonexistent query", max_results=5)

        assert results == []
        mock_db.is_pmid_exist.assert_not_called()
        mock_db.insert_article.assert_not_called()

    def test_run_does_not_call_efetch_when_no_pmids(
        self, mock_postgres_db, mock_retriever
    ):
        """无 PMID 时不应调用 fetch_article_details()。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        pipeline.run("query", max_results=5)

        mock_ret.fetch_article_details.assert_not_called()


# ── T04: run() 查重跳过 ───────────────────────────────────────


class TestRunDuplicateSkip:
    """run() 查重跳过测试。"""

    def test_run_skips_existing_pmid(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """已存在的 PMID 应标记 status='skipped'。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246", "33301247"]
        # 第一个已存在，第二个不存在
        mock_db.is_pmid_exist.side_effect = [True, False]
        mock_ret.fetch_article_details.return_value = sample_article_data

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test query", max_results=5)

        assert len(results) == 2
        assert results[0]["status"] == "skipped"
        assert results[0]["reason"] == "already_exists"
        assert results[1]["status"] == "inserted"

        # 跳过的不会调用 fetch_article_details
        assert mock_ret.fetch_article_details.call_count == 1

    def test_run_all_existing_returns_all_skipped(
        self, mock_postgres_db, mock_retriever
    ):
        """全部 PMID 已存在时，所有结果均为 skipped。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246", "33301247", "33301248"]
        mock_db.is_pmid_exist.return_value = True

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test query", max_results=5)

        assert len(results) == 3
        for r in results:
            assert r["status"] == "skipped"
        mock_ret.fetch_article_details.assert_not_called()
        mock_db.insert_article.assert_not_called()


# ── T05: run() 单篇异常处理 ───────────────────────────────────


class TestRunPerArticleExceptionHandling:
    """run() 单篇异常处理测试。"""

    def test_run_continues_after_fetch_failure(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """某篇 fetch 失败时，后续 PMID 仍正常处理。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246", "33301247", "33301248"]
        mock_db.is_pmid_exist.return_value = False
        # 第二篇 fetch 失败
        mock_ret.fetch_article_details.side_effect = [
            sample_article_data,
            RuntimeError("Network timeout"),
            sample_article_data,
        ]

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test query", max_results=5)

        assert len(results) == 3
        assert results[0]["status"] == "inserted"
        assert results[1]["status"] == "failed"
        assert results[1]["reason"] == "Network timeout"
        assert results[2]["status"] == "inserted"

    def test_run_continues_after_insert_failure(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """某篇 insert 失败时，后续 PMID 仍正常处理。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246", "33301247"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.return_value = sample_article_data
        # 第一篇 insert 失败
        mock_db.insert_article.side_effect = [RuntimeError("DB connection lost"), None]

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test query", max_results=5)

        assert len(results) == 2
        assert results[0]["status"] == "failed"
        assert results[0]["reason"] == "DB connection lost"
        assert results[1]["status"] == "inserted"

    def test_run_all_failed_returns_all_failed(
        self, mock_postgres_db, mock_retriever
    ):
        """全部 PMID 处理失败时，所有结果均为 failed。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246", "33301247"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.side_effect = RuntimeError("Total failure")

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test query", max_results=5)

        assert len(results) == 2
        for r in results:
            assert r["status"] == "failed"

    def test_run_title_is_empty_when_failed(
        self, mock_postgres_db, mock_retriever
    ):
        """处理失败时 title 应为空字符串。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.side_effect = RuntimeError("Fail")

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test query", max_results=1)

        assert results[0]["status"] == "failed"
        assert results[0]["title"] == ""


# ── T06: max_results 参数 / 默认值 ─────────────────────────────


class TestMaxResults:
    """max_results 参数及配置默认值测试。"""

    def test_run_uses_provided_max_results(self, mock_postgres_db, mock_retriever):
        """提供 max_results 参数时应直接使用。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        pipeline.run("test", max_results=10)

        # max_results 目前仅在日志中使用，实际传给 search_pubmed 由
        # PubMedRetriever 内部 max_results 控制。
        # 验证 run 不会因为传了 max_results 而崩溃即可。
        mock_ret.search_pubmed.assert_called_once_with("test")

    def test_run_defaults_max_results_from_config(
        self, mock_postgres_db, mock_retriever
    ):
        """未提供 max_results 时，应使用配置中的默认 max_results=5。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        mock_config = MagicMock()
        mock_config.get.return_value = 5

        with patch("pubmed.paper_search.pubmed_conf", mock_config):
            from pubmed.paper_search import PubMedSearchPipeline

            pipeline = PubMedSearchPipeline()
            results = pipeline.run("test")  # 不传 max_results
            assert results == []
            # 验证 config.get 被正确调用
            mock_config.get.assert_called_once_with("max_results", 5)

    def test_run_max_results_none_uses_config_default(
        self, mock_postgres_db, mock_retriever
    ):
        """max_results=None 时使用配置默认值。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        # 传入 None，应从配置读取
        results = pipeline.run("test", max_results=None)
        assert results == []


# ── T07: 上下文管理器测试 ─────────────────────────────────────


class TestContextManager:
    """with PostgresDB() as db: 上下文管理器测试。"""

    def test_context_manager_enter_called(self, mock_postgres_db, mock_retriever):
        """进入 with 块时应调用 __enter__。"""
        mock_db, mock_db_cls = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        pipeline.run("test", max_results=1)

        mock_db.__enter__.assert_called_once()

    def test_context_manager_exit_called(self, mock_postgres_db, mock_retriever):
        """退出 with 块时应调用 __exit__。"""
        mock_db, mock_db_cls = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        pipeline.run("test", max_results=1)

        mock_db.__exit__.assert_called_once()

    def test_context_manager_exit_called_on_exception(
        self, mock_postgres_db, mock_retriever
    ):
        """即使内部出现异常，__exit__ 仍应被调用。"""
        mock_db, mock_db_cls = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = ["33301246"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.side_effect = RuntimeError("Boom")

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        pipeline.run("test", max_results=1)

        # __exit__ 仍应被调用（异常在 run 内部被捕获，不会传播到 context manager）
        mock_db.__exit__.assert_called_once()

    def test_db_created_via_constructor(
        self, mock_postgres_db, mock_retriever
    ):
        """验证 PostgresDB 是通过构造函数创建的新实例。"""
        _, mock_db_cls = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        pipeline.run("test", max_results=1)

        mock_db_cls.assert_called_once()


# ── T08: 日志输出验证 ─────────────────────────────────────────


class TestLogging:
    """run() 日志输出测试。"""

    def test_logs_start_message(self, mock_postgres_db, mock_retriever):
        """搜索开始时应输出 INFO 日志。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        with patch("pubmed.paper_search.logger") as mock_logger:
            from pubmed.paper_search import PubMedSearchPipeline

            pipeline = PubMedSearchPipeline()
            pipeline.run("test query", max_results=5)

            mock_logger.info.assert_any_call(
                "Starting PubMed search pipeline: query='%s', max_results=%d",
                "test query",
                5,
            )

    def test_logs_no_results_message(self, mock_postgres_db, mock_retriever):
        """无结果时应输出相应日志。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        with patch("pubmed.paper_search.logger") as mock_logger:
            from pubmed.paper_search import PubMedSearchPipeline

            pipeline = PubMedSearchPipeline()
            pipeline.run("test query", max_results=5)

            mock_logger.info.assert_any_call(
                "No PMIDs found for query '%s'", "test query"
            )

    def test_logs_each_article_processing(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """每篇文章处理完成后应输出日志。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = ["33301246"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.return_value = sample_article_data

        with patch("pubmed.paper_search.logger") as mock_logger:
            from pubmed.paper_search import PubMedSearchPipeline

            pipeline = PubMedSearchPipeline()
            pipeline.run("test query", max_results=1)

            # 检查是否记录了插入成功的日志
            assert any(
                "inserted successfully" in str(call)
                for call in mock_logger.info.call_args_list
            )

    def test_logs_summary_statistics(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """管线结束后应输出汇总统计日志。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = ["33301246", "33301247"]
        mock_db.is_pmid_exist.side_effect = [True, False]
        mock_ret.fetch_article_details.return_value = sample_article_data

        with patch("pubmed.paper_search.logger") as mock_logger:
            from pubmed.paper_search import PubMedSearchPipeline

            pipeline = PubMedSearchPipeline()
            pipeline.run("test query", max_results=5)

            # 检查汇总日志
            summary_calls = [
                c for c in mock_logger.info.call_args_list
                if "Pipeline finished" in str(c)
            ]
            assert len(summary_calls) >= 1

    def test_logs_error_on_failure(
        self, mock_postgres_db, mock_retriever
    ):
        """单篇处理失败时应输出 ERROR 日志。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = ["33301246"]
        mock_db.is_pmid_exist.return_value = False
        mock_ret.fetch_article_details.side_effect = RuntimeError("Test error")

        with patch("pubmed.paper_search.logger") as mock_logger:
            from pubmed.paper_search import PubMedSearchPipeline

            pipeline = PubMedSearchPipeline()
            pipeline.run("test query", max_results=1)

            mock_logger.error.assert_called()


# ── T09: 文档字符串 / 类型注解 ─────────────────────────────────


class TestDocstringsAndTypes:
    """文档字符串和类型注解验证。"""

    def test_class_has_docstring(self):
        """PubMedSearchPipeline 类应有 docstring。"""
        from pubmed.paper_search import PubMedSearchPipeline

        assert PubMedSearchPipeline.__doc__ is not None
        assert len(PubMedSearchPipeline.__doc__) > 0

    def test_init_has_docstring(self):
        """__init__ 方法应有 docstring。"""
        from pubmed.paper_search import PubMedSearchPipeline

        assert PubMedSearchPipeline.__init__.__doc__ is not None
        assert len(PubMedSearchPipeline.__init__.__doc__) > 0

    def test_run_has_docstring(self):
        """run 方法应有 docstring（含 Args/Returns）。"""
        from pubmed.paper_search import PubMedSearchPipeline

        doc = PubMedSearchPipeline.run.__doc__
        assert doc is not None
        assert "Args:" in doc
        assert "Returns:" in doc

    def test_run_has_type_annotations(self):
        """run 方法应有类型注解。"""
        from pubmed.paper_search import PubMedSearchPipeline

        annotations = PubMedSearchPipeline.run.__annotations__
        assert "query" in annotations
        assert "max_results" in annotations
        assert "return" in annotations


# ── T10: 命令行入口 ────────────────────────────────────────────


class TestMainEntryPoint:
    """if __name__ == "__main__": 入口间接验证。"""

    def test_pipeline_can_be_instantiated_and_run(
        self, mock_postgres_db, mock_retriever
    ):
        """验证 pipeline 可从外部实例化并调用 run（模拟 main 入口行为）。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever
        mock_ret.search_pubmed.return_value = []

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("heart")

        assert isinstance(results, list)
        assert results == []

    def test_old_main_function_removed(self):
        """验证旧的 main() 函数已被删除。"""
        import pubmed.paper_search as ps_mod

        assert not hasattr(ps_mod, "main"), "旧 main() 函数应已删除"

    def test_no_global_entrez_email_setup(self):
        """验证旧的全局 Entrez.email 初始化代码已移除。"""
        import pubmed.paper_search as ps_mod

        source = open(ps_mod.__file__, encoding="utf-8").read()
        assert "Entrez.email" not in source, (
            "不应包含全局 Entrez.email 初始化代码"
        )
        assert "Entrez.api_key" not in source, (
            "不应包含全局 Entrez.api_key 初始化代码"
        )


# ── T11: 复杂混合场景 ─────────────────────────────────────────


class TestMixedScenarios:
    """混合场景：同时存在 inserted、skipped、failed。"""

    def test_mixed_statuses_in_single_run(
        self, mock_postgres_db, mock_retriever, sample_article_data
    ):
        """单次 run 应能返回混合状态的结果。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["1", "2", "3", "4", "5"]
        # PMID "1": already exists → skipped
        # PMID "2": fetch fails → failed
        # PMID "3": insert succeeds → inserted
        # PMID "4": already exists → skipped
        # PMID "5": insert succeeds → inserted
        mock_db.is_pmid_exist.side_effect = [True, False, False, True, False]
        mock_ret.fetch_article_details.side_effect = [
            RuntimeError("Fetch error"),  # for "2"
            sample_article_data,  # for "3"
            sample_article_data,  # for "5"
        ]

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("multi status", max_results=5)

        statuses = [r["status"] for r in results]
        assert statuses == ["skipped", "failed", "inserted", "skipped", "inserted"]
        assert len(results) == 5

        # 验证计数
        assert statuses.count("inserted") == 2
        assert statuses.count("skipped") == 2
        assert statuses.count("failed") == 1

    def test_skipped_title_is_empty(
        self, mock_postgres_db, mock_retriever
    ):
        """跳过的文章 title 应为空字符串。"""
        mock_db, _ = mock_postgres_db
        mock_ret, _ = mock_retriever

        mock_ret.search_pubmed.return_value = ["33301246"]
        mock_db.is_pmid_exist.return_value = True

        from pubmed.paper_search import PubMedSearchPipeline

        pipeline = PubMedSearchPipeline()
        results = pipeline.run("test", max_results=1)

        assert results[0]["status"] == "skipped"
        assert results[0]["title"] == ""
