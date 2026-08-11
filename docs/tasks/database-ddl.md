# 模块: 数据库 DDL — pubmed_articles 表 Schema 迁移

**文件路径**: `docs/ddl_migration.sql` (新增，SQL 脚本)  
**优先级**: P1 (Phase 2 基础设施前置 — 所有 PG 操作依赖此迁移)  
**前置依赖**: 无  
**被依赖模块**: `postgres_db.py`, `pubmed_ingester.py`, `pubmed_search_service.py`

---

## 子任务清单

### DDL 脚本编写

- [ ] **T01** — 创建 `docs/ddl_migration.sql` 文件，添加注释头（项目名、日期、用途、执行方式）
- [ ] **T02** — 编写 `ALTER TABLE pubmed_articles ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(20) DEFAULT 'uningested';`
- [ ] **T03** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP;`
- [ ] **T04** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS chunk_count INTEGER;`
- [ ] **T05** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS vector_ids JSONB;`
- [ ] **T06** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();`
- [ ] **T07** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();`
- [ ] **T08** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS search_query TEXT;`
- [ ] **T09** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ingestion_error TEXT;`
- [ ] **T10** — 编写 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS raw_response JSONB;`

### 索引创建

- [ ] **T11** — 编写 `CREATE INDEX IF NOT EXISTS idx_pubmed_ingestion_status ON pubmed_articles(ingestion_status);`
- [ ] **T12** — 编写 `CREATE INDEX IF NOT EXISTS idx_pubmed_created_at ON pubmed_articles(created_at);`
- [ ] **T13** — 编写 `CREATE INDEX IF NOT EXISTS idx_pubmed_article_gin ON pubmed_articles USING GIN (article_info jsonb_path_ops);`

### 执行与验证

- [ ] **T14** — 在目标 PostgreSQL 数据库 (medicineKB) 上执行 `docs/ddl_migration.sql`
- [ ] **T15** — 执行 `SELECT column_name, data_type FROM information_schema.columns WHERE table_name='pubmed_articles' ORDER BY ordinal_position;` 验证所有新增字段存在
- [ ] **T16** — 执行 `SELECT indexname FROM pg_indexes WHERE tablename='pubmed_articles';` 验证 3 个新索引存在
- [ ] **T17** — 确认已有数据的 `ingestion_status` 被默认值 `'uningested'` 正确填充
