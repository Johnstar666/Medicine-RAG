from abc import ABC, abstractmethod
from typing import List
from domain.entities.document import Document
from domain.entities.query import Query
from domain.entities.rag_response import RAGResponse

class RAGSummarizeService(ABC):
    """RAG摘要服务接口"""
    
    @abstractmethod
    def summarize(self, query: Query) -> RAGResponse:
        """根据查询和相关文档生成摘要
        
        Args:
            query: 查询实体，包含问题和关键词
            
        Returns:
            RAG响应结果，包含答案、来源等
        """
        pass
    
    @abstractmethod
    def get_relevant_documents(self, query: Query) -> List[Document]:
        """获取与查询相关的文档
        
        Args:
            query: 查询实体
            
        Returns:
            相关文档列表
        """
        pass