"""测试 ServiceFactory DI 容器（tests/infrastructure/services）。

覆盖:
    - 懒加载单例（同一 getter 多次调用返回同一实例）
    - 依赖注入正确性（PubMedSearchAppService 注入 PostgresDB/PubMedRetriever）
    - 跨服务共享实例（ingester 与 knowledge-management-service 共享 PostgresDB）
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

# 模块级 import 会经 vector_store → factory.py 实例化 DashScopeEmbeddings，
# 需先设置 dummy key（与 test_vector_store.py 相同做法）
os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from infrastructure.services.service_factory import ServiceFactory


class TestServiceFactory:
    """ServiceFactory 懒加载单例与依赖注入测试。"""

    # ── T12: 懒加载单例 ─────────────────────────────────────────

    def test_get_postgres_db_returns_same_instance(self) -> None:
        """两次调用 get_postgres_db 应返回同一实例（懒加载单例）。"""
        factory = ServiceFactory()
        with patch(
            "infrastructure.services.service_factory.PostgresDB",
            return_value=MagicMock(),
        ) as mock_cls:
            db1 = factory.get_postgres_db()
            db2 = factory.get_postgres_db()
        assert db1 is db2
        mock_cls.assert_called_once()

    def test_get_vector_store_service_returns_same_instance(self) -> None:
        """两次调用 get_vector_store_service 应返回同一实例。"""
        factory = ServiceFactory()
        with patch(
            "infrastructure.services.service_factory.VectorStoreService",
            return_value=MagicMock(),
        ) as mock_cls:
            vs1 = factory.get_vector_store_service()
            vs2 = factory.get_vector_store_service()
        assert vs1 is vs2
        mock_cls.assert_called_once()

    # ── T13: 依赖注入正确性 ──────────────────────────────────────

    def test_get_pubmed_search_service_injects_dependencies(self) -> None:
        """get_pubmed_search_service 应注入 PostgresDB 与 PubMedRetriever。"""
        factory = ServiceFactory()
        with patch(
            "infrastructure.services.service_factory.PostgresDB",
            return_value=MagicMock(),
        ) as mock_db, patch(
            "infrastructure.services.service_factory.PubMedRetriever",
            return_value=MagicMock(),
        ) as mock_retriever, patch(
            "infrastructure.services.service_factory.PubMedArticleIngester",
            return_value=MagicMock(),
        ), patch(
            "infrastructure.services.service_factory.VectorStoreService",
            return_value=MagicMock(),
        ), patch(
            "infrastructure.services.service_factory.PubMedSearchAppService",
            return_value=MagicMock(),
        ) as mock_app:
            svc = factory.get_pubmed_search_service()

        assert svc is not None
        mock_db.assert_called_once()
        mock_retriever.assert_called_once()
        call = mock_app.call_args
        assert call is not None
        assert call.kwargs["pubmed_retriever"] is factory._pubmed_retriever
        assert call.kwargs["postgres_db"] is factory._postgres_db
        assert call.kwargs["pubmed_ingester"] is factory._pubmed_ingester
        assert call.kwargs["request_interval"] == 0.15

    # ── T14: 跨服务共享实例 ──────────────────────────────────────

    def test_ingester_and_km_service_share_postgres_db(self) -> None:
        """ingester 与 knowledge-management-service 应共享 PostgresDB。"""
        factory = ServiceFactory()
        with patch(
            "infrastructure.services.service_factory.PostgresDB",
            return_value=MagicMock(),
        ) as mock_db, patch(
            "infrastructure.services.service_factory.VectorStoreService",
            return_value=MagicMock(),
        ), patch(
            "infrastructure.services.service_factory.PubMedArticleIngester",
            return_value=MagicMock(),
        ) as mock_ingester, patch(
            "infrastructure.services.service_factory.KnowledgeManagementService",
            return_value=MagicMock(),
        ) as mock_km:
            ingester = factory.get_pubmed_ingester()
            km = factory.get_knowledge_management_service()

        assert ingester is not None and km is not None
        mock_db.assert_called_once()
        ing_call = mock_ingester.call_args
        assert ing_call is not None
        assert ing_call.args[0] is factory._postgres_db
        km_call = mock_km.call_args
        assert km_call is not None
        assert km_call.kwargs["postgres_db"] is factory._postgres_db
        assert km_call.kwargs["pubmed_ingester"] is factory._pubmed_ingester

    def test_ingester_and_retriever_share_vector_store(self) -> None:
        """ingester 与 document_retriever 应共享 VectorStoreService。"""
        factory = ServiceFactory()
        with patch(
            "infrastructure.services.service_factory.PostgresDB",
            return_value=MagicMock(),
        ), patch(
            "infrastructure.services.service_factory.VectorStoreService",
            return_value=MagicMock(),
        ), patch(
            "infrastructure.services.service_factory.PubMedArticleIngester",
            return_value=MagicMock(),
        ) as mock_ingester, patch(
            "infrastructure.services.service_factory.VectorDocumentRetriever",
            return_value=MagicMock(),
        ) as mock_doc:
            ingester = factory.get_pubmed_ingester()
            retriever = factory.get_document_retriever()

        assert ingester is not None and retriever is not None
        ing_call = mock_ingester.call_args
        assert ing_call is not None
        assert ing_call.args[1] is factory._vector_store_service
        doc_call = mock_doc.call_args
        assert doc_call is not None
        assert doc_call.args[0] is factory._vector_store_service
