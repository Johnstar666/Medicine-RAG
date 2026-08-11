"""服务工厂（DI 容器）。

负责全系统服务的创建与单例管理（懒加载）：
    - 原有 RAG 服务链：向量存储/文档检索/关键词提取/RAG 摘要/查询服务
    - Phase 5 新增：PostgreSQL/PubMed 检索器/PubMed 文章向量化/
      PubMed 搜索应用服务/知识库管理服务
所有 getter 均懒加载，保证跨服务共享同一实例。
"""

from application.services.knowledge_management_service import KnowledgeManagementService
from application.services.pubmed_search_service import PubMedSearchAppService
from application.services.rag_query_service import RAGQueryService
from infrastructure.persistence.document_retriever_impl import VectorDocumentRetriever
from infrastructure.persistence.postgres_db import PostgresDB
from infrastructure.persistence.pubmed_ingester import PubMedArticleIngester
from infrastructure.persistence.vector_store import VectorStoreService
from infrastructure.utils.config_handler import pubmed_conf
from infrastructure.utils.keyword_extractor_impl import RuleBasedKeywordExtractor
from infrastructure.utils.rag_summarizer_impl import LangChainRAGSummarizer
from pubmed.pubmed_retriever import PubMedRetriever


class ServiceFactory:
    """服务工厂类，用于创建和管理服务实例"""
    
    def __init__(self):
        """初始化服务工厂"""
        self._vector_store_service = None
        self._document_retriever = None
        self._keyword_extractor = None
        self._rag_summarizer = None
        self._rag_query_service = None
        self._postgres_db = None
        self._pubmed_retriever = None
        self._pubmed_ingester = None
        self._pubmed_search_service = None
        self._knowledge_management_service = None
    
    def get_vector_store_service(self) -> VectorStoreService:
        """获取向量存储服务实例"""
        if not self._vector_store_service:
            self._vector_store_service = VectorStoreService()
        return self._vector_store_service
    
    def get_document_retriever(self) -> VectorDocumentRetriever:
        """获取文档检索服务实例"""
        if not self._document_retriever:
            self._document_retriever = VectorDocumentRetriever(
                self.get_vector_store_service()
            )
        return self._document_retriever
    
    def get_keyword_extractor(self) -> RuleBasedKeywordExtractor:
        """获取关键词提取服务实例"""
        if not self._keyword_extractor:
            self._keyword_extractor = RuleBasedKeywordExtractor()
        return self._keyword_extractor
    
    def get_rag_summarizer(self) -> LangChainRAGSummarizer:
        """获取RAG摘要服务实例"""
        if not self._rag_summarizer:
            self._rag_summarizer = LangChainRAGSummarizer(
                self.get_document_retriever()
            )
        return self._rag_summarizer
    
    def get_rag_query_service(self) -> RAGQueryService:
        """获取RAG查询应用服务实例"""
        if not self._rag_query_service:
            self._rag_query_service = RAGQueryService(
                self.get_keyword_extractor(),
                self.get_document_retriever(),
                self.get_rag_summarizer()
            )
        return self._rag_query_service

    def get_postgres_db(self) -> PostgresDB:
        """获取PostgreSQL数据库访问实例（懒加载单例）"""
        if not self._postgres_db:
            self._postgres_db = PostgresDB()
        return self._postgres_db

    def get_pubmed_retriever(self) -> PubMedRetriever:
        """获取PubMed检索器实例（懒加载单例）"""
        if not self._pubmed_retriever:
            self._pubmed_retriever = PubMedRetriever()
        return self._pubmed_retriever

    def get_pubmed_ingester(self) -> PubMedArticleIngester:
        """获取PubMed文章向量化实例（懒加载单例）"""
        if not self._pubmed_ingester:
            self._pubmed_ingester = PubMedArticleIngester(
                self.get_postgres_db(),
                self.get_vector_store_service(),
            )
        return self._pubmed_ingester

    def get_pubmed_search_service(self) -> PubMedSearchAppService:
        """获取PubMed搜索应用服务实例（懒加载单例）"""
        if not self._pubmed_search_service:
            self._pubmed_search_service = PubMedSearchAppService(
                pubmed_retriever=self.get_pubmed_retriever(),
                postgres_db=self.get_postgres_db(),
                pubmed_ingester=self.get_pubmed_ingester(),
                request_interval=float(pubmed_conf["request_interval"]),
            )
        return self._pubmed_search_service

    def get_knowledge_management_service(self) -> KnowledgeManagementService:
        """获取知识库管理应用服务实例（懒加载单例）"""
        if not self._knowledge_management_service:
            self._knowledge_management_service = KnowledgeManagementService(
                postgres_db=self.get_postgres_db(),
                vector_store_service=self.get_vector_store_service(),
                pubmed_ingester=self.get_pubmed_ingester(),
            )
        return self._knowledge_management_service