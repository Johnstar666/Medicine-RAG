# 模块: pubmed/paper_search.py — 独立搜索管线

**文件路径**: `pubmed/paper_search.py` (重构)  
**优先级**: P2 (Phase 2 — 基础设施，API 不直接依赖)  
**前置依赖**: `postgres-db`, `pubmed-retriever`  
**被依赖模块**: 无（独立可运行模块）

---

## 子任务清单

### 重构为 PubMedSearchPipeline 类

- [ ] **T01** — 修复文件头 import 路径：`from utils.logger_handler` → `from infrastructure.utils.logger_handler`；`from utils.postgres_db` → `from infrastructure.persistence.postgres_db`；`from utils.config_handler` → `from infrastructure.utils.config_handler`
- [ ] **T02** — 添加 `sys.path.insert(0, ...)` 确保项目根目录在 Python path
- [ ] **T03** — 定义 `PubMedSearchPipeline` 类：
  - `__init__(self)`: 初始化 `self._retriever = PubMedRetriever()`
  - docstring 说明与 `PubMedSearchAppService` 的分工关系
- [ ] **T04** — 实现 `run(self, query: str, max_results: int = None) -> list` 方法：
  - `max_results` 默认从 `pubmed_conf` 读取
  - 内部使用 `with PostgresDB() as db:` 上下文管理器
  - Step 1: `self._retriever.search_pubmed(query)` → PMID 列表
  - Step 2: 遍历 PMID，查重 → fetch → insert
  - Step 3: 返回结果列表 `[{"pmid": ..., "status": ..., "title": ...}]`
- [ ] **T05** — 在 `run()` 中实现单篇异常处理：`try/except` 包裹 fetch+insert，失败记录 `"status": "failed"` 并继续
- [ ] **T06** — 在 `run()` 中添加 INFO 日志：搜索开始、每篇处理结果、总体统计

### 保留命令行入口

- [ ] **T07** — 保留 `if __name__ == "__main__":` 代码块，改为调用 `PubMedSearchPipeline().run(test_query)`
- [ ] **T08** — 删除原全局 `Entrez` 初始化代码（`Entrez.email = ...` 等，已在 `PubMedRetriever.__init__` 中处理）

### 旧代码清理

- [ ] **T09** — 删除原 `main(pubmed_query)` 函数，替换为 pipeline 调用
- [ ] **T10** — 保留文件末尾注释掉的交互式代码（`keyword = input(...)` 等）仅作为参考或直接删除

### 自测验证

- [ ] **T11** — 命令行运行 `python pubmed/paper_search.py` → 使用硬编码 test_query 验证：搜索成功 → 入库 → 打印结果
- [ ] **T12** — 验证 `with PostgresDB() as db:` 上下文管理器正常 connect 和 close
