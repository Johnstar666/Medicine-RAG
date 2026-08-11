# 模块: schemas/knowledge.py — 知识库统计 Schema

**文件路径**: `schemas/knowledge.py` (新增)  
**优先级**: P0 (Phase 1 — Schema 层)  
**前置依赖**: 无  
**被依赖模块**: `knowledge_router.py`, `knowledge_management_service.py`

---

## 子任务清单

### 文件创建与 Pydantic 模型

- [ ] **T01** — 创建 `schemas/knowledge.py` 文件，添加文件头注释和 import 语句
- [ ] **T02** — 定义 `VectorStoreInfo(BaseModel)`：
  - `collection_name: str`
  - `storage_path: str`
  - `embedding_model: str`
- [ ] **T03** — 定义 `KnowledgeStatsData(BaseModel)`：
  - `local_documents: int = 0`
  - `pubmed_articles_total: int = 0`
  - `pubmed_articles_ingested: int = 0`
  - `pubmed_articles_uningested: int = 0`
  - `total_vector_chunks: int = 0`
  - `by_source_type: Dict[str, int]` (使用 `Field(default_factory=dict)`)
  - `vector_store: VectorStoreInfo` (使用 `Field(default_factory=VectorStoreInfo)`)
- [ ] **T04** — 为每个字段添加 `Field(description="...")` 中文说明

### 自测验证

- [ ] **T05** — 编写自测脚本：
  - 不传任何参数直接 `KnowledgeStatsData()` → 所有字段为默认值 (0 / {} / 默认 VectorStoreInfo)
  - 传入完整数据 → `.model_dump()` 输出与预期一致
  - `by_source_type={"local_file": 1820, "pubmed": 520}` 正确序列化
