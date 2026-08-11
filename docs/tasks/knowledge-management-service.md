# 模块: application/services/knowledge_management_service.py — 知识库管理服务

**文件路径**: `application/services/knowledge_management_service.py` (新增)  
**优先级**: P1 (Phase 3 — 应用服务)  
**前置依赖**: `postgres-db`, `vector-store`, `pubmed-ingester`, `schemas-pubmed`, `schemas-knowledge`  
**被依赖模块**: `pubmed_router.py`, `knowledge_router.py`, `service_factory.py`

---

## 子任务清单

### 文件创建

- [ ] **T01** — 创建 `application/services/knowledge_management_service.py` 文件，添加文件头注释
- [ ] **T02** — 添加 import 语句：`Optional`, `Dict`, `List`, `get_logger`, `chroma_conf`, `rag_conf`, `ArticleListData`, `ArticleSummary`, `ArticleDetailData`, `DeleteResultData`, `KnowledgeStatsData`, `VectorStoreInfo`, `get_abs_path`
- [ ] **T03** — 初始化 `logger = get_logger(name="knowledge_mgmt")`

### 类定义与构造函数

- [ ] **T04** — 定义 `KnowledgeManagementService` 类及 `__init__(self, postgres_db, vector_store_service, pubmed_ingester)`：
  - docstring 说明对外暴露 4 个方法

### list_articles()

- [ ] **T05** — 实现 `list_articles(self, page, page_size, search, ingestion_status, sort_by, order) -> ArticleListData`：
  - 防御性参数校验（page≥1, page_size 1-100, status 白名单, sort_by 白名单, order 白名单）
  - 调用 `self._db.list_articles(...)` → `(rows, total)`
  - 将 rows 中每个 dict 转换为 `ArticleSummary` 对象
  - 构建并返回 `ArticleListData(total, page, page_size, articles)`
- [ ] **T06** — 在 `list_articles()` 中添加 DEBUG 日志记录查询参数

### get_article_detail()

- [ ] **T07** — 实现 `get_article_detail(self, pmid: str) -> Optional[ArticleDetailData]`：
  - 调用 `self._db.get_article_by_pmid(pmid)` → row 或 None
  - 若 None → 返回 None
  - 若 row 存在 → 逐字段映射到 `ArticleDetailData`（注意 JSONB 字段可能为 None，需提供默认值）
- [ ] **T08** — 处理 `article_info`、`results_info` 字段可能为 `None` 的情况 → 默认 `{}`

### delete_article()

- [ ] **T09** — 实现 `delete_article(self, pmid: str) -> DeleteResultData`：
  - Step 1: try → `self._ingester.remove_from_vector_store(pmid)` → `deleted_vector = (n > 0)`
  - Step 2: except → ERROR 日志 → `deleted_vector = False`
  - Step 3: try → `deleted_pg = self._db.delete_article(pmid)`
  - Step 4: except → ERROR 日志 → `deleted_pg = False`
  - 返回 `DeleteResultData(pmid, deleted_pg, deleted_vector)`
- [ ] **T10** — Step 1 和 Step 3 的异常各自独立 catch，确保一步失败不影响另一步

### get_knowledge_stats()

- [ ] **T11** — 实现 `get_knowledge_stats(self) -> KnowledgeStatsData`：
  - 从 `self._db.count_articles_by_status()` 获取 PG 统计
  - 从 `self._vs.get_collection_stats()` 获取 ChromaDB 统计
  - 调用 `self._get_local_document_count()` 获取本地文档数
  - 构建 `VectorStoreInfo` 和 `KnowledgeStatsData` 返回
- [ ] **T12** — 实现 `_get_local_document_count(self) -> int`：
  - 扫描 `chroma_conf["data_path"]` 目录
  - 统计 `allow_knowledge_file_type` 中扩展名的文件数量
  - 目录不存在时返回 0
  - 添加 WARNING 日志当 data_path 不存在时

### 单元测试

- [ ] **T13** — 测试 `list_articles()`：mock DB 返回预制 rows → 验证 ArticleListData 构建正确
- [ ] **T14** — 测试 `list_articles()` 非法参数：`page=0` → 抛出 ValueError
- [ ] **T15** — 测试 `get_article_detail()` 存在的 PMID → 返回正确 ArticleDetailData
- [ ] **T16** — 测试 `get_article_detail()` 不存在的 PMID → 返回 None
- [ ] **T17** — 测试 `delete_article()` 两端成功：验证 DeleteResultData(deleted_pg=True, deleted_vector=True)
- [ ] **T18** — 测试 `delete_article()` PG 失败：mock `delete_article` 抛异常 → 验证 deleted_pg=False, deleted_vector=True（容错）
- [ ] **T19** — 测试 `get_knowledge_stats()`：mock 所有数据源 → 验证 KnowledgeStatsData 聚合正确
