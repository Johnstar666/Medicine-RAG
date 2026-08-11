# 模块: infrastructure/persistence/postgres_db.py — PostgreSQL 持久化

**文件路径**: `infrastructure/persistence/postgres_db.py` (从 `infrastructure/utils/` 迁入并重构)  
**优先级**: P0 (Phase 2 — 基础设施核心，所有 PG 操作的基础)  
**前置依赖**: `database-ddl` (字段存在), `config-files`  
**被依赖模块**: `pubmed_ingester.py`, `pubmed_search_service.py`, `knowledge_management_service.py`, `paper_search.py`

---

## 子任务清单

### 文件迁移

- [ ] **T01** — 将 `infrastructure/utils/postgres_db.py` 复制到 `infrastructure/persistence/postgres_db.py`（保留原文件作为过渡，后续 Phase 清理）
- [ ] **T02** — 修复 import 路径：`from utils.logger_handler` → `from infrastructure.utils.logger_handler`；`from utils.config_handler` → `from infrastructure.utils.config_handler`
- [ ] **T03** — 新增 import：`from psycopg2.extras import RealDictCursor`；`from typing import Optional, List, Dict, Tuple`；`import json`

### 上下文管理器

- [ ] **T04** — 实现 `__enter__(self)` 方法：调用 `self.connect()`，返回 `self`
- [ ] **T05** — 实现 `__exit__(self, exc_type, exc_val, exc_tb)` 方法：调用 `self.close()`，返回 `False`（不吞异常）
- [ ] **T06** — 编写 docstring 说明两种使用方式（上下文管理器 + 显式 connect/close）

### 连接管理增强

- [ ] **T07** — 修改 `connect()` 方法：在连接前检查并关闭旧连接 (`if self.conn: self.close()`)
- [ ] **T08** — 实现 `_ensure_connected(self)` 方法：检查 `self.conn` 是否为 None 或已关闭，若是则调用 `self.connect()`
- [ ] **T09** — 修改 `__init__` 中 `self.cur = self.conn.cursor(cursor_factory=RealDictCursor)` → 将 `cursor_factory` 移到 `connect()` 中；`__init__` 仅保存配置

### 现有方法适配

- [ ] **T10** — 修改 `is_pmid_exist()` 方法：首行添加 `self._ensure_connected()`；保持其余逻辑不变
- [ ] **T11** — 修改 `insert_article()` 方法：添加 `search_query` 和 `raw_response` 字段的插入逻辑；首行添加 `self._ensure_connected()`
- [ ] **T12** — 确认 `insert_article()` 的 `ingestion_status` 硬编码为 `'uningested'`

### 新增查询方法

- [ ] **T13** — 实现 `get_article_by_pmid(self, pmid: str) -> Optional[Dict]`：
  - SQL: `SELECT * FROM {table} WHERE pmid = %s`
  - 使用 `RealDictCursor` 返回字典（或 `None`）
  - 首行 `self._ensure_connected()`
- [ ] **T14** — 实现 `list_articles(self, page, page_size, search, ingestion_status, sort_by, order) -> Tuple[List[Dict], int]`：
  - WHERE 条件动态构建：`search` → `ILIKE` title/abstract；`ingestion_status` → 等值过滤
  - 排序白名单校验 (`ALLOWED_SORT`, `ALLOWED_ORDER`)
  - COUNT 查询 + 分页查询共两次 SQL
  - 返回 `(rows, total_count)`
- [ ] **T15** — 在 `list_articles()` 中为 `sort_by` 和 `order` 实现 SQL 注入白名单防护

### 新增更新方法

- [ ] **T16** — 实现 `update_ingestion_status(self, pmid, status, error=None, chunk_count=None, vector_ids=None) -> None`：
  - 动态构建 SET 子句（仅更新传入的非 None 参数）
  - `status="ingested"` 时自动设置 `ingested_at = NOW()` 且清除 `ingestion_error`
  - `status="failed"` 时设置 `ingestion_error`
  - `vector_ids` 以 `json.dumps()` 写入 JSONB

### 新增统计方法

- [ ] **T17** — 实现 `count_articles_by_status(self) -> Dict[str, int]`：
  - SQL: `COUNT(*) FILTER (WHERE ingestion_status = ...)` 一次性聚合
  - 返回 `{"total": N, "ingested": N, "uningested": N, "failed": N}`
- [ ] **T18** — 实现 `count_all(self) -> int`：`SELECT COUNT(*) FROM {table}`

### 新增删除方法

- [ ] **T19** — 实现 `delete_article(self, pmid: str) -> bool`：
  - SQL: `DELETE FROM {table} WHERE pmid = %s`
  - 返回 `self.cur.rowcount > 0`

### 向后兼容

- [ ] **T20** — 保留文件末尾的 `PostgresDB_singleton = PostgresDB()` 单例（供 `paper_search.py` 过渡使用）
- [ ] **T21** — 在原 `infrastructure/utils/postgres_db.py` 中添加弃用注释：`# DEPRECATED: 请使用 infrastructure.persistence.postgres_db`

### 单元测试

- [ ] **T22** — 测试 `__enter__`/`__exit__`：`with PostgresDB() as db: ...` 自动 connect 和 close
- [ ] **T23** — 测试 `_ensure_connected()`：模拟 `conn.closed=True` 后调用方法，验证自动重连
- [ ] **T24** — 测试 `list_articles()` SQL 注入防护：传入 `sort_by="; DROP TABLE--"` → 回退到默认值
- [ ] **T25** — 测试 `insert_article()` 重复 PMID → 抛出唯一约束异常
- [ ] **T26** — 测试 `update_ingestion_status()` 成功/失败场景的状态字段变更
- [ ] **T27** — 测试 `delete_article()` 不存在的 PMID → 返回 `False`
