# 概要设计文档

> **项目**: Medicine_RAG_Project — 生物药物资料检索知识库  
> **日期**: 2026-08-11  
> **版本**: v1.0  
> **作者**: Junhao Li  
> **依赖文档**: [proposal.md](./proposal.md)

---

## 目录

1. [总体架构概述](#1-总体架构概述)
2. [系统模块划分清单](#2-系统模块划分清单)
3. [各模块职责说明](#3-各模块职责说明)
4. [模块间依赖与数据流](#4-模块间依赖与数据流)
5. [全局公共设计](#5-全局公共设计)
6. [架构约束与风险点](#6-架构约束与风险点)

---

## 1. 总体架构概述

### 1.1 架构分层

本项目采用 **DDD 分层架构**（Domain-Driven Design Lite），自上而下分为四层：

```
┌─────────────────────────────────────────────────────────────────────┐
│                        表示层 (Presentation)                         │
│  api/routers/         FastAPI 路由，HTTP 请求解析与响应封装           │
│  schemas/             Pydantic 请求/响应模型                         │
├─────────────────────────────────────────────────────────────────────┤
│                        应用层 (Application)                          │
│  application/services/ 业务用例编排，协调领域服务完成复合操作          │
├─────────────────────────────────────────────────────────────────────┤
│                        领域层 (Domain)                               │
│  domain/entities/     纯数据实体 (dataclass)                         │
│  domain/services/     抽象接口 (ABC)，定义服务契约                    │
├─────────────────────────────────────────────────────────────────────┤
│                       基础设施层 (Infrastructure)                     │
│  infrastructure/persistence/  向量存储、文档检索、PostgreSQL 持久化   │
│  infrastructure/utils/        关键词提取、摘要生成、配置、日志等工具   │
│  infrastructure/models/       LLM / Embedding 模型工厂               │
│  infrastructure/services/     DI 容器 (ServiceFactory)               │
└─────────────────────────────────────────────────────────────────────┘
```

**核心原则**：
- **依赖方向**: 表示层 → 应用层 → 领域层 ← 基础设施层。领域层不依赖任何外层，基础设施层实现领域层定义的接口。
- **最小侵入**: 本次整合不修改现有 RAG 领域接口（ABC），新功能通过新增服务和扩展基础设施实现。
- **模块解耦**: 每个模块通过 ABC 接口隔离，可独立替换实现和编写单元测试。

### 1.2 系统拓扑

```
┌────────────────────────── FastAPI :8000 ──────────────────────────────┐
│                                                                        │
│  api/routers/                                                         │
│  ├── rag_router        POST /rag/query          (现有，内部增强)       │
│  ├── pubmed_router     POST /pubmed/search       (新增)                │
│  │                     GET  /pubmed/articles                          │
│  │                     GET  /pubmed/articles/{pmid}                    │
│  │                     POST /pubmed/ingest/{pmid}                      │
│  │                     POST /pubmed/ingest/batch                       │
│  │                     POST /pubmed/ingest/all-uningested              │
│  │                     DELETE /pubmed/articles/{pmid}                  │
│  └── knowledge_router  GET  /knowledge/stats     (新增)                │
│                                                                        │
│  application/services/                                                │
│  ├── RAGQueryService              (现有)                               │
│  ├── PubMedSearchAppService       (新增)                               │
│  └── KnowledgeManagementService   (新增)                               │
│                                                                        │
│  infrastructure/persistence/                                          │
│  ├── VectorStoreService           (现有，扩展)                         │
│  ├── VectorDocumentRetriever      (现有，扩展)                         │
│  ├── PostgresDB                   (重构: utils → persistence)          │
│  └── PubMedArticleIngester        (新增)                               │
│                                                                        │
│  ┌────────────────── 外部依赖 ──────────────────────┐                  │
│  │  ChromaDB (本地)    DashScope (阿里云)            │                  │
│  │  PostgreSQL (本地)  NCBI Entrez (PubMed API)      │                  │
│  └──────────────────────────────────────────────────┘                  │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心技术栈

| 组件             | 技术选型                          | 版本      | 用途                       |
| ---------------- | --------------------------------- | --------- | -------------------------- |
| Web 框架         | FastAPI + Uvicorn                 | 0.109.0   | HTTP 服务                  |
| 向量数据库       | ChromaDB (本地持久化)             | 1.5.5     | 文档向量存储与相似度检索    |
| 嵌入模型         | DashScope text-embedding-v4       | -         | 文本向量化                 |
| LLM              | Qwen3-max (ChatTongyi)            | -         | RAG 摘要生成               |
| 关键词提取       | Jieba (词性标注)                  | 0.42.1    | 中文分词与关键词提取        |
| 文本分割         | RecursiveCharacterTextSplitter    | 1.1.1     | 文档分块                   |
| 关系数据库       | PostgreSQL (本地实例)             | -         | PubMed 文献结构化存储       |
| PubMed API       | NCBI Entrez (Biopython)           | -         | 文献检索与详情获取          |
| 文档加载         | PyPDF + Docx2txt + LibreOffice    | -         | 多格式文档解析              |
| LLM 编排         | LangChain                         | 1.2.15    | RAG 管线编排               |
| ORM/驱动         | psycopg2-binary                   | 2.9.11    | PostgreSQL 连接            |

---

## 2. 系统模块划分清单

### 2.1 新增模块

| 层级           | 文件路径                                                   | 类/模块名                     | 用途                           |
| -------------- | ---------------------------------------------------------- | ----------------------------- | ------------------------------ |
| **API 路由**   | `api/routers/pubmed_router.py`                             | pubmed_router                 | PubMed 搜索、文献管理端点      |
| **API 路由**   | `api/routers/knowledge_router.py`                          | knowledge_router              | 知识库统计端点                 |
| **应用服务**   | `application/services/pubmed_search_service.py`            | PubMedSearchAppService        | PubMed 搜索→入库→索引编排      |
| **应用服务**   | `application/services/knowledge_management_service.py`     | KnowledgeManagementService    | 文献查询、统计、删除            |
| **基础设施**   | `infrastructure/persistence/pubmed_ingester.py`            | PubMedArticleIngester         | JSONB→文本→分块→ChromaDB 管线 |
| **基础设施**   | `infrastructure/persistence/postgres_db.py` (迁移+重构)    | PostgresDB                    | PG 连接管理 + 完整 CRUD        |
| **Schema**     | `schemas/pubmed.py`                                        | 请求/响应 Pydantic 模型        | PubMed 相关接口 Schema          |
| **Schema**     | `schemas/knowledge.py`                                     | 请求/响应 Pydantic 模型        | 知识库统计接口 Schema          |

### 2.2 修改模块

| 文件                                                     | 修改内容                                                              | 影响范围 |
| -------------------------------------------------------- | --------------------------------------------------------------------- | -------- |
| `pubmed/paper_search.py`                                 | 重构 `main()` 为可参数化类 `PubMedSearchPipeline`；修复 import 路径   | 中       |
| `pubmed/pubmed_retriever.py`                             | `fetch_article_details()` 扩展提取 DOI、publish_date、PMC ID、publication_type | 低       |
| `infrastructure/persistence/postgres_db.py` (迁移后)     | 迁移路径 `utils/→persistence/`；新增 `get_article_by_pmid`、`list_articles`、`update_ingestion_status`、`delete_article`、`get_stats`；添加连接池/上下文管理器 | 中       |
| `infrastructure/persistence/vector_store.py`             | 暴露 `add_documents_direct(documents, embeddings)` 方法；支持 metadata 过滤删除 | 低       |
| `infrastructure/persistence/document_retriever_impl.py`  | `format_documents_for_context()` 区分 source_type 生成不同引文格式    | 低       |
| `infrastructure/services/service_factory.py`             | 注册新服务：PostgresDB、PubMedArticleIngester、PubMedSearchAppService、KnowledgeManagementService | 中       |
| `main.py`                                                | 注册新 Router、初始化新服务                                            | 低       |
| `config/pubmed.yml`                                      | 添加 `auto_ingest`、`request_interval`、`ingestion_chunk_size` 等      | 低       |
| `config/chroma.yml`                                      | 添加 PubMed 分块配置（`pubmed_chunk_size`、`pubmed_chunk_overlap`）    | 低       |
| `prompts/rag_summarize_prompt.txt`                       | 增强引文格式处理指引：区分指导原则文件与期刊文献                        | 低       |

### 2.3 模块全景图

```
项目模块树 (仅含 .py 源文件)
═══════════════════════════════════════════════════════════════

main.py                              ← FastAPI 入口

api/
├── __init__.py
└── routers/
    ├── __init__.py
    ├── rag_router.py                ← POST /rag/query (已有)
    ├── pubmed_router.py             ← PubMed 相关端点 (新增)
    └── knowledge_router.py          ← 知识库统计端点 (新增)

application/
├── __init__.py
└── services/
    ├── __init__.py
    ├── rag_query_service.py         ← RAG 查询编排 (已有)
    ├── pubmed_search_service.py     ← PubMed 搜索编排 (新增)
    └── knowledge_management_service.py ← 知识库管理编排 (新增)

domain/
├── __init__.py
├── entities/
│   ├── __init__.py
│   ├── document.py                  ← Document 数据类
│   ├── query.py                     ← Query 数据类
│   └── rag_response.py              ← RAGResponse 数据类
└── services/
    ├── __init__.py
    ├── keyword_extraction_service.py    ← ABC: 关键词提取
    ├── document_retrieval_service.py    ← ABC: 文档检索
    └── rag_summarize_service.py         ← ABC: RAG 摘要

infrastructure/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── factory.py                   ← ChatModel + Embedding 工厂
├── persistence/
│   ├── __init__.py
│   ├── vector_store.py              ← ChromaDB 向量存储 (扩展)
│   ├── document_retriever_impl.py   ← 向量检索实现 (扩展)
│   ├── postgres_db.py               ← PG 持久化 (从 utils 迁入, 重构)
│   └── pubmed_ingester.py           ← PubMed 文章向量化管线 (新增)
├── services/
│   └── service_factory.py           ← DI 容器 (扩展)
└── utils/
    ├── __init__.py
    ├── config_handler.py            ← YAML 配置加载
    ├── file_handler.py              ← 多格式文档加载器
    ├── keyword_extractor_impl.py    ← Jieba 关键词提取
    ├── logger_handler.py            ← 双通道日志
    ├── path_tool.py                 ← 路径解析工具
    ├── prompt_loader.py             ← Prompt 文件加载
    └── rag_summarizer_impl.py       ← LangChain RAG 摘要

schemas/
├── __init__.py
├── rag_query.py                     ← RAG 查询 Schema (已有)
├── pubmed.py                        ← PubMed Schema (新增)
└── knowledge.py                     ← 知识库统计 Schema (新增)

pubmed/
├── pubmed_retriever.py              ← NCBI Entrez 客户端 (扩展)
└── paper_search.py                  ← PubMed 搜索管线 (重构)

config/                              ← YAML 配置文件 (部分扩展)
prompts/                             ← LLM 提示词模板 (部分扩展)
```

---

## 3. 各模块职责说明

### 3.1 表示层 — API 路由

#### 3.1.1 `api/routers/rag_router.py` (已有，内部增强)

| 属性       | 说明                                                              |
| ---------- | ----------------------------------------------------------------- |
| **职责**   | 接收 RAG 查询请求，转换 Schema → 领域实体，委托应用服务，封装响应  |
| **端点**   | `POST /rag/query`                                                 |
| **依赖**   | `RAGQueryService`（通过 `set_rag_query_service()` 注入）          |
| **变更点** | 无 Schema 变更；内部检索结果混合 local_file + pubmed 两类来源     |

#### 3.1.2 `api/routers/pubmed_router.py` (新增)

| 属性       | 说明                                                                                     |
| ---------- | ---------------------------------------------------------------------------------------- |
| **职责**   | PubMed 文献搜索触发、文献浏览/详情查询、索引触发、文献删除                                |
| **端点**   | `POST /pubmed/search`、`GET /pubmed/articles`、`GET /pubmed/articles/{pmid}`、`POST /pubmed/ingest/{pmid}`、`POST /pubmed/ingest/batch`、`POST /pubmed/ingest/all-uningested`、`DELETE /pubmed/articles/{pmid}` |
| **依赖**   | `PubMedSearchAppService`、`KnowledgeManagementService`（通过 setter 注入）               |
| **输入**   | `schemas/pubmed.py` 中定义的 Pydantic Request 模型                                        |
| **输出**   | 统一 `ApiResponse` 信封 (code + message + data)                                           |

#### 3.1.3 `api/routers/knowledge_router.py` (新增)

| 属性       | 说明                                                                    |
| ---------- | ----------------------------------------------------------------------- |
| **职责**   | 知识库统计概览（跨 PostgreSQL + ChromaDB 聚合数据）                      |
| **端点**   | `GET /knowledge/stats`                                                  |
| **依赖**   | `KnowledgeManagementService`（通过 setter 注入）                        |
| **输入**   | 无请求体，仅路径参数                                                    |
| **输出**   | `schemas/knowledge.py` 中定义的 `KnowledgeStatsResponse`                |

---

### 3.2 应用层 — 应用服务

#### 3.2.1 `application/services/rag_query_service.py` (已有)

| 属性         | 说明                                                                      |
| ------------ | ------------------------------------------------------------------------- |
| **职责**     | 编排 RAG 查询三阶段：关键词提取 → 可选预处理 → LLM 摘要                    |
| **协作接口** | `KeywordExtractionService`、`DocumentRetrievalService`、`RAGSummarizeService` |
| **输入**     | `domain.entities.Query`                                                    |
| **输出**     | `domain.entities.RAGResponse`                                              |

```
process_query(query)
  │
  ├──► KeywordExtractionService.extract_keywords(question)
  │       → 中文分词 + 词性过滤
  │
  └──► RAGSummarizeService.summarize(query_with_keywords)
          │
          ├──► ChromaDB.similarity_search(keywords, k=3)
          │       → 混合返回 local_file + pubmed 结果
          ├──► deduplicate + format_context
          └──► Qwen3-max 生成回答 (温哥华引文)
```

#### 3.2.2 `application/services/pubmed_search_service.py` (新增)

| 属性         | 说明                                                              |
| ------------ | ----------------------------------------------------------------- |
| **职责**     | 编排 PubMed 搜索→去重→入库→自动索引 的完整业务流程                  |
| **协作接口** | `PubMedRetriever`、`PostgresDB`、`PubMedArticleIngester`          |
| **对外方法** | `search_and_store(query, max_results, auto_ingest) → SearchResult` |

```
search_and_store(query, max_results, auto_ingest)
  │
  ├──► PubMedRetriever.search_pubmed(query)
  │       → NCBI Entrez esearch → PMID 列表
  │
  ├──► FOR EACH pmid:
  │     ├──► PostgresDB.is_pmid_exist(pmid) → 已存在则 skip
  │     ├──► PubMedRetriever.fetch_article_details(pmid) → 结构化数据
  │     └──► PostgresDB.insert_article(data) → ingestion_status = 'uningested'
  │
  ├──► IF auto_ingest:
  │     └──► FOR EACH new pmid:
  │           └──► PubMedArticleIngester.ingest_article(pmid)
  │
  └──► RETURN SearchResult(pmids_found, pmids_new, pmids_skipped, details[])
```

**异常处理**：单篇文献失败（网络错误 / 解析异常）不阻塞整批操作，失败信息记录在 `details[].status = "failed"` 中。

#### 3.2.3 `application/services/knowledge_management_service.py` (新增)

| 属性         | 说明                                                                             |
| ------------ | -------------------------------------------------------------------------------- |
| **职责**     | 文献查询与统计的跨数据源聚合（PostgreSQL 文献 CRUD + ChromaDB 向量统计）          |
| **协作接口** | `PostgresDB`、`VectorStoreService`                                               |
| **对外方法** | `list_articles(page, page_size, search, status, sort_by, order) → ArticlePage`   |
|             | `get_article_detail(pmid) → ArticleDetail`                                        |
|             | `delete_article(pmid) → DeleteResult` (同时清理 PG 和 ChromaDB)                   |
|             | `get_knowledge_stats() → KnowledgeStats`                                          |

```
get_knowledge_stats()
  │
  ├──► PostgresDB.count_articles_by_status()
  │       → {total: 47, ingested: 42, uningested: 5}
  │
  ├──► ChromaDB (via VectorStoreService)
  │       → collection.count() → total_vector_chunks
  │       → metadata 按 source_type 分组统计
  │
  └──► RETURN KnowledgeStats {
          local_documents, pubmed_articles_total,
          pubmed_articles_ingested, pubmed_articles_uningested,
          total_vector_chunks, by_source_type, vector_store_info
        }
```

---

### 3.3 领域层 — 实体与抽象接口

#### 3.3.1 领域实体 (dataclass)

| 实体           | 文件                                    | 字段                                                         | 说明                   |
| -------------- | --------------------------------------- | ------------------------------------------------------------ | ---------------------- |
| `Document`     | `domain/entities/document.py`           | `content: str`, `metadata: Dict[str, Any]`                   | 文档块，含 source 属性 |
| `Query`        | `domain/entities/query.py`              | `question: str`, `top_k: int`, `keywords: Optional[str]`     | 查询实体               |
| `RAGResponse`  | `domain/entities/rag_response.py`       | `question: str`, `answer: str`, `sources: List[str]`, `keywords: str` | 查询响应               |

**本次不新增领域实体**，现有实体足以承载混合检索场景（PubMed 文献的元数据通过 `Document.metadata` 的 `source_type` 字段区分来源）。

#### 3.3.2 领域服务接口 (ABC)

| 接口                           | 抽象方法                                                                        | 实现类                          |
| ------------------------------ | ------------------------------------------------------------------------------- | ------------------------------- |
| `KeywordExtractionService`     | `extract_keywords(text: str) → str`                                             | `RuleBasedKeywordExtractor`     |
| `DocumentRetrievalService`     | `retrieve_documents(query, top_k) → List[Document]`                             | `VectorDocumentRetriever`       |
|                                | `deduplicate_documents(documents) → List[Document]`                             |                                 |
|                                | `format_documents_for_context(documents) → str`                                 |                                 |
| `RAGSummarizeService`          | `summarize(query: Query) → RAGResponse`                                         | `LangChainRAGSummarizer`        |
|                                | `get_relevant_documents(query: Query) → List[Document]`                         |                                 |

**设计决策**：本次不新增领域抽象（ABC）。理由：
- `PubMedArticleIngester` 当前只有 PubMed 一个数据源，硬编码领域抽象得不偿失
- `PostgresDB` 是数据库工具类，不适合抽象为领域接口
- 未来接入新文献库时，若出现 ≥2 个实现，再提取 ABC 接口（YAGNI 原则）

---

### 3.4 基础设施层 — 实现与工具

#### 3.4.1 `infrastructure/persistence/vector_store.py` (已有，扩展)

| 属性         | 说明                                                                     |
| ------------ | ------------------------------------------------------------------------ |
| **职责**     | ChromaDB Collection 生命周期管理；本地文档批量导入；提供检索器             |
| **扩展点**   | 新增 `add_documents_direct(documents)` 方法，跳过 MD5 去重，供 PubMed 摄入管线直接写入 |
|             | 新增 `delete_by_metadata_filter(metadata_filter)` 方法，按 metadata 条件删除向量 |

```
已有方法:
  get_retriever() → ChromaDB Retriever
  load_document() → 扫描 ./data/ → MD5查重 → 加载 → 分块 → 写入

新增方法:
  add_documents_direct(documents: List[Document]) → None
  delete_by_metadata_filter(filter: Dict) → int (删除数量)
  get_collection_stats() → Dict (collection 统计信息)
```

#### 3.4.2 `infrastructure/persistence/document_retriever_impl.py` (已有，扩展)

| 属性         | 说明                                                                         |
| ------------ | ---------------------------------------------------------------------------- |
| **职责**     | 实现 `DocumentRetrievalService` 接口；检索结果 LangChain → 领域实体转换       |
| **扩展点**   | `format_documents_for_context()` 按 `source_type` 生成差异化引文格式           |

```
扩展前 format_documents_for_context():
  [N] 《文件名》
  → 所有来源统一格式

扩展后 format_documents_for_context():
  source_type == "local_file":
    [N] 《文件名（无后缀）》.
  source_type == "pubmed":
    [N] Authors. Title. Journal. Year. PMID: xxxxx.
  → 根据 metadata.source_type 自动选择引文模板
```

#### 3.4.3 `infrastructure/persistence/postgres_db.py` (重构)

| 属性         | 说明                                                                                  |
| ------------ | ------------------------------------------------------------------------------------- |
| **变更**     | 从 `infrastructure/utils/` 迁入 `infrastructure/persistence/`，语义更清晰              |
| **重构内容** | 修复 import 路径（原 `from utils.xxx` 改为 `from infrastructure.utils.xxx`）         |
|              | 新增上下文管理器支持 (`with PostgresDB() as db:`)，确保连接正确释放                    |
|              | 使用 `psycopg2.extras.RealDictCursor` 统一返回字典格式                                 |
| **新增方法** | `get_article_by_pmid(pmid) → Optional[Dict]` — 单篇详情                                |
|              | `list_articles(page, page_size, search, status, sort, order) → (List[Dict], total)` — 分页查询 |
|              | `update_ingestion_status(pmid, status, error=None, chunk_count=None, vector_ids=None)` — 状态更新 |
|              | `count_articles_by_status() → Dict[str, int]` — 按状态计数                             |
|              | `delete_article(pmid) → bool` — 删除记录                                               |
|              | `count_all() → int` — 文献总数                                                         |

**保留方法**: `is_pmid_exist(pmid)`、`insert_article(article_data)`

#### 3.4.4 `infrastructure/persistence/pubmed_ingester.py` (新增)

| 属性           | 说明                                                                        |
| -------------- | --------------------------------------------------------------------------- |
| **职责**       | 将 PostgreSQL 中 JSONB 格式的 PubMed 文章转换为向量化文本块并写入 ChromaDB    |
| **核心方法**   | `ingest_article(pmid, force=False) → IngestResult`                          |
|                | `batch_ingest(pmids: List[str], force=False) → List[IngestResult]`          |
|                | `ingest_all_uningested() → List[IngestResult]`                              |
|                | `remove_from_vector_store(pmid) → bool`                                     |

```
ingest_article(pmid)
  │
  ├──► PostgresDB.get_article_by_pmid(pmid) → article dict
  │
  ├──► 检查 ingestion_status:
  │      'ingested' ∧ ¬force → no-op, 返回 {"status": "already_ingested"}
  │      否则 → 更新 status 为 'ingesting'
  │
  ├──► _build_article_text(article) → 结构化文本
  │     模板: [PubMed Article]
  │           Title: {title}
  │           Authors: {authors}
  │           Journal: {journal}
  │           ...
  │           Abstract: {abstract}
  │
  ├──► RecursiveCharacterTextSplitter.split_text(text) → chunks (1~3 块/篇)
  │
  ├──► 构建每个 chunk 的 metadata:
  │     {source, source_type: "pubmed", pmid, title, authors, journal,
  │      publish_date, doi, is_free_download, chunk_index, total_chunks}
  │
  ├──► VectorStoreService.add_documents_direct(chunks_with_metadata)
  │
  ├──► PostgresDB.update_ingestion_status(pmid, "ingested", chunk_count=..., vector_ids=...)
  │
  └──► RETURN IngestResult(pmid, status="ingested", chunk_count=N)
```

**失败处理**：任何步骤失败 → `update_ingestion_status(pmid, "failed", error=msg)`，不抛异常到调用方。

#### 3.4.5 `infrastructure/models/factory.py` (已有，不变)

| 属性       | 说明                                                       |
| ---------- | ---------------------------------------------------------- |
| **职责**   | 工厂方法模式创建 LLM (`ChatTongyi`) 和 Embedding (`DashScopeEmbeddings`) 单例 |
| **输出**   | `embed_model`、`chat_model` 模块级全局变量                   |

#### 3.4.6 `infrastructure/services/service_factory.py` (扩展)

| 属性         | 说明                                                                               |
| ------------ | ---------------------------------------------------------------------------------- |
| **扩展内容** | 新增懒加载 getter：`get_postgres_db()`、`get_pubmed_ingester()`、`get_pubmed_search_service()`、`get_knowledge_management_service()` |
|              | 新增 `get_pubmed_retriever()` 用于获取 NCBI Entrez 客户端实例                        |

#### 3.4.7 `pubmed/pubmed_retriever.py` (扩展)

| 属性         | 说明                                                                     |
| ------------ | ------------------------------------------------------------------------ |
| **扩展内容** | `fetch_article_details()` 新增提取: `doi`、`publish_date`、`pmc_id`、`publication_type` |
|              | 新增返回字段纳入 `article_info` JSONB 中                                  |

#### 3.4.8 `pubmed/paper_search.py` (重构)

| 属性         | 说明                                                                               |
| ------------ | ---------------------------------------------------------------------------------- |
| **重构内容** | 将 `main(pubmed_query)` 函数重构为 `PubMedSearchPipeline` 类，支持参数化调用        |
|              | 修复 import 路径：`from utils.xxx` → `from infrastructure.utils.xxx`              |
|              | 保留命令行直接运行能力 (`if __name__ == "__main__"`)                               |

---

### 3.5 Schema 层

#### 3.5.1 `schemas/rag_query.py` (已有，不变)

| 模型            | 字段                                                                 |
| --------------- | -------------------------------------------------------------------- |
| `QueryRequest`  | `question: str`, `top_k: Optional[int] = 3`                          |
| `RAGResponse`   | `question: str`, `answer: str`, `sources: List[str]`, `keywords: str` |
| `ApiResponse`   | `code: int`, `message: str`, `data: Optional[RAGResponse]`            |

#### 3.5.2 `schemas/pubmed.py` (新增)

| 模型                       | 用途             | 关键字段                                                                                               |
| -------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------ |
| `PubMedSearchRequest`      | 搜索请求         | `query: str`, `max_results: int = 5`, `auto_ingest: bool = True`                                      |
| `PubMedSearchResponse`     | 搜索响应 data    | `query`, `pmids_found`, `pmids_new`, `pmids_ingested`, `pmids_skipped`, `pmids_failed`, `details[]`   |
| `ArticleDetailResponse`    | 文献详情 data    | `pmid`, `article_info`, `study_groups`, `results_info`, `objectives`, `is_free_download`, `ingestion_status`, `chunk_count`, `ingested_at`, `created_at`, `updated_at` |
| `ArticleListResponse`      | 文献列表 data    | `total`, `page`, `page_size`, `articles[]`                                                            |
| `IngestResultResponse`     | 索引结果 data    | `total_uningested`, `ingested`, `failed`, `details[]`                                                 |
| `DeleteResultResponse`     | 删除结果 data    | `pmid`, `deleted_pg`, `deleted_vector`                                                                |
| `ApiResponse[T]`           | 统一响应信封     | `code: int`, `message: str`, `data: Optional[T]`                                                      |

#### 3.5.3 `schemas/knowledge.py` (新增)

| 模型                       | 用途             | 关键字段                                                                                               |
| -------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------ |
| `KnowledgeStatsResponse`   | 统计响应 data    | `local_documents`, `pubmed_articles_total`, `pubmed_articles_ingested`, `pubmed_articles_uningested`, `total_vector_chunks`, `by_source_type: Dict[str, int]`, `vector_store: Dict[str, str]` |

---

## 4. 模块间依赖与数据流

### 4.1 依赖关系图

```
                        main.py (启动组装)
                       /      |       \
                      /       |        \
              rag_router  pubmed_router  knowledge_router
                  |           |               |
                  |    PubMedSearchAppService |
                  |           |               |
              RAGQueryService |    KnowledgeManagementService
                  |           |               |
          ┌───────┴───────┐   |       ┌───────┴───────┐
          │               │   |       │               │
   KeywordExtractor  RAGSummarizer   │         PostgresDB
          │               │          │               │
          │        DocumentRetriever │        VectorStoreService
          │               │          │               │
          └───────────────┴──────────┴───────────────┘
                                  │
                     PubMedRetriever  PubMedArticleIngester
                          │                  │
                     NCBI Entrez      PostgresDB + VectorStoreService
```

**依赖约束**：
- 表示层 (Router) 只依赖应用层服务，不直接访问基础设施
- 应用层服务通过 ABC 接口依赖领域服务，通过具体类引用基础设施组件
- 领域层无外部依赖（纯 Python dataclass + ABC）
- 基础设施层实现领域接口，可引用其他基础设施组件

### 4.2 核心数据流

#### 4.2.1 搜索入库流 (PubMed Search → Store → Index)

```
POST /pubmed/search {"query": "...", "max_results": 5, "auto_ingest": true}
        │
        ▼
PubMedSearchAppService.search_and_store()
        │
  ┌─────┴──────────────────────────────────────────┐
  │ 1. PubMedRetriever.search_pubmed(query)        │
  │    → NCBI Entrez.esearch → [pmid1, pmid2, ...] │
  └─────┬──────────────────────────────────────────┘
        │
  ┌─────┴──────────────────────────────────────────────────────┐
  │ 2. FOR EACH pmid:                                          │
  │    ├─ PostgresDB.is_pmid_exist(pmid) → skip if exists      │
  │    ├─ PubMedRetriever.fetch_article_details(pmid)           │
  │    │   → {"pmid", "article_info": {title, authors, ...}}   │
  │    └─ PostgresDB.insert_article(data)                       │
  │        → INSERT INTO pubmed_articles                        │
  │        → ingestion_status = 'uningested'                    │
  └─────┬──────────────────────────────────────────────────────┘
        │
  ┌─────┴──────────────────────────────────────────────────────┐
  │ 3. IF auto_ingest:                                         │
  │    FOR EACH new_pmid:                                      │
  │      PubMedArticleIngester.ingest_article(pmid)             │
  │      ├─ PostgresDB.get_article_by_pmid(pmid)                │
  │      ├─ _build_article_text() → 结构化文本                  │
  │      ├─ RecursiveCharacterTextSplitter → chunks             │
  │      ├─ VectorStoreService.add_documents_direct()           │
  │      │   → ChromaDB collection "agent"                      │
  │      └─ PostgresDB.update_ingestion_status("ingested")     │
  └─────┬──────────────────────────────────────────────────────┘
        │
        ▼
RETURN PubMedSearchResponse {
  pmids_found: 5, pmids_new: 3, pmids_ingested: 3,
  pmids_skipped: 2, pmids_failed: 0, details: [...]
}
```

#### 4.2.2 RAG 混合查询流 (Hybrid Retrieval + Generation)

```
POST /rag/query {"question": "mRNA疫苗的有效性数据是什么？"}
        │
        ▼
RAGQueryService.process_query(Query)
        │
  ┌─────┴─────────────────────────────────────────────────────┐
  │ 1. KeywordExtractionService.extract_keywords(question)     │
  │    → Jieba POS tagging                                     │
  │    → "mRNA，疫苗，有效性，数据"                               │
  └─────┬─────────────────────────────────────────────────────┘
        │
  ┌─────┴─────────────────────────────────────────────────────┐
  │ 2. RAGSummarizeService.summarize(query_with_keywords)      │
  │    │                                                       │
  │    ├─ DocumentRetriever.retrieve_documents(keywords, k=3)  │
  │    │   → ChromaDB.similarity_search()                      │
  │    │   → 混合结果:                                          │
  │    │     [1] source_type=local_file, source="《疫苗...》"   │
  │    │     [2] source_type=pubmed,   source="PMID:12345678"   │
  │    │     [3] source_type=pubmed,   source="PMID:87654321"   │
  │    │                                                       │
  │    ├─ DocumentRetriever.deduplicate_documents()             │
  │    │   → 按 source 合并同文献多 chunk                       │
  │    │                                                       │
  │    ├─ DocumentRetriever.format_documents_for_context()      │
  │    │   → source_type == "local_file":                       │
  │    │     "[1] 《疫苗临床试验技术指导原则》."                  │
  │    │   → source_type == "pubmed":                           │
  │    │     "[2] Baden LR, et al. Efficacy... N Engl J Med.    │
  │    │      2020. PMID: 12345678"                             │
  │    │                                                       │
  │    └─ LLM chain.invoke({input, context})                    │
  │        → Qwen3-max 生成回答 (温哥华引文格式)                  │
  └─────┬─────────────────────────────────────────────────────┘
        │
        ▼
RETURN RAGResponse {
  answer: "...根据mRNA疫苗III期临床试验...¹。同时，《疫苗临床...》要求...²",
  sources: ["《疫苗临床试验技术指导原则》", "PMID:12345678: Efficacy...", ...],
  keywords: "mRNA，疫苗，有效性，数据"
}
```

#### 4.2.3 自动增量索引流 (Auto Incremental Index)

```
PostgresDB.insert_article(data) 成功
        │
        ▼
ingestion_status = 'uningested'
        │
  ┌─────┴──────────────────────────────────────────────────┐
  │ PubMedSearchAppService 检测到 auto_ingest=true          │
  │   → PubMedArticleIngester.ingest_article(pmid)         │
  │                                                        │
  │   ├─ CHECK ingestion_status:                           │
  │   │   'uningested'/'failed' → 继续                      │
  │   │   'ingested' ∧ ¬force → 跳过 (幂等)                 │
  │   │                                                    │
  │   ├─ UPDATE status → 'ingesting'                       │
  │   │                                                    │
  │   ├─ 构建文本 → 分块 → ChromaDB.add_documents()         │
  │   │                                                    │
  │   ├─ SUCCESS:                                          │
  │   │   UPDATE status → 'ingested'                       │
  │   │   SET chunk_count, vector_ids, ingested_at         │
  │   │                                                    │
  │   └─ FAILURE:                                          │
  │       UPDATE status → 'failed'                         │
  │       SET ingestion_error = error_message              │
  │       ROLLBACK (不阻塞其他文献)                          │
  └────────────────────────────────────────────────────────┘
```

#### 4.2.4 文献删除流 (Cascade Delete)

```
DELETE /pubmed/articles/{pmid}
        │
        ▼
KnowledgeManagementService.delete_article(pmid)
        │
  ┌─────┴─────────────────────────────────────────────────┐
  │ 1. PubMedArticleIngester.remove_from_vector_store(pmid)│
  │    → VectorStoreService.delete_by_metadata_filter()    │
  │    → ChromaDB: 删除所有 metadata.pmid == pmid 的 chunks │
  └─────┬─────────────────────────────────────────────────┘
        │
  ┌─────┴─────────────────────────────────────────────────┐
  │ 2. PostgresDB.delete_article(pmid)                     │
  │    → DELETE FROM pubmed_articles WHERE pmid = %s       │
  └─────┬─────────────────────────────────────────────────┘
        │
        ▼
RETURN DeleteResultResponse {pmid, deleted_pg: true, deleted_vector: true}
```

**容错策略**：若 ChromaDB 删除成功但 PG 删除失败（或反之），记录错误日志但不回滚已成功的操作。前端提示用户检查实际状态。

---

## 5. 全局公共设计

### 5.1 配置管理

**现状**：6 个 YAML 文件，`config_handler.py` 在 import 时加载为模块级全局字典。

**扩展**：

```yaml
# config/pubmed.yml 新增项
auto_ingest: true               # 搜索后是否自动索引
request_interval: 0.15          # NCBI API 请求间隔 (秒)，避免触发频率限制 (10 req/s)
ingestion_chunk_size: 800       # PubMed 文章分块大小
ingestion_chunk_overlap: 200    # PubMed 文章分块重叠

# config/chroma.yml 新增项
pubmed_chunk_size: 800
pubmed_chunk_overlap: 200
pubmed_separator: ["\n\n", "\n", ". ", "! ", "? ", "。", "！", "？", " ", ""]
```

**约束**：保持现有 YAML → 模块全局变量的加载方式不变，避免引入新的配置框架。

### 5.2 日志规范

使用现有 `infrastructure/utils/logger_handler.py` 的 `get_logger()` 统一获取 Logger 实例。

**级别使用约定**：

| 级别    | 场景                                              |
| ------- | ------------------------------------------------- |
| DEBUG   | 开发调试信息（chunk 数量、检索耗时）              |
| INFO    | 业务流程节点（搜索完成、入库成功、索引完成）       |
| WARNING | 非致命异常（PMID 已存在跳过、空摘要跳过、API 重试） |
| ERROR   | 需关注的失败（入库失败、索引失败、LLM 调用异常）   |

**格式统一**：`%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s`

**命名规范**：各模块使用 `get_logger(name="模块名")` 创建具名 Logger（如 `pubmed_search`、`pubmed_ingester`）。

### 5.3 异常处理顶层方案

```
┌──────────────────────────────────────────────────────────┐
│                      异常处理层级                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  API 层 (Router)                                         │
│  ├── 捕获所有异常 → HTTPException(500, detail=str(e))     │
│  └── 不在此层做业务判断                                    │
│                                                          │
│  应用层 (Application Service)                             │
│  ├── 定义业务异常边界（如 ArticleNotFoundError）          │
│  ├── 批量操作: try/except 单条 → 收集失败结果，不中断批次  │
│  └── 关键操作: 记录完整上下文后抛出                         │
│                                                          │
│  基础设施层 (Infrastructure)                              │
│  ├── 外部 API 调用: 默认重试 + 指数退避                    │
│  ├── DB 操作: rollback + 记录 SQL 上下文                   │
│  └── 向量操作: 标记失败状态, 不抛异常到调用链               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**关键容错策略**：

| 场景                 | 策略                                                                      |
| -------------------- | ------------------------------------------------------------------------- |
| 批量索引中单篇失败   | 捕获异常 → 标记 `ingestion_status='failed'` → 记录 `ingestion_error` → 继续下一篇 |
| PubMed API 不可用    | 重试 3 次 (指数退避 3s/6s/12s) → 仍失败则抛出，由上层返回友好错误信息     |
| ChromaDB 写入失败    | 标记 `ingestion_status='failed'` → 文章仍在 PG 可查 → 支持手动重试        |
| DashScope API 不可用 | 中断当前批次 → 已入库文章保留为 `uningested` → API 恢复后批量索引          |
| PostgreSQL 连接断开  | 每次操作前检查连接状态 → 自动重连 → 失败则抛出                              |

### 5.4 跨模块公共组件

| 组件                | 位置                                      | 用途                                   | 共享范围             |
| ------------------- | ----------------------------------------- | -------------------------------------- | -------------------- |
| `config_handler`    | `infrastructure/utils/config_handler.py`  | 所有 YAML 配置入口                      | 全局                 |
| `logger_handler`    | `infrastructure/utils/logger_handler.py`  | 统一日志输出                            | 全局                 |
| `path_tool`         | `infrastructure/utils/path_tool.py`       | 项目根目录定位 + 绝对路径转换            | 全局                 |
| `prompt_loader`     | `infrastructure/utils/prompt_loader.py`   | Prompt 模板文件加载                     | `rag_summarizer_impl` |
| `file_handler`      | `infrastructure/utils/file_handler.py`    | 文档加载器 (PDF/DOC/DOCX/TXT)           | `vector_store`        |
| `ServiceFactory`    | `infrastructure/services/service_factory.py` | DI 容器, 统一管理服务实例生命周期      | `main.py` + Router   |
| `embed_model`       | `infrastructure/models/factory.py`        | DashScope Embeddings 单例               | ChromaDB 写入方      |
| `chat_model`        | `infrastructure/models/factory.py`        | ChatTongyi LLM 单例                     | RAG Summarizer       |

### 5.5 向量化文本模板

PubMed 文章 JSONB → 结构化文本的标准模板（`PubMedArticleIngester._build_article_text()`）：

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

**设计理由**：
- **字段标签** (`Title:`、`Abstract:`) 为嵌入模型提供语义锚点
- **PMID 在文本中**：支持通过 PMID 直接向量检索
- **前置高区分度信息** (标题/作者/期刊) 在 chunk 开头，分块时优先保留
- **分层结构**：Objectives → Study Groups → Results → Abstract 对应临床方法学逻辑层次

### 5.6 ChromaDB 元数据 Schema 统一

统一 Collection `"agent"` 内所有 chunk 的 metadata schema：

| 字段              | local_file 值                        | pubmed 值                                        |
| ----------------- | ------------------------------------ | ------------------------------------------------ |
| `source`          | `《文件名（无后缀）》`               | `PMID:12345678: Title of Article`                |
| `source_type`     | `"local_file"`                       | `"pubmed"`                                       |
| `pmid`            | (不存在)                             | `"12345678"`                                     |
| `title`           | (不存在)                             | `"Title of Article"`                             |
| `authors`         | (不存在)                             | `"Baden LR, El Sahly HM, ..."`                   |
| `journal`         | (不存在)                             | `"N Engl J Med"`                                 |
| `publish_date`    | (不存在)                             | `"2020-12-31"`                                    |
| `doi`             | (不存在)                             | `"10.1056/NEJMoa2035389"`                        |
| `is_free_download`| (不存在)                             | `true` / `false`                                 |
| `chunk_index`     | `0`                                  | `0`                                              |
| `total_chunks`    | `N`                                  | `M`                                              |
| `file_type`       | `"pdf"`/`"doc"`/`"docx"`            | (不存在)                                         |

> **约定**：`source_type` 不存在默认视同 `"local_file"`，确保向后兼容。

---

## 6. 架构约束与风险点

### 6.1 架构约束

| #   | 约束                                        | 说明                                                                                           |
| --- | ------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 1   | **单 Collection 共存**                      | PubMed 文献与本地文档存入同一个 ChromaDB Collection (`"agent"`)，通过 `metadata.source_type` 区分。不可拆分为多个 Collection，避免引入检索结果合并层 |
| 2   | **PMID 级别去重**                           | PostgreSQL 层以 PMID 为唯一去重键；ChromaDB 层通过 `ingestion_status` 避免重复索引               |
| 3   | **不修改现有领域接口 (ABC)**                | `KeywordExtractionService`、`DocumentRetrievalService`、`RAGSummarizeService` 签名不变          |
| 4   | **POST /rag/query 向后兼容**                | 请求/响应 Schema 不变，仅内部数据源扩展。现有调用方无需修改代码                                  |
| 5   | **配置外部化**                              | 所有可变参数放在 `config/*.yml`，不在代码中硬编码                                               |
| 6   | **同步阻塞模型**                            | 当前系统非异步（FastAPI 路由为 `async def` 但内部操作同步）。本次不引入 asyncio 改造，后续可考虑  |
| 7   | **依赖注入方式**                            | 保持现有 ServiceFactory + setter 注入模式，不引入 FastAPI Depends() 或第三方 DI 框架            |

### 6.2 风险矩阵

| #   | 风险                                     | 严重度 | 可能性 | 缓解措施                                                                                |
| --- | ---------------------------------------- | ------ | ------ | --------------------------------------------------------------------------------------- |
| 1   | PubMed API 频率限制 (≤10 req/s)          | **高** | 中     | 请求间隔 0.15s；指数退避重试 (3s/6s/12s)；批次操作进度日志                              |
| 2   | DashScope Embedding API 调用成本         | **中** | 高     | 限制单批次 ≤30 篇；实现 `dry_run` 预估模式；评估本地嵌入模型作为降级                    |
| 3   | 中英文跨语言检索质量下降                 | **中** | 中     | 中文查询词 + 原始英文关键词混合检索；后续可引入关键词翻译模块                            |
| 4   | PostgreSQL 连接在 FastAPI 环境下的安全性  | **中** | 中     | 上下文管理器确保连接释放；使用 `psycopg2` 连接池；后续考虑 `asyncpg`                     |
| 5   | ChromaDB 单 Collection 规模退化          | **低** | 低     | 当前千级 chunks 远低于 ChromaDB 瓶颈 (~100K)；通过 `/knowledge/stats` 监控增长           |
| 6   | PubMed XML 解析异常（非标准字段）         | **低** | 低     | `raw_response` 列存储原始响应用于调试；单篇解析失败不阻塞整批                            |
| 7   | 文章内容更新导致向量过期                 | **低** | 低     | `force=true` 支持强制重索引；后续可增加基于 `updated_at` 的定时刷新                      |
| 8   | `pubmed_retriever.py` import 路径硬编码   | **中** | 中     | Phase 1 统一修复所有跨模块 import 路径，添加 `sys.path` 安全加固                          |

### 6.3 降级与回退方案

| 场景                 | 降级策略                                                                     | 用户感知                             |
| -------------------- | ---------------------------------------------------------------------------- | ------------------------------------ |
| PubMed API 不可用    | 使用本地已索引文献回答；提示"PubMed 搜索暂时不可用，当前仅基于本地知识库回答" | 功能降级，RAG 查询仍可用              |
| ChromaDB 写入失败    | 标记 `ingestion_status='failed'`；文章仍在 PG 可查；提供手动重试端点          | 搜索成功但索引延迟，用户可手动触发    |
| DashScope API 不可用 | 中断当前批次索引；已入库文章保留 `uningested`；API 恢复后 `/pubmed/ingest/all-uningested` 一键补索引 | 搜索成功但新文献暂时不可检索          |
| PostgreSQL 不可用    | 返回 503 错误；PubMed 搜索和文献管理端点不可用；RAG 查询（仅本地 ChromaDB）仍可用 | 部分功能不可用，RAG 查询降级为仅本地  |

### 6.4 扩展预留

| 扩展点               | 预留方式                                                           | 触发条件                         |
| -------------------- | ------------------------------------------------------------------ | -------------------------------- |
| 新增文献数据源       | `PubMedArticleIngester` 无领域抽象，新源接入时评估是否提取 ABC      | 接入临床试验注册网等第 2 个源    |
| 关键词翻译           | 在 `KeywordExtractionService` 接口外新增 `TranslationService` ABC  | 中英文检索质量不满足要求时       |
| 异步化               | 当前同步模型不阻塞后续迁移；ServiceFactory 隐藏了实现细节          | 并发量提升到需要异步 DB/HTTP 时  |
| 新 LLM 模型          | 通过 `infrastructure/models/factory.py` 添加新工厂类              | 切换或对比不同 LLM 时            |
| 新 Embedding 模型    | 同上，添加新 `EmbeddingsFactory`                                   | 更换向量化后端时                 |

---

## 附录: 关键设计决策速查

| #   | 决策点             | 选择                        | 理由                                                                 |
| --- | ------------------ | --------------------------- | -------------------------------------------------------------------- |
| 1   | 检索策略           | 单 Collection 混合存储      | 避免检索结果合并层，ChromaDB 原生支持单查询返回多类型结果            |
| 2   | 领域抽象           | 摄入管线不走 ABC            | 当前仅 1 个数据源，避免过度抽象 (YAGNI)                               |
| 3   | PostgresDB 位置    | `infrastructure/persistence/` | 与 ChromaDB 并列，语义上都是持久化层                                |
| 4   | 索引时机           | 搜索后自动触发 (可关闭)     | `auto_ingest` 默认为 true，用户可通过 API 参数或配置关闭               |
| 5   | 引文格式           | 按 source_type 自动区分     | local_file 用书名号格式，pubmed 用温哥华期刊格式                      |
| 6   | 知识库管理粒度     | 单个 KnowledgeManagementService | 文献 CRUD + 统计逻辑紧密相关，拆分会增加跨服务调用                 |
| 7   | 依赖注入           | ServiceFactory + setter     | 保持现有模式，不引入新框架                                           |
