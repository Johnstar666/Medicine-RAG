# 模块: prompts/rag_summarize_prompt.txt — Prompt 增强

**文件路径**: `prompts/rag_summarize_prompt.txt` (修改)  
**优先级**: P3 (Phase 6 — 最后调优)  
**前置依赖**: `document-retriever-impl` (引文格式已支持混合来源)  
**被依赖模块**: 无

---

## 子任务清单

### 读取现有 Prompt

- [ ] **T01** — 读 `prompts/rag_summarize_prompt.txt`，确认现有结构和现有引文规则

### 追加文献类型识别段落

- [ ] **T02** — 在现有 Prompt 末尾追加 `### 文献类型识别与引文格式（新增）` 标题
- [ ] **T03** — 添加第 1 小节：指导原则/机构文件的识别特征和引文格式规则 `[N] 《文件标题》.`
- [ ] **T04** — 添加第 2 小节：PubMed 期刊文献的识别特征和引文格式规则 `[N] Authors. Title. Journal. Year. PMID: xxxxx.`
- [ ] **T05** — 添加第 3 小节：内容重叠处理策略（先规范要求 → 再研究证据 → "指导原则要求……，相关研究进一步表明……"）
- [ ] **T06** — 添加第 4 小节：参考文献列表规则（编号一致性、不可重复）

### 验证

- [ ] **T07** — 检查追加内容与现有 Prompt 的逻辑一致性（不冲突、不重复）
- [ ] **T08** — 检查引文格式规则与 `document_retriever_impl.py` 中 `_format_pubmed_citation()` 的输出格式一致
- [ ] **T09** — 用示例问题 + 混合来源文档做一次端到端 RAG 查询，确认 LLM 遵循新 Prompt 的引文规则
