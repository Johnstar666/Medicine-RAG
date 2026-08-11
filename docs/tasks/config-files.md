# 模块: config/pubmed.yml + config/chroma.yml — 配置文件扩展

**文件路径**: `config/pubmed.yml` (修改), `config/chroma.yml` (修改)  
**优先级**: P1 (Phase 1-2 — 基础设施前置)  
**前置依赖**: 无  
**被依赖模块**: `postgres_db.py`, `pubmed_ingester.py`, `vector_store.py`, `pubmed_search_service.py`

---

## 子任务清单

### config/pubmed.yml 扩展

- [ ] **T01** — 在 `config/pubmed.yml` 末尾追加 `auto_ingest: true`（搜索后自动索引，默认开启）
- [ ] **T02** — 追加 `request_interval: 0.15`（NCBI API 请求间隔，秒）
- [ ] **T03** — 追加 `ingestion_chunk_size: 800`（PubMed 文章分块大小）
- [ ] **T04** — 追加 `ingestion_chunk_overlap: 200`（PubMed 文章分块重叠）
- [ ] **T05** — 确认现有字段 (`email`, `api_key`, `max_results`, `max_tries`, `sleep_between_tries`) 不受影响

### config/chroma.yml 扩展

- [ ] **T06** — 在 `config/chroma.yml` 末尾追加 `pubmed_chunk_size: 800`
- [ ] **T07** — 追加 `pubmed_chunk_overlap: 200`
- [ ] **T08** — 追加 `pubmed_separator: ["\n\n", "\n", ". ", "! ", "? ", "。", "！", "？", " ", ""]`
- [ ] **T09** — 确认现有字段 (`collection_name`, `persist_directory`, `chunk_size`, `chunk_overlap`, `separator` 等) 不受影响

### 自测验证

- [ ] **T10** — 在 Python 交互环境中用 `config_handler.load_pubmed_config()` 读取，验证新增字段存在且类型正确
- [ ] **T11** — 在 Python 交互环境中用 `config_handler.load_chroma_config()` 读取，验证新增字段存在且类型正确
- [ ] **T12** — 确认 `pubmed_separator` 的首个元素 `"\n\n"` 与本地文档 separator `"\n\n"` 一致的语义正确性
