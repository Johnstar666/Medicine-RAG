# 模块: 集成测试与收尾

**文件路径**: 无固定文件（测试脚本 + 手动验证）  
**优先级**: P1 (Phase 7 — 全系统验证)  
**前置依赖**: `main-py` (全系统可启动)  
**被依赖模块**: 无

---

## 子任务清单

### 端到端测试: PubMed 搜索入库索引

- [ ] **T01** — 启动应用 `python main.py`，确认 FASTAPI 启动无错误
- [ ] **T02** — 构造 `POST /pubmed/search` 请求 `{"query": "COVID-19 mRNA vaccine efficacy", "max_results": 3, "auto_ingest": true}`
- [ ] **T03** — 验证响应 HTTP 200，`data.pmids_found ≥ 0`
- [ ] **T04** — 查询 PostgreSQL：`SELECT pmid, ingestion_status FROM pubmed_articles WHERE search_query = 'COVID-19 mRNA vaccine efficacy'`，验证新增记录 `ingestion_status='ingested'`
- [ ] **T05** — 查询 ChromaDB：通过 `collection.get(where={"pmid": "..."})` 验证向量块存在

### 端到端测试: RAG 混合查询

- [ ] **T06** — 构造 `POST /rag/query` 请求 `{"question": "mRNA疫苗的有效性数据是什么？"}`，确保 ChromaDB 中同时有 local_file 和 pubmed 数据
- [ ] **T07** — 验证响应 `data.sources` 数组中混合包含 `《...》` 格式（local_file）和 `PMID:` 开头的来源（pubmed）
- [ ] **T08** — 验证 `data.answer` 中文末参考文献列表包含两类引文格式

### 端到端测试: 文献管理

- [ ] **T09** — 构造 `GET /pubmed/articles?page=1&page_size=5` → 验证分页和返回结构
- [ ] **T10** — 构造 `GET /pubmed/articles?search=vaccine` → 验证模糊搜索返回相关文献
- [ ] **T11** — 构造 `GET /pubmed/articles/{已知PMID}` → 验证返回完整详情

### 端到端测试: 知识库统计

- [ ] **T12** — 构造 `GET /knowledge/stats` → 验证返回 `local_documents`, `pubmed_articles_total`, `total_vector_chunks`, `by_source_type` 数值 > 0

### 端到端测试: 删除

- [ ] **T13** — 用测试 PMID 先确认存在 → `DELETE /pubmed/articles/{pmid}` → 验证 `deleted_pg=true, deleted_vector=true`
- [ ] **T14** — 再次 `GET /pubmed/articles/{pmid}` → 验证返回 404

### 边界情况手动验证

- [ ] **T15** — 构造 `POST /pubmed/search` 空 query → 验证 HTTP 422（Pydantic 校验）
- [ ] **T16** — 构造 `POST /pubmed/search` 无意义的 query（如 "xyzasdfghjkl12345"）→ 验证 HTTP 200, `pmids_found=0`
- [ ] **T17** — 连续两次 `POST /pubmed/ingest/{pmid}` (同一 PMID, force=false) → 第二次返回 "already_ingested"
- [ ] **T18** — 构造 `DELETE /pubmed/articles/不存在的PMID` → 验证 HTTP 404

### 性能测试

- [ ] **T19** — 测量 `POST /pubmed/search` (max_results=5, auto_ingest=true) 的端到端耗时 → 验证 ≤ 30 秒
- [ ] **T20** — 测量 `GET /knowledge/stats` 的响应时间 → 验证 < 2 秒

### 文档更新

- [ ] **T21** — 更新 `README.md`：添加新增 API 端点说明
- [ ] **T22** — 更新 `test_main.http`：添加新端点的测试用例
- [ ] **T23** — 检查所有新增文件的 docstring 和注释完整性
- [ ] **T24** — 在 `infrastructure/utils/postgres_db.py` 中添加弃用注释指向新路径
