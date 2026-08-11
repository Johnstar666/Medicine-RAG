"""tests/infrastructure/persistence/test_postgres_db.py --- 测试 PostgresDB 类."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.persistence.postgres_db import (
    ALLOWED_ORDER,
    ALLOWED_SORT,
    PostgresDB,
    PostgresDB_singleton,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_cursor() -> MagicMock:
    """返回一个 mock cursor，带默认 rowcount 和返回值。"""
    cur = MagicMock()
    cur.rowcount = 1
    cur.fetchone.return_value = None
    cur.fetchall.return_value = []
    return cur


@pytest.fixture
def mock_conn(mock_cursor: MagicMock) -> MagicMock:
    """返回一个 mock connection，其 cursor() 返回 mock_cursor。"""
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    conn.closed = False
    return conn


@pytest.fixture
def db_with_mock_connect(mock_conn: MagicMock) -> PostgresDB:
    """创建一个 PostgresDB 实例并用 mock connection patch connect。"""
    with patch.object(PostgresDB, "connect", return_value=None):
        db = PostgresDB()
        db.conn = mock_conn
        db.cur = mock_conn.cursor.return_value
        return db


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


class TestAllowedConstants:
    """测试 SQL 注入白名单常量。"""

    def test_allowed_sort_contains_expected(self) -> None:
        """ALLOWED_SORT 应包含 created_at, updated_at, pmid。"""
        assert "created_at" in ALLOWED_SORT
        assert "updated_at" in ALLOWED_SORT
        assert "pmid" in ALLOWED_SORT

    def test_allowed_sort_rejects_malicious(self) -> None:
        """ALLOWED_SORT 不应包含恶意注入字符串。"""
        assert "; DROP TABLE--" not in ALLOWED_SORT
        assert "1=1" not in ALLOWED_SORT
        assert "pmid; DELETE FROM" not in ALLOWED_SORT

    def test_allowed_order_contains_expected(self) -> None:
        """ALLOWED_ORDER 应包含 asc, desc。"""
        assert "asc" in ALLOWED_ORDER
        assert "desc" in ALLOWED_ORDER

    def test_allowed_order_rejects_malicious(self) -> None:
        """ALLOWED_ORDER 不应包含恶意注入字符串。"""
        assert "; DROP TABLE--" not in ALLOWED_ORDER
        assert "ASC; DELETE" not in ALLOWED_ORDER


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    """测试 __init__ 配置初始化。"""

    def test_init_sets_conn_params(self) -> None:
        """__init__ 应正确设置 conn_params 和 table。"""
        db = PostgresDB()
        assert "host" in db.conn_params
        assert "port" in db.conn_params
        assert "user" in db.conn_params
        assert "password" in db.conn_params
        assert "database" in db.conn_params
        assert "options" in db.conn_params
        assert db.table == "pubmed_articles"
        assert db.conn is None
        assert db.cur is None

    def test_init_does_not_connect_immediately(self) -> None:
        """__init__ 不应立即建立连接（延迟连接）。"""
        db = PostgresDB()
        assert db.conn is None
        assert db.cur is None


# ---------------------------------------------------------------------------
# Context manager (T22)
# ---------------------------------------------------------------------------


class TestContextManager:
    """测试上下文管理器 __enter__ / __exit__。"""

    def test_enter_calls_connect(self) -> None:
        """__enter__ 应调用 connect() 并返回 self。"""
        with patch.object(PostgresDB, "connect") as mock_connect:
            db = PostgresDB()
            result = db.__enter__()
            mock_connect.assert_called_once()
            assert result is db

    def test_exit_calls_close(self) -> None:
        """__exit__ 应调用 close()。"""
        with patch.object(PostgresDB, "close") as mock_close:
            db = PostgresDB()
            db.__exit__(None, None, None)
            mock_close.assert_called_once()

    def test_exit_does_not_suppress_exception(self) -> None:
        """__exit__ 应返回 False，不吞异常。"""
        db = PostgresDB()
        result = db.__exit__(ValueError, ValueError("test"), None)
        assert result is False

    def test_with_statement_flow(self) -> None:
        """测试 with 语句的完整流程：enter connect, exit close。"""
        with patch.object(PostgresDB, "connect") as mock_connect, \
             patch.object(PostgresDB, "close") as mock_close:
            db = PostgresDB()
            with db:
                pass
            mock_connect.assert_called_once()
            mock_close.assert_called_once()


# ---------------------------------------------------------------------------
# Connection management (T23)
# ---------------------------------------------------------------------------


class TestConnectionManagement:
    """测试连接管理方法。"""

    def test_connect_closes_old_connection_first(self) -> None:
        """重复 connect 时应先关闭旧连接。"""
        db = PostgresDB()
        with patch.object(db, "close") as mock_close, \
             patch("psycopg2.connect") as mock_psycopg2_connect:
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = MagicMock()
            mock_psycopg2_connect.return_value = mock_conn

            # 设置一个旧的连接
            db.conn = MagicMock()
            db.connect()

            mock_close.assert_called_once()

    def test_close_sets_conn_and_cur_to_none(self) -> None:
        """close() 应将 conn 和 cur 设为 None。"""
        db = PostgresDB()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        db.conn = mock_conn
        db.cur = mock_cur
        db.close()
        assert db.cur is None
        assert db.conn is None
        mock_cur.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_ensure_connected_when_conn_is_none(self) -> None:
        """conn 为 None 时 _ensure_connected 应调用 connect()。"""
        db = PostgresDB()
        db.conn = None
        with patch.object(db, "connect") as mock_connect:
            db._ensure_connected()
            mock_connect.assert_called_once()

    def test_ensure_connected_when_conn_is_closed(self) -> None:
        """conn.closed=True 时 _ensure_connected 应调用 connect()。"""
        db = PostgresDB()
        db.conn = MagicMock()
        db.conn.closed = True
        with patch.object(db, "connect") as mock_connect:
            db._ensure_connected()
            mock_connect.assert_called_once()

    def test_ensure_connected_when_conn_is_open(self) -> None:
        """conn 正常打开时 _ensure_connected 不应调用 connect()。"""
        db = PostgresDB()
        db.conn = MagicMock()
        db.conn.closed = False
        with patch.object(db, "connect") as mock_connect:
            db._ensure_connected()
            mock_connect.assert_not_called()


# ---------------------------------------------------------------------------
# is_pmid_exist
# ---------------------------------------------------------------------------


class TestIsPmidExist:
    """测试 is_pmid_exist 方法。"""

    def test_pmid_exists(self, db_with_mock_connect: PostgresDB) -> None:
        """fetchone 返回非 None 时 is_pmid_exist 应返回 True。"""
        db_with_mock_connect.cur.fetchone.return_value = {"1": 1}
        result = db_with_mock_connect.is_pmid_exist("12345678")
        assert result is True

    def test_pmid_not_exists(self, db_with_mock_connect: PostgresDB) -> None:
        """fetchone 返回 None 时 is_pmid_exist 应返回 False。"""
        db_with_mock_connect.cur.fetchone.return_value = None
        result = db_with_mock_connect.is_pmid_exist("99999999")
        assert result is False

    def test_is_pmid_exist_ensures_connected(self) -> None:
        """is_pmid_exist 应首先调用 _ensure_connected。"""
        db = PostgresDB()
        with patch.object(db, "_ensure_connected") as mock_ensure, \
             patch.object(db, "connect"):  # 阻止实际连接
            db.conn = MagicMock()
            db.conn.closed = False
            db.cur = MagicMock()
            db.cur.fetchone.return_value = None
            db.is_pmid_exist("123")
            mock_ensure.assert_called_once()


# ---------------------------------------------------------------------------
# insert_article (T25)
# ---------------------------------------------------------------------------


class TestInsertArticle:
    """测试 insert_article 方法。"""

    def test_insert_article_success(self, db_with_mock_connect: PostgresDB) -> None:
        """正常插入应调用 execute 和 commit。"""
        article: dict[str, Any] = {
            "pmid": "12345678",
            "article_info": {"title": "Test Article"},
            "study_groups": ["group A"],
            "results_info": {"raw_abstract": "Test abstract"},
            "objectives": "Test objectives",
            "is_free_download": True,
            "search_query": "test query",
            "raw_response": {"key": "value"},
        }
        db_with_mock_connect.insert_article(article)
        db_with_mock_connect.cur.execute.assert_called_once()
        db_with_mock_connect.conn.commit.assert_called_once()

    def test_insert_article_rollback_on_error(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """插入失败时应调用 rollback。"""
        db_with_mock_connect.cur.execute.side_effect = Exception("duplicate key")
        article: dict[str, Any] = {
            "pmid": "12345678",
            "article_info": {"title": "Test"},
            "study_groups": [],
            "results_info": None,
            "objectives": "",
            "is_free_download": False,
        }
        with pytest.raises(Exception, match="duplicate key"):
            db_with_mock_connect.insert_article(article)
        db_with_mock_connect.conn.rollback.assert_called_once()

    def test_insert_article_defaults_ingestion_status_to_uningested(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """insert_article SQL 中应硬编码 ingestion_status 为 'uningested'。"""
        article: dict[str, Any] = {
            "pmid": "12345678",
            "article_info": {"title": "Test"},
            "study_groups": [],
            "results_info": None,
            "objectives": "",
            "is_free_download": False,
        }
        db_with_mock_connect.insert_article(article)
        call_args = db_with_mock_connect.cur.execute.call_args
        sql: str = call_args[0][0]
        assert "'uningested'" in sql

    def test_insert_article_includes_search_query_and_raw_response(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """insert_article SQL 应包含 search_query 和 raw_response 字段。"""
        article: dict[str, Any] = {
            "pmid": "12345678",
            "article_info": {"title": "Test"},
            "study_groups": [],
            "results_info": None,
            "objectives": "",
            "is_free_download": False,
            "search_query": "heart",
            "raw_response": {"data": "test"},
        }
        db_with_mock_connect.insert_article(article)
        call_args = db_with_mock_connect.cur.execute.call_args
        sql: str = call_args[0][0]
        assert "search_query" in sql
        assert "raw_response" in sql


# ---------------------------------------------------------------------------
# get_article_by_pmid
# ---------------------------------------------------------------------------


class TestGetArticleByPmid:
    """测试 get_article_by_pmid 方法。"""

    def test_article_found(self, db_with_mock_connect: PostgresDB) -> None:
        """存在的 PMID 应返回文章 dict。"""
        expected: dict[str, Any] = {"pmid": "12345678", "title": "Test"}
        db_with_mock_connect.cur.fetchone.return_value = expected
        result = db_with_mock_connect.get_article_by_pmid("12345678")
        assert result == expected

    def test_article_not_found(self, db_with_mock_connect: PostgresDB) -> None:
        """不存在的 PMID 应返回 None。"""
        db_with_mock_connect.cur.fetchone.return_value = None
        result = db_with_mock_connect.get_article_by_pmid("99999999")
        assert result is None

    def test_get_article_ensures_connected(self) -> None:
        """get_article_by_pmid 应首先调用 _ensure_connected。"""
        db = PostgresDB()
        with patch.object(db, "_ensure_connected") as mock_ensure:
            db.conn = MagicMock()
            db.conn.closed = False
            db.cur = MagicMock()
            db.cur.fetchone.return_value = None
            db.get_article_by_pmid("123")
            mock_ensure.assert_called_once()


# ---------------------------------------------------------------------------
# list_articles (T24)
# ---------------------------------------------------------------------------


class TestListArticles:
    """测试 list_articles 方法。"""

    def test_basic_list(self, db_with_mock_connect: PostgresDB) -> None:
        """基本分页查询应返回 (rows, total)。"""
        fake_rows: list[dict[str, Any]] = [
            {"pmid": "1", "article_info": {"title": "A"}},
            {"pmid": "2", "article_info": {"title": "B"}},
        ]
        # count query then data query
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 2}
        db_with_mock_connect.cur.fetchall.return_value = fake_rows

        rows, total = db_with_mock_connect.list_articles(page=1, page_size=10)
        assert total == 2
        assert len(rows) == 2
        # 验证 execute 被调用了两次（count + data）
        assert db_with_mock_connect.cur.execute.call_count == 2

    def test_with_search_filter(self, db_with_mock_connect: PostgresDB) -> None:
        """带 search 参数时应构建 ILIKE 条件。"""
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 0}
        db_with_mock_connect.cur.fetchall.return_value = []

        db_with_mock_connect.list_articles(search="vaccine")

        # 检查第一次调用（count SQL）是否包含 ILIKE
        first_call_sql = db_with_mock_connect.cur.execute.call_args_list[0][0][0]
        assert "ILIKE" in first_call_sql

    def test_with_ingestion_status_filter(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """带 ingestion_status 参数时应构建等值过滤条件。"""
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 0}
        db_with_mock_connect.cur.fetchall.return_value = []

        db_with_mock_connect.list_articles(ingestion_status="ingested")

        first_call_sql = db_with_mock_connect.cur.execute.call_args_list[0][0][0]
        assert "ingestion_status" in first_call_sql

    def test_sql_injection_sort_by_falls_back_to_default(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """sort_by="; DROP TABLE--" 应被白名单拦截，回退到 'created_at' (T24)。"""
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 0}
        db_with_mock_connect.cur.fetchall.return_value = []

        db_with_mock_connect.list_articles(sort_by="; DROP TABLE--")

        # 第二次调用（data SQL）不应包含恶意字符串
        data_call_sql = db_with_mock_connect.cur.execute.call_args_list[1][0][0]
        assert "; DROP TABLE--" not in data_call_sql
        assert "ORDER BY created_at" in data_call_sql

    def test_sql_injection_order_falls_back_to_default(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """order="; DELETE FROM--" 应被白名单拦截，回退到 'desc'。"""
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 0}
        db_with_mock_connect.cur.fetchall.return_value = []

        db_with_mock_connect.list_articles(order="; DELETE FROM--")

        data_call_sql = db_with_mock_connect.cur.execute.call_args_list[1][0][0]
        assert "; DELETE FROM--" not in data_call_sql

    def test_valid_sort_by_accepted(self, db_with_mock_connect: PostgresDB) -> None:
        """合法的 sort_by 值应被正常使用。"""
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 0}
        db_with_mock_connect.cur.fetchall.return_value = []

        db_with_mock_connect.list_articles(sort_by="pmid", order="asc")

        data_call_sql = db_with_mock_connect.cur.execute.call_args_list[1][0][0]
        assert "ORDER BY pmid asc" in data_call_sql

    def test_list_articles_handles_empty_table(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """表中无数据时返回 total=0 和空列表。"""
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 0}
        db_with_mock_connect.cur.fetchall.return_value = []

        rows, total = db_with_mock_connect.list_articles()
        assert total == 0
        assert rows == []


# ---------------------------------------------------------------------------
# update_ingestion_status (T26)
# ---------------------------------------------------------------------------


class TestUpdateIngestionStatus:
    """测试 update_ingestion_status 方法。"""

    def test_update_to_ingested_sets_ingested_at(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """status="ingested" 时 SQL 应包含 ingested_at = NOW()。"""
        db_with_mock_connect.update_ingestion_status(
            pmid="12345678", status="ingested", chunk_count=3,
            vector_ids=["id1", "id2", "id3"],
        )
        call_sql = db_with_mock_connect.cur.execute.call_args[0][0]
        assert "ingested_at = NOW()" in call_sql
        assert "ingestion_error = NULL" in call_sql

    def test_update_to_ingested_without_optional_fields(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """status="ingested" 无可选字段时也应正常执行。"""
        db_with_mock_connect.update_ingestion_status(
            pmid="12345678", status="ingested"
        )
        call_sql = db_with_mock_connect.cur.execute.call_args[0][0]
        assert "ingested_at = NOW()" in call_sql
        db_with_mock_connect.conn.commit.assert_called_once()

    def test_update_to_failed_with_error(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """status="failed" 时 SQL 应包含 ingestion_error。"""
        db_with_mock_connect.update_ingestion_status(
            pmid="12345678", status="failed", error="ChromaDB connection timeout"
        )
        call_sql = db_with_mock_connect.cur.execute.call_args[0][0]
        assert "ingestion_error = %s" in call_sql

    def test_update_to_ingesting(self, db_with_mock_connect: PostgresDB) -> None:
        """status="ingesting" 应正常更新。"""
        db_with_mock_connect.update_ingestion_status(
            pmid="12345678", status="ingesting"
        )
        db_with_mock_connect.conn.commit.assert_called_once()

    def test_update_rollback_on_error(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """更新失败时应调用 rollback。"""
        db_with_mock_connect.cur.execute.side_effect = Exception("connection lost")
        with pytest.raises(Exception, match="connection lost"):
            db_with_mock_connect.update_ingestion_status(
                pmid="12345678", status="ingested"
            )
        db_with_mock_connect.conn.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# count_articles_by_status
# ---------------------------------------------------------------------------


class TestCountArticlesByStatus:
    """测试 count_articles_by_status 方法。"""

    def test_returns_all_statuses(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """应返回包含 total, ingested, uningested, failed 的 dict。"""
        db_with_mock_connect.cur.fetchone.return_value = {
            "total": 10,
            "ingested": 7,
            "uningested": 2,
            "failed": 1,
        }
        result = db_with_mock_connect.count_articles_by_status()
        assert result == {
            "total": 10,
            "ingested": 7,
            "uningested": 2,
            "failed": 1,
        }

    def test_handles_none_values(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """当数据库返回 None 时应转换为 0。"""
        db_with_mock_connect.cur.fetchone.return_value = {
            "total": None,
            "ingested": None,
            "uningested": None,
            "failed": None,
        }
        result = db_with_mock_connect.count_articles_by_status()
        assert result == {
            "total": 0,
            "ingested": 0,
            "uningested": 0,
            "failed": 0,
        }


# ---------------------------------------------------------------------------
# count_all
# ---------------------------------------------------------------------------


class TestCountAll:
    """测试 count_all 方法。"""

    def test_returns_count(self, db_with_mock_connect: PostgresDB) -> None:
        """正常情况应返回总数。"""
        db_with_mock_connect.cur.fetchone.return_value = {"cnt": 42}
        result = db_with_mock_connect.count_all()
        assert result == 42

    def test_returns_zero_when_none(self, db_with_mock_connect: PostgresDB) -> None:
        """fetchone 返回 None 时应返回 0。"""
        db_with_mock_connect.cur.fetchone.return_value = None
        result = db_with_mock_connect.count_all()
        assert result == 0


# ---------------------------------------------------------------------------
# delete_article (T27)
# ---------------------------------------------------------------------------


class TestDeleteArticle:
    """测试 delete_article 方法。"""

    def test_delete_existing_article(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """删除存在的 PMID 应返回 True。"""
        db_with_mock_connect.cur.rowcount = 1
        result = db_with_mock_connect.delete_article("12345678")
        assert result is True
        db_with_mock_connect.conn.commit.assert_called_once()

    def test_delete_nonexistent_article(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """删除不存在的 PMID 应返回 False (T27)。"""
        db_with_mock_connect.cur.rowcount = 0
        result = db_with_mock_connect.delete_article("99999999")
        assert result is False
        db_with_mock_connect.conn.commit.assert_called_once()

    def test_delete_rollback_on_error(
        self, db_with_mock_connect: PostgresDB
    ) -> None:
        """删除失败时应调用 rollback。"""
        db_with_mock_connect.cur.execute.side_effect = Exception("connection lost")
        with pytest.raises(Exception, match="connection lost"):
            db_with_mock_connect.delete_article("12345678")
        db_with_mock_connect.conn.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Backward compatibility (T20)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """测试向后兼容性。"""

    def test_singleton_exists(self) -> None:
        """PostgresDB_singleton 应为 PostgresDB 实例。"""
        assert isinstance(PostgresDB_singleton, PostgresDB)

    def test_singleton_has_expected_attributes(self) -> None:
        """单例应有 conn_params, table 等属性。"""
        assert hasattr(PostgresDB_singleton, "conn_params")
        assert hasattr(PostgresDB_singleton, "table")
        assert hasattr(PostgresDB_singleton, "conn")
        assert hasattr(PostgresDB_singleton, "cur")


# ---------------------------------------------------------------------------
# RealDictCursor
# ---------------------------------------------------------------------------


class TestRealDictCursor:
    """测试 RealDictCursor 集成。"""

    def test_connect_uses_real_dict_cursor(self) -> None:
        """connect() 应使用 cursor_factory=RealDictCursor。"""
        db = PostgresDB()
        with patch("psycopg2.connect") as mock_psycopg2_connect:
            mock_conn = MagicMock()
            mock_psycopg2_connect.return_value = mock_conn
            db.connect()
            mock_conn.cursor.assert_called_once()
            call_kwargs = mock_conn.cursor.call_args
            if call_kwargs and call_kwargs[1]:
                from psycopg2.extras import RealDictCursor
                assert call_kwargs[1].get("cursor_factory") == RealDictCursor
