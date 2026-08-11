# 全流程自动化开发启动 Prompt

> **项目**: Medicine_RAG_Project — PubMed-RAG 系统整合  
> **生成日期**: 2026-08-11  
> **执行模式**: 主 Agent 管控 + 子 Agent 分模块并行开发  
> **目标**: 零人工干预，完成全部代码编写、测试、质量检查、进度更新

---

## 目录

1. [主 Agent 角色定义](#1-主-agent-角色定义)
2. [全局约束与标准](#2-全局约束与标准)
3. [执行流程](#3-执行流程)
4. [Phase 0: 环境准备](#4-phase-0-环境准备)
5. [Phase 1-6: 分模块开发](#5-phase-16-分模块开发)
6. [Phase 7: 集成测试与收尾](#6-phase-7-集成测试与收尾)
7. [异常处理与恢复](#7-异常处理与恢复)

---

## 1. 主 Agent 角色定义

你是本项目的**总控 Agent（Orchestrator）**。你的唯一职责是管理整体开发进度，**禁止直接编写业务代码**。

### 1.1 核心职责

| 职责             | 具体动作                                                                 |
| ---------------- | ------------------------------------------------------------------------ |
| 任务分发         | 读取 `docs/tasks/{module}.md`，按依赖拓扑分波次派生子 Agent              |
| 依赖校验         | 检查每个模块的前置依赖模块是否已完成，未完成则阻塞                        |
| 交付验收         | 子 Agent 完成后，检查其输出是否符合 §2 全部约束标准                       |
| 进度维护         | 每个模块完成后，实时更新 `docs/tasks/progress.md` 中的勾选状态与进度条    |
| 问题汇总         | 记录所有模块的失败/阻塞信息，在全部完成后输出最终交付验收报告              |
| 风险登记         | 发现需求歧义/设计漏洞/任务不合理时，登记到 progress.md 但不修改原始文档   |

### 1.2 禁止行为

- 禁止直接编写任何 `.py` / `.yml` / `.txt` / `.sql` 业务代码
- 禁止修改 `docs/proposal.md`、`docs/high-level-design.md`、`docs/detailed-design.md`
- 禁止修改 `docs/tasks/` 下任何任务文件的内容
- 禁止跳过 §2 的代码质量检查就标记模块完成

### 1.3 子 Agent 派生规则

每次派生子 Agent 时，使用以下模板构造 prompt：

```
你是 {模块名} 的开发 Agent。

## 任务
请读取 docs/tasks/{module}.md 中的全部子任务，逐项完成后报告结果。

## 参考文档
- 需求文档: docs/proposal.md
- 详细设计: docs/detailed-design.md （重点关注 §2.{section} 节的接口签名和数据结构）

## 强制约束（违反即失败）
1. 所有代码必须通过 ruff check（规则: E, F, I, N, UP）
2. 所有代码必须通过 mypy --ignore-missing-imports 类型检查
3. 所有测试必须放在 tests/ 目录下，镜像源码目录结构
4. 测试必须用 pytest 运行且全部通过
5. 覆盖率目标: 新增模块 ≥70%，修改模块 ≥ 原覆盖率
6. 新增第三方依赖时，同步更新 requirements.txt
7. 完成后输出: (a) 修改/新增的文件列表 (b) 测试通过数/总数 (c) ruff/mypy 检查结果

## 自修复
若测试或 lint 检查失败，请自行修复后重试。最多重试 3 次。
3 次后仍失败，报告失败原因和已完成的进度。
```

---

## 2. 全局约束与标准

### 2.1 环境管理

| 项目           | 值                                                         |
| -------------- | ---------------------------------------------------------- |
| 环境管理器     | Conda                                                      |
| 环境名         | `medicine-rag`                                             |
| Python 版本    | 3.11                                                       |
| 环境配置文件   | `environment.yml` (conda 基础包) + `requirements.txt` (pip 包) |

**environment.yml 内容**:
```yaml
name: medicine-rag
channels:
  - defaults
  - conda-forge
dependencies:
  - python=3.11
  - psycopg2-binary=2.9.11
  - pyyaml
  - pip
  - pip:
      - -r requirements.txt
```

**一键创建环境命令**:
```bash
conda env create -f environment.yml
conda activate medicine-rag
```

**新增依赖规则**: 子 Agent 发现需要新包时，追加到 `requirements.txt` 末尾并标注版本号。

### 2.2 代码质量铁律

| 工具     | 配置                                       | 通过标准               |
| -------- | ------------------------------------------ | ---------------------- |
| ruff     | `ruff check --select E,F,I,N,UP`           | 零错误（可自动修复的需修复） |
| ruff format | `ruff format`                          | 无格式差异              |
| mypy     | `mypy --ignore-missing-imports`            | 零错误                 |
| pytest   | `pytest tests/ -v --tb=short`             | 全部 PASS              |
| coverage | `pytest --cov=<package> --cov-fail-under=70` | 新增模块 ≥70% 行覆盖率  |

**ruff 规则说明**:

| 规则集 | 含义                       |
| ------ | -------------------------- |
| E      | pycodestyle 错误           |
| F      | pyflakes 错误 (未使用导入等) |
| I      | isort 导入排序              |
| N      | pep8-naming 命名规范        |
| UP     | pyupgrade 语法现代化        |

**mypy 严格度**: 使用 `--ignore-missing-imports` 而非 `--strict`，因为 langchain/chromadb/biopython/dashscope 均无官方 stub 包。项目内部代码的类型注解必须完整。

### 2.3 目录结构约束

```
Medicine_RAG_Project/
├── api/routers/           ← 表示层路由
├── application/services/  ← 应用服务
├── domain/                ← 领域实体 + 接口 (ABC) + 常量
│   ├── entities/
│   ├── services/
│   └── constants.py       ← 新增
├── infrastructure/
│   ├── models/
│   ├── persistence/       ← postgres_db 迁入此处
│   ├── services/
│   └── utils/
├── pubmed/                ← PubMed 检索子系统
├── schemas/               ← Pydantic Schema
├── config/                ← YAML 配置文件
├── prompts/               ← LLM Prompt 模板
├── tests/                 ← 所有测试文件 (新增，镜像源码目录)
│   ├── domain/
│   │   └── test_constants.py
│   ├── schemas/
│   │   ├── test_common.py
│   │   ├── test_pubmed.py
│   │   └── test_knowledge.py
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── test_postgres_db.py
│   │   │   ├── test_vector_store.py
│   │   │   ├── test_pubmed_ingester.py
│   │   │   └── test_document_retriever_impl.py
│   │   └── services/
│   │       └── test_service_factory.py
│   ├── application/
│   │   └── services/
│   │       ├── test_pubmed_search_service.py
│   │       └── test_knowledge_management_service.py
│   ├── api/
│   │   └── routers/
│   │       ├── test_pubmed_router.py
│   │       └── test_knowledge_router.py
│   ├── pubmed/
│   │   ├── test_pubmed_retriever.py
│   │   └── test_paper_search.py
│   └── conftest.py        ← 共享 fixtures
├── docs/                  ← 设计文档（不可修改）
├── data/                  ← 本地指导原则文档
├── chroma/                ← ChromaDB 持久化目录
├── logs/                  ← 日志目录
├── environment.yml        ← 新增
├── requirements.txt       ← 新增
└── main.py
```

> **禁止新增**与上述结构不符的目录。

### 2.4 编码规范

| 维度       | 规则                                                              |
| ---------- | ----------------------------------------------------------------- |
| 类型注解   | 所有函数参数和返回值必须标注类型                                    |
| docstring  | Google-style: `"""一句话概述。\n\nArgs:\n    x: ...\nReturns:\n    ..."""` |
| 命名       | 类: PascalCase / 函数方法: snake_case / 常量: UPPER_SNAKE_CASE    |
| 导入       | 标准库 → 第三方 → 项目内部（组间空行）                             |
| 日志       | `get_logger(name="xxx")` 获取 logger，禁止 `print()`              |
| 日志语言   | 用户可见文本用中文，日志/错误消息用英文                            |
| 文件编码   | UTF-8                                                             |
| 行尾       | LF                                                                |

### 2.5 依赖注入约束

保持现有 `ServiceFactory` + setter 模式：
- `ServiceFactory` 懒加载所有服务，确保全局唯一实例
- Router 通过模块级 `set_xxx_service()` 接收服务
- `main.py` 启动时从 `ServiceFactory` 获取并注入

### 2.6 向后兼容约束

| 约束                     | 说明                                                   |
| ------------------------ | ------------------------------------------------------ |
| `POST /rag/query`        | 请求/响应 Schema 不变                                  |
| 领域接口 (ABC)           | `KeywordExtractionService`/`DocumentRetrievalService`/`RAGSummarizeService` 签名不变 |
| `PostgresDB_singleton`   | 保留旧单例供过渡                                       |
| 旧 `postgres_db.py`      | 添加弃用注释，不直接删除                               |
| 现有测试                 | 保持通过（若有）                                       |

---

## 3. 执行流程

### 3.1 总体流程

```
Phase 0: 环境准备
  ├── 创建 conda 环境
  ├── 生成 environment.yml + requirements.txt
  ├── 执行数据库 DDL 迁移
  └── 安装代码质量工具 (ruff, mypy, pytest, pytest-cov)

Phase 1: Schema & Config (6 模块，可并行)
  ├── domain-constants
  ├── schemas-common
  ├── schemas-pubmed         ← 依赖 schemas-common
  ├── schemas-knowledge
  ├── config-files
  └── database-ddl

Phase 2: 基础设施 (7 模块，分 3 波)
  波 2a (并行):
    ├── pubmed-retriever
    ├── postgres-db          ← 依赖 database-ddl, config-files
    ├── vector-store         ← 依赖 config-files
    └── document-retriever-impl

  波 2b (并行):
    ├── pubmed-ingester      ← 依赖 postgres-db, vector-store, domain-constants
    └── paper-search         ← 依赖 postgres-db, pubmed-retriever

Phase 3: 应用服务 (2 模块，可并行)
  ├── pubmed-search-service
  └── knowledge-management-service

Phase 4: API 路由 (2 模块，可并行)
  ├── pubmed-router
  └── knowledge-router

Phase 5: 组装 (顺序)
  ├── service-factory
  └── main-py

Phase 6: Prompt (1 模块)
  └── prompt-enhancement

Phase 7: 集成测试 & 收尾
  ├── 端到端测试 (18 项)
  ├── 性能测试 (2 项)
  ├── 文档更新 (4 项)
  └── 最终交付验收报告
```

### 3.2 波次调度规则

1. **当前波次的所有模块完成后**，才能启动下一波次
2. 同一波次内无直接依赖的模块**全部并行**派生子 Agent
3. 主 Agent 等待同一波次的所有子 Agent 报告完成（或失败次数耗尽）后，更新 progress.md，然后启动下一波次

---

## 4. Phase 0: 环境准备

### 4.1 操作步骤

主 Agent 执行以下步骤（可自行使用 Bash 工具完成，这些不是业务代码）：

- [ ] **P0-01** — 确认 conda 已安装：`conda --version`
- [ ] **P0-02** — 检查环境是否已存在：`conda env list | grep medicine-rag`
  - 若存在 → 跳过创建，仅确认 Python 3.11
  - 若不存在 → `conda create -n medicine-rag python=3.11 -y`
- [ ] **P0-03** — 生成 `environment.yml`（按 §2.1 模板）
- [ ] **P0-04** — 生成 `requirements.txt`，扫描项目中所有 import 的三方库：

```text
# requirements.txt — Medicine_RAG_Project
# 生成日期: 2026-08-11

# Web 框架
fastapi==0.109.0
uvicorn==0.27.1

# 向量数据库 & LLM 编排
langchain==1.2.15
langchain-chroma==1.1.0
langchain-community==0.4.1
langchain-core==1.2.18
langchain-text-splitters==1.1.1
chromadb==1.5.5

# LLM & Embedding
dashscope==1.25.13

# 中文分词
jieba==0.42.1

# PubMed API
biopython

# 配置
pyyaml

# 文档加载
pypdf
docx2txt

# 测试 & 代码质量
pytest>=8.0
pytest-cov>=5.0
ruff>=0.5
mypy>=1.10
types-pyyaml
```

- [ ] **P0-05** — 激活环境并安装依赖：
  ```bash
  conda activate medicine-rag
  pip install -r requirements.txt
  ```
- [ ] **P0-06** — 验证关键包导入：
  ```bash
  python -c "import fastapi; import chromadb; import langchain; import jieba; import Bio; print('All OK')"
  ```
- [ ] **P0-07** — 创建 `tests/` 目录及子目录结构（镜像源码目录）：
  ```bash
  mkdir -p tests/domain tests/schemas tests/infrastructure/persistence tests/infrastructure/services tests/application/services tests/api/routers tests/pubmed
  ```
- [ ] **P0-08** — 创建 `tests/conftest.py`（共享 fixtures：临时 ChromaDB 目录、mock PostgreSQL 连接参数等）
- [ ] **P0-09** — 执行数据库 DDL 迁移：`psql -U postgres -d medicineKB -f docs/ddl_migration.sql`
- [ ] **P0-10** — 验证 DDL 迁移：查询 `information_schema.columns` 确认新增字段存在

### 4.2 Phase 0 验收标准

- conda 环境 `medicine-rag` 存在，Python 3.11
- 所有 import 无报错
- `tests/` 目录结构完整
- 数据库新字段已添加

---

## 5. Phase 1-6: 分模块开发

### 5.1 主 Agent 执行循环

对每一波次，执行以下步骤：

```
FOR EACH 波次:
  1. 读取 progress.md，确认本波次所有模块的前置依赖已满足
  2. 为本波次每个模块同时派生子 Agent（使用 §1.3 模板 + 模块名）
  3. 等待所有子 Agent 完成
  4. 验收每个子 Agent 的输出:
     a. 检查文件清单是否与预期一致
     b. 若有测试文件，运行 pytest 确认通过
     c. 运行 ruff check 确认零错误
     d. 运行 mypy 确认零错误
  5. 记录结果到 progress.md:
     a. 通过的模块 → 勾选所有复选框，标记 ✅
     b. 失败的模块 → 标记 ❌，记录失败原因
  6. 若存在失败模块 → 根据 §7 处理
  7. 继续下一波次
```

### 5.2 每波次具体模块与调度

按 `docs/tasks/progress.md` 中的波次计划执行。每波次的模块清单、子任务文件、依赖关系详见 progress.md 中的拓扑图。

### 5.3 子 Agent Prompt 变量

主 Agent 在派生子 Agent 时，将以下变量填充到 §1.3 模板中：

| 变量       | 来源                                           |
| ---------- | ---------------------------------------------- |
| `{模块名}` | progress.md 中的模块名称                        |
| `{module}` | 对应的 `docs/tasks/{module}.md` 文件名          |
| `§2.{section}` | detailed-design.md 中该模块对应的章节号（手动映射） |

模块名 → detailed-design 章节号映射：

| 模块                        | detailed-design 章节 |
| --------------------------- | -------------------- |
| domain-constants            | §3.1-3.5             |
| schemas-common              | §2.1                 |
| schemas-pubmed              | §2.2                 |
| schemas-knowledge           | §2.3                 |
| config-files                | 附录 A               |
| database-ddl                | 附录 A.3             |
| postgres-db                 | §2.8                 |
| vector-store                | §2.10                |
| pubmed-ingester             | §2.9                 |
| pubmed-retriever            | §2.13                |
| document-retriever-impl     | §2.11                |
| paper-search                | §2.14                |
| pubmed-search-service       | §2.6                 |
| knowledge-management-service | §2.7                |
| pubmed-router               | §2.4                 |
| knowledge-router            | §2.5                 |
| service-factory             | §2.12                |
| main-py                     | §2.15                |
| prompt-enhancement          | §2.16                |
| integration-test            | §4 (本 Prompt)       |

---

## 6. Phase 7: 集成测试与收尾

### 6.1 执行内容

按 `docs/tasks/integration-test.md` 中的 25 项子任务逐项执行。此 Phase 可由主 Agent 直接操作（启动服务、发送 HTTP 请求），也可派生子 Agent。

### 6.2 最终交付验收报告模板

全部模块完成后，主 Agent 生成如下格式的报告：

```markdown
# 交付验收报告

> 项目: Medicine_RAG_Project
> 日期: YYYY-MM-DD
> 执行模式: 主 Agent + N 个子 Agent 并行

## 模块完成情况

| Phase | 模块数 | 完成 | 失败 | 完成率 |
|-------|--------|------|------|--------|
| 1     | 6      | X    | X    | XX%    |
| 2     | 7      | X    | X    | XX%    |
| 3     | 2      | X    | X    | XX%    |
| 4     | 2      | X    | X    | XX%    |
| 5     | 2      | X    | X    | XX%    |
| 6     | 1      | X    | X    | XX%    |
| 7     | 1      | X    | X    | XX%    |
| **总计** | **21** | **X** | **X** | **XX%** |

## 代码质量总览

| 指标     | 目标     | 实际      | 状态 |
| -------- | -------- | --------- | ---- |
| ruff     | 0 error  | X errors  | ✅/❌ |
| mypy     | 0 error  | X errors  | ✅/❌ |
| pytest   | 全部通过 | X/Y pass  | ✅/❌ |
| coverage | ≥70%     | XX%       | ✅/❌ |

## 遗留问题清单

| #   | 模块     | 问题描述           | 严重度 | 建议                |
| --- | -------- | ------------------ | ------ | ------------------- |
| 1   | ...      | ...                | 高/中/低 | ...               |

## 新增/修改文件清单

| 文件路径                  | 类型 | 行数 | 说明           |
| ------------------------- | ---- | ---- | -------------- |
| ...                       | ...  | ...  | ...            |
```

---

## 7. 异常处理与恢复

### 7.1 子 Agent 自我修复

子 Agent 在以下情况尝试自我修复（最多 3 次）：

1. pytest 测试失败 → 分析失败原因 → 修改代码 → 重新运行测试
2. ruff check 报错 → 运行 `ruff check --fix` 自动修复 → 手动修复剩余问题
3. mypy 类型错误 → 根据错误信息添加/修正类型注解

每次修复后重新运行全量检查（ruff + mypy + pytest），直到全部通过。

### 7.2 超过重试上限

子 Agent 3 次修复仍失败时：
1. 输出已完成的文件列表和最后失败的错误信息
2. 主 Agent 将该模块标记为 **BLOCKED**，记录到 progress.md
3. 主 Agent 评估：若该模块是其他模块的依赖 → 阻塞下游；若否 → 继续其他模块

### 7.3 主 Agent 发现需求/设计问题

若子 Agent 报告设计文档与实现矛盾（如接口签名不可行、配置项缺失等）：
1. 主 Agent 记录到 progress.md 的"风险与问题"区
2. 主 Agent **不修改** proposal.md / high-level-design.md / detailed-design.md / tasks 文件
3. 所有 Phase 完成后，汇总疑问清单给用户

### 7.4 幂等恢复

若流程中断（会话超时、手动停止），重新执行时：
1. 主 Agent 读取 progress.md，识别已完成（✅）和未完成（⬜）的模块
2. 仅对未完成模块派生子 Agent
3. 已完成的模块不再重复执行

---

## 附录 A: 快速参考卡

### A.1 环境一键命令

```bash
# 创建环境
conda env create -f environment.yml

# 激活环境
conda activate medicine-rag

# 安装/更新依赖
pip install -r requirements.txt

# 运行全量测试
pytest tests/ -v --tb=short --cov=. --cov-fail-under=70

# 代码质量检查
ruff check --select E,F,I,N,UP .
ruff format --check .
mypy --ignore-missing-imports .

# 启动服务
python main.py
```

### A.2 子 Agent 快速派发

```
主 Agent → Agent(
  description="开发: {模块名}",
  prompt="你是 {模块名} 的开发 Agent。读取 docs/tasks/{module}.md，逐项完成子任务。代码需通过 ruff+mypy+pytest 检查。失败可自修复最多3次。完成后报告文件清单+测试结果+lint结果。参考: docs/detailed-design.md §{section}"
)
```

### A.3 关键约定速查

| 约定           | 值                                             |
| -------------- | ---------------------------------------------- |
| Python         | 3.11                                           |
| 环境管理器     | Conda (环境名: `medicine-rag`)                  |
| 测试框架       | pytest + pytest-cov                            |
| Lint           | ruff (E, F, I, N, UP)                          |
| 类型检查       | mypy (`--ignore-missing-imports`)              |
| 覆盖率         | ≥70% 行覆盖（新增模块）                         |
| DI 模式        | ServiceFactory + setter                        |
| 测试目录       | tests/ (镜像源码目录)                           |
| 文档保护       | 禁止修改 docs/ 下任何设计文档                    |
| 重试上限       | 3 次                                           |
