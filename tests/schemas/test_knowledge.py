"""tests for schemas/knowledge.py — KnowledgeStatsData and VectorStoreInfo."""

from schemas.knowledge import KnowledgeStatsData, VectorStoreInfo


class TestVectorStoreInfo:
    """VectorStoreInfo 模型单元测试。"""

    def test_default_values(self) -> None:
        """不传任何参数 → 所有字段为默认空字符串。"""
        vs = VectorStoreInfo()
        assert vs.collection_name == ""
        assert vs.storage_path == ""
        assert vs.embedding_model == ""

    def test_full_construction(self) -> None:
        """传入完整数据 → 各字段值与传入一致。"""
        vs = VectorStoreInfo(
            collection_name="pubmed_collection",
            storage_path="/data/chroma",
            embedding_model="text-embedding-v2",
        )
        assert vs.collection_name == "pubmed_collection"
        assert vs.storage_path == "/data/chroma"
        assert vs.embedding_model == "text-embedding-v2"

    def test_model_dump(self) -> None:
        """.model_dump() 输出与预期一致。"""
        vs = VectorStoreInfo(
            collection_name="test_col",
            storage_path="/tmp/chroma",
            embedding_model="bge-large-zh",
        )
        dump = vs.model_dump()
        assert dump == {
            "collection_name": "test_col",
            "storage_path": "/tmp/chroma",
            "embedding_model": "bge-large-zh",
        }

    def test_field_descriptions_present(self) -> None:
        """确保每个字段都有中文 description。"""
        fields = VectorStoreInfo.model_fields
        for field_name in ("collection_name", "storage_path", "embedding_model"):
            assert fields[field_name].description, (
                f"Field '{field_name}' 缺少 description"
            )


class TestKnowledgeStatsData:
    """KnowledgeStatsData 模型单元测试。"""

    def test_default_values(self) -> None:
        """不传任何参数 → 所有字段为默认值。"""
        stats = KnowledgeStatsData()
        assert stats.local_documents == 0
        assert stats.pubmed_articles_total == 0
        assert stats.pubmed_articles_ingested == 0
        assert stats.pubmed_articles_uningested == 0
        assert stats.total_vector_chunks == 0
        assert stats.by_source_type == {}
        assert isinstance(stats.vector_store, VectorStoreInfo)
        # 嵌套的 VectorStoreInfo 也是默认空值
        assert stats.vector_store.collection_name == ""

    def test_full_construction(self) -> None:
        """传入完整数据 → .model_dump() 输出与预期一致。"""
        vs = VectorStoreInfo(
            collection_name="kb_collection",
            storage_path="/app/chroma_data",
            embedding_model="qwen-embedding",
        )
        stats = KnowledgeStatsData(
            local_documents=15,
            pubmed_articles_total=47,
            pubmed_articles_ingested=42,
            pubmed_articles_uningested=5,
            total_vector_chunks=2340,
            by_source_type={"local_file": 1820, "pubmed": 520},
            vector_store=vs,
        )
        dump = stats.model_dump()
        expected = {
            "local_documents": 15,
            "pubmed_articles_total": 47,
            "pubmed_articles_ingested": 42,
            "pubmed_articles_uningested": 5,
            "total_vector_chunks": 2340,
            "by_source_type": {"local_file": 1820, "pubmed": 520},
            "vector_store": {
                "collection_name": "kb_collection",
                "storage_path": "/app/chroma_data",
                "embedding_model": "qwen-embedding",
            },
        }
        assert dump == expected

    def test_default_vector_store_is_independent(self) -> None:
        """确保默认的 VectorStoreInfo 是每次调用时新建的实例。"""
        stats1 = KnowledgeStatsData()
        stats2 = KnowledgeStatsData()
        assert stats1.vector_store is not stats2.vector_store
        stats1.vector_store.collection_name = "changed"
        assert stats2.vector_store.collection_name == ""

    def test_by_source_type_serialization(self) -> None:
        """by_source_type 正确序列化 Dict[str, int]。"""
        stats = KnowledgeStatsData(
            by_source_type={"local_file": 1820, "pubmed": 520},
        )
        assert stats.by_source_type == {"local_file": 1820, "pubmed": 520}
        assert stats.by_source_type["local_file"] == 1820
        assert stats.by_source_type["pubmed"] == 520
        dump = stats.model_dump()
        assert dump["by_source_type"] == {"local_file": 1820, "pubmed": 520}

    def test_by_source_type_empty_default(self) -> None:
        """未传 by_source_type 时默认为空 dict。"""
        stats = KnowledgeStatsData()
        assert stats.by_source_type == {}
        assert isinstance(stats.by_source_type, dict)

    def test_partial_construction(self) -> None:
        """只传入部分字段 → 未传字段使用默认值。"""
        stats = KnowledgeStatsData(local_documents=5, total_vector_chunks=100)
        assert stats.local_documents == 5
        assert stats.pubmed_articles_total == 0
        assert stats.pubmed_articles_ingested == 0
        assert stats.pubmed_articles_uningested == 0
        assert stats.total_vector_chunks == 100
        assert stats.by_source_type == {}
        assert isinstance(stats.vector_store, VectorStoreInfo)

    def test_field_descriptions_present(self) -> None:
        """确保每个字段都有中文 description。"""
        fields = KnowledgeStatsData.model_fields
        expected_fields = (
            "local_documents",
            "pubmed_articles_total",
            "pubmed_articles_ingested",
            "pubmed_articles_uningested",
            "total_vector_chunks",
            "by_source_type",
            "vector_store",
        )
        for field_name in expected_fields:
            assert fields[field_name].description, (
                f"Field '{field_name}' 缺少 description"
            )
