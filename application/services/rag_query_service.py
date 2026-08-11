from typing import List
from domain.entities.query import Query
from domain.entities.rag_response import RAGResponse
from domain.services.keyword_extraction_service import KeywordExtractionService
from domain.services.document_retrieval_service import DocumentRetrievalService
from domain.services.rag_summarize_service import RAGSummarizeService

class RAGQueryService:
    """RAG查询应用服务"""
    
    def __init__(self,
                 keyword_extraction_service: KeywordExtractionService,
                 document_retrieval_service: DocumentRetrievalService,
                 rag_summarize_service: RAGSummarizeService):
        """初始化RAG查询服务
        
        Args:
            keyword_extraction_service: 关键词提取服务
            document_retrieval_service: 文档检索服务
            rag_summarize_service: RAG摘要服务
        """
        self.keyword_extraction_service = keyword_extraction_service
        self.document_retrieval_service = document_retrieval_service
        self.rag_summarize_service = rag_summarize_service
    
    def process_query(self, query: Query) -> RAGResponse:
        """处理RAG查询请求
        
        Args:
            query: 查询实体
            
        Returns:
            RAG响应结果
        """
        # 1. 提取关键词
        keywords = self.keyword_extraction_service.extract_keywords(query.question)
        query_with_keywords = query.with_keywords(keywords)
        
        # 2. 使用RAG摘要服务处理查询
        response = self.rag_summarize_service.summarize(query_with_keywords)
        
        return response