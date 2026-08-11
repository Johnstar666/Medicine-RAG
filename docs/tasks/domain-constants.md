# 模块: domain/constants.py — 全局枚举与错误码

**文件路径**: `domain/constants.py` (新增)  
**优先级**: P0 (Phase 1 — 所有模块的基础依赖)  
**前置依赖**: 无  
**被依赖模块**: `pubmed_search_service.py`, `pubmed_ingester.py`, `pubmed_router.py`, `knowledge_router.py`

---

## 子任务清单

### 文件创建与枚举定义

- [ ] **T01** — 创建 `domain/constants.py` 文件，添加文件头注释（项目名、日期、用途说明）
- [ ] **T02** — 定义 `IngestionStatus(str, Enum)` 枚举：`UNINGESTED="uningested"`, `INGESTING="ingesting"`, `INGESTED="ingested"`, `FAILED="failed"`
- [ ] **T03** — 定义 `ErrorCode(int, Enum)` 枚举：`SUCCESS=200`, `BAD_REQUEST=400`, `PMID_NOT_FOUND=404`, `INTERNAL_ERROR=500`, `SERVICE_NOT_INITIALIZED=500`, `PUBMED_API_UNAVAILABLE=503`, `PG_UNAVAILABLE=503`, `CHROMADB_UNAVAILABLE=503`, `INGESTION_PARTIAL_FAILURE=1001`, `SEARCH_PARTIAL_FAILURE=1002`
- [ ] **T04** — 定义 `IngestResultStatus(str, Enum)` 枚举：`INGESTED="ingested"`, `ALREADY_INGESTED="already_ingested"`, `FAILED="failed"`
- [ ] **T05** — 定义 `SearchItemStatus(str, Enum)` 枚举：`INGESTED="ingested"`, `STORED="stored"`, `SKIPPED="skipped"`, `FAILED="failed"`

### 自测验证

- [ ] **T06** — 编写 `if __name__ == "__main__"` 自测：遍历每个枚举的成员并打印 name/value，确认所有值正确
- [ ] **T07** — 验证 `IngestionStatus` 与数据库 `ingestion_status` 字段的可选值完全一致
- [ ] **T08** — 验证 `ErrorCode` 中 HTTP 状态码与 FastAPI `HTTPException` 的对应关系正确
