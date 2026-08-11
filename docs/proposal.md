# PubMed 文献检索工具与 RAG 系统整合方案

> **项目**: Medicine_RAG_Project — 生物药物资料检索知识库  
> **日期**: 2026-08-10  
> **版本**: v1.0  
> **作者**: Junhao Li

---

## 目录

1. [项目背景与现状分析](#1-项目背景与现状分析)
2. [需求定义](#2-需求定义)
3. [系统整合架构设计](#3-系统整合架构设计)
4. [数据流设计](#4-数据流设计)
5. [API 设计](#5-api-设计)
6. [PubMed 文章向量化方案](#6-pubmed-文章向量化方案)
7. [数据库 Schema 扩展](#7-数据库-schema-扩展)
8. [引文格式方案](#8-引文格式方案)
9. [实施路线图](#9-实施路线图)
10. [风险评估与缓解](#10-风险评估与缓解)

---

## 1. 项目背景与现状分析

### 1.1 项目概述

Medicine_RAG_Project 是一个面向生物制药领域的 RAG（检索增强生成）知识库系统。当前项目包含两个功能独立、数据隔离的子系统：

```
┌─────────────────────────────────────────────────────────────────┐
│                       当前架构（两个独立子系统）                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [PubMed 文献检索工具]               [RAG 知识库系统]              │
│  pubmed/                             FastAPI :8000               │
│  ├─ paper_search.py                  POST /rag/query              │
│  │   search → fetch → insert         ├─ 关键词提取 (Jieba)        │
│  └─ pubmed_retriever.py              ├─ 向量检索 (ChromaDB)       │
│      NCBI Entrez API                  └─ 摘要生成 (Qwen3-max)     │
│         │                                ▲                       │
│         ▼                                │                       │
│  PostgreSQL (medicineKB)            ./data/ (31份文档)            │
│  └─ pubmed_articles                 .doc / .docx / .pdf           │
│     ├─ pmid (去重键)                │                             │
│     ├─ article_info (JSONB)         ▼                             │
│     ├─ study_groups               ChromaDB (./chroma/)            │
│     ├─ results_info (JSONB)       collection: "agent"             │
│     ├─ objectives                 chunk=800, overlap=200          │
│     └─ is_free_download           embeddings: DashScope           │
│                                                                   │
│  🔴 核心断裂点：PubMed 文章在 PostgreSQL 中，                      │
│     但从未进入 ChromaDB，RAG 系统无法检索和使用它们                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 RAG 系统详细架构

| 层级           | 目录/文件                                               | 说明                                                                                    |
| -------------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **表示层**     | `api/routers/rag_router.py`                             | FastAPI 路由，`POST /rag/query`                                                         |
| **应用层**     | `application/services/rag_query_service.py`             | 编排查询流程                                                                            |
| **领域层**     | `domain/entities/`                                      | Document、Query、RAGResponse 实体                                                       |
| **领域层**     | `domain/services/`                                      | 抽象接口 (ABC): KeywordExtractionService, DocumentRetrievalService, RAGSummarizeService |
| **基础设施层** | `infrastructure/persistence/vector_store.py`            | ChromaDB 向量存储 + 文档加载                                                            |
| **基础设施层** | `infrastructure/persistence/document_retriever_impl.py` | 向量检索实现                                                                            |
| **基础设施层** | `infrastructure/utils/rag_summarizer_impl.py`           | LangChain + Qwen3-max 摘要生成                                                          |
| **基础设施层** | `infrastructure/utils/keyword_extractor_impl.py`        | Jieba 分词 + 词性标注关键词提取                                                         |
| **基础设施层** | `infrastructure/models/factory.py`                      | 模型工厂: ChatTongyi + DashScopeEmbeddings                                              |

**RAG 查询管线**:  
用户问题 → Jieba 提取关键词 → ChromaDB 相似度检索 (k=3) → 文档去重合并 → 格式化上下文 → Qwen3-max 生成回答（温哥华引文格式）

**数据摄入管线**:  
`./data/` 文件 → 格式检测 (txt/pdf/doc/docx) → 文档加载器 → RecursiveCharacterTextSplitter (chunk=800, overlap=200) → ChromaDB 向量化 → MD5 去重记录

### 1.3 PubMed 检索工具详细架构

| 文件                         | 说明                                                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `pubmed/pubmed_retriever.py` | `PubMedRetriever` 类: `search_pubmed(query)` 返回 PMID 列表, `fetch_article_details(pmid)` 返回结构化文章数据 |
| `pubmed/paper_search.py`     | 主流程: 连接 PG → 搜索 PubMed → 逐 PMID 查重 → 提取详情 → 插入数据库                                          |

**PubMed 文章数据结构**（存入 `pubmed_articles` 表）:

| 字段               | 类型    | 说明                                    |
| ------------------ | ------- | --------------------------------------- |
| `pmid`             | TEXT    | PubMed 唯一标识符                       |
| `article_info`     | JSONB   | `{title, authors[], abstract, journal}` |
| `study_groups`     | TEXT[]  | 研究分组（当前默认空数组）              |
| `results_info`     | JSONB   | `{raw_abstract, endpoints, stats}`      |
| `objectives`       | TEXT    | 研究目标（摘要前 200 字符）             |
| `is_free_download` | BOOLEAN | 是否可免费获取                          |

### 1.4 数据现状

| 数据源            | 数量   | 格式            | 语言     | 内容类型                                         |
| ----------------- | ------ | --------------- | -------- | ------------------------------------------------ |
| `./data/`         | 31 份  | .doc/.docx/.pdf | 中文为主 | CDE/FDA/EMA 指导原则、审评报告、临床试验相关指南 |
| `pubmed_articles` | 待填充 | JSONB           | 英文为主 | PubMed 学术文献（标题、摘要、作者、期刊）        |

### 1.5 技术栈

| 组件       | 技术选型                       | 说明                   |
| ---------- | ------------------------------ | ---------------------- |
| Web 框架   | FastAPI + Uvicorn              | localhost:8000         |
| 向量数据库 | ChromaDB (本地持久化)          | collection: "agent"    |
| 嵌入模型   | DashScope text-embedding-v4    | 阿里云                 |
| LLM        | Qwen3-max (ChatTongyi)         | 阿里云 DashScope       |
| 关键词提取 | Jieba (词性标注)               | 保留名词/动词/专有名词 |
| 文本分割   | RecursiveCharacterTextSplitter | chunk=800, overlap=200 |
| 关系数据库 | PostgreSQL 本地实例            | medicineKB 数据库      |
| PubMed API | NCBI Entrez (Biopython)        | E-utilities            |
| 文档加载   | PyPDF + Docx2txt + LibreOffice | 多格式回退策略         |

---

## 2. 需求定义

### 2.1 原始功能需求（来自项目需求文档）

本节汇总 `功能需求&启动指令.txt` 中与本整合相关的需求条目：

**1.1 普通 RAG 功能**

- 读取 PDF/Word 等格式文档，转换为易存储的格式
- 存储较大体量的文档
- 实现较快的响应速度和准确度（可考虑知识图谱等方法）
- 将用户诉求拆分为关键词进行检索，而非整句话匹配

**1.2 RAG 输出功能**

- 成文后附带引文格式，标注来源于哪个文件
- 参考温哥华引文格式

**1.3 搜索功能**

- 梳理关键词 + 检索策略
- 检索包括但不限于 PubMed 等文献数据库网站

**1.4 维护本地文献数据库**

- 用户上传文献，拆分解读、结果提炼、数据提炼
- PostgreSQL 数据库，内容部分使用 JSONB 格式存储
- 按方法、结果（有效性、安全性）、Meta 表等 JSONB 字段存储文章信息

**1.5 知识库内容**

- CDE、FDA、EMA 指导原则
- 器审中心、药审中心审评报告
- 试验登记信息
- SAP、Protocol

### 2.2 本次整合目标

将 PubMed 文献搜索拉取工具与 RAG 系统深度整合，实现：

1. **搜索即入库**: 通过 API 触发 PubMed 搜索，结果自动存入本地 PostgreSQL 数据库
2. **入库即索引**: PubMed 文章存入 PostgreSQL 后自动触发向量化索引进入 ChromaDB
3. **混合检索**: RAG 查询时同时搜索本地指导原则文档和 PubMed 学术文献
4. **智能解读**: 通过 LLM 对检索到的文献内容进行结构化解读和摘要
5. **规范引文**: 自动区分机构文件和期刊论文的引文格式，统一使用温哥华规范

### 2.3 设计决策（已确认）

| #   | 决策点           | 选择                        | 说明                                                                                  |
| --- | ---------------- | --------------------------- | ------------------------------------------------------------------------------------- |
| 1   | 检索策略         | **两边混合**                | 同一 ChromaDB collection 中同时存储指导原则文档和 PubMed 文献，查询时不做源类型隔离   |
| 2   | JSONB 向量化方式 | **分字段索引 + 元数据过滤** | 将 article_info 各字段分别标注后拼接为结构化文本，通过 metadata 支持字段级过滤        |
| 3   | 搜索触发方式     | **API 驱动**                | 新增 `POST /pubmed/search` 端点，用户通过 API 主动触发搜索                            |
| 4   | 索引时机         | **自动增量索引**            | 新文章 insert 成功后自动触发 ChromaDB 索引，通过 `ingestion_status` 追踪状态          |
| 5   | 引文格式         | **自动区分**                | 指导原则文件沿用文件标题格式，PubMed 文献采用温哥华期刊格式；内容重叠时两者均保留说明 |
| 6   | 去重策略         | **PMID 级别去重**           | PostgreSQL 层基于 PMID 去重，ChromaDB 层基于 `ingestion_status` 避免重复索引          |

### 2.4 非功能需求

| 类别     | 要求                                                       |
| -------- | ---------------------------------------------------------- |
| 性能     | PubMed 搜索 + 入库 + 索引应在 30 秒内完成（10 篇以内文献） |
| 可靠性   | 单篇文献索引失败不应阻塞整批操作                           |
| 可扩展性 | 后续可接入更多文献数据库（临床试验注册网等）               |
| 向后兼容 | 现有 `/rag/query` 端点行为不变，仅数据源扩展               |
| 可观测性 | 所有新增操作有完整日志记录                                 |

---

## 3. 系统整合架构设计

### 3.1 目标架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           目标整合架构                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────── FastAPI :8000 ──────────────────────────┐  │
│  │                                                                     │  │
│  │  POST /rag/query           POST /pubmed/search                     │  │
│  │  (现有，内部增强)            (新增)                                  │  │
│  │       │                         │                                   │  │
│  │       ▼                         ▼                                   │  │
│  │  RAGQueryService           PubMedSearchAppService                   │  │
│  │       │                         │                                   │  │
│  │       │                    ┌────┴────┐                              │  │
│  │       │                    │         │                              │  │
│  │       │                    ▼         ▼                              │  │
│  │       │             PubMedRetriever  PostgresDB                     │  │
│  │       │             (NCBI Entrez)    (INSERT + 查重)                 │  │
│  │       │                    │         │                              │  │
│  │       │                    │    [自动触发]                           │  │
│  │       │                    │         │                              │  │
│  │       │                    ▼         ▼                              │  │
│  │       │             PubMedArticleIngester (NEW)                     │  │
│  │       │             1. 从 PG 读取文章                                │  │
│  │       │             2. 构建结构化文本                                 │  │
│  │       │             3. 分块 (RecursiveCharacterTextSplitter)         │  │
│  │       │             4. 写入 ChromaDB                                 │  │
│  │       │             5. 更新 ingestion_status                         │  │
│  │       │                    │                                         │  │
│  │       ▼                    ▼                                         │  │
│  │  ┌──────────────────────────────────────────────┐                   │  │
│  │  │           ChromaDB Collection "agent"          │                   │  │
│  │  │  ┌─────────────────┐  ┌─────────────────────┐ │                   │  │
│  │  │  │ source_type:     │  │ source_type:        │ │                   │  │
│  │  │  │ "local_file"     │  │ "pubmed"            │ │                   │  │
│  │  │  │ (./data/ 指导原则)│  │ (PubMed 学术文献)    │ │                   │  │
│  │  │  └─────────────────┘  └─────────────────────┘ │                   │  │
│  │  └──────────────────────────────────────────────┘                   │  │
│  │                                                                     │  │
│  │  GET /pubmed/articles ──── PostgresDB (查询本地文献库)               │  │
│  │  GET /knowledge/stats ──── ChromaDB + PostgresDB (统计)             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心设计原则

1. **单 Collection 共存**: PubMed 文献和本地指导原则文档存入同一个 ChromaDB Collection，通过 `metadata.source_type` 字段区分来源，避免引入检索结果合并层
2. **最小侵入**: 不修改现有 RAG 领域接口抽象（ABC），新功能通过新增服务和扩展基础设施实现
3. **自动级联**: PubMed 文章入库 → 自动触发向量索引，无需用户手动操作
4. **元数据驱动**: 向量块携带丰富元数据（PMID、标题、作者、期刊），支持未来按字段过滤检索

### 3.3 新增模块清单

| 层级         | 文件路径                                               | 类/模块名                       | 用途                              |
| ------------ | ------------------------------------------------------ | ------------------------------- | --------------------------------- |
| **API 路由** | `api/routers/pubmed_router.py`                         | pubmed_router                   | PubMed 搜索、文献管理端点         |
| **API 路由** | `api/routers/knowledge_router.py`                      | knowledge_router                | 知识库统计端点                    |
| **应用服务** | `application/services/pubmed_search_service.py`        | PubMedSearchAppService          | PubMed 搜索编排（搜索→入库→索引） |
| **应用服务** | `application/services/knowledge_management_service.py` | KnowledgeManagementService      | 知识库查询与统计                  |
| **基础设施** | `infrastructure/persistence/pubmed_ingester.py`        | PubMedArticleIngester           | JSONB → 文本 → 分块 → ChromaDB    |
| **Schema**   | `schemas/pubmed.py`                                    | PubMedSearchRequest/Response 等 | 请求/响应模型                     |
| **Schema**   | `schemas/knowledge.py`                                 | KnowledgeStatsResponse 等       | 统计响应模型                      |

### 3.4 现有文件修改清单

| 文件                                                    | 修改内容                                                                      | 影响范围 |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- | -------- |
| `pubmed/paper_search.py`                                | 修复 import 路径 (`utils.xxx` → `infrastructure.utils.xxx`)，重构为可参数化类 | 中       |
| `pubmed/pubmed_retriever.py`                            | `fetch_article_details()` 扩展提取 DOI、publish_date、PMC ID                  | 低       |
| `infrastructure/utils/postgres_db.py`                   | 新增查询方法 + 简单连接池                                                     | 中       |
| `infrastructure/persistence/vector_store.py`            | 暴露 `add_documents_direct()` 方法                                            | 低       |
| `infrastructure/persistence/document_retriever_impl.py` | 增强上下文格式化以支持混合来源                                                | 低       |
| `infrastructure/services/service_factory.py`            | 注册新服务实例                                                                | 低       |
| `main.py`                                               | 注册新 Router                                                                 | 低       |
| `config/pubmed.yml`                                     | 添加 `auto_ingest`、`ingestion_chunk_size` 等配置项                           | 低       |
| `config/chroma.yml`                                     | 添加 PubMed 专属块配置                                                        | 低       |
| `prompts/rag_summarize_prompt.txt`                      | 增强引文格式说明以覆盖 PubMed 文献                                            | 低       |

---

## 4. 数据流设计

### 4.1 搜索入库流

```
POST /pubmed/search {"query": "...", "max_results": 5}
        │
        ▼
PubMedSearchAppService.search_and_store()
        │
        ├──► PubMedRetriever.search_pubmed(query)
        │       └──► NCBI Entrez.esearch → PMID 列表
        │
        ├──► FOR EACH pmid:
        │       │
        │       ├──► PostgresDB.is_pmid_exist(pmid)
        │       │       └──► 已存在 → 跳过，记录 "skipped"
        │       │
        │       ├──► PubMedRetriever.fetch_article_details(pmid)
        │       │       └──► NCBI Entrez.efetch → 结构化文章数据
        │       │
        │       ├──► PostgresDB.insert_article(article_data)
        │       │       └──► 写入 pubmed_articles，ingestion_status='uningested'
        │       │
        │       └──► [auto_ingest=true] PubMedArticleIngester.ingest_article(pmid)
        │               │
        │               ├──► PostgresDB.get_article_by_pmid(pmid)
        │               ├──► _build_article_text() → 结构化文本
        │               ├──► RecursiveCharacterTextSplitter.split_text() → chunks
        │               ├──► ChromaDB.add_documents(chunks + metadata)
        │               └──► PostgresDB.update_ingestion_status(pmid, "ingested")
        │
        └──► 返回: {pmids_found, pmids_new, pmids_ingested, pmids_skipped, details[]}
```

### 4.2 RAG 混合查询流

```
POST /rag/query {"question": "mRNA疫苗的有效性数据是什么？"}
        │
        ▼
RAGQueryService.process_query()
        │
        ├──► RuleBasedKeywordExtractor.extract_keywords(question)
        │       └──► Jieba POS tagging → "mRNA，疫苗，有效性，数据"
        │
        └──► LangChainRAGSummarizer.summarize(query_with_keywords)
                │
                ├──► VectorDocumentRetriever.retrieve_documents(keywords, top_k=3)
                │       └──► ChromaDB.similarity_search()
                │           返回混合结果:
                │           ├── [1] 疫苗临床试验技术指导原则.doc (source_type=local_file)
                │           ├── [2] PMID: 12345678 - mRNA Vaccine Efficacy... (source_type=pubmed)
                │           └── [3] PMID: 87654321 - Safety of mRNA Vaccines... (source_type=pubmed)
                │
                ├──► deduplicate_documents() → 按 source 合并同文献的多个 chunks
                │
                ├──► format_documents_for_context()
                │       区分格式:
                │       [1] 《疫苗临床试验技术指导原则》（指导原则文件）
                │       [2] Baden LR, et al. Efficacy and Safety of mRNA-1273 Vaccine.
                │           N Engl J Med. 2020. PMID: 12345678
                │
                └──► LLM chain.invoke({input, context})
                        └──► Qwen3-max 生成回答（温哥华格式引文，混合来源）
```

### 4.3 自动增量索引流

```
PostgresDB.insert_article(article_data)
        │
        ├──► INSERT INTO pubmed_articles (..., ingestion_status='uningested')
        │
        └──► [auto_ingest 开启] 触发回调:
                │
                PubMedArticleIngester.ingest_article(pmid)
                │
                ├──► 检查 ingestion_status ≠ 'ingested' → 继续
                ├──► 更新 status → 'ingesting'
                ├──► 构建文本 + 分块 + 写入 ChromaDB
                ├──► 更新 status → 'ingested', 记录 chunk_count
                │
                └──► [失败] 更新 status → 'failed', 记录 ingestion_error
```

---

## 5. API 设计

### 5.1 新增端点总览

| 方法     | 路径                            | 说明                              |
| -------- | ------------------------------- | --------------------------------- |
| `POST`   | `/pubmed/search`                | 搜索 PubMed，入库，自动索引       |
| `GET`    | `/pubmed/articles`              | 浏览/搜索本地文献库（分页、筛选） |
| `GET`    | `/pubmed/articles/{pmid}`       | 获取单篇文献完整详情              |
| `POST`   | `/pubmed/ingest/{pmid}`         | 手动触发单篇文献向量索引          |
| `POST`   | `/pubmed/ingest/batch`          | 批量索引指定 PMID                 |
| `POST`   | `/pubmed/ingest/all-uningested` | 一键索引所有未入库文章            |
| `DELETE` | `/pubmed/articles/{pmid}`       | 删除文章（PG + ChromaDB）         |
| `GET`    | `/knowledge/stats`              | 知识库统计概览                    |

### 5.2 端点详细设计

#### `POST /pubmed/search`

触发 PubMed 搜索，结果自动存入 PostgreSQL 并（默认）自动索引到 ChromaDB。

**Request**:

```json
{
  "query": "COVID-19 mRNA vaccine efficacy and safety",
  "max_results": 5,
  "auto_ingest": true
}
```

| 参数        | 类型   | 必填 | 默认值     | 说明                                      |
| ----------- | ------ | ---- | ---------- | ----------------------------------------- |
| query       | string | ✅   | -          | PubMed 查询词（支持 PubMed 高级检索语法） |
| max_results | int    | ❌   | 5 (config) | 最大返回文献数                            |
| auto_ingest | bool   | ❌   | true       | 是否自动索引到 ChromaDB                   |

**Response** (200):

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "query": "COVID-19 mRNA vaccine efficacy and safety",
    "pmids_found": 5,
    "pmids_new": 3,
    "pmids_ingested": 3,
    "pmids_skipped": 2,
    "pmids_failed": 0,
    "details": [
      {
        "pmid": "12345678",
        "status": "ingested",
        "title": "Efficacy and Safety of the mRNA-1273..."
      },
      {
        "pmid": "87654321",
        "status": "ingested",
        "title": "Safety and Efficacy of the BNT162b2..."
      },
      {
        "pmid": "11111111",
        "status": "ingested",
        "title": "mRNA vaccine phase III trial results..."
      },
      { "pmid": "22222222", "status": "skipped", "reason": "already_exists" },
      { "pmid": "33333333", "status": "skipped", "reason": "already_exists" }
    ]
  }
}
```

#### `GET /pubmed/articles`

浏览和搜索本地已存储的文献。

**Query Parameters**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页条数（最大 100） |
| search | string | - | 关键词搜索（匹配标题和摘要） |
| ingestion_status | string | "all" | "all" / "ingested" / "uningested" / "failed" |
| sort_by | string | "created_at" | 排序字段 |
| order | string | "desc" | "asc" / "desc" |

**Response** (200):

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": 47,
    "page": 1,
    "page_size": 20,
    "articles": [
      {
        "pmid": "12345678",
        "title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
        "authors": ["Baden LR", "El Sahly HM", "Essink B"],
        "journal": "N Engl J Med",
        "publish_date": "2020-12-31",
        "abstract_preview": "BACKGROUND: Vaccination...",
        "is_free_download": true,
        "ingestion_status": "ingested",
        "ingested_at": "2026-08-10T14:30:00Z",
        "study_groups": ["vaccine group", "placebo group"]
      }
    ]
  }
}
```

#### `GET /pubmed/articles/{pmid}`

获取单篇文献完整详情。

**Response** (200):

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "pmid": "12345678",
    "article_info": {
      "title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
      "authors": ["Baden LR", "El Sahly HM", "Essink B"],
      "abstract": "BACKGROUND: ... METHODS: ... RESULTS: ... CONCLUSIONS: ...",
      "journal": "N Engl J Med",
      "doi": "10.1056/NEJMoa2035389",
      "publish_date": "2020-12-31"
    },
    "study_groups": ["vaccine group", "placebo group"],
    "results_info": {
      "raw_abstract": "BACKGROUND: Vaccination...",
      "endpoints": "从摘要提取的核心终点指标",
      "stats": "从摘要提取的统计结果"
    },
    "objectives": "To evaluate the efficacy and safety of mRNA-1273...",
    "is_free_download": true,
    "ingestion_status": "ingested",
    "chunk_count": 5,
    "ingested_at": "2026-08-10T14:30:00Z",
    "created_at": "2026-08-10T14:25:00Z",
    "updated_at": "2026-08-10T14:30:00Z"
  }
}
```

#### `POST /pubmed/ingest/all-uningested`

一键将所有未索引的 PubMed 文章排入 ChromaDB。

**Response** (200):

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total_uningested": 15,
    "ingested": 14,
    "failed": 1,
    "details": [
      { "pmid": "11111111", "status": "ingested", "chunk_count": 4 },
      {
        "pmid": "99999999",
        "status": "failed",
        "reason": "Empty abstract, no extractable text"
      }
    ]
  }
}
```

#### `GET /knowledge/stats`

获取知识库总体统计信息。

**Response** (200):

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "local_documents": 31,
    "pubmed_articles_total": 47,
    "pubmed_articles_ingested": 42,
    "pubmed_articles_uningested": 5,
    "total_vector_chunks": 2340,
    "by_source_type": {
      "local_file": 1820,
      "pubmed": 520
    },
    "vector_store": {
      "collection_name": "agent",
      "storage_path": "./chroma/",
      "embedding_model": "text-embedding-v4"
    }
  }
}
```

### 5.3 现有端点影响

`POST /rag/query` — **请求和响应 Schema 不变**。内部增强：

- `sources` 数组中混合出现文件名和 PMID 引用
- `answer` 中引文格式自动区分指导原则文件和期刊文献

---

## 6. PubMed 文章向量化方案

### 6.1 分字段文本模板

为最大化语义检索精度，将 PubMed JSONB 数据按字段标注后拼接为结构化文本，而非简单拼接：

```
[PubMed Article]
Title: {article_info.title}
Authors: {authors_list_formatted}
Journal: {article_info.journal}
Publication Date: {publish_date}
DOI: {doi}
PMID: {pmid}

Research Objectives:
{objectives}

Study Groups:
{study_groups_formatted}

Key Results:
{results_info.raw_abstract}

Abstract:
{article_info.abstract}
```

**设计理由**:

- **字段标签**（如 `Title:`、`Abstract:`）为嵌入模型提供了语义锚点，提升按特定字段匹配的精度
- **PMID 在文本中**: 使 PMID 本身可被向量搜索匹配
- **前置元数据**: 标题/作者/期刊在文本开头，因为这些信息区分度最高，且在 Chunk 切分时优先保留
- **分层结构**: Objectives → Study Groups → Results → Abstract 对应临床研究方法学的逻辑层次

### 6.2 块策略

复用现有 `RecursiveCharacterTextSplitter` 配置，保持与本地文档一致：

```yaml
# config/chroma.yml 新增
pubmed_chunk_size: 800
pubmed_chunk_overlap: 200
pubmed_separator: ["\n\n", "\n", ". ", "! ", "? ", "。", "！", "？", " ", ""]
```

PubMed 摘要通常 200-400 词，加上元数据和字段标签后约 500-800 词，大多数文章会生成 1-3 个 chunks。

### 6.3 元数据 Schema

每个 PubMed 向量块携带以下元数据：

```python
{
    "source": "PMID:12345678: Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
    "source_type": "pubmed",
    "pmid": "12345678",
    "title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
    "authors": "Baden LR, El Sahly HM, Essink B",
    "journal": "N Engl J Med",
    "publish_date": "2020-12-31",
    "doi": "10.1056/NEJMoa2035389",
    "is_free_download": True,
    "chunk_index": 0,
    "total_chunks": 5,
}
```

**与本地文件元数据的对比**:

| 字段        | 本地文件                           | PubMed 文献                                      |
| ----------- | ---------------------------------- | ------------------------------------------------ |
| source      | `《疫苗临床试验技术指导原则》.doc` | `PMID:12345678: Title...`                        |
| source_type | `local_file`                       | `pubmed`                                         |
| 特有字段    | 无                                 | pmid, title, authors, journal, publish_date, doi |

### 6.4 增量索引与去重

- **去重键**: PMID（不同于本地文件用 MD5）
- **状态追踪**: `pubmed_articles.ingestion_status` 字段（uningested → ingesting → ingested / failed）
- **强制重索引**: 若 `force=true`，先通过 `metadata.pmid` 查询 ChromaDB 删除旧 chunks，再重新索引
- **幂等性**: 重复调用 `ingest_article(pmid)` 对已 ingested 的文章为 no-op（除非 force=true）

---

## 7. 数据库 Schema 扩展

### 7.1 `pubmed_articles` 表新增字段

```sql
-- 新增列
ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(20) DEFAULT 'uningested',
ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS chunk_count INTEGER,
ADD COLUMN IF NOT EXISTS vector_ids JSONB,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS search_query TEXT,
ADD COLUMN IF NOT EXISTS ingestion_error TEXT,
ADD COLUMN IF NOT EXISTS raw_response JSONB;

-- 索引
CREATE INDEX IF NOT EXISTS idx_pubmed_ingestion_status ON pubmed_articles(ingestion_status);
CREATE INDEX IF NOT EXISTS idx_pubmed_created_at ON pubmed_articles(created_at);
CREATE INDEX IF NOT EXISTS idx_pubmed_article_gin ON pubmed_articles USING GIN (article_info jsonb_path_ops);
```

### 7.2 扩展后表结构总览

| 字段                   | 类型        | 默认值         | 说明                                                       |
| ---------------------- | ----------- | -------------- | ---------------------------------------------------------- |
| `id`                   | SERIAL      | AUTO           | 自增主键                                                   |
| `pmid`                 | TEXT        | -              | PubMed 唯一标识（去重键）                                  |
| `article_info`         | JSONB       | -              | `{title, authors[], abstract, journal, doi, publish_date}` |
| `study_groups`         | TEXT[]      | `[]`           | 研究分组标签                                               |
| `results_info`         | JSONB       | -              | `{raw_abstract, endpoints, stats}`                         |
| `objectives`           | TEXT        | -              | 研究目标摘要                                               |
| `is_free_download`     | BOOLEAN     | false          | PMC 可免费获取标识                                         |
| **`ingestion_status`** | VARCHAR(20) | `'uningested'` | **新增**: uningested/ingesting/ingested/failed             |
| **`ingested_at`**      | TIMESTAMP   | NULL           | **新增**: 索引完成时间                                     |
| **`chunk_count`**      | INTEGER     | NULL           | **新增**: 向量块数量                                       |
| **`vector_ids`**       | JSONB       | NULL           | **新增**: ChromaDB chunk IDs                               |
| **`created_at`**       | TIMESTAMP   | NOW()          | **新增**: 入库时间                                         |
| **`updated_at`**       | TIMESTAMP   | NOW()          | **新增**: 最后更新时间                                     |
| **`search_query`**     | TEXT        | NULL           | **新增**: 检索查询词                                       |
| **`ingestion_error`**  | TEXT        | NULL           | **新增**: 索引失败原因                                     |
| **`raw_response`**     | JSONB       | NULL           | **新增**: PubMed 原始完整响应                              |

### 7.3 `article_info` JSONB 结构扩展

```json
{
  "title": "Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine",
  "authors": ["Baden LR", "El Sahly HM", "Essink B"],
  "abstract": "BACKGROUND: ... METHODS: ... RESULTS: ... CONCLUSIONS: ...",
  "journal": "N Engl J Med",
  "doi": "10.1056/NEJMoa2035389",
  "publish_date": "2020-12-31",
  "pmc_id": "PMC7717217",
  "publication_type": "Clinical Trial, Phase III"
}
```

新增提取字段：`doi`、`publish_date`、`pmc_id`、`publication_type`。

---

## 8. 引文格式方案

### 8.1 两类文献的引文格式

**指导原则/机构文件**（沿用现有格式）:

```
[N] 《文件标题（不含文件后缀名）》.
```

示例: `[1] 《疫苗临床试验技术指导原则》.`

**PubMed 期刊文献**（温哥华格式）:

```
[N] Authors. Title. Journal Abbreviation. Year Month Day;Volume(Issue):Pages. PMID: xxxxxxxx.
```

示例: `[2] Baden LR, El Sahly HM, Essink B, et al. Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine. N Engl J Med. 2020 Dec 31;383(27):2603-2615. PMID: 33301246.`

### 8.2 正文引用方式

正文中使用统一的上标数字引用，文末参考文献列表混合排列：

> 根据 mRNA 疫苗的 III 期临床试验数据，疫苗有效性达到 94.1%²。同时，《疫苗临床试验技术指导原则》要求疫苗临床试验需采用随机、双盲、安慰剂对照设计¹。该试验在方法学上完全符合指导原则的要求，采用了严格的随机化分组和盲法评估²。

### 8.3 内容重叠处理策略

当 PubMed 文献的内容与 `./data/` 中指导原则文件高度重叠（如都涉及"生物等效性评价方法"）：

1. **两篇文献都保留**在检索结果中
2. **LLM 提示词要求**：当多个来源涉及同一主题时，先陈述指导原则的规定，再引用学术文献中的具体研究数据或案例，用"指导原则要求……，相关研究进一步表明……"的结构
3. **在回答中区分角色**: 指导原则 = "规范性要求"，学术文献 = "研究证据"

### 8.4 Prompt 增强

`prompts/rag_summarize_prompt.txt` 需增加以下指引：

```
### 文献类型识别（新增）
- 参考资料中标注为「指导原则文件」的为监管机构发布的规范性文件
- 参考资料中标注为「PMID:」开头的为 PubMed 学术文献
- 引文格式区分：
  - 指导原则文件：[N] 《文件标题》.
  - 期刊文献：[N] Authors. Title. Journal. Year. PMID: xxxxx.
- 当多个来源对同一主题有论述时，先陈述规范性要求，再引用研究证据
```

---

## 9. 实施路线图

### Phase 1: 基础重构（预计 2-3 天）

**目标**: 使 PubMed 模块可被 API 层调用，数据库 Schema 就绪。

| #   | 任务                                                                                           | 涉及文件                                 |
| --- | ---------------------------------------------------------------------------------------------- | ---------------------------------------- |
| 1.1 | 修复 `pubmed/paper_search.py` import 路径                                                      | `pubmed/paper_search.py`                 |
| 1.2 | 重构 `main()` 为可参数化调用的函数                                                             | `pubmed/paper_search.py`                 |
| 1.3 | 扩展 `fetch_article_details()` 提取 DOI、publish_date、PMC ID                                  | `pubmed/pubmed_retriever.py`             |
| 1.4 | 新增 `PostgresDB` 查询方法 (`get_article_by_pmid`, `list_articles`, `update_ingestion_status`) | `infrastructure/utils/postgres_db.py`    |
| 1.5 | 执行数据库迁移（新增字段 + 索引）                                                              | DDL 脚本                                 |
| 1.6 | 添加 PubMed 配置项                                                                             | `config/pubmed.yml`, `config/chroma.yml` |

### Phase 2: 索引引擎（预计 3-4 天）

**目标**: 实现 JSONB → 文本 → 分块 → ChromaDB 的完整管线。

| #   | 任务                                                    | 涉及文件                                               |
| --- | ------------------------------------------------------- | ------------------------------------------------------ |
| 2.1 | 实现 `PubMedArticleIngester` 类                         | `infrastructure/persistence/pubmed_ingester.py` (新建) |
| 2.2 | 在 `VectorStoreService` 中暴露 `add_documents_direct()` | `infrastructure/persistence/vector_store.py`           |
| 2.3 | 实现单篇/批量/全量索引方法                              | `pubmed_ingester.py`                                   |
| 2.4 | 实现 `remove_from_vector_store()`                       | `pubmed_ingester.py`                                   |
| 2.5 | 编写单元测试                                            | 测试文件                                               |

### Phase 3: API 层（预计 3-4 天）

**目标**: 所有新端点可用，与现有 RAG 端点互通。

| #   | 任务                               | 涉及文件                                                      |
| --- | ---------------------------------- | ------------------------------------------------------------- |
| 3.1 | 创建 Pydantic Schema               | `schemas/pubmed.py`, `schemas/knowledge.py` (新建)            |
| 3.2 | 实现 `PubMedSearchAppService`      | `application/services/pubmed_search_service.py` (新建)        |
| 3.3 | 实现 `KnowledgeManagementService`  | `application/services/knowledge_management_service.py` (新建) |
| 3.4 | 实现 PubMed Router                 | `api/routers/pubmed_router.py` (新建)                         |
| 3.5 | 实现 Knowledge Router              | `api/routers/knowledge_router.py` (新建)                      |
| 3.6 | 更新 ServiceFactory + main.py 注册 | `infrastructure/services/service_factory.py`, `main.py`       |

### Phase 4: 集成测试与调优（预计 2-3 天）

**目标**: 端到端验证混合检索质量。

| #   | 任务                                                  |
| --- | ----------------------------------------------------- |
| 4.1 | 用 5-10 篇真实 PubMed 文献进行端到端测试              |
| 4.2 | 验证 RAG 查询同时返回指导原则 + PubMed 文献的结果质量 |
| 4.3 | 调优 prompt 以正确处理混合文源的引文格式              |
| 4.4 | 边界情况测试（空摘要、0 结果、网络失败、已存在文献）  |
| 4.5 | 性能测试（批量索引 20 篇文章的耗时和 API 成本）       |

### Phase 5: 文档与收尾（预计 1-2 天）

| #   | 任务                                      |
| --- | ----------------------------------------- |
| 5.1 | 更新 README.md（新增 API 文档）           |
| 5.2 | 更新 `test_main.http`（新增端点测试用例） |
| 5.3 | 补充代码注释和 docstring                  |
| 5.4 | 创建错误处理指南                          |

---

## 10. 风险评估与缓解

### 风险矩阵

| #   | 风险                                         | 严重度 | 可能性 | 缓解措施                                                                              |
| --- | -------------------------------------------- | ------ | ------ | ------------------------------------------------------------------------------------- |
| 1   | PubMed API 频率限制 (10 req/s)               | **高** | 中     | 添加请求间隔配置 (0.15s)，指数退避重试，批次操作进度提示                              |
| 2   | DashScope Embedding API 成本                 | **中** | 高     | 限制单批次索引量 (≤30 篇)；评估本地嵌入模型作为降级方案；实现 `dry_run` 模式预估成本  |
| 3   | 中英文跨语言检索质量                         | **中** | 中     | 保留原始英文查询词与中文关键词混合检索；后续可引入关键词翻译                          |
| 4   | PostgreSQL 连接在 FastAPI 异步环境下的安全性 | **中** | 中     | 使用 `psycopg2` 连接池或上下文管理器；后续考虑 `asyncpg` 迁移                         |
| 5   | ChromaDB 混合内容规模增长导致检索退化        | **低** | 低     | 当前规模（千级 chunks）远低于 ChromaDB 瓶颈 (~100K)；通过 `/knowledge/stats` 监控增长 |
| 6   | PubMed XML 解析异常                          | **低** | 低     | 已有重试逻辑；新增 `raw_response` 列存储原始响应用于调试；单篇失败不阻塞整批          |
| 7   | 文章内容更新导致向量过期                     | **低** | 低     | 通过 `force=true` 支持强制重索引；后续可增加定时刷新机制                              |

### 降级方案

| 场景                 | 降级策略                                                                 |
| -------------------- | ------------------------------------------------------------------------ |
| PubMed API 不可用    | 通过缓存本地已有文献回答；提示用户稍后重试                               |
| ChromaDB 写入失败    | 标记 `ingestion_status='failed'`；文章仍在 PG 中可查询；支持手动重试     |
| DashScope API 不可用 | 中断索引操作，已入库文章标记为 `uningested`，等待 API 恢复后一键批量索引 |

---

## 附录 A: 关键文件路径索引

| 文件            | 绝对路径                                                |
| --------------- | ------------------------------------------------------- |
| PubMed 入口     | `pubmed/paper_search.py`                                |
| PubMed 检索器   | `pubmed/pubmed_retriever.py`                            |
| PostgreSQL 工具 | `infrastructure/utils/postgres_db.py`                   |
| 向量存储服务    | `infrastructure/persistence/vector_store.py`            |
| 文档检索器      | `infrastructure/persistence/document_retriever_impl.py` |
| RAG 摘要器      | `infrastructure/utils/rag_summarizer_impl.py`           |
| 关键词提取器    | `infrastructure/utils/keyword_extractor_impl.py`        |
| 模型工厂        | `infrastructure/models/factory.py`                      |
| 服务工厂        | `infrastructure/services/service_factory.py`            |
| 配置处理器      | `infrastructure/utils/config_handler.py`                |
| RAG 查询服务    | `application/services/rag_query_service.py`             |
| FastAPI 入口    | `main.py`                                               |
| RAG 路由        | `api/routers/rag_router.py`                             |
| RAG Prompt      | `prompts/rag_summarize_prompt.txt`                      |
| PubMed 配置     | `config/pubmed.yml`                                     |
| ChromaDB 配置   | `config/chroma.yml`                                     |
| PostgreSQL 配置 | `config/postgre.yml`                                    |
| RAG 模型配置    | `config/rag.yml`                                        |

## 附录 B: 依赖项

| 包                       | 版本    | 用途                              |
| ------------------------ | ------- | --------------------------------- |
| langchain                | 1.2.15  | RAG 编排框架                      |
| langchain-chroma         | 1.1.0   | ChromaDB 集成                     |
| langchain-community      | 0.4.1   | ChatTongyi, DashScope, 文档加载器 |
| langchain-core           | 1.2.18  | 核心类型与接口                    |
| langchain-text-splitters | 1.1.1   | 文本分割                          |
| chromadb                 | 1.5.5   | 向量数据库                        |
| dashscope                | 1.25.13 | 阿里云模型 SDK                    |
| jieba                    | 0.42.1  | 中文分词/关键词提取               |
| fastapi                  | 0.109.0 | Web 框架                          |
| uvicorn                  | 0.27.1  | ASGI 服务器                       |
| psycopg2-binary          | 2.9.11  | PostgreSQL 驱动                   |
| biopython                | -       | NCBI Entrez API                   |
| pyyaml                   | -       | YAML 配置解析                     |
