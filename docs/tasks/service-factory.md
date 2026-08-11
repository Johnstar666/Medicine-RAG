# 模块: infrastructure/services/service_factory.py — DI 容器扩展

**文件路径**: `infrastructure/services/service_factory.py` (修改)  
**优先级**: P1 (Phase 5 — 组装)  
**前置依赖**: 所有被注入的模块（`postgres-db`, `vector-store`, `pubmed-retriever`, `pubmed-ingester`, `pubmed-search-service`, `knowledge-management-service`）  
**被依赖模块**: `main.py`

---

## 子任务清单

### 新增 import

- [ ] **T01** — 添加新增模块的 import：
  - `from infrastructure.persistence.postgres_db import PostgresDB`
  - `from infrastructure.persistence.pubmed_ingester import PubMedArticleIngester`
  - `from pubmed.pubmed_retriever import PubMedRetriever`
  - `from application.services.pubmed_search_service import PubMedSearchAppService`
  - `from application.services.knowledge_management_service import KnowledgeManagementService`
  - `from infrastructure.utils.config_handler import pubmed_conf`

### 新增私有字段

- [ ] **T02** — 在 `__init__` 中添加 5 个私有字段初始化：
  - `self._postgres_db = None`
  - `self._pubmed_retriever = None`
  - `self._pubmed_ingester = None`
  - `self._pubmed_search_service = None`
  - `self._knowledge_management_service = None`

### 新增 getter 方法

- [ ] **T03** — 实现 `get_postgres_db(self) -> PostgresDB`：懒初始化，直接 `PostgresDB()`
- [ ] **T04** — 实现 `get_pubmed_retriever(self) -> PubMedRetriever`：懒初始化，直接 `PubMedRetriever()`
- [ ] **T05** — 实现 `get_pubmed_ingester(self) -> PubMedArticleIngester`：懒初始化，注入 `PostgresDB` + `VectorStoreService`
- [ ] **T06** — 实现 `get_pubmed_search_service(self) -> PubMedSearchAppService`：懒初始化，注入 `PubMedRetriever` + `PostgresDB` + `PubMedArticleIngester`，`request_interval` 从 `pubmed_conf` 读取
- [ ] **T07** — 实现 `get_knowledge_management_service(self) -> KnowledgeManagementService`：懒初始化，注入 `PostgresDB` + `VectorStoreService` + `PubMedArticleIngester`
- [ ] **T08** — 确认 5 个现有 getter 不受影响（`get_vector_store_service`, `get_document_retriever`, `get_keyword_extractor`, `get_rag_summarizer`, `get_rag_query_service`）

### 依赖注入一致性验证

- [ ] **T09** — 确认 `PubMedArticleIngester` 和 `KnowledgeManagementService` 共享同一个 `PostgresDB` 实例（通过懒初始化保证）
- [ ] **T10** — 确认 `PubMedArticleIngester` 和 `VectorDocumentRetriever` 共享同一个 `VectorStoreService` 实例
- [ ] **T11** — 绘制更新后的依赖关系图（或肉眼核对：无循环依赖）

### 单元测试

- [ ] **T12** — 测试 `get_postgres_db()` 两次调用返回同一实例（懒加载单例）
- [ ] **T13** — 测试 `get_pubmed_search_service()` 正确注入了 PostgresDB 和 PubMedRetriever
- [ ] **T14** — 测试 `get_knowledge_management_service()` 和 `get_pubmed_ingester()` 共享 PostgresDB
