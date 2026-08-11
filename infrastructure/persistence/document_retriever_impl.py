from typing import List
from domain.entities.document import Document
from domain.services.document_retrieval_service import DocumentRetrievalService
from infrastructure.persistence.vector_store import VectorStoreService
from langchain_core.documents import Document as LangchainDocument

class VectorDocumentRetriever(DocumentRetrievalService):
    """基于向量存储的文档检索实现"""
    
    def __init__(self, vector_store_service: VectorStoreService):
        """初始化向量文档检索器
        
        Args:
            vector_store_service: 向量存储服务
        """
        self.vector_store_service = vector_store_service
        self.retriever = self.vector_store_service.get_retriever()
    
    def retrieve_documents(self, query: str, top_k: int = 3) -> List[Document]:
        """根据查询检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的文档数量
            
        Returns:
            相关文档列表
        """
        langchain_docs = self.retriever.invoke(query)
        return self._convert_to_domain_documents(langchain_docs)
    
    def deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """根据来源对文档进行去重
        
        Args:
            documents: 文档列表
            
        Returns:
            去重后的文档列表
        """
        seen_sources = {}
        for doc in documents:
            source = doc.source
            if source and source not in seen_sources:
                seen_sources[source] = doc
            elif source:
                # 合并相同来源的文档内容
                seen_sources[source].content += "\n" + doc.content
        return list(seen_sources.values())
    
    def format_documents_for_context(self, documents: List[Document]) -> str:
        """将文档格式化为上下文字符串
        
        Args:
            documents: 文档列表
            
        Returns:
            格式化后的上下文字符串
        """
        context = ""
        for i, doc in enumerate(documents, 1):
            source = doc.source or f"参考资料{i}"
            context += f"[{i}] {source}\n{doc.content}\n\n"
        return context
    
    def _convert_to_domain_documents(self, langchain_docs: List[LangchainDocument]) -> List[Document]:
        """将LangChain文档转换为领域文档
        
        Args:
            langchain_docs: LangChain文档列表
            
        Returns:
            领域文档列表
        """
        return [
            Document(
                content=doc.page_content,
                metadata=doc.metadata
            )
            for doc in langchain_docs
        ]