# 模块: infrastructure/persistence/pubmed_ingester.py — PubMed 文章向量化

**文件路径**: `infrastructure/persistence/pubmed_ingester.py` (新增)  
**优先级**: P0 (Phase 2 — 基础设施核心)  
**前置依赖**: `postgres-db`, `vector-store`, `domain-constants`, `config-files`  
**被依赖模块**: `pubmed_search_service.py`, `knowledge_management_service.py`

---

## 子任务清单

### 文件创建与数据结构

- [ ] **T01** — 创建 `infrastructure/persistence/pubmed_ingester.py` 文件，添加文件头注释
- [ ] **T02** — 添加 import 语句：`dataclass`, `Dict`, `List`, `Optional`, `RecursiveCharacterTextSplitter`, `LangchainDocument`, `chroma_conf`, `pubmed_conf`, `get_logger`, `IngestionStatus`, `IngestResultStatus`
- [ ] **T03** — 定义 `IngestResult` dataclass：`pmid: str`, `status: str`, `chunk_count: int=0`, `reason: str=""`, `vector_ids: List[str]=[]`
- [ ] **T04** — 初始化 `logger = get_logger(name="pubmed_ingester")`

### 类定义与构造函数

- [ ] **T05** — 定义 `PubMedArticleIngester` 类及 `__init__(self, postgres_db, vector_store_service)`：
  - 保存 `self._db`, `self._vs` 引用
  - 编写 docstring 说明 6 步管线

### 核心方法: ingest_article()

- [ ] **T06** — 实现 `ingest_article(self, pmid: str, force: bool = False) -> IngestResult` 主流程框架：
  - Step 1: `self._db.get_article_by_pmid(pmid)` → None 则返回 failed
  - Step 2: 幂等检查 (status=="ingested" ∧ ¬force → already_ingested)
  - Step 3: force 清理 (force=True → self.remove_from_vector_store(pmid))
  - Step 4: `self._db.update_ingestion_status(pmid, "ingesting")`
  - Step 5: `self._build_article_text(article)` → 空则 failed
  - Step 6: `self._vs.get_splitter("pubmed").split_text(text)` → 空则 failed
  - Step 7: 循环构建 `LangchainDocument` + metadata
  - Step 8: `self._vs.add_documents_direct(docs)` → vector_ids
  - Step 9: `self._db.update_ingestion_status(pmid, "ingested", ...)`
- [ ] **T07** — 在 `ingest_article()` 中实现 try/except 包裹全流程，异常时：
  - ERROR 日志含 exc_info=True
  - try: `self._db.update_ingestion_status(pmid, "failed", error=str(e))`
  - 返回 `IngestResult(pmid, "failed", reason=str(e))`

### 辅助方法: _build_article_text()

- [ ] **T08** — 实现 `_build_article_text(self, article: Dict) -> str`：
  - 按设计文档模板拼接结构化文本
  - 提取 `article_info.title/.authors/.journal/.publish_date/.doi/.abstract`
  - 提取 `objectives`, `study_groups`, `results_info.raw_abstract`
  - 返回 `.strip()` 后的文本
- [ ] **T09** — 处理 authors 为空 → 显示 "N/A"；study_groups 为空 → 显示 "N/A"
- [ ] **T10** — 测试 template 输出：用一条完整 mock 数据验证文本格式

### 辅助方法: _build_chunk_metadata()

- [ ] **T11** — 实现 `_build_chunk_metadata(self, article: Dict, chunk_index: int, total_chunks: int) -> Dict`：
  - 构建 `source = f"PMID:{pmid}: {title[:80]}"`
  - 构建 authors_str (最多 5 位 + et al.)
  - 返回所有 metadata 字段的完整 dict
- [ ] **T12** — 验证 metadata dict 的字段名与 `high-level-design.md` §5.6 完全一致

### 批量方法

- [ ] **T13** — 实现 `batch_ingest(self, pmids: List[str], force: bool = False) -> List[IngestResult]`：
  - 循环调用 `self.ingest_article(pmid, force)`，单篇失败不中断
  - 每篇 DEBUG 日志记录进度
- [ ] **T14** — 实现 `ingest_all_uningested(self, force: bool = False) -> List[IngestResult]`：
  - 从 PG 查询 `ingestion_status="uningested"` + `"failed"` 的所有 PMID
  - 调用 `self.batch_ingest(pmids, force)`
  - INFO 日志记录待处理总数

### 删除方法

- [ ] **T15** — 实现 `remove_from_vector_store(self, pmid: str) -> int`：
  - 调用 `self._vs.delete_by_metadata_filter({"pmid": pmid})`
  - 返回删除的 chunk 数量
  - INFO 日志记录删除数量

### 单元测试

- [ ] **T16** — 测试 `ingest_article()` 正常路径：mock PG 返回完整数据 + mock VS → 验证返回 status="ingested", chunk_count≥1
- [ ] **T17** — 测试 `ingest_article()` 幂等：第二次相同 pmid 调用 → status="already_ingested"
- [ ] **T18** — 测试 `ingest_article()` 强制重索引：force=True → 先调用 remove 再索引
- [ ] **T19** — 测试 `ingest_article()` PMID 不存在 → status="failed", reason 含 "not found"
- [ ] **T20** — 测试 `ingest_article()` 空文本 → status="failed", reason 含 "Empty"
- [ ] **T21** — 测试 `ingest_article()` ChromaDB 写入失败 → status="failed", PG 状态更新为 failed
- [ ] **T22** — 测试 `batch_ingest()` 第 2 篇失败不影响第 1、3 篇
- [ ] **T23** — 测试 `remove_from_vector_store()` → 调用 `vs.delete_by_metadata_filter({"pmid": pmid})`
