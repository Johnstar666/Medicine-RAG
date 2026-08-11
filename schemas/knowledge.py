"""知识库统计 Schema 模块。

提供知识库统计概览所需的数据模型，包括向量存储信息和知识库统计数据。
"""

from pydantic import BaseModel, Field


class VectorStoreInfo(BaseModel):
    """向量存储信息。"""

    collection_name: str = Field(
        default="",
        description="ChromaDB collection 名称",
    )
    storage_path: str = Field(
        default="",
        description="向量存储持久化目录路径",
    )
    embedding_model: str = Field(
        default="",
        description="当前使用的 Embedding 模型名称",
    )


class KnowledgeStatsData(BaseModel):
    """知识库统计概览。

    汇总本地文档、PubMed 文献和 ChromaDB 向量存储的统计数据。
    """

    local_documents: int = Field(
        default=0,
        description="./data/ 目录中的本地文档数量",
    )
    pubmed_articles_total: int = Field(
        default=0,
        description="PubMed 文献总数（PostgreSQL 中记录数）",
    )
    pubmed_articles_ingested: int = Field(
        default=0,
        description="已向量索引的 PubMed 文献数",
    )
    pubmed_articles_uningested: int = Field(
        default=0,
        description="未向量索引的 PubMed 文献数",
    )
    total_vector_chunks: int = Field(
        default=0,
        description="ChromaDB 中的总 chunk 数量",
    )
    by_source_type: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "按来源类型分组的 chunk 数量统计，"
            "如 {'local_file': 1820, 'pubmed': 520}"
        ),
    )
    vector_store: VectorStoreInfo = Field(
        default_factory=VectorStoreInfo,
        description="向量存储基础信息",
    )
