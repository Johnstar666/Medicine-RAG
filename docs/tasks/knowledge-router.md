# 模块: api/routers/knowledge_router.py — 知识库路由

**文件路径**: `api/routers/knowledge_router.py` (新增)  
**优先级**: P2 (Phase 4 — API 层)  
**前置依赖**: `schemas-knowledge`, `schemas-common`, `knowledge-management-service`  
**被依赖模块**: `main.py`

---

## 子任务清单

### 文件创建与注入

- [ ] **T01** — 创建 `api/routers/knowledge_router.py` 文件，添加文件头注释
- [ ] **T02** — 添加 import 语句：
  - `sys`, `os`, `sys.path.insert(...)`
  - `fastapi.APIRouter`, `fastapi.HTTPException`
  - `schemas.common.ApiResponse`
  - `schemas.knowledge.KnowledgeStatsData`
  - `application.services.knowledge_management_service.KnowledgeManagementService`
- [ ] **T03** — 创建 `router = APIRouter(prefix="/knowledge")`
- [ ] **T04** — 声明模块级 `knowledge_management_service: Optional[KnowledgeManagementService] = None`
- [ ] **T05** — 实现 `set_knowledge_management_service(service)` setter 函数

### GET /knowledge/stats

- [ ] **T06** — 实现 `get_knowledge_stats()` 端点：
  - 校验 service 已注入 → 否则 HTTPException(500)
  - 调用 `knowledge_management_service.get_knowledge_stats()`
  - 返回 `ApiResponse(code=200, message="success", data=result)`
  - try/except: 未知异常 → HTTPException(500, detail=str(e))
- [ ] **T07** — 添加 INFO 日志记录每次统计请求

### 自测验证

- [ ] **T08** — 使用 FastAPI `TestClient` 测试 `GET /knowledge/stats`：mock service 返回预制统计数据 → 验证 HTTP 200 + 响应结构
- [ ] **T09** — 测试 `GET /knowledge/stats` service 未注入 → 预期 HTTP 500
- [ ] **T10** — 验证 `KnowledgeStatsData` 中的 `by_source_type` 正确序列化为 JSON
