from langchain_core.documents import Document as LangchainDocument

from domain.entities.document import Document
from domain.services.document_retrieval_service import DocumentRetrievalService
from infrastructure.persistence.vector_store import VectorStoreService


class VectorDocumentRetriever(DocumentRetrievalService):
    """基于向量存储的文档检索实现"""
    
    def __init__(self, vector_store_service: VectorStoreService):
        """初始化向量文档检索器
        
        Args:
            vector_store_service: 向量存储服务
        """
        self.vector_store_service = vector_store_service
        self.retriever = self.vector_store_service.get_retriever()
    
    def retrieve_documents(self, query: str, top_k: int = 3) -> list[Document]:
        """根据查询检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的文档数量
            
        Returns:
            相关文档列表
        """
        langchain_docs = self.retriever.invoke(query)
        return self._convert_to_domain_documents(langchain_docs)
    
    def deduplicate_documents(self, documents: list[Document]) -> list[Document]:
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
    
    def format_documents_for_context(self, documents: list[Document]) -> str:
        """按 source_type 生成差异化引文格式。

        local_file: [N] 《文件名（无后缀）》.
        pubmed:     [N] Authors. Title. Journal. Year. PMID: xxxxx.

        若 source_type 为空或未知，默认按 local_file 格式处理（向后兼容）。

        Args:
            documents: 文档列表

        Returns:
            格式化后的上下文字符串
        """
        context_parts: list[str] = []
        for i, doc in enumerate(documents, 1):
            source_type = doc.metadata.get("source_type", "local_file")

            if source_type == "pubmed":
                formatted = self._format_pubmed_citation(doc, i)
            else:
                formatted = self._format_local_citation(doc, i)

            context_parts.append(f"{formatted}\n{doc.content}\n\n")

        return "".join(context_parts)

    @staticmethod
    def _format_local_citation(doc: Document, index: int) -> str:
        """格式化本地文件引文: [N] 《文件名》.

        Args:
            doc: 文档实体
            index: 引文序号

        Returns:
            格式化后的本地文件引文字符串
        """
        source = doc.source or f"参考资料{index}"
        # 去掉文件后缀
        for ext in [".docx", ".doc", ".pdf", ".txt"]:
            if source.endswith(ext):
                source = source[:-len(ext)]
                break
        return f"[{index}] 《{source}》."

    @staticmethod
    def _format_pubmed_citation(doc: Document, index: int) -> str:
        """格式化 PubMed 文献引文（温哥华格式）。

        格式: [N] Authors. Title. Journal. Year. PMID: xxxxx.

        Args:
            doc: 文档实体
            index: 引文序号

        Returns:
            格式化后的 PubMed 引文字符串
        """
        meta = doc.metadata
        authors = meta.get("authors", "")
        title = meta.get("title", "Unknown Title")
        journal = meta.get("journal", "")
        pub_date = meta.get("publish_date", "")
        year = pub_date[:4] if pub_date else ""
        pmid = meta.get("pmid", "")

        parts: list[str] = []
        if authors:
            parts.append(f"{authors}.")
        parts.append(f"{title}.")
        if journal:
            parts.append(f"{journal}.")
        if year:
            parts.append(f"{year}.")
        if pmid:
            parts.append(f"PMID: {pmid}.")

        return f"[{index}] {' '.join(parts)}"
    
    def _convert_to_domain_documents(
        self, langchain_docs: list[LangchainDocument],
    ) -> list[Document]:
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