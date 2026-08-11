from infrastructure.persistence.vector_store import VectorStoreService
from infrastructure.persistence.document_retriever_impl import VectorDocumentRetriever
from infrastructure.utils.keyword_extractor_impl import RuleBasedKeywordExtractor
from infrastructure.utils.rag_summarizer_impl import LangChainRAGSummarizer
from application.services.rag_query_service import RAGQueryService

class ServiceFactory:
    """服务工厂类，用于创建和管理服务实例"""
    
    def __init__(self):
        """初始化服务工厂"""
        self._vector_store_service = None
        self._document_retriever = None
        self._keyword_extractor = None
        self._rag_summarizer = None
        self._rag_query_service = None
    
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