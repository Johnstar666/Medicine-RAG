# 模块: application/services/pubmed_search_service.py — PubMed 搜索服务

**文件路径**: `application/services/pubmed_search_service.py` (新增)  
**优先级**: P1 (Phase 3 — 应用服务)  
**前置依赖**: `postgres-db`, `pubmed-ingester`, `pubmed-retriever`, `domain-constants`  
**被依赖模块**: `pubmed_router.py`, `service_factory.py`

---

## 子任务清单

### 文件创建与数据结构

- [ ] **T01** — 创建 `application/services/pubmed_search_service.py` 文件，添加文件头注释
- [ ] **T02** — 添加 import 语句：`time`, `dataclass`, `Dict`, `List`, `Optional`, `get_logger`, `PubMedSearchData`, `SearchDetailItem`, `IngestBatchData`, `IngestResultItem` (后两者从 schemas.pubmed 导入)
- [ ] **T03** — 定义内部 dataclass `SearchResultItem`：`pmid`, `status`, `title=""`, `reason=""`
- [ ] **T04** — 初始化 `logger = get_logger(name="pubmed_search")`

### 类定义与构造函数

- [ ] **T05** — 定义 `PubMedSearchAppService` 类及 `__init__(self, pubmed_retriever, postgres_db, pubmed_ingester, request_interval=0.15)`：
  - docstring 说明对外暴露 `search_and_store()` 和 `ingest_all_uningested()` 两个方法

### 核心方法: search_and_store()

- [ ] **T06** — 实现 `search_and_store(self, query: str, max_results: int = 5, auto_ingest: bool = True) -> PubMedSearchData`：
  - Step 1: `self._retriever.search_pubmed(query)` → PMID 列表
  - Step 2: 若 PMID 列表为空 → 直接返回零统计结果
  - Step 3: FOR EACH pmid (加 `time.sleep(self._interval)` 间隔)
  - Step 4: 逐篇查重 → fetch → insert → 收集结果
  - Step 5: 若 `auto_ingest=True` → 循环新入库的 PMID → `self._ingester.ingest_article(pmid)`
  - Step 6: 汇总统计 → 构建 `PubMedSearchData` 返回
- [ ] **T07** — 实现搜索入库循环中的逐篇异常处理：
  - `search_pubmed` 失败 → 重试 3 次（指数退避 3s/6s/12s）→ 仍失败则抛出
  - 单篇 `fetch_article_details` 失败 → `SearchDetailItem(status="failed", reason=str(e))` → 继续下一篇
  - 单篇 `insert_article` 失败 → 同上
  - 单篇 `ingest_article` 失败 → 更新 status 为 "failed" → 继续下一篇
- [ ] **T08** — 在每个步骤添加 INFO 日志：搜索开始 (query + max_results)、每篇结果 (pmid + status)、批次完成统计

### 便捷方法: ingest_all_uningested()

- [ ] **T09** — 实现 `ingest_all_uningested(self, force: bool = False) -> IngestBatchData`：
  - 调用 `self._ingester.ingest_all_uningested(force)` → 得到 `List[IngestResult]`
  - 汇总统计 → 构建 `IngestBatchData` 返回
- [ ] **T10** — 添加 INFO 日志记录全量索引开始和完成统计

### 单元测试

- [ ] **T11** — 测试 `search_and_store()` 正常路径：mock retriever 返回 3 个 PMID → mock 全部成功 → 验证 `pmids_found=3, pmids_new=3, pmids_ingested=3`
- [ ] **T12** — 测试 `search_and_store()` 全部已存在：mock `is_pmid_exist` 全部返回 True → 验证 `pmids_new=0, pmids_skipped=3`
- [ ] **T13** — 测试 `search_and_store()` 部分失败：mock 第 2 篇 fetch 抛异常 → 验证该篇 status="failed"，其余正常
- [ ] **T14** — 测试 `search_and_store()` 不自动索引：`auto_ingest=False` → 验证 `pmids_ingested=0`，details 中 status 均为 "stored"
- [ ] **T15** — 测试 `search_and_store()` PubMed API 完全不可用：mock `search_pubmed` 抛异常 → 验证异常向上抛出
- [ ] **T16** — 测试 `ingest_all_uningested()`：mock ingester 返回混合结果 → 验证 IngestBatchData 统计正确
