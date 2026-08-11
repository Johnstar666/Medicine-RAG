"""Tests for api/routers/knowledge_router.py — GET /knowledge/stats."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_project_root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
)
sys.path.insert(0, _project_root)

from api.routers.knowledge_router import (  # noqa: E402
    router,
    set_knowledge_management_service,
)
from schemas.knowledge import KnowledgeStatsData, VectorStoreInfo  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def mock_service() -> MagicMock:
    """返回一个 mock 的 KnowledgeManagementService。"""
    return MagicMock()


@pytest.fixture
def sample_stats() -> KnowledgeStatsData:
    """返回一份示例统计数据。"""
    vs_info = VectorStoreInfo(
        collection_name="test_collection",
        storage_path="/tmp/chroma_test",
        embedding_model="test-embedding-v1",
    )
    return KnowledgeStatsData(
        local_documents=15,
        pubmed_articles_total=47,
        pubmed_articles_ingested=42,
        pubmed_articles_uningested=5,
        total_vector_chunks=2340,
        by_source_type={"local_file": 1820, "pubmed": 520},
        vector_store=vs_info,
    )


@pytest.fixture
def app_with_service(
    mock_service: MagicMock,
    sample_stats: KnowledgeStatsData,
) -> FastAPI:
    """创建已注入 mock service 的 FastAPI 测试应用。"""
    mock_service.get_knowledge_stats.return_value = sample_stats
    set_knowledge_management_service(mock_service)

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app_with_service: FastAPI) -> TestClient:
    """FastAPI TestClient。"""
    return TestClient(app_with_service)


# ── Tests: GET /knowledge/stats (成功路径) ────────────────────


class TestGetKnowledgeStatsSuccess:
    """正常统计查询测试。"""

    def test_returns_200(self, client: TestClient) -> None:
        """注入 service 且 service 正常返回 → HTTP 200。"""
        response = client.get("/knowledge/stats")
        assert response.status_code == 200

    def test_response_structure(self, client: TestClient) -> None:
        """响应体包含 code=200, message='success' 和完整的 data 结构。"""
        response = client.get("/knowledge/stats")
        body = response.json()

        assert body["code"] == 200
        assert body["message"] == "success"
        assert body["data"] is not None

        data = body["data"]
        assert data["local_documents"] == 15
        assert data["pubmed_articles_total"] == 47
        assert data["pubmed_articles_ingested"] == 42
        assert data["pubmed_articles_uningested"] == 5
        assert data["total_vector_chunks"] == 2340
        assert data["by_source_type"] == {
            "local_file": 1820,
            "pubmed": 520,
        }
        assert data["vector_store"]["collection_name"] == "test_collection"
        assert data["vector_store"]["storage_path"] == "/tmp/chroma_test"
        assert data["vector_store"]["embedding_model"] == "test-embedding-v1"

    def test_calls_get_knowledge_stats_on_service(
        self,
        client: TestClient,
        mock_service: MagicMock,
    ) -> None:
        """确保端点调用了 service.get_knowledge_stats()。"""
        client.get("/knowledge/stats")
        mock_service.get_knowledge_stats.assert_called_once()


# ── Tests: GET /knowledge/stats (by_source_type 序列化) ───────


class TestBySourceTypeSerialization:
    """by_source_type 字段 JSON 序列化测试。"""

    def test_by_source_type_serialized_correctly(self) -> None:
        """by_source_type 正确序列化为 JSON object.

        T10: 验证 by_source_type 在 JSON 中表示为
        ``{"local_file": N, "pubmed": M}``。
        """
        stats = KnowledgeStatsData(
            by_source_type={"local_file": 1820, "pubmed": 520},
        )
        dump = stats.model_dump()
        assert dump["by_source_type"] == {
            "local_file": 1820,
            "pubmed": 520,
        }
        assert isinstance(dump["by_source_type"], dict)

    def test_by_source_type_in_api_response(self) -> None:
        """通过 API 端点验证 by_source_type 在 HTTP 响应中正确序列化。"""
        mock_svc = MagicMock()
        vs_info = VectorStoreInfo(
            collection_name="c",
            storage_path="/p",
            embedding_model="m",
        )
        stats = KnowledgeStatsData(
            by_source_type={"local_file": 100, "pubmed": 50},
            vector_store=vs_info,
        )
        mock_svc.get_knowledge_stats.return_value = stats
        set_knowledge_management_service(mock_svc)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/knowledge/stats")
        body = response.json()

        assert body["data"]["by_source_type"] == {
            "local_file": 100,
            "pubmed": 50,
        }
        # 确保值是 int 类型（JSON 中的 number）
        assert isinstance(body["data"]["by_source_type"]["local_file"], int)
        assert isinstance(body["data"]["by_source_type"]["pubmed"], int)

    def test_empty_by_source_type(self) -> None:
        """未传入 by_source_type 时序列化为 {}。"""
        stats = KnowledgeStatsData()
        dump = stats.model_dump()
        assert dump["by_source_type"] == {}


# ── Tests: GET /knowledge/stats (service 未注入) ──────────────


class TestGetKnowledgeStatsServiceNotInitialized:
    """service 未注入场景测试。"""

    def test_returns_500_when_service_not_set(self) -> None:
        """T09: service 未注入 → HTTP 500。

        未注入服务时，端点应返回 500 并附带 'not initialized' 消息。
        """
        # 注入 None 以重置 service 状态
        set_knowledge_management_service(None)  # type: ignore[arg-type]

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/knowledge/stats")
        assert response.status_code == 500

        body = response.json()
        assert "detail" in body
        assert "not initialized" in body["detail"].lower()

    def test_returns_500_when_service_is_none_explicitly(self) -> None:
        """显式将 service 设为 None → HTTP 500。"""
        set_knowledge_management_service(None)  # type: ignore[arg-type]

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/knowledge/stats")
        assert response.status_code == 500


# ── Tests: GET /knowledge/stats (service 抛出异常) ────────────


class TestGetKnowledgeStatsServiceException:
    """service 内部异常测试。"""

    def test_service_exception_maps_to_500(self) -> None:
        """service 抛出异常 → HTTP 500 + detail=str(e)。"""
        mock_svc = MagicMock()
        mock_svc.get_knowledge_stats.side_effect = RuntimeError(
            "Database connection failed"
        )
        set_knowledge_management_service(mock_svc)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/knowledge/stats")
        assert response.status_code == 500

        body = response.json()
        assert body["detail"] == "Database connection failed"

    def test_value_error_maps_to_500(self) -> None:
        """service 抛出 ValueError → HTTP 500。"""
        mock_svc = MagicMock()
        mock_svc.get_knowledge_stats.side_effect = ValueError(
            "Invalid config"
        )
        set_knowledge_management_service(mock_svc)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/knowledge/stats")
        assert response.status_code == 500
        assert response.json()["detail"] == "Invalid config"
