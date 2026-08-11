import os

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.documents import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from infrastructure.models.factory import embed_model
from infrastructure.utils.config_handler import chroma_conf
from infrastructure.utils.file_handler import (
    doc_loader,
    docx_loader,
    get_file_md5_hex,
    listdir_with_allowed_types,
    pdf_loader,
    text_loader,
)
from infrastructure.utils.logger_handler import logger
from infrastructure.utils.path_tool import get_abs_path


class VectorStoreService:
    def __init__(self):
        self.vector_store=Chroma(
            collection_name=chroma_conf["collection_name"],
            persist_directory=get_abs_path(chroma_conf["persist_directory"]),
            embedding_function=embed_model,
        )
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separator"],
            length_function=len
        )
    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k":chroma_conf["k"]})
    def load_document(self):
        md5_path = get_abs_path(chroma_conf["md5_hex_store"])

        def check_md5_hex(md5_str: str):
            # 检查字符串是否已经被处理过
            if not os.path.exists(md5_path):
                open(md5_path, 'w', encoding='utf-8').close()
                return False  # 未被处理过
            else:
                for line in open(md5_path, encoding='utf-8').readlines():
                    line = line.strip()
                    if md5_str == line:
                        return True
                return False

        def save_md5(md5_str: str):
            with open(md5_path, 'a', encoding='utf-8') as f:
                f.write(md5_str + '\n')

        def get_file_documents(read_path:str)->list[Document]:
            if read_path.endswith('.txt'):
                return text_loader(read_path)
            elif read_path.endswith('.pdf'):
                return pdf_loader(read_path)
            elif read_path.endswith('.doc'):
                return doc_loader(read_path)
            elif read_path.endswith('.docx'):
                return docx_loader(read_path)
            else:
                return []
        allowed_files_path=listdir_with_allowed_types(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"])
        )
        for path in allowed_files_path:
            file_md5=get_file_md5_hex(path)
            if check_md5_hex(file_md5):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                continue
            try:
                documents: list[Document] = get_file_documents(path)
                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue
                split_document:list[Document]=self.spliter.split_documents(documents)
                if not split_document:
                    logger.warning(f"[加载知识库]分片后{path}内没有有效文本内容，跳过")
                    continue
                self.vector_store.add_documents(split_document)
                save_md5(file_md5)
                logger.info(f"[加载知识库]{path}内容加载成功")
            except Exception as e:
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}",exc_info=True)

    def add_documents_direct(
        self, documents: list[LangchainDocument]
    ) -> list[str]:
        """直接写入 ChromaDB，跳过 MD5 去重。

        供 PubMedArticleIngester 调用。
        与 load_document() 的区别：跳过 MD5 去重和文件类型判断，
        直接写入已构建好 metadata 的 LangchainDocument 列表。

        Args:
            documents: 已构建好 metadata 的 LangchainDocument 列表

        Returns:
            ChromaDB 分配的 ID 列表
        """
        try:
            ids = self.vector_store.add_documents(documents)
            logger.info(f"直接写入 {len(documents)} 个文档到 ChromaDB")
            return ids
        except Exception as e:
            logger.error(f"ChromaDB 写入失败: {e}")
            raise

    def delete_by_metadata_filter(self, metadata_filter: dict) -> int:
        """按 metadata 条件删除向量。

        ChromaDB 不支持直接 delete(where=...), 需两步操作：
        1. collection.get(where=filter) → 获取匹配的 IDs
        2. collection.delete(ids=ids)  → 删除

        Args:
            metadata_filter: ChromaDB where 条件，如 {"pmid": "12345678"}

        Returns:
            删除的 chunk 数量
        """
        try:
            results = self.vector_store.get(where=metadata_filter)
            ids = results.get("ids", [])
            if not ids:
                logger.debug(f"未找到匹配的向量: {metadata_filter}")
                return 0

            self.vector_store.delete(ids=ids)
            logger.info(f"按条件 {metadata_filter} 删除了 {len(ids)} 个 chunks")
            return len(ids)
        except Exception as e:
            logger.error(f"ChromaDB 条件删除失败 (filter={metadata_filter}): {e}")
            raise

    def get_collection_stats(self) -> dict:
        """获取 ChromaDB collection 统计信息。

        通过 self.vector_store._collection.count() 获取总 chunk 数，
        遍历 self.vector_store.get() 结果按 source_type 分组统计。
        若遍历失败（数据量大），返回 -1 表示不可用。

        Returns:
            {
                "total_chunks": 2340,
                "by_source_type": {"local_file": 1820, "pubmed": 520}
            }
        """
        try:
            total = self.vector_store._collection.count()

            by_type: dict[str, int] = {"local_file": 0, "pubmed": 0}
            try:
                all_data = self.vector_store.get(limit=99999, include=["metadatas"])
                for meta in all_data.get("metadatas", []):
                    st = meta.get("source_type", "local_file")
                    by_type[st] = by_type.get(st, 0) + 1
            except Exception:
                # 若数据量大，get() 可能耗时，返回 -1 表示不可用
                by_type = {"local_file": -1, "pubmed": -1}

            return {"total_chunks": total, "by_source_type": by_type}
        except Exception as e:
            logger.error(f"获取 ChromaDB 统计信息失败: {e}")
            return {"total_chunks": 0, "by_source_type": {}}

    def get_splitter(
        self, source_type: str = "local_file"
    ) -> RecursiveCharacterTextSplitter:
        """根据来源类型获取对应的 TextSplitter。

        Args:
            source_type: "local_file" 或 "pubmed"

        Returns:
            配置了对应 chunk_size / chunk_overlap 的 RecursiveCharacterTextSplitter
        """
        if source_type == "pubmed":
            chunk_size = chroma_conf.get("pubmed_chunk_size", 800)
            chunk_overlap = chroma_conf.get("pubmed_chunk_overlap", 200)
            separators = chroma_conf.get(
                "pubmed_separator",
                ["\n\n", "\n", ". ", "! ", "? ", "。", "！", "？", " ", ""]
            )
        else:
            chunk_size = chroma_conf.get("chunk_size", 800)
            chunk_overlap = chroma_conf.get("chunk_overlap", 200)
            separators = chroma_conf.get(
                "separator",
                ["\n\n", "\n", ".", "!", "?", "。", "！", "？", " ", ""]
            )

        logger.info(
            "创建 splitter (source_type=%s, chunk_size=%d, chunk_overlap=%d)",
            source_type, chunk_size, chunk_overlap
        )

        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )

if __name__ == '__main__':
    vs=VectorStoreService()
    vs.load_document()
    retriever=vs.get_retriever()
    res=retriever.invoke("体外诊断")
    for r in res:
        print(r.page_content)
        print("-"*20)


