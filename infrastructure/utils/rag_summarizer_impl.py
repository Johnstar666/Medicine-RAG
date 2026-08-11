from typing import List
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from domain.entities.document import Document
from domain.entities.query import Query
from domain.entities.rag_response import RAGResponse
from domain.services.rag_summarize_service import RAGSummarizeService
from domain.services.document_retrieval_service import DocumentRetrievalService
from infrastructure.utils.prompt_loader import load_rag_summarize_prompt
from infrastructure.models.factory import chat_model

class LangChainRAGSummarizer(RAGSummarizeService):
    """基于LangChain的RAG摘要服务实现"""
    
    def __init__(self, document_retrieval_service: DocumentRetrievalService):
        """初始化RAG摘要服务
        
        Args:
            document_retrieval_service: 文档检索服务
        """
        self.document_retrieval_service = document_retrieval_service
        self.prompt_text = load_rag_summarize_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()
        
    def _init_chain(self):
        """初始化LLM链"""
        return self.prompt_template | self.model | StrOutputParser()
    
    def summarize(self, query: Query) -> RAGResponse:
        """根据查询和相关文档生成摘要
        
        Args:
            query: 查询实体，包含问题和关键词
            
        Returns:
            RAG响应结果，包含答案、来源等
        """
        if not query.keywords:
            raise ValueError("关键词不能为空")
            
        # 1. 检索相关文档
        context_docs = self.retrieve_documents(query.keywords, query.top_k)
        
        # 2. 文档去重
        context_docs = self.deduplicate_documents(context_docs)
        
        # 3. 格式化上下文
        context = self.format_documents_for_context(context_docs)
        
        # 4. 调用LLM生成响应
        response = self.chain.invoke({
            "input": query.keywords,
            "context": context
        })
        
        # 5. 提取来源
        sources = [doc.source for doc in context_docs if doc.source]
        
        return RAGResponse(
            question=query.question,
            answer=response,
            sources=sources,
            keywords=query.keywords
        )
    
    def retrieve_documents(self, query: str, top_k: int = 3) -> List[Document]:
        """获取与查询相关的文档
        
        Args:
            query: 查询文本
            top_k: 返回的文档数量
            
        Returns:
            相关文档列表
        """
        return self.document_retrieval_service.retrieve_documents(query, top_k)
    
    def deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """根据来源对文档进行去重
        
        Args:
            documents: 文档列表
            
        Returns:
            去重后的文档列表
        """
        return self.document_retrieval_service.deduplicate_documents(documents)
    
    def format_documents_for_context(self, documents: List[Document]) -> str:
        """将文档格式化为上下文字符串
        
        Args:
            documents: 文档列表
            
        Returns:
            格式化后的上下文字符串
        """
        return self.document_retrieval_service.format_documents_for_context(documents)
    
    def get_relevant_documents(self, query: Query) -> List[Document]:
        """获取与查询相关的文档
        
        Args:
            query: 查询实体
            
        Returns:
            相关文档列表
        """
        if not query.keywords:
            raise ValueError("关键词不能为空")
            
        return self.retrieve_documents(query.keywords, query.top_k)