# 模块: api/routers/pubmed_router.py — PubMed 路由

**文件路径**: `api/routers/pubmed_router.py` (新增)  
**优先级**: P1 (Phase 4 — API 层)  
**前置依赖**: `schemas-pubmed`, `schemas-common`, `pubmed-search-service`, `knowledge-management-service`  
**被依赖模块**: `main.py`

---

## 子任务清单

### 文件创建与注入

- [ ] **T01** — 创建 `api/routers/pubmed_router.py` 文件，添加文件头注释
- [ ] **T02** — 添加 import 语句：
  - `sys`, `os`, `sys.path.insert(...)`
  - `fastapi.APIRouter`, `fastapi.HTTPException`, `fastapi.Query`, `fastapi.Path`
  - `schemas.common.ApiResponse`
  - `schemas.pubmed.*` (所有请求/响应 Schema)
  - `application.services.pubmed_search_service.PubMedSearchAppService`
  - `application.services.knowledge_management_service.KnowledgeManagementService`
- [ ] **T03** — 创建 `router = APIRouter(prefix="/pubmed")`
- [ ] **T04** — 声明模块级 `pubmed_search_service: Optional[PubMedSearchAppService] = None` 和 `knowledge_management_service: Optional[KnowledgeManagementService] = None`
- [ ] **T05** — 实现 `set_pubmed_search_service(service)` 和 `set_knowledge_management_service(service)` setter 函数

### POST /pubmed/search

- [ ] **T06** — 实现 `search_pubmed(request: PubMedSearchRequest)` 端点：
  - 校验 service 已注入 → 否则 HTTPException(500)
  - 调用 `pubmed_search_service.search_and_store(request.query, request.max_results, request.auto_ingest)`
  - 返回 `ApiResponse(code=200, message="success", data=result)`
  - try/except: `PubMed API 不可用` → 503；未知异常 → 500
- [ ] **T07** — 处理 `search_pubmed` 抛出 RuntimeError（如 NCBI 不可达）→ HTTPException(503, "PubMed API 暂时不可用，请稍后重试")
- [ ] **T08** — 添加 INFO 日志记录每次搜索请求（query + max_results）

### GET /pubmed/articles

- [ ] **T09** — 实现 `list_articles(...)` 端点：
  - Query 参数校验由 FastAPI Query() 完成 (page≥1, page_size 1-100, status pattern, sort_by pattern, order pattern)
  - 调用 `knowledge_management_service.list_articles(...)`
  - 返回 `ApiResponse(code=200, message="success", data=result)`
  - ValueError (非法参数) → HTTPException(400)
  - 未知异常 → HTTPException(500)

### GET /pubmed/articles/{pmid}

- [ ] **T10** — 实现 `get_article_detail(pmid: str)` 端点：
  - 调用 `knowledge_management_service.get_article_detail(pmid)`
  - 若返回 None → HTTPException(404, f"PMID {pmid} not found")
  - 正常返回 `ApiResponse(code=200, message="success", data=result)`

### POST /pubmed/ingest/{pmid}

- [ ] **T11** — 实现 `ingest_single_article(pmid: str, force: bool = False)` 端点：
  - 校验 service 已注入
  - 调用 `pubmed_search_service` 的 ingester → `ingester.ingest_article(pmid, force)`
  - 将单个 `IngestResult` 包装为 `IngestBatchData` 返回
  - 异常 → HTTPException(500)

### POST /pubmed/ingest/batch

- [ ] **T12** — 实现 `ingest_batch(request: IngestBatchRequest)` 端点：
  - 校验 service 已注入
  - 调用 `pubmed_search_service` 的 ingester → `ingester.batch_ingest(request.pmids, request.force)`
  - 汇总为 `IngestBatchData` 返回
  - 异常 → HTTPException(500)

### POST /pubmed/ingest/all-uningested

- [ ] **T13** — 实现 `ingest_all_uningested()` 端点：
  - 调用 `pubmed_search_service.ingest_all_uningested()`
  - 返回 `ApiResponse(code=200, message="success", data=result)`

### DELETE /pubmed/articles/{pmid}

- [ ] **T14** — 实现 `delete_article(pmid: str)` 端点：
  - 调用 `knowledge_management_service.delete_article(pmid)`
  - 若 `deleted_pg=False` 且 `deleted_vector=False` → HTTPException(404, "PMID not found in both PG and ChromaDB")
  - 正常返回 `ApiResponse(code=200, message="success", data=result)`

### 自测验证

- [ ] **T15** — 使用 FastAPI `TestClient` 测试 `POST /pubmed/search`：mock service 返回预制数据 → 验证 HTTP 200 + 响应结构
- [ ] **T16** — 测试 `POST /pubmed/search` service 未注入 → 预期 HTTP 500
- [ ] **T17** — 测试 `GET /pubmed/articles` 默认分页参数 → 验证响应结构
- [ ] **T18** — 测试 `GET /pubmed/articles?page=0` → 预期 FastAPI 422 (Query 校验)
- [ ] **T19** — 测试 `GET /pubmed/articles/{pmid}` 不存在的 PMID → HTTP 404
- [ ] **T20** — 测试 `DELETE /pubmed/articles/{pmid}` → 验证响应包含 `deleted_pg` 和 `deleted_vector`
