# 模块: schemas/common.py — 通用响应信封

**文件路径**: `schemas/common.py` (新增)  
**优先级**: P0 (Phase 1 — Schema 层基础)  
**前置依赖**: 无  
**被依赖模块**: `pubmed_router.py`, `knowledge_router.py`

---

## 子任务清单

### 文件创建与 Pydantic 模型

- [ ] **T01** — 创建 `schemas/common.py` 文件，添加文件头注释
- [ ] **T02** — 定义 `ApiResponse(BaseModel)` 类：
  - `code: int` — HTTP 状态码
  - `message: str` — 人类可读的状态描述
  - `data: Optional[Any] = None` — 业务载荷
- [ ] **T03** — 为 `ApiResponse` 添加 docstring，说明其作为统一响应信封的用途和使用约定
- [ ] **T04** — 确认 `Optional[Any]` 的 `data` 字段与现有 `schemas/rag_query.py` 中的 `ApiResponse` 不冲突（各自独立使用）

### 自测验证

- [ ] **T05** — 编写自测脚本：实例化 `ApiResponse(code=200, message="success", data={"key": "val"})`，验证 `.model_dump()` 输出格式正确
- [ ] **T06** — 编写自测脚本：实例化 `ApiResponse(code=404, message="not found")`（data=None），验证不传 data 时正常工作
