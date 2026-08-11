from abc import ABC, abstractmethod
from typing import List
from domain.entities.document import Document

class DocumentRetrievalService(ABC):
    """文档检索服务接口"""
    
    @abstractmethod
    def retrieve_documents(self, query: str, top_k: int = 3) -> List[Document]:
        """根据查询检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的文档数量
            
        Returns:
            相关文档列表
        """
        pass
    
    @abstractmethod
    def deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """根据来源对文档进行去重
        
        Args:
            documents: 文档列表
            
        Returns:
            去重后的文档列表
        """
        pass
    
    @abstractmethod
    def format_documents_for_context(self, documents: List[Document]) -> str:
        """将文档格式化为上下文字符串
        
        Args:
            documents: 文档列表
            
        Returns:
            格式化后的上下文字符串
        """
        pass