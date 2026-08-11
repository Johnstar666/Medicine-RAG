# 模块: pubmed/pubmed_retriever.py — PubMed 检索器扩展

**文件路径**: `pubmed/pubmed_retriever.py` (修改)  
**优先级**: P1 (Phase 2 — 基础设施)  
**前置依赖**: 无  
**被依赖模块**: `pubmed_search_service.py`, `paper_search.py`

---

## 子任务清单

### fetch_article_details() 重构

- [ ] **T01** — 读取现有 `fetch_article_details()` 方法 (L22-56)，理解当前简化版解析逻辑
- [ ] **T02** — 读取现有 8 个静态辅助方法 (L99-181)，确认每个方法的功能和输入输出
- [ ] **T03** — 重构 `fetch_article_details()`：内部调用 `_parse_authors()`, `_parse_abstract()`, `_parse_publish_date()`, `_parse_doi()`, `_parse_study_groups()`, `_parse_results_info()`, `_parse_objectives()`, `_is_free_download()`
- [ ] **T04** — 删除 `fetch_article_details()` 中与静态方法重复的内联解析代码
- [ ] **T05** — 在 `fetch_article_details()` 中新增提取 `pmc_id` 和 `publication_type` 字段
- [ ] **T06** — 新增静态方法 `_get_pmc_id(article_id_list) -> str`
- [ ] **T07** — 修改返回 dict 结构：
  - `article_info` 新增 `doi`, `publish_date`, `pmc_id`, `publication_type` 字段
  - 根级新增 `search_query: ""` 和 `raw_response: dict`
- [ ] **T08** — 在 `fetch_article_details()` 中使用 `import copy; copy.deepcopy(records)` 保存 raw_response

### search_pubmed() — 保持不变

- [ ] **T09** — 确认 `search_pubmed()` 方法无需修改
- [ ] **T10** — 确认 `Entrez.email`, `Entrez.api_key`, `Entrez.max_tries` 的初始化逻辑不受影响

### 自测验证

- [ ] **T11** — 用一个已知 PMID（如 "33301246"）调用 `fetch_article_details()` → 验证返回 dict 结构完整性
- [ ] **T12** — 验证 `article_info.authors` 格式为 `["LastName ForeName", ...]`
- [ ] **T13** — 验证 `publish_date` 格式为 `YYYY-MM-DD`
- [ ] **T14** — 验证 `is_free_download` 对有 PMC ID 的文章返回 `True`
- [ ] **T15** — 验证 `raw_response` 包含完整的 PubMed XML 解析后的 Python 对象
- [ ] **T16** — 用无效 PMID 测试 → 确认抛出异常而非返回空 dict
