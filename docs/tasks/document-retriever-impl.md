# 模块: infrastructure/persistence/document_retriever_impl.py — 检索器扩展

**文件路径**: `infrastructure/persistence/document_retriever_impl.py` (修改)  
**优先级**: P2 (Phase 2 — 基础设施，但依赖 Phase 4 集成时才需验证)  
**前置依赖**: 无  
**被依赖模块**: `rag_summarizer_impl.py` (间接)

---

## 子任务清单

### 重构 format_documents_for_context()

- [ ] **T01** — 读取现有 `format_documents_for_context()` 方法，理解当前逻辑（统一格式 `[N] source\ncontent`）
- [ ] **T02** — 重构 `format_documents_for_context()`：按 `doc.metadata.get("source_type", "local_file")` 分支：
  - `"pubmed"` → 调用 `self._format_pubmed_citation()`
  - 其他/不存在 → 调用 `self._format_local_citation()`
- [ ] **T03** — 实现 `_format_local_citation(doc, index) -> str` 静态方法：
  - 格式: `[N] 《文件名（无后缀）》.`
  - 去掉 `.docx`/`.doc`/`.pdf`/`.txt` 后缀
- [ ] **T04** — 实现 `_format_pubmed_citation(doc, index) -> str` 静态方法：
  - 格式: `[N] Authors. Title. Journal. Year. PMID: xxxxx.`
  - 从 metadata 中提取 `authors`, `title`, `journal`, `publish_date`, `pmid`
  - 若字段缺失，跳过对应的部分（如无 authors 则不输出 "Authors."）
- [ ] **T05** — 确认 main 循环逻辑不变：遍历文档、调用格式化函数、拼接 content

### 向后兼容验证

- [ ] **T06** — 验证旧数据（`source_type` 不存在于 metadata）走 `_format_local_citation()` 分支
- [ ] **T07** — 验证 `retrieve_documents()` 和 `deduplicate_documents()` 无需修改

### 单元测试

- [ ] **T08** — 测试 `_format_local_citation`：传入 `metadata={"source": "指南.docx"}` → 输出 `[1] 《指南》.`
- [ ] **T09** — 测试 `_format_local_citation`：传入 `metadata={"source": "指南"}` (无后缀) → 输出 `[1] 《指南》.`
- [ ] **T10** — 测试 `_format_pubmed_citation`：传入完整 pubmed metadata → 输出正确温哥华格式
- [ ] **T11** — 测试 `_format_pubmed_citation`：传入缺少 authors 的 pubmed metadata → 输出跳过 authors 部分
- [ ] **T12** — 测试 `format_documents_for_context` 混合文档列表（1 local + 1 pubmed）→ 输出两种引文格式
