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
        """根据查询检索相关文档，保证源多样性。

        策略：
        1. 先取 top_k * 3 候选（或用 similarity_search 直接指定 k）
        2. 按 source_type 分组：local_file / pubmed
        3. 交叉选取 top_k 篇，至少包含每种来源 1 篇（若存在）

        Args:
            query: 查询文本
            top_k: 返回的文档数量

        Returns:
            相关文档列表
        """
        # 取更多候选，为源多样性留空间
        fetch_k = max(top_k * 3, 10)
        try:
            langchain_docs = self.vector_store_service.vector_store.similarity_search(
                query, k=fetch_k
            )
        except Exception:
            # 若 similarity_search 失败，回退到预配置的 retriever
            langchain_docs = self.retriever.invoke(query)

        domain_docs = self._convert_to_domain_documents(langchain_docs)

        # 源多样性选取：保证每种存在 source_type 至少 1 篇
        local_docs = [
            d
            for d in domain_docs
            if d.metadata.get("source_type", "local_file") != "pubmed"
        ]
        pubmed_docs = [
            d for d in domain_docs if d.metadata.get("source_type") == "pubmed"
        ]

        diverse: list[Document] = []
        # 先从每种来源取 1 篇（若存在）
        if local_docs:
            diverse.append(local_docs.pop(0))
        if pubmed_docs:
            diverse.append(pubmed_docs.pop(0))

        # 剩余位置按原始排序交叉填充
        remaining = local_docs + pubmed_docs  # 保持原有相似度排序（组间）
        diverse.extend(remaining[: top_k - len(diverse)])

        return diverse[:top_k]
    
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