# 模块: infrastructure/persistence/vector_store.py — 向量存储扩展

**文件路径**: `infrastructure/persistence/vector_store.py` (已有，追加方法)  
**优先级**: P1 (Phase 2 — 基础设施)  
**前置依赖**: `config-files` (pubmed_chunk_size 等新配置项)  
**被依赖模块**: `pubmed_ingester.py`, `knowledge_management_service.py`

---

## 子任务清单

### 新增方法: add_documents_direct()

- [ ] **T01** — 实现 `add_documents_direct(self, documents: List[LangchainDocument]) -> List[str]`：
  - 直接调用 `self.vector_store.add_documents(documents)`
  - 返回 ChromaDB 分配的 ID 列表
  - 添加 INFO 日志记录写入的文档数量
  - 异常时 ERROR 日志 + raise
- [ ] **T02** — 编写 docstring：说明与 `load_document()` 的区别（跳过 MD5 去重）

### 新增方法: delete_by_metadata_filter()

- [ ] **T03** — 实现 `delete_by_metadata_filter(self, metadata_filter: Dict) -> int`：
  - Step 1: `self.vector_store.get(where=metadata_filter)` → 获取匹配的 IDs
  - Step 2: 若 IDs 非空 → `self.vector_store.delete(ids=ids)` → 返回删除数量
  - Step 3: 若 IDs 为空 → DEBUG 日志 + 返回 0
  - 异常时 ERROR 日志 + raise
- [ ] **T04** — 编写 docstring：说明 ChromaDB 两步操作的原因（API 限制）

### 新增方法: get_collection_stats()

- [ ] **T05** — 实现 `get_collection_stats(self) -> Dict`：
  - 获取 `total_chunks`：`self.vector_store._collection.count()`
  - 获取 `by_source_type`：遍历 `self.vector_store.get(include=["metadatas"])`，按 `metadata.source_type` 计数
  - 若遍历失败（数据量大），返回 `{"local_file": -1, "pubmed": -1}`
  - 返回 `{"total_chunks": N, "by_source_type": {...}}`
- [ ] **T06** — 编写 docstring：说明统计可能的性能开销

### 新增方法: get_splitter()

- [ ] **T07** — 实现 `get_splitter(self, source_type: str = "local_file") -> RecursiveCharacterTextSplitter`：
  - `source_type == "pubmed"` → 使用 `pubmed_chunk_size` / `pubmed_chunk_overlap` / `pubmed_separator`
  - 否则 → 使用现有 `chunk_size` / `chunk_overlap` / `separator`
  - 创建并返回一个新的 `RecursiveCharacterTextSplitter` 实例
- [ ] **T08** — 添加 INFO 日志记录使用的 splitter 配置参数

### 现有代码保护

- [ ] **T09** — 确认新增方法不修改现有 `__init__`, `get_retriever()`, `load_document()` 的逻辑
- [ ] **T10** — 确认 `self.spliter` (本地文档 splitter) 保持不变

### 单元测试

- [ ] **T11** — 测试 `add_documents_direct()`：创建 2 个 LangchainDocument → 写入临时 ChromaDB → 验证返回 2 个 ID → 用 get() 验证确实写入
- [ ] **T12** — 测试 `delete_by_metadata_filter()`：先 `add_documents_direct` 写入带 `{"pmid": "test123"}` metadata 的文档 → `delete_by_metadata_filter({"pmid": "test123"})` → 验证返回数量 > 0 → 验证 get 查不到
- [ ] **T13** — 测试 `delete_by_metadata_filter()` 无匹配：传入不存在的 filter → 返回 0
- [ ] **T14** — 测试 `get_splitter("pubmed")`：验证返回的 splitter 使用 pubmed 配置的 chunk_size
- [ ] **T15** — 测试 `get_splitter("local_file")`：验证返回的 splitter 使用本地文档配置
