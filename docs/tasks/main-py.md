# 模块: main.py — 启动入口

**文件路径**: `main.py` (修改)  
**优先级**: P1 (Phase 5 — 组装)  
**前置依赖**: 所有 Router 和 `service-factory`  
**被依赖模块**: 无（入口文件）

---

## 子任务清单

### 新增 import

- [ ] **T01** — 添加新增 Router 和 setter 的 import：
  - `from api.routers.pubmed_router import router as pubmed_router, set_pubmed_search_service, set_knowledge_management_service as set_km_for_pubmed`
  - `from api.routers.knowledge_router import router as knowledge_router, set_knowledge_management_service as set_km_for_knowledge`
- [ ] **T02** — 确认现有 import 不受影响

### 服务初始化与注入

- [ ] **T03** — 在 `factory = ServiceFactory()` 之后，新增：
  - `pubmed_search_service = factory.get_pubmed_search_service()`
  - `set_pubmed_search_service(pubmed_search_service)`
- [ ] **T04** — 新增知识库管理服务注入到两个 Router：
  - `knowledge_mgmt_service = factory.get_knowledge_management_service()`
  - `set_km_for_pubmed(knowledge_mgmt_service)`
  - `set_km_for_knowledge(knowledge_mgmt_service)`
- [ ] **T05** — 确认现有 RAG 服务注入保持不变：
  - `rag_query_service = factory.get_rag_query_service()`
  - `set_rag_query_service(rag_query_service)`

### 路由注册

- [ ] **T06** — 新增 `app.include_router(pubmed_router)`
- [ ] **T07** — 新增 `app.include_router(knowledge_router)`
- [ ] **T08** — 确认 `app.include_router(rag_router)` 保持不变
- [ ] **T09** — 确认 CORS 中间件配置保持不变

### 综合验证

- [ ] **T10** — 启动应用 `python main.py` → 确认 FastAPI 启动无 import 错误
- [ ] **T11** — 访问 `http://localhost:8000/docs` → 确认 Swagger UI 列出所有 3 组路由（rag + pubmed + knowledge）
- [ ] **T12** — 检查 Swagger UI 中所有端点 URL 和请求 Schema 与设计文档一致
