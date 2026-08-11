# 详细设计文档

> **项目**: Medicine_RAG_Project — 生物药物资料检索知识库  
> **日期**: 2026-08-11  
> **版本**: v1.0  
> **作者**: Junhao Li  
> **依赖文档**: [proposal.md](./proposal.md) | [high-level-design.md](./high-level-design.md)

---

## 目录

1. [设计总则](#1-设计总则)
2. [分模块详细实现](#2-分模块详细实现)
   - 2.1 [schemas/common.py — 通用响应信封](#21-schemascommonpy--通用响应信封)
   - 2.2 [schemas/pubmed.py — PubMed 接口 Schema](#22-schemaspubmedpy--pubmed-接口-schema)
   - 2.3 [schemas/knowledge.py — 知识库统计 Schema](#23-schemasknowledgepy--知识库统计-schema)
   - 2.4 [api/routers/pubmed_router.py — PubMed 路由](#24-apirouterspubmed_routerpy--pubmed-路由)
   - 2.5 [api/routers/knowledge_router.py — 知识库路由](#25-apiroutersknowledge_routerpy--知识库路由)
   - 2.6 [application/services/pubmed_search_service.py — PubMed 搜索服务](#26-applicationservicespubmed_search_servicepy--pubmed-搜索服务)
   - 2.7 [application/services/knowledge_management_service.py — 知识库管理服务](#27-applicationservicesknowledge_management_servicepy--知识库管理服务)
   - 2.8 [infrastructure/persistence/postgres_db.py — PostgreSQL 持久化](#28-infrastructurepersistencepostgres_dbpy--postgresql-持久化)
   - 2.9 [infrastructure/persistence/pubmed_ingester.py — PubMed 文章向量化](#29-infrastructurepersistencepubmed_ingesterpy--pubmed-文章向量化)
   - 2.10 [infrastructure/persistence/vector_store.py — 向量存储扩展](#210-infrastructurepersistencevector_storepy--向量存储扩展)
   - 2.11 [infrastructure/persistence/document_retriever_impl.py — 检索器扩展](#211-infrastructurepersistencedocument_retriever_implpy--检索器扩展)
   - 2.12 [infrastructure/services/service_factory.py — DI 容器扩展](#212-infrastructureservicesservice_factorypy--di-容器扩展)
   - 2.13 [pubmed/pubmed_retriever.py — PubMed 检索器扩展](#213-pubmedpubmed_retrieverpy--pubmed-检索器扩展)
   - 2.14 [pubmed/paper_search.py — 独立搜索管线](#214-pubmedpaper_searchpy--独立搜索管线)
   - 2.15 [main.py — 启动入口](#215-mainpy--启动入口)
   - 2.16 [prompts/rag_summarize_prompt.txt — Prompt 增强](#216-promptsrag_summarize_prompttxt--prompt-增强)
3. [全局枚举与错误码定义](#3-全局枚举与错误码定义)
4. [单元测试设计要点](#4-单元测试设计要点)
5. [性能优化细节](#5-性能优化细节)

---

## 1. 设计总则

### 1.1 编码约定

| 维度           | 约定                                                               |
| -------------- | ------------------------------------------------------------------ |
| Python 版本    | ≥ 3.10                                                            |
| 类型注解       | 所有公开方法必须标注参数类型和返回值类型                             |
| 文档字符串     | Google-style docstring (Args / Returns / Raises)                   |
| 导入顺序       | 标准库 → 第三方 → 项目内部（每组间空行分隔）                        |
| 命名           | 类: PascalCase / 函数方法: snake_case / 常量: UPPER_SNAKE_CASE     |
| 日志           | 使用 `get_logger(name="模块名")` 获取 logger，禁止 `print()`       |
| 字符串         | 用户可见文本使用中文；日志/错误消息使用英文                         |

### 1.2 依赖注入约定

遵循概要设计约束 7：**保持 ServiceFactory + setter 注入模式**。

- `ServiceFactory` 懒加载所有服务实例，保证每个服务全局只有一个实例
- Router 通过模块级 `set_xxx_service()` 函数接收服务实例
- `main.py` 在启动时从 ServiceFactory 获取服务并注入到各 Router

### 1.3 响应信封约定

每个模块定义自己的具名响应 data 类。API 响应的外层信封复用 `schemas/common.py` 中的 `ApiResponse`：

```python
# 所有端点统一返回格式
{
  "code": 200,          # HTTP 状态码
  "message": "success", # 提示信息
  "data": { ... }       # 业务数据，类型因端点而异
}
```

### 1.4 后端实现顺序

按依赖关系自底向上实现：

```
Phase 1: Schema     → schemas/common.py, pubmed.py, knowledge.py
Phase 2: 基础设施    → postgres_db.py, pubmed_ingester.py, vector_store.py, pubmed_retriever.py
Phase 3: 应用服务    → pubmed_search_service.py, knowledge_management_service.py
Phase 4: API 路由    → pubmed_router.py, knowledge_router.py
Phase 5: 组装       → service_factory.py, main.py
Phase 6: Prompt     → rag_summarize_prompt.txt
```

---

## 2. 分模块详细实现

### 2.1 schemas/common.py — 通用响应信封

**文件**: `schemas/common.py` (新增)  
**依赖**: 无

#### 2.1.1 数据结构

```python
from pydantic import BaseModel
from typing import Optional, Any

class ApiResponse(BaseModel):
    """统一 API 响应信封。

    所有端点均通过此结构返回，data 字段类型由各端点自行定义。
    """
    code: int           # HTTP 状态码
    message: str        # 人类可读的状态描述
    data: Optional[Any] = None  # 业务载荷，可为任意 Pydantic 模型或 None
```

#### 2.1.2 接口说明

| 字段      | 类型           | 说明                                        |
| --------- | -------------- | ------------------------------------------- |
| `code`    | `int`          | HTTP 状态码（200 / 400 / 404 / 500 / 503）  |
| `message` | `str`          | 成功时 `"success"`，失败时为具体错误描述     |
| `data`    | `Optional[Any]`| 成功时有值；失败/无数据时为 `None`           |

#### 2.1.3 使用示例

```python
# 在 router 中使用
from schemas.common import ApiResponse

return ApiResponse(code=200, message="success", data=result)
return ApiResponse(code=404, message=f"PMID {pmid} not found", data=None)
```

> **说明**: 原 `schemas/rag_query.py` 中的 `ApiResponse` 保留不动，新增代码统一使用 `schemas/common.py` 的版本，避免修改已有路由。

---

### 2.2 schemas/pubmed.py — PubMed 接口 Schema

**文件**: `schemas/pubmed.py` (新增)  
**依赖**: `pydantic`

#### 2.2.1 数据结构总览

| 模型                          | 用途                   |
| ----------------------------- | ---------------------- |
| `PubMedSearchRequest`         | POST /pubmed/search 请求体 |
| `SearchDetailItem`            | 单篇文献搜索结果明细     |
| `PubMedSearchData`            | POST /pubmed/search 响应 data |
| `ArticleSummary`              | 文献列表中的摘要项       |
| `ArticleListData`             | GET /pubmed/articles 响应 data |
| `ArticleDetailData`           | GET /pubmed/articles/{pmid} 响应 data |
| `IngestResultItem`            | 单篇索引结果明细         |
| `IngestBatchData`             | 批量索引响应 data        |
| `DeleteResultData`            | DELETE 响应 data         |

#### 2.2.2 详细定义

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class PubMedSearchRequest(BaseModel):
    """PubMed 搜索请求"""
    query: str = Field(..., min_length=1, max_length=500,
                       description="PubMed 查询词，支持 PubMed 高级检索语法")
    max_results: int = Field(default=5, ge=1, le=30,
                             description="最大返回文献数")
    auto_ingest: bool = Field(default=True,
                              description="是否在入库后自动触发向量索引")

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query 不能为空或仅包含空白字符")
        return stripped


class SearchDetailItem(BaseModel):
    """单篇文献的搜索/入库结果明细"""
    pmid: str
    status: str              # "ingested" | "skipped" | "failed"
    title: str = ""
    reason: str = ""         # 当 status="skipped" 时为 "already_exists"
                             # 当 status="failed" 时为具体错误信息


class PubMedSearchData(BaseModel):
    """搜索入库操作的聚合结果"""
    query: str
    pmids_found: int          # Entrez 返回的 PMID 总数
    pmids_new: int            # 实际新增入库的篇数
    pmids_ingested: int       # 成功向量索引的篇数
    pmids_skipped: int        # 因已存在而跳过的篇数
    pmids_failed: int         # 入库或索引失败的篇数
    details: List[SearchDetailItem] = []


class ArticleSummary(BaseModel):
    """文献列表中的单条摘要"""
    pmid: str
    title: str = ""
    authors: List[str] = []
    journal: str = ""
    publish_date: str = ""
    abstract_preview: str = ""   # 摘要前 200 字符
    is_free_download: bool = False
    ingestion_status: str = "uningested"
    ingested_at: Optional[datetime] = None
    study_groups: List[str] = []
    created_at: Optional[datetime] = None


class ArticleListData(BaseModel):
    """文献分页列表"""
    total: int
    page: int
    page_size: int
    articles: List[ArticleSummary]


class ArticleDetailData(BaseModel):
    """单篇文献完整详情"""
    pmid: str
    article_info: Dict[str, Any] = {}
    study_groups: List[str] = []
    results_info: Dict[str, Any] = {}
    objectives: str = ""
    is_free_download: bool = False
    ingestion_status: str = "uningested"
    chunk_count: Optional[int] = None
    vector_ids: Optional[List[str]] = None
    ingested_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    search_query: Optional[str] = None
    ingestion_error: Optional[str] = None


class IngestResultItem(BaseModel):
    """单篇索引结果"""
    pmid: str
    status: str              # "ingested" | "already_ingested" | "failed"
    chunk_count: int = 0
    reason: str = ""         # 失败原因


class IngestBatchData(BaseModel):
    """批量索引操作结果"""
    total_uningested: int = 0
    ingested: int = 0
    failed: int = 0
    details: List[IngestResultItem] = []


class DeleteResultData(BaseModel):
    """文献删除结果"""
    pmid: str
    deleted_pg: bool         # PostgreSQL 中是否删除成功
    deleted_vector: bool     # ChromaDB 中是否删除成功
```

#### 2.2.3 入参校验规则

| 端点                          | 校验规则                                                                 |
| ----------------------------- | ------------------------------------------------------------------------ |
| `POST /pubmed/search`         | `query`: 非空，≤500 字符；`max_results`: 1-30；`auto_ingest`: bool      |
| `GET /pubmed/articles`        | `page`: ≥1；`page_size`: 1-100；`ingestion_status`: "all"/"ingested"/"uningested"/"failed"；`sort_by`: 白名单 ["created_at","updated_at","pmid"]；`order`: "asc"/"desc" |
| `GET /pubmed/articles/{pmid}` | `pmid`: 非空字符串，纯数字                                              |
| `POST /pubmed/ingest/{pmid}`  | `pmid`: 非空字符串；可选 query param `force`: bool                       |
| `POST /pubmed/ingest/batch`   | 请求体 `pmids`: List[str]，长度 1-50，每个元素非空                        |
| `DELETE /pubmed/articles/{pmid}` | `pmid`: 非空字符串                                                   |

---

### 2.3 schemas/knowledge.py — 知识库统计 Schema

**文件**: `schemas/knowledge.py` (新增)  
**依赖**: `pydantic`

#### 2.3.1 数据结构

```python
from pydantic import BaseModel, Field
from typing import Dict


class VectorStoreInfo(BaseModel):
    """向量存储信息"""
    collection_name: str
    storage_path: str
    embedding_model: str


class KnowledgeStatsData(BaseModel):
    """知识库统计概览"""
    local_documents: int = 0              # ./data/ 中文档数
    pubmed_articles_total: int = 0        # PubMed 文献总数
    pubmed_articles_ingested: int = 0     # 已索引文献数
    pubmed_articles_uningested: int = 0   # 未索引文献数
    total_vector_chunks: int = 0          # ChromaDB 总 chunk 数
    by_source_type: Dict[str, int] = Field(default_factory=dict)
    # 如 {"local_file": 1820, "pubmed": 520}
    vector_store: VectorStoreInfo = Field(default_factory=VectorStoreInfo)
```

---

### 2.4 api/routers/pubmed_router.py — PubMed 路由

**文件**: `api/routers/pubmed_router.py` (新增)  
**依赖**: `PubMedSearchAppService`, `KnowledgeManagementService`

#### 2.4.1 模块级注入

```python
# 模块级服务引用（由 main.py 在启动时注入）
pubmed_search_service: Optional[PubMedSearchAppService] = None
knowledge_management_service: Optional[KnowledgeManagementService] = None


def set_pubmed_search_service(service: PubMedSearchAppService) -> None:
    global pubmed_search_service
    pubmed_search_service = service


def set_knowledge_management_service(service: KnowledgeManagementService) -> None:
    global knowledge_management_service
    knowledge_management_service = service
```

#### 2.4.2 端点清单与签名

```python
from fastapi import APIRouter, HTTPException, Query, Path

router = APIRouter(prefix="/pubmed")


@router.post("/search")
async def search_pubmed(request: PubMedSearchRequest):
    """触发 PubMed 搜索，结果自动入库并（默认）向量索引。

    Args:
        request: 包含 query、max_results、auto_ingest 的请求体

    Returns:
        ApiResponse[PubMedSearchData]
    """
```

**内部执行流程**:

```
1. 校验 pubmed_search_service 已注入，否则 500
2. 调用 pubmed_search_service.search_and_store(
       query=request.query,
       max_results=request.max_results,
       auto_ingest=request.auto_ingest,
   )
3. 将返回的 PubMedSearchData 包装为 ApiResponse 返回
4. try/except: 业务异常 → HTTPException(具体code, detail); 未知异常 → HTTPException(500)
```

| 异常场景                 | HTTP 状态码 | 处理方式                                         |
| ------------------------ | ----------- | ------------------------------------------------ |
| service 未初始化         | 500         | `"Service not initialized"`                      |
| query 为空或仅空白       | 400         | Pydantic 自动校验，返回 `"query 不能为空..."`     |
| PubMed API 完全不可用    | 503         | `"PubMed API 暂时不可用，请稍后重试"`             |
| 部分文献失败             | 200         | 正常返回，details 中包含失败条目                 |
| 未知异常                 | 500         | `str(e)`                                         |

---

```python
@router.get("/articles")
async def list_articles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    ingestion_status: str = Query(default="all",
                                   pattern=r"^(all|ingested|uningested|failed)$"),
    sort_by: str = Query(default="created_at",
                          pattern=r"^(created_at|updated_at|pmid)$"),
    order: str = Query(default="desc", pattern=r"^(asc|desc)$"),
):
    """分页浏览/搜索本地 PubMed 文献库。

    Returns:
        ApiResponse[ArticleListData]
    """
```

**内部执行流程**:

```
1. 校验 knowledge_management_service 已注入
2. 调用 knowledge_management_service.list_articles(
       page, page_size, search, ingestion_status, sort_by, order
   )
3. 包装为 ApiResponse 返回
```

---

```python
@router.get("/articles/{pmid}")
async def get_article_detail(pmid: str = Path(..., min_length=1)):
    """获取单篇文献完整详情。

    Args:
        pmid: PubMed 唯一标识符

    Returns:
        ApiResponse[ArticleDetailData]

    Raises:
        HTTPException(404): PMID 不存在
    """
```

**内部执行流程**:

```
1. 校验 knowledge_management_service 已注入
2. 调用 knowledge_management_service.get_article_detail(pmid)
3. 若返回 None → HTTPException(404, f"PMID {pmid} not found")
4. 正常返回 ApiResponse[ArticleDetailData]
```

---

```python
@router.post("/ingest/{pmid}")
async def ingest_single_article(
    pmid: str = Path(..., min_length=1),
    force: bool = Query(default=False),
):
    """手动触发单篇文献向量索引。

    Returns:
        ApiResponse[IngestBatchData] (包含单条 detail)
    """
```

---

```python
@router.post("/ingest/batch")
async def ingest_batch(request: IngestBatchRequest):
    """批量索引指定 PMID 列表。

    Request Body: {"pmids": ["12345678", "87654321"], "force": false}
    """
```

**`IngestBatchRequest`**（内联定义于 router 或 schema 中）:

```python
class IngestBatchRequest(BaseModel):
    pmids: List[str] = Field(..., min_length=1, max_length=50)
    force: bool = False
```

---

```python
@router.post("/ingest/all-uningested")
async def ingest_all_uningested():
    """一键索引所有未入库文章。

    Returns:
        ApiResponse[IngestBatchData]
    """
```

**内部执行流程**:

```
1. 调用 pubmed_search_service.ingest_all_uningested()  # 委托到 PubMedSearchAppService
   （或直接调用 PubMedArticleIngester.ingest_all_uningested()）
2. 包装返回
```

---

```python
@router.delete("/articles/{pmid}")
async def delete_article(pmid: str = Path(..., min_length=1)):
    """删除文献（PostgreSQL 记录 + ChromaDB 向量块）。

    Returns:
        ApiResponse[DeleteResultData]
    """
```

**内部执行流程**:

```
1. 调用 knowledge_management_service.delete_article(pmid)
2. 若 PG 和 ChromaDB 均未找到 → HTTPException(404)
3. 包装 DeleteResultData 返回
```

---

### 2.5 api/routers/knowledge_router.py — 知识库路由

**文件**: `api/routers/knowledge_router.py` (新增)  
**依赖**: `KnowledgeManagementService`

#### 2.5.1 模块级注入

```python
knowledge_management_service: Optional[KnowledgeManagementService] = None

def set_knowledge_management_service(service: KnowledgeManagementService) -> None:
    global knowledge_management_service
    knowledge_management_service = service
```

#### 2.5.2 端点

```python
router = APIRouter(prefix="/knowledge")

@router.get("/stats")
async def get_knowledge_stats():
    """获取知识库总体统计。

    Returns:
        ApiResponse[KnowledgeStatsData]
    """
```

**内部执行流程**:

```
1. 调用 knowledge_management_service.get_knowledge_stats()
2. 正常返回 ApiResponse[KnowledgeStatsData]
3. 异常 → HTTPException(500, detail=str(e))
```

---

### 2.6 application/services/pubmed_search_service.py — PubMed 搜索服务

**文件**: `application/services/pubmed_search_service.py` (新增)  
**依赖**: `PubMedRetriever`, `PostgresDB`, `PubMedArticleIngester`

#### 2.6.1 数据结构

```python
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchResultItem:
    """单篇文献搜索入库结果"""
    pmid: str
    status: str            # "ingested" | "skipped" | "failed"
    title: str = ""
    reason: str = ""       # "already_exists" | 错误消息
```

#### 2.6.2 类定义

```python
import time
from infrastructure.utils.logger_handler import get_logger

logger = get_logger(name="pubmed_search")


class PubMedSearchAppService:
    """PubMed 搜索→入库→索引 业务编排。

    对外暴露：
        search_and_store(query, max_results, auto_ingest) → PubMedSearchData
        ingest_all_uningested() → IngestBatchData
    """

    def __init__(
        self,
        pubmed_retriever,          # PubMedRetriever
        postgres_db,               # PostgresDB
        pubmed_ingester,           # PubMedArticleIngester
        request_interval: float = 0.15,  # NCBI API 请求间隔（秒）
    ):
        self._retriever = pubmed_retriever
        self._db = postgres_db
        self._ingester = pubmed_ingester
        self._interval = request_interval
```

#### 2.6.3 search_and_store()

```python
    def search_and_store(
        self, query: str, max_results: int = 5, auto_ingest: bool = True
    ) -> PubMedSearchData:
        """PubMed 搜索 → 逐篇入库 → 可选自动索引。

        执行流程：
        1. 调用 PubMedRetriever.search_pubmed(query) → PMID 列表
        2. FOR EACH pmid:
             a. 若 PostgresDB.is_pmid_exist(pmid) → skip (status="skipped")
             b. 否则调用 PubMedRetriever.fetch_article_details(pmid)
             c. PostgresDB.insert_article(data)
             d. 记录 status="stored"
        3. 若 auto_ingest=True:
             FOR EACH 新入库的 pmid:
               PubMedArticleIngester.ingest_article(pmid)
               → status 更新为 "ingested" 或 "failed"
        4. 汇总统计 → PubMedSearchData

        Args:
            query: PubMed 查询词
            max_results: 最大返回条数 (1-30)
            auto_ingest: 是否自动触发向量索引

        Returns:
            PubMedSearchData: 聚合统计结果
        """
```

**分支逻辑**:

```
search_and_store(query, max_results, auto_ingest)
  │
  ├──► PubMedRetriever.search_pubmed(query)
  │      │
  │      ├── 返回空列表 → 直接返回 (pmids_found=0)
  │      │
  │      └── 返回 [pmid1, pmid2, ...] → 继续
  │
  ├──► FOR EACH pmid (加 time.sleep(0.15) 间隔):
  │      │
  │      ├── PostgresDB.is_pmid_exist(pmid) → True:
  │      │      detail = SearchResultItem(pmid, "skipped", title="", reason="already_exists")
  │      │
  │      ├── PubMedRetriever.fetch_article_details(pmid):
  │      │      │
  │      │      ├── 成功: article_data dict
  │      │      │
  │      │      └── 异常 (网络/解析):
  │      │             detail = SearchResultItem(pmid, "failed", title="", reason=str(e))
  │      │             continue (不抛异常，继续下一篇)
  │      │
  │      ├── PostgresDB.insert_article(article_data):
  │      │      │
  │      │      ├── 成功: detail = SearchResultItem(pmid, "stored", title=title)
  │      │      │
  │      │      └── 异常 (唯一约束冲突等):
  │      │             detail = SearchResultItem(pmid, "failed", title=title, reason=str(e))
  │      │
  │      └── 收集 detail 到 results 列表
  │
  ├──► 若 auto_ingest=True:
  │      FOR EACH result where status == "stored":
  │        │
  │        ├── PubMedArticleIngester.ingest_article(pmid):
  │        │      │
  │        │      ├── 成功: 更新 result.status = "ingested"
  │        │      │
  │        │      └── 异常: 更新 result.status = "failed", result.reason = str(e)
  │        │               (单篇失败不中断整批)
  │
  ├──► 汇总: pmids_new = count(status ∈ {stored, ingested, failed})
  │          pmids_ingested = count(status == "ingested")
  │          pmids_skipped = count(status == "skipped")
  │          pmids_failed = count(status == "failed")
  │
  └──► RETURN PubMedSearchData(query, pmids_found, pmids_new,
                                pmids_ingested, pmids_skipped, pmids_failed, details)
```

**异常捕获方案**:

| 步骤           | 异常类型                | 处理                                  | 是否中断批次 |
| -------------- | ----------------------- | ------------------------------------- | ------------ |
| search_pubmed  | 网络错误 / Entrez 异常  | 重试 3 次（指数退避 3s/6s/12s）→ 仍失败则向上抛出 | 是（整批）   |
| fetch_article  | 网络错误 / XML 解析异常 | 记录 failed → 继续下一篇              | 否           |
| insert_article | 唯一约束冲突 / 连接断开 | 记录 failed → 继续下一篇              | 否           |
| ingest_article | 各种（见 2.9）          | 记录 failed → 继续下一篇              | 否           |

---

### 2.7 application/services/knowledge_management_service.py — 知识库管理服务

**文件**: `application/services/knowledge_management_service.py` (新增)  
**依赖**: `PostgresDB`, `VectorStoreService`, `PubMedArticleIngester`

#### 2.7.1 类定义

```python
logger = get_logger(name="knowledge_mgmt")


class KnowledgeManagementService:
    """知识库文献查询与统计，跨 PostgreSQL + ChromaDB 聚合。"""

    def __init__(self, postgres_db, vector_store_service, pubmed_ingester):
        self._db = postgres_db
        self._vs = vector_store_service
        self._ingester = pubmed_ingester
```

#### 2.7.2 list_articles()

```python
    def list_articles(
        self, page: int = 1, page_size: int = 20,
        search: Optional[str] = None,
        ingestion_status: str = "all",
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> ArticleListData:
        """分页查询本地 PubMed 文献。

        内部委托 PostgresDB.list_articles() 执行 SQL 查询。
        search 参数使用 ILIKE 模糊匹配 title 和 article_info->>'abstract'。
        """
```

**入参校验**（在 Router 层由 Pydantic 完成，此处为防御性二次校验）:

```python
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")
        if ingestion_status not in ("all", "ingested", "uningested", "failed"):
            raise ValueError(f"invalid ingestion_status: {ingestion_status}")
        if sort_by not in ("created_at", "updated_at", "pmid"):
            raise ValueError(f"invalid sort_by: {sort_by}")
        if order not in ("asc", "desc"):
            raise ValueError(f"invalid order: {order}")
```

**内部执行**: `self._db.list_articles(...) → (rows, total)` → 构建 `ArticleListData`

#### 2.7.3 get_article_detail()

```python
    def get_article_detail(self, pmid: str) -> Optional[ArticleDetailData]:
        """获取单篇文献完整详情。

        直接从 PostgreSQL 获取 JSONB 全量数据。
        PMID 不存在时返回 None（由调用方 Router 转为 404）。
        """
        row = self._db.get_article_by_pmid(pmid)
        if row is None:
            return None
        return ArticleDetailData(
            pmid=row["pmid"],
            article_info=row["article_info"] or {},
            study_groups=row["study_groups"] or [],
            results_info=row["results_info"] or {},
            objectives=row["objectives"] or "",
            is_free_download=row["is_free_download"] or False,
            ingestion_status=row["ingestion_status"] or "uningested",
            chunk_count=row.get("chunk_count"),
            vector_ids=row.get("vector_ids"),
            ingested_at=row.get("ingested_at"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            search_query=row.get("search_query"),
            ingestion_error=row.get("ingestion_error"),
        )
```

#### 2.7.4 delete_article()

```python
    def delete_article(self, pmid: str) -> DeleteResultData:
        """级联删除：先 ChromaDB 向量，再 PostgreSQL 记录。

        容错：两步独立 try/except，即使一步失败也继续执行另一步。
        """
        deleted_vector = False
        deleted_pg = False

        # Step 1: 删除 ChromaDB 中的向量块
        try:
            n = self._ingester.remove_from_vector_store(pmid)
            deleted_vector = (n > 0)
            logger.info(f"Deleted {n} vector chunks for PMID {pmid}")
        except Exception as e:
            logger.error(f"Failed to delete vectors for PMID {pmid}: {e}")

        # Step 2: 删除 PostgreSQL 中的文献记录
        try:
            deleted_pg = self._db.delete_article(pmid)
            logger.info(f"Deleted PG record for PMID {pmid}: {deleted_pg}")
        except Exception as e:
            logger.error(f"Failed to delete PG record for PMID {pmid}: {e}")

        return DeleteResultData(pmid=pmid, deleted_pg=deleted_pg, deleted_vector=deleted_vector)
```

#### 2.7.5 get_knowledge_stats()

```python
    def get_knowledge_stats(self) -> KnowledgeStatsData:
        """跨数据源聚合统计。

        数据来源：
        - PostgreSQL: 文献总数、已索引数、未索引数
        - ChromaDB: 总 chunk 数、按 source_type 分组统计
        - 本地: ./data/ 文件数
        """
        # 1. PostgreSQL 统计
        status_counts = self._db.count_articles_by_status()
        # → {"total": 47, "ingested": 42, "uningested": 5, "failed": 0}

        # 2. ChromaDB 统计
        vs_stats = self._vs.get_collection_stats()
        # → {"total_chunks": 2340, "by_source_type": {"local_file": 1820, "pubmed": 520}}

        # 3. 本地文档数
        local_count = self._get_local_document_count()

        # 4. 向量存储信息
        from schemas.knowledge import VectorStoreInfo
        vs_info = VectorStoreInfo(
            collection_name=chroma_conf["collection_name"],
            storage_path=chroma_conf["persist_directory"],
            embedding_model=rag_conf["embedding_model_name"],
        )

        return KnowledgeStatsData(
            local_documents=local_count,
            pubmed_articles_total=status_counts.get("total", 0),
            pubmed_articles_ingested=status_counts.get("ingested", 0),
            pubmed_articles_uningested=status_counts.get("uningested", 0),
            total_vector_chunks=vs_stats.get("total_chunks", 0),
            by_source_type=vs_stats.get("by_source_type", {}),
            vector_store=vs_info,
        )

    def _get_local_document_count(self) -> int:
        """统计 ./data/ 目录中文档数量"""
        import os
        from infrastructure.utils.path_tool import get_abs_path
        data_path = get_abs_path(chroma_conf["data_path"])
        allowed_exts = chroma_conf.get("allow_knowledge_file_type", [])
        if not os.path.isdir(data_path):
            return 0
        count = 0
        for f in os.listdir(data_path):
            ext = f.rsplit(".", 1)[-1] if "." in f else ""
            if ext in allowed_exts:
                count += 1
        return count
```

---

### 2.8 infrastructure/persistence/postgres_db.py — PostgreSQL 持久化

**文件**: `infrastructure/persistence/postgres_db.py` (从 `infrastructure/utils/` 迁入并重构)  
**依赖**: `psycopg2`, `psycopg2.extras`, `config_handler`, `logger_handler`

#### 2.8.1 类定义与上下文管理器

```python
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Tuple
from infrastructure.utils.config_handler import postgre_conf
from infrastructure.utils.logger_handler import get_logger

logger = get_logger(name="postgres_db")


class PostgresDB:
    """PostgreSQL 数据库工具类。

    支持两种使用方式：
    1. 上下文管理器（推荐）:
       with PostgresDB() as db:
           db.is_pmid_exist("12345678")

    2. 显式 connect/close（向后兼容）:
       db = PostgresDB()
       db.connect()
       db.is_pmid_exist("12345678")
       db.close()
    """

    def __init__(self):
        self.conn_params = {
            "host": postgre_conf["PG_HOST"],
            "port": postgre_conf["PG_PORT"],
            "user": postgre_conf["PG_USER"],
            "password": postgre_conf["PG_PASSWORD"],
            "database": postgre_conf["PG_DATABASE"],
            "options": "-c client_encoding=utf8",
        }
        self.table = postgre_conf["PG_TABLE"]
        self.conn = None
        self.cur = None

    # ── 上下文管理器 ─────────────────────────────────
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # 不吞异常
```

#### 2.8.2 连接管理

```python
    def connect(self):
        """建立数据库连接。重复调用时先关闭旧连接。"""
        if self.conn:
            self.close()
        try:
            for key in list(self.conn_params.keys()):
                if isinstance(self.conn_params[key], str):
                    self.conn_params[key] = (
                        self.conn_params[key]
                        .encode('gbk', errors='ignore')
                        .decode('utf8', errors='ignore')
                    )
            self.conn = psycopg2.connect(**self.conn_params)
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("PostgreSQL 连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def close(self):
        """关闭连接。"""
        if self.cur:
            self.cur.close()
            self.cur = None
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("PostgreSQL 连接已关闭")

    def _ensure_connected(self):
        """确保连接有效，失败则自动重连。"""
        if not self.conn or self.conn.closed:
            self.connect()
```

#### 2.8.3 已存在方法（保留）

```python
    def is_pmid_exist(self, pmid: str) -> bool:
        """判断 PMID 是否已存在。"""
        self._ensure_connected()
        try:
            sql = f"SELECT 1 FROM {self.table} WHERE pmid = %s LIMIT 1"
            self.cur.execute(sql, (pmid,))
            return self.cur.fetchone() is not None
        except Exception as e:
            logger.error(f"PMID 查重失败 (pmid={pmid}): {e}")
            self.conn.rollback()
            raise

    def insert_article(self, article_data: Dict) -> None:
        """插入单篇文献。包含新增的 search_query 和 raw_response 字段。"""
        self._ensure_connected()
        try:
            sql = f"""
                INSERT INTO {self.table}
                    (pmid, article_info, study_groups, results_info,
                     objectives, is_free_download, ingestion_status,
                     search_query, raw_response)
                VALUES (%s, %s, %s, %s, %s, %s, 'uningested', %s, %s)
            """
            params = (
                article_data["pmid"],
                json.dumps(article_data["article_info"]),
                article_data.get("study_groups", []),
                json.dumps(article_data["results_info"])
                    if article_data.get("results_info") else None,
                article_data.get("objectives", ""),
                article_data.get("is_free_download", False),
                article_data.get("search_query", ""),
                json.dumps(article_data.get("raw_response"))
                    if article_data.get("raw_response") else None,
            )
            self.cur.execute(sql, params)
            self.conn.commit()
            logger.info(f"文献插入成功 (pmid={article_data['pmid']})")
        except Exception as e:
            logger.error(f"文献插入失败 (pmid={article_data['pmid']}): {e}")
            self.conn.rollback()
            raise
```

#### 2.8.4 新增方法

```python
    # ── 查询方法 ─────────────────────────────────

    def get_article_by_pmid(self, pmid: str) -> Optional[Dict]:
        """获取单篇文献完整数据。

        Returns:
            文献 dict，不存在时返回 None。
        """
        self._ensure_connected()
        try:
            sql = f"SELECT * FROM {self.table} WHERE pmid = %s"
            self.cur.execute(sql, (pmid,))
            return self.cur.fetchone()
        except Exception as e:
            logger.error(f"查询文献失败 (pmid={pmid}): {e}")
            raise

    def list_articles(
        self, page: int = 1, page_size: int = 20,
        search: Optional[str] = None,
        ingestion_status: str = "all",
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> Tuple[List[Dict], int]:
        """分页查询文献列表。

        支持按标题/摘要模糊搜索，按 ingestion_status 过滤。
        使用 RealDictCursor 返回字典列表。

        Returns:
            (rows: List[Dict], total_count: int)
        """
        self._ensure_connected()
        try:
            # 构建 WHERE 条件
            conditions = []
            params = []

            if search:
                conditions.append(
                    "(article_info->>'title' ILIKE %s "
                    "OR article_info->>'abstract' ILIKE %s)"
                )
                like_pattern = f"%{search}%"
                params.extend([like_pattern, like_pattern])

            if ingestion_status != "all":
                conditions.append("ingestion_status = %s")
                params.append(ingestion_status)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # 排序（白名单校验后使用，防止 SQL 注入）
            ALLOWED_SORT = {"created_at", "updated_at", "pmid"}
            ALLOWED_ORDER = {"asc", "desc"}
            sort_col = sort_by if sort_by in ALLOWED_SORT else "created_at"
            sort_order = order if order in ALLOWED_ORDER else "desc"

            # 总数
            count_sql = f"SELECT COUNT(*) as cnt FROM {self.table} {where_clause}"
            self.cur.execute(count_sql, params)
            total = self.cur.fetchone()["cnt"]

            # 分页
            offset = (page - 1) * page_size
            data_sql = f"""
                SELECT pmid, article_info, study_groups, objectives,
                       is_free_download, ingestion_status, ingested_at,
                       created_at
                FROM {self.table}
                {where_clause}
                ORDER BY {sort_col} {sort_order}
                LIMIT %s OFFSET %s
            """
            self.cur.execute(data_sql, params + [page_size, offset])
            rows = self.cur.fetchall()

            return rows, total
        except Exception as e:
            logger.error(f"查询文献列表失败: {e}")
            raise

    # ── 更新方法 ─────────────────────────────────

    def update_ingestion_status(
        self, pmid: str, status: str,
        error: Optional[str] = None,
        chunk_count: Optional[int] = None,
        vector_ids: Optional[List[str]] = None,
    ) -> None:
        """更新文献的向量索引状态。

        Args:
            pmid: 文献 PMID
            status: "ingesting" | "ingested" | "failed"
            error: 失败原因（status=failed 时填写）
            chunk_count: 生成的 chunk 数量
            vector_ids: ChromaDB 分配的 chunk ID 列表
        """
        self._ensure_connected()
        try:
            set_parts = ["ingestion_status = %s", "updated_at = NOW()"]
            params: List = [status]

            if status == "ingested":
                set_parts.append("ingested_at = NOW()")
            if chunk_count is not None:
                set_parts.append("chunk_count = %s")
                params.append(chunk_count)
            if vector_ids is not None:
                set_parts.append("vector_ids = %s")
                params.append(json.dumps(vector_ids))
            if error is not None:
                set_parts.append("ingestion_error = %s")
                params.append(error)
            elif status == "ingested":
                # 成功时清除旧的错误信息
                set_parts.append("ingestion_error = NULL")

            set_clause = ", ".join(set_parts)
            sql = f"UPDATE {self.table} SET {set_clause} WHERE pmid = %s"
            params.append(pmid)

            self.cur.execute(sql, params)
            self.conn.commit()
            logger.info(
                f"更新摄入状态成功 (pmid={pmid}, status={status}, "
                f"chunks={chunk_count})"
            )
        except Exception as e:
            logger.error(f"更新摄入状态失败 (pmid={pmid}): {e}")
            self.conn.rollback()
            raise

    # ── 统计方法 ─────────────────────────────────

    def count_articles_by_status(self) -> Dict[str, int]:
        """按 ingestion_status 统计文献数量。

        Returns:
            {"total": N, "ingested": N, "uningested": N, "failed": N}
        """
        self._ensure_connected()
        try:
            sql = f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE ingestion_status = 'ingested') as ingested,
                    COUNT(*) FILTER (WHERE ingestion_status = 'uningested') as uningested,
                    COUNT(*) FILTER (WHERE ingestion_status = 'failed') as failed
                FROM {self.table}
            """
            self.cur.execute(sql)
            row = self.cur.fetchone()
            return {
                "total": row["total"] or 0,
                "ingested": row["ingested"] or 0,
                "uningested": row["uningested"] or 0,
                "failed": row["failed"] or 0,
            }
        except Exception as e:
            logger.error(f"统计文献数量失败: {e}")
            raise

    def count_all(self) -> int:
        """返回文献总数。"""
        self._ensure_connected()
        try:
            sql = f"SELECT COUNT(*) as cnt FROM {self.table}"
            self.cur.execute(sql)
            return self.cur.fetchone()["cnt"]
        except Exception as e:
            logger.error(f"统计总数失败: {e}")
            raise

    # ── 删除方法 ─────────────────────────────────

    def delete_article(self, pmid: str) -> bool:
        """删除单篇文献记录。

        Returns:
            True 表示成功删除至少 1 行，False 表示 PMID 不存在。
        """
        self._ensure_connected()
        try:
            sql = f"DELETE FROM {self.table} WHERE pmid = %s"
            self.cur.execute(sql, (pmid,))
            self.conn.commit()
            deleted = self.cur.rowcount > 0
            logger.info(f"删除文献 (pmid={pmid}): {'成功' if deleted else 'PMID不存在'}")
            return deleted
        except Exception as e:
            logger.error(f"删除文献失败 (pmid={pmid}): {e}")
            self.conn.rollback()
            raise
```

#### 2.8.5 SQL 注入防护

`list_articles()` 中 `sort_by` 和 `order` 参数通过白名单校验后直接拼入 SQL（不使用 `%s` 占位符）。白名单为硬编码常量，确保用户输入不可绕过。

#### 2.8.6 向后兼容：保留单例

```python
# 单例：供 pubmed/paper_search.py 等旧代码过渡使用
PostgresDB_singleton = PostgresDB()
```

---

### 2.9 infrastructure/persistence/pubmed_ingester.py — PubMed 文章向量化

**文件**: `infrastructure/persistence/pubmed_ingester.py` (新增)  
**依赖**: `PostgresDB`, `VectorStoreService`, `RecursiveCharacterTextSplitter`

#### 2.9.1 数据结构

```python
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class IngestResult:
    """单篇摄入结果"""
    pmid: str
    status: str          # "ingested" | "already_ingested" | "failed"
    chunk_count: int = 0
    reason: str = ""     # 失败原因
    vector_ids: List[str] = field(default_factory=list)
```

#### 2.9.2 类定义

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangchainDocument
from infrastructure.utils.config_handler import chroma_conf, pubmed_conf
from infrastructure.utils.logger_handler import get_logger

logger = get_logger(name="pubmed_ingester")


class PubMedArticleIngester:
    """PubMed 文章 → 结构化文本 → 分块 → ChromaDB 向量索引。

    核心管线：
        1. 从 PG 获取 JSONB 文章数据
        2. _build_article_text() 按模板拼接结构化文本
        3. RecursiveCharacterTextSplitter 分块
        4. 为每个 chunk 构建 metadata（含 source_type="pubmed"）
        5. VectorStoreService.add_documents_direct() 写入 ChromaDB
        6. 更新 PG ingestion_status
    """

    def __init__(self, postgres_db, vector_store_service):
        """
        Args:
            postgres_db: PostgresDB 实例
            vector_store_service: VectorStoreService 实例
        """
        self._db = postgres_db
        self._vs = vector_store_service
        # TextSplitter 通过 VectorStoreService 根据 source_type 获取
```

#### 2.9.3 ingest_article()

```python
    def ingest_article(self, pmid: str, force: bool = False) -> IngestResult:
        """将单篇 PubMed 文章向量化并写入 ChromaDB。

        幂等性：
        - 已 ingested + force=False → 直接返回 (status="already_ingested")
        - 已 ingested + force=True → 先删旧 chunks 再重索引
        - 状态为 ingesting → 检查是否僵死 (超过 10 分钟)，僵死则继续

        Args:
            pmid: PubMed 唯一标识符
            force: 是否强制重索引（覆盖已有向量）

        Returns:
            IngestResult(pmid, status, chunk_count, reason, vector_ids)
        """
        try:
            # 1. 从 PG 获取文章
            article = self._db.get_article_by_pmid(pmid)
            if article is None:
                return IngestResult(pmid, "failed", reason=f"PMID {pmid} not found in database")

            current_status = article.get("ingestion_status", "uningested")

            # 2. 幂等检查
            if current_status == "ingested" and not force:
                return IngestResult(
                    pmid, "already_ingested",
                    chunk_count=article.get("chunk_count") or 0
                )

            # 若 force=True，先清理旧向量
            if force and current_status == "ingested":
                self.remove_from_vector_store(pmid)

            # 3. 标记为 ingesting
            self._db.update_ingestion_status(pmid, "ingesting")

            # 4. 构建结构化文本
            article_text = self._build_article_text(article)
            if not article_text or not article_text.strip():
                self._db.update_ingestion_status(
                    pmid, "failed",
                    error="Empty article text after building template"
                )
                return IngestResult(pmid, "failed", reason="Empty article text")

            # 5. 分块
            splitter = self._vs.get_splitter(source_type="pubmed")
            chunks = splitter.split_text(article_text)
            if not chunks:
                self._db.update_ingestion_status(
                    pmid, "failed", error="No chunks produced"
                )
                return IngestResult(pmid, "failed", reason="No chunks produced")

            # 6. 为每个 chunk 构建 metadata
            langchain_docs = []
            for i, chunk_text in enumerate(chunks):
                metadata = self._build_chunk_metadata(article, i, len(chunks))
                langchain_docs.append(
                    LangchainDocument(page_content=chunk_text, metadata=metadata)
                )

            # 7. 写入 ChromaDB，获取分配的 IDs
            vector_ids = self._vs.add_documents_direct(langchain_docs)

            # 8. 更新状态为 ingested
            self._db.update_ingestion_status(
                pmid, "ingested",
                chunk_count=len(chunks),
                vector_ids=vector_ids,
            )

            logger.info(f"文献索引成功 (pmid={pmid}, chunks={len(chunks)})")
            return IngestResult(
                pmid, "ingested",
                chunk_count=len(chunks),
                vector_ids=vector_ids,
            )

        except Exception as e:
            logger.error(f"文献索引失败 (pmid={pmid}): {e}", exc_info=True)
            # 尝试将状态标记为 failed
            try:
                self._db.update_ingestion_status(pmid, "failed", error=str(e))
            except Exception as db_err:
                logger.error(f"更新失败状态时再次出错 (pmid={pmid}): {db_err}")
            return IngestResult(pmid, "failed", reason=str(e))
```

**分支逻辑图**:

```
ingest_article(pmid, force)
  │
  ├──► PG 中不存在 pmid → FAILED
  │
  ├──► status=="ingested" ∧ ¬force → ALREADY_INGESTED（幂等，直接返回）
  │
  ├──► force=True → 先 remove_from_vector_store(pmid)
  │
  ├──► 更新 status → "ingesting"
  │
  ├──► _build_article_text(article)
  │      │
  │      ├── 结果为空 → FAILED (Empty text)
  │      └── 有效文本 → 继续
  │
  ├──► splitter.split_text(text)
  │      │
  │      ├── 结果为空列表 → FAILED (No chunks)
  │      └── 返回 chunks → 继续
  │
  ├──► FOR EACH chunk: 构建 metadata → LangchainDocument
  │
  ├──► vs.add_documents_direct(docs) → vector_ids
  │
  ├──► 更新 status → "ingested" (chunk_count + vector_ids + ingested_at)
  │
  └──► RETURN IngestResult("ingested", ...)

任何步骤异常 → catch → 更新 status → "failed" → RETURN IngestResult("failed", ...)
```

#### 2.9.4 _build_article_text()

```python
    def _build_article_text(self, article: Dict) -> str:
        """将 PostgreSQL JSONB 文章数据按模板拼接为结构化文本。

        模板:
            [PubMed Article]
            Title: {title}
            Authors: {authors}
            Journal: {journal}
            Publication Date: {date}
            DOI: {doi}
            PMID: {pmid}

            Research Objectives:
            {objectives}

            Study Groups:
            {study_groups}

            Key Results:
            {results_summary}

            Abstract:
            {abstract}
        """
        info = article.get("article_info") or {}
        title = info.get("title", "")
        authors_list = info.get("authors", [])
        authors_str = ", ".join(authors_list) if authors_list else "N/A"
        journal = info.get("journal", "")
        pub_date = info.get("publish_date", "")
        doi = info.get("doi", "")
        abstract = info.get("abstract", "")

        objectives = article.get("objectives") or ""
        study_groups = article.get("study_groups") or []
        groups_str = ", ".join(study_groups) if study_groups else "N/A"

        results_info = article.get("results_info") or {}
        results_summary = results_info.get("raw_abstract", "")

        text = f"""[PubMed Article]
Title: {title}
Authors: {authors_str}
Journal: {journal}
Publication Date: {pub_date}
DOI: {doi}
PMID: {article.get('pmid', '')}

Research Objectives:
{objectives}

Study Groups:
{groups_str}

Key Results:
{results_summary}

Abstract:
{abstract}"""

        return text.strip()
```

#### 2.9.5 _build_chunk_metadata()

```python
    def _build_chunk_metadata(
        self, article: Dict, chunk_index: int, total_chunks: int
    ) -> Dict:
        """为单个 chunk 构建 ChromaDB metadata。

        metadata 字段（与概要设计 5.6 一致）:
            source, source_type, pmid, title, authors,
            journal, publish_date, doi, is_free_download,
            chunk_index, total_chunks
        """
        info = article.get("article_info") or {}
        title = info.get("title", "")
        authors_list = info.get("authors", [])
        authors_str = ", ".join(authors_list[:5])  # 最多 5 位作者
        if len(authors_list) > 5:
            authors_str += ", et al."

        pmid = article.get("pmid", "")

        return {
            "source": f"PMID:{pmid}: {title[:80]}",
            "source_type": "pubmed",
            "pmid": pmid,
            "title": title,
            "authors": authors_str,
            "journal": info.get("journal", ""),
            "publish_date": info.get("publish_date", ""),
            "doi": info.get("doi", ""),
            "is_free_download": article.get("is_free_download", False),
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
        }
```

#### 2.9.6 batch_ingest()

```python
    def batch_ingest(
        self, pmids: List[str], force: bool = False
    ) -> List[IngestResult]:
        """批量索引。

        逐篇调用 ingest_article()，单篇失败不影响其他篇。
        """
        results = []
        for pmid in pmids:
            result = self.ingest_article(pmid, force=force)
            results.append(result)
            logger.debug(f"Batch ingest progress: {pmid} → {result.status}")
        return results
```

#### 2.9.7 ingest_all_uningested()

```python
    def ingest_all_uningested(self, force: bool = False) -> List[IngestResult]:
        """索引所有 ingestion_status 为 'uningested' 或 'failed' 的文献。

        内部调用 PostgresDB.list_articles(status="uningested", page_size=9999) 获取列表，
        然后逐篇调用 ingest_article()。
        """
        rows, total = self._db.list_articles(
            page=1, page_size=9999, ingestion_status="uningested"
        )
        pmids = [row["pmid"] for row in rows]

        # 同时包含 failed 的文章
        failed_rows, _ = self._db.list_articles(
            page=1, page_size=9999, ingestion_status="failed"
        )
        pmids.extend([row["pmid"] for row in failed_rows])

        logger.info(f"开始全量索引: {len(pmids)} 篇待处理 (uningested + failed)")
        return self.batch_ingest(pmids, force=force)
```

#### 2.9.8 remove_from_vector_store()

```python
    def remove_from_vector_store(self, pmid: str) -> int:
        """从 ChromaDB 中删除指定 PMID 的所有向量块。

        Returns:
            实际删除的 chunk 数量。
        """
        try:
            n = self._vs.delete_by_metadata_filter({"pmid": pmid})
            logger.info(f"从向量存储中删除 PMID {pmid}: {n} 个 chunks")
            return n
        except Exception as e:
            logger.error(f"删除向量块失败 (pmid={pmid}): {e}")
            raise
```

---

### 2.10 infrastructure/persistence/vector_store.py — 向量存储扩展

**文件**: `infrastructure/persistence/vector_store.py` (已有，追加 3 个方法)  
**依赖**: `Chroma`, `RecursiveCharacterTextSplitter`

#### 2.10.1 新增方法 add_documents_direct()

```python
    def add_documents_direct(
        self, documents: List[LangchainDocument]
    ) -> List[str]:
        """直接写入 ChromaDB，跳过 MD5 去重。

        供 PubMedArticleIngester 调用。
        返回 ChromaDB 分配的 chunk ID 列表。

        Args:
            documents: 已构建好 metadata 的 LangchainDocument 列表

        Returns:
            ChromaDB 分配的 ID 列表
        """
        try:
            ids = self.vector_store.add_documents(documents)
            logger.info(f"直接写入 {len(documents)} 个文档到 ChromaDB")
            return ids
        except Exception as e:
            logger.error(f"ChromaDB 写入失败: {e}")
            raise
```

#### 2.10.2 新增方法 delete_by_metadata_filter()

```python
    def delete_by_metadata_filter(self, metadata_filter: Dict) -> int:
        """按 metadata 条件删除向量。

        ChromaDB 不支持直接 delete(where=...), 需两步:
        1. collection.get(where=filter) → 获取匹配的 IDs
        2. collection.delete(ids=ids)  → 删除

        Args:
            metadata_filter: ChromaDB where 条件，如 {"pmid": "12345678"}

        Returns:
            删除的 chunk 数量
        """
        try:
            results = self.vector_store.get(where=metadata_filter)
            ids = results.get("ids", [])
            if not ids:
                logger.debug(f"未找到匹配的向量: {metadata_filter}")
                return 0

            self.vector_store.delete(ids=ids)
            logger.info(f"按条件 {metadata_filter} 删除了 {len(ids)} 个 chunks")
            return len(ids)
        except Exception as e:
            logger.error(f"ChromaDB 条件删除失败 (filter={metadata_filter}): {e}")
            raise
```

#### 2.10.3 新增方法 get_collection_stats()

```python
    def get_collection_stats(self) -> Dict:
        """获取 ChromaDB collection 统计信息。

        Returns:
            {
                "total_chunks": 2340,
                "by_source_type": {"local_file": 1820, "pubmed": 520}
            }
        """
        try:
            total = self.vector_store._collection.count()

            # 按 source_type 分组统计
            # ChromaDB 1.5 get() 返回所有 metadata, 我们按 source_type 分组
            by_type = {"local_file": 0, "pubmed": 0}
            try:
                all_data = self.vector_store.get(limit=99999, include=["metadatas"])
                for meta in all_data.get("metadatas", []):
                    st = meta.get("source_type", "local_file")
                    by_type[st] = by_type.get(st, 0) + 1
            except Exception:
                # 如果数据量大，get() 可能耗时，返回 -1 表示不可用
                by_type = {"local_file": -1, "pubmed": -1}

            return {"total_chunks": total, "by_source_type": by_type}
        except Exception as e:
            logger.error(f"获取 ChromaDB 统计信息失败: {e}")
            return {"total_chunks": 0, "by_source_type": {}}
```

#### 2.10.4 新增方法 get_splitter()

```python
    def get_splitter(
        self, source_type: str = "local_file"
    ) -> RecursiveCharacterTextSplitter:
        """根据来源类型获取对应的 TextSplitter。

        Args:
            source_type: "local_file" 或 "pubmed"

        Returns:
            配置了对应 chunk_size / chunk_overlap 的 RecursiveCharacterTextSplitter
        """
        if source_type == "pubmed":
            chunk_size = chroma_conf.get("pubmed_chunk_size", 800)
            chunk_overlap = chroma_conf.get("pubmed_chunk_overlap", 200)
            separators = chroma_conf.get(
                "pubmed_separator",
                ["\n\n", "\n", ". ", "! ", "? ", "。", "！", "？", " ", ""]
            )
        else:
            chunk_size = chroma_conf.get("chunk_size", 800)
            chunk_overlap = chroma_conf.get("chunk_overlap", 200)
            separators = chroma_conf.get(
                "separator",
                ["\n\n", "\n", ".", "!", "?", "。", "！", "？", " ", ""]
            )

        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )
```

> **说明**: 现有的 `self.spliter` (本地文档用) 保持不变。`get_splitter()` 为新增的工厂方法，`PubMedArticleIngester` 通过它获取 PubMed 配置的 splitter。

---

### 2.11 infrastructure/persistence/document_retriever_impl.py — 检索器扩展

**文件**: `infrastructure/persistence/document_retriever_impl.py` (已有，修改 `format_documents_for_context`)  
**依赖**: 无新增依赖

#### 2.11.1 修改方法 format_documents_for_context()

**变更前**（当前代码）:

```python
def format_documents_for_context(self, documents: List[Document]) -> str:
    context = ""
    for i, doc in enumerate(documents, 1):
        source = doc.source or f"参考资料{i}"
        context += f"[{i}] {source}\n{doc.content}\n\n"
    return context
```

**变更后**:

```python
    def format_documents_for_context(self, documents: List[Document]) -> str:
        """按 source_type 生成差异化引文格式。

        local_file: [N] 《文件名（无后缀）》.
        pubmed:     [N] Authors. Title. Journal. Year. PMID: xxxxx.

        若 source_type 为空或未知，默认按 local_file 格式处理（向后兼容）。
        """
        context = ""
        for i, doc in enumerate(documents, 1):
            source_type = doc.metadata.get("source_type", "local_file")

            if source_type == "pubmed":
                formatted = self._format_pubmed_citation(doc, i)
            else:
                formatted = self._format_local_citation(doc, i)

            context += f"{formatted}\n{doc.content}\n\n"

        return context

    @staticmethod
    def _format_local_citation(doc: Document, index: int) -> str:
        """格式化本地文件引文: [N] 《文件名》."""
        source = doc.source or f"参考资料{index}"
        # 去掉文件后缀
        for ext in [".docx", ".doc", ".pdf", ".txt"]:
            if source.endswith(ext):
                source = source[:-len(ext)]
                break
        return f"[{index}] 《{source}》."

    @staticmethod
    def _format_pubmed_citation(doc: Document, index: int) -> str:
        """格式化 PubMed 文献引文（温哥华格式）。

        格式: [N] Authors. Title. Journal Abbr. Year. PMID: xxxxx.
        """
        meta = doc.metadata
        authors = meta.get("authors", "")
        title = meta.get("title", "Unknown Title")
        journal = meta.get("journal", "")
        pub_date = meta.get("publish_date", "")
        year = pub_date[:4] if pub_date else ""
        pmid = meta.get("pmid", "")

        parts = []
        if authors:
            parts.append(f"{authors}.")
        parts.append(f"{title}.")
        if journal:
            parts.append(f"{journal}.")
        if year:
            parts.append(f"{year}.")
        if pmid:
            parts.append(f"PMID: {pmid}.")

        return f"[{index}] {' '.join(parts)}"
```

> **向后兼容**: 若 `source_type` 不存在于 metadata（旧数据），默认走 `_format_local_citation`，与变更前行为等价。

---

### 2.12 infrastructure/services/service_factory.py — DI 容器扩展

**文件**: `infrastructure/services/service_factory.py` (已有，新增 getter)  
**依赖**: 各新增模块

#### 2.12.1 新增 getter

```python
# 新增 import
from infrastructure.persistence.postgres_db import PostgresDB
from infrastructure.persistence.pubmed_ingester import PubMedArticleIngester
from pubmed.pubmed_retriever import PubMedRetriever
from application.services.pubmed_search_service import PubMedSearchAppService
from application.services.knowledge_management_service import KnowledgeManagementService
from infrastructure.utils.config_handler import pubmed_conf


class ServiceFactory:
    def __init__(self):
        # ... 现有字段 ...
        self._postgres_db = None
        self._pubmed_retriever = None
        self._pubmed_ingester = None
        self._pubmed_search_service = None
        self._knowledge_management_service = None

    # ── 新增 getter ─────────────────────────────────

    def get_postgres_db(self) -> PostgresDB:
        if not self._postgres_db:
            self._postgres_db = PostgresDB()
        return self._postgres_db

    def get_pubmed_retriever(self) -> PubMedRetriever:
        if not self._pubmed_retriever:
            self._pubmed_retriever = PubMedRetriever()
        return self._pubmed_retriever

    def get_pubmed_ingester(self) -> PubMedArticleIngester:
        if not self._pubmed_ingester:
            self._pubmed_ingester = PubMedArticleIngester(
                postgres_db=self.get_postgres_db(),
                vector_store_service=self.get_vector_store_service(),
            )
        return self._pubmed_ingester

    def get_pubmed_search_service(self) -> PubMedSearchAppService:
        if not self._pubmed_search_service:
            interval = pubmed_conf.get("request_interval", 0.15)
            self._pubmed_search_service = PubMedSearchAppService(
                pubmed_retriever=self.get_pubmed_retriever(),
                postgres_db=self.get_postgres_db(),
                pubmed_ingester=self.get_pubmed_ingester(),
                request_interval=interval,
            )
        return self._pubmed_search_service

    def get_knowledge_management_service(self) -> KnowledgeManagementService:
        if not self._knowledge_management_service:
            self._knowledge_management_service = KnowledgeManagementService(
                postgres_db=self.get_postgres_db(),
                vector_store_service=self.get_vector_store_service(),
                pubmed_ingester=self.get_pubmed_ingester(),
            )
        return self._knowledge_management_service
```

#### 2.12.2 依赖注入图 (更新后)

```
ServiceFactory
  ├── VectorStoreService ──────────────┬─────────────────┐
  ├── VectorDocumentRetriever(VS)      │                 │
  ├── RuleBasedKeywordExtractor        │                 │
  ├── LangChainRAGSummarizer(DR)       │                 │
  ├── RAGQueryService(KE, DR, RS)      │                 │
  ├── PostgresDB ← 新增                │                 │
  ├── PubMedRetriever ← 新增           │                 │
  ├── PubMedArticleIngester(PG, VS) ←──┘                 │
  ├── PubMedSearchAppService(PR, PG, PI) ← 新增          │
  └── KnowledgeManagementService(PG, VS, PI) ←───────────┘
```

---

### 2.13 pubmed/pubmed_retriever.py — PubMed 检索器扩展

**文件**: `pubmed/pubmed_retriever.py` (修改，仅改 `fetch_article_details`)  
**依赖**: `Bio.Entrez`

#### 2.13.1 修改 fetch_article_details()

**变更点**: 内部改为调用已有静态辅助方法（`_parse_authors`, `_parse_abstract`, `_parse_publish_date`, `_parse_doi`, `_parse_study_groups`, `_parse_results_info`, `_parse_objectives`, `_is_free_download`），消除重复代码。

**变更后**:

```python
    def fetch_article_details(self, pmid: str) -> Dict:
        """根据 PMID 获取文献详情（扩展版）。

        提取字段（扩展现有 article_info JSONB）:
            title, authors, abstract, journal, doi, publish_date, pmc_id, publication_type

        Returns:
            {
                "pmid": str,
                "article_info": {
                    "title": str, "authors": [str], "abstract": str,
                    "journal": str, "doi": str, "publish_date": str,
                    "pmc_id": str, "publication_type": str,
                },
                "study_groups": [str],
                "results_info": {"raw_abstract": str, "endpoints": str, "stats": str} | None,
                "objectives": str,
                "is_free_download": bool,
                "search_query": str,
                "raw_response": dict,
            }
        """
        try:
            handle = Entrez.efetch(db="pubmed", id=pmid, rettype="xml", retmode="text")
            records = Entrez.read(handle)
            handle.close()

            article = records["PubmedArticle"][0]["MedlineCitation"]["Article"]
            medline = records["PubmedArticle"][0]["MedlineCitation"]

            # 提取各字段（使用静态辅助方法）
            abstract_text = self._parse_abstract(article.get("Abstract", {}))
            authors = self._parse_authors(article.get("AuthorList", []))
            pub_date = self._parse_publish_date(article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {}))
            article_ids = records["PubmedArticle"][0].get("PubmedData", {}).get("ArticleIdList", [])
            doi = self._parse_doi(article_ids)
            pmc_id = self._get_pmc_id(article_ids)
            pub_type_list = article.get("PublicationTypeList", [])
            pub_types = [str(pt) for pt in pub_type_list] if pub_type_list else []
            publication_type = ", ".join(pub_types) if pub_types else ""

            # 期刊名（缩写优先）
            journal = article.get("Journal", {})
            journal_title = journal.get("ISOAbbreviation", "") or journal.get("Title", "")

            # 构建返回数据
            article_info = {
                "title": article.get("ArticleTitle", ""),
                "authors": [f"{a.get('last_name', '')} {a.get('first_name', '')}"
                           for a in authors],
                "abstract": abstract_text,
                "journal": journal_title,
                "doi": doi,
                "publish_date": pub_date,
                "pmc_id": pmc_id,
                "publication_type": publication_type,
            }

            results_info = self._parse_results_info(abstract_text)
            objectives = self._parse_objectives(abstract_text) or "未明确研究目标"

            # 原始响应（供调试）
            import copy
            raw_response = copy.deepcopy(records)

            return {
                "pmid": pmid,
                "article_info": article_info,
                "study_groups": self._parse_study_groups(abstract_text),
                "results_info": results_info,
                "objectives": objectives,
                "is_free_download": self._is_free_download(article_ids),
                "search_query": "",
                "raw_response": raw_response,
            }

        except Exception as e:
            logger.error(f"提取文献详情失败 (pmid={pmid}): {e}", exc_info=True)
            raise
```

**新增辅助方法**:

```python
    @staticmethod
    def _get_pmc_id(article_id_list) -> str:
        """从 ArticleIdList 中提取 PMC ID。"""
        for aid in article_id_list:
            if aid.attributes.get("IdType") == "pmc":
                return str(aid)
        return ""
```

#### 2.13.2 search_pubmed() — 不变

`search_pubmed(query)` 方法签名和实现保持不变。

---

### 2.14 pubmed/paper_search.py — 独立搜索管线

**文件**: `pubmed/paper_search.py` (重构后)  
**依赖**: `PubMedRetriever`, `PostgresDB`

#### 2.14.1 重构目标

将 `main(pubmed_query)` 函数重构为 `PubMedSearchPipeline` 类，使其可被外部调用，同时保留 `if __name__ == "__main__"` 命令行入口。

#### 2.14.2 类定义

```python
"""
PubMed 文献搜索 → 入库的独立管线。

功能: 搜索 PubMed → 逐 PMID 查重 → 提取详情 → 插入 PostgreSQL。

用法:
  from pubmed.paper_search import PubMedSearchPipeline
  pipeline = PubMedSearchPipeline()
  results = pipeline.run("COVID-19 mRNA vaccine", max_results=10)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.utils.logger_handler import get_logger
from infrastructure.utils.config_handler import pubmed_conf
from infrastructure.persistence.postgres_db import PostgresDB
from pubmed.pubmed_retriever import PubMedRetriever

logger = get_logger(name="pubmed_pipeline")


class PubMedSearchPipeline:
    """PubMed 搜索入库管线（独立于 API 服务，可命令行运行）。

    与 PubMedSearchAppService 的关系:
        - PubMedSearchPipeline: 纯搜索+入库，不含向量索引
        - PubMedSearchAppService: 搜索+入库+索引的完整编排，供 API 使用

    管道在内部调用 PostgresDB 的上下文管理器管理连接生命周期。
    """

    def __init__(self):
        self._retriever = PubMedRetriever()

    def run(self, query: str, max_results: int = None) -> list:
        """执行搜索入库管线。

        Args:
            query: PubMed 查询词
            max_results: 最大结果数，默认从配置读取

        Returns:
            list of dict: 每条文献的处理结果
                [{"pmid": "12345", "status": "inserted"|"skipped"|"failed", "title": "..."}]
        """
        if max_results is None:
            max_results = pubmed_conf.get("max_results", 5)

        results = []

        with PostgresDB() as db:
            # 1. 搜索
            pmids = self._retriever.search_pubmed(query)
            if not pmids:
                logger.info(f"查询 '{query}' 无结果")
                return results

            # 2. 逐篇处理
            for pmid in pmids:
                result = {"pmid": pmid, "status": "unknown", "title": ""}
                try:
                    if db.is_pmid_exist(pmid):
                        result["status"] = "skipped"
                        result["reason"] = "already_exists"
                        results.append(result)
                        continue

                    article_data = self._retriever.fetch_article_details(pmid)
                    article_data["search_query"] = query
                    db.insert_article(article_data)

                    result["status"] = "inserted"
                    result["title"] = article_data.get("article_info", {}).get("title", "")
                except Exception as e:
                    logger.error(f"处理 PMID {pmid} 失败: {e}")
                    result["status"] = "failed"
                    result["reason"] = str(e)

                results.append(result)

        return results


if __name__ == "__main__":
    test_query = "heart"
    pipeline = PubMedSearchPipeline()
    results = pipeline.run(test_query)
    for r in results:
        print(f"PMID: {r['pmid']}, Status: {r['status']}")
```

---

### 2.15 main.py — 启动入口

**文件**: `main.py` (修改)  
**依赖**: ServiceFactory, 各 Router

#### 2.15.1 修改内容

```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infrastructure.utils.config_handler import fastapi_conf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 现有 Router
from api.routers.rag_router import router as rag_router, set_rag_query_service

# 新增 Router
from api.routers.pubmed_router import (
    router as pubmed_router,
    set_pubmed_search_service,
    set_knowledge_management_service as set_km_for_pubmed,
)
from api.routers.knowledge_router import (
    router as knowledge_router,
    set_knowledge_management_service as set_km_for_knowledge,
)

from infrastructure.services.service_factory import ServiceFactory


# 初始化 FastAPI
app = FastAPI()

# 初始化服务工厂
factory = ServiceFactory()

# ── 初始化并注入服务 ───────────────────────────────

# 1. RAG 服务（现有）
rag_query_service = factory.get_rag_query_service()
set_rag_query_service(rag_query_service)

# 2. PubMed 服务（新增）
pubmed_search_service = factory.get_pubmed_search_service()
set_pubmed_search_service(pubmed_search_service)

# 3. 知识库管理服务（新增，注入到两个 Router）
knowledge_mgmt_service = factory.get_knowledge_management_service()
set_km_for_pubmed(knowledge_mgmt_service)
set_km_for_knowledge(knowledge_mgmt_service)

# ── 注册路由 ───────────────────────────────────────

app.include_router(rag_router)       # POST /rag/query
app.include_router(pubmed_router)    # POST /pubmed/search, GET /pubmed/articles, ...
app.include_router(knowledge_router) # GET /knowledge/stats

# ── CORS ───────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=fastapi_conf["FASTAPI_HOST"],
        port=fastapi_conf["FASTAPI_PORT"],
    )
```

> **说明**: `set_knowledge_management_service` 被注入到 `pubmed_router` 和 `knowledge_router` 两个模块中，但底层是同一个实例。导入时使用别名区分。

---

### 2.16 prompts/rag_summarize_prompt.txt — Prompt 增强

**文件**: `prompts/rag_summarize_prompt.txt` (修改)  
**变更**: 在现有 Prompt 末尾追加文献类型识别指引。

**追加内容**:

```text
### 文献类型识别与引文格式（新增）

参考资料中可能包含两类文献，你需要根据标注区分并采用不同的引文格式：

#### 1. 指导原则/机构文件
- 特征：标注为「指导原则文件」或参考资料中以《》括起的中文文件名
- 引文格式：[N] 《文件标题》.
- 示例：[1] 《疫苗临床试验技术指导原则》.

#### 2. PubMed 期刊文献
- 特征：标注为「PMID:」开头
- 引文格式：[N] Authors. Title. Journal. Year. PMID: xxxxx.
- 示例：[2] Baden LR, El Sahly HM, Essink B, et al. Efficacy and Safety of the mRNA-1273 SARS-CoV-2 Vaccine. N Engl J Med. 2020. PMID: 33301246.

#### 3. 内容重叠处理
当多个来源对同一主题有论述时：
- 先陈述指导原则的规定（规范性要求）
- 再引用学术文献中的具体研究数据或案例（研究证据）
- 用「指导原则要求……，相关研究进一步表明……」的结构区分角色

#### 4. 参考文献列表
- 正文中引用的上标数字必须与文末参考文献列表中的编号完全一致
- 参考文献列表按出现顺序排列，不允许重复
```

---

## 3. 全局枚举与错误码定义

### 3.1 文件位置

**文件**: `domain/constants.py` (新增)

### 3.2 摄入状态枚举

```python
from enum import Enum


class IngestionStatus(str, Enum):
    """PubMed 文献向量索引状态。"""
    UNINGESTED = "uningested"   # 未索引
    INGESTING  = "ingesting"    # 索引中
    INGESTED   = "ingested"     # 已索引
    FAILED     = "failed"       # 索引失败
```

### 3.3 业务错误码枚举

```python
class ErrorCode(int, Enum):
    """业务错误码。与 HTTP 状态码配合使用，放在 ApiResponse.code 中。

    约定:
        - 200-299: 成功
        - 400-499: 客户端错误
        - 500-599: 服务端错误
        - 1000-1999: 业务逻辑错误（用于 HTTP 200 下的部分失败）
    """
    # 成功
    SUCCESS = 200

    # 客户端错误 (400-499)
    BAD_REQUEST = 400
    PMID_NOT_FOUND = 404

    # 服务端错误 (500-599)
    INTERNAL_ERROR = 500
    SERVICE_NOT_INITIALIZED = 500
    PUBMED_API_UNAVAILABLE = 503
    PG_UNAVAILABLE = 503
    CHROMADB_UNAVAILABLE = 503

    # 业务级部分失败 (1000+)
    INGESTION_PARTIAL_FAILURE = 1001   # 批量索引中部分失败
    SEARCH_PARTIAL_FAILURE = 1002      # 搜索入库中部分 PMID 失败
```

### 3.4 摄入结果状态

```python
class IngestResultStatus(str, Enum):
    """单篇摄入操作的结果状态。"""
    INGESTED = "ingested"
    ALREADY_INGESTED = "already_ingested"
    FAILED = "failed"
```

### 3.5 搜索入库状态

```python
class SearchItemStatus(str, Enum):
    """单篇文献搜索入库结果状态。"""
    INGESTED = "ingested"    # 入库并索引成功
    STORED = "stored"        # 仅入库（auto_ingest=false 时）
    SKIPPED = "skipped"      # PMID 已存在，跳过
    FAILED = "failed"        # 入库或索引失败
```

---

## 4. 单元测试设计要点

### 4.1 可独立测试模块清单

每个模块的设计保证了可脱离完整系统做单元测试（通过 ABC 接口 mock / 依赖注入）：

| 模块                         | 独立测试方式                                           | Mock 依赖                                          |
| ---------------------------- | ----------------------------------------------------- | -------------------------------------------------- |
| `PubMedArticleIngester`      | 注入 mock PostgresDB + mock VectorStoreService        | `_db.get_article_by_pmid()` 返回预制 dict           |
| `PubMedSearchAppService`     | 注入 mock Retriever + mock DB + mock Ingester         | 所有外部调用                                       |
| `KnowledgeManagementService` | 注入 mock PostgresDB + mock VectorStoreService        | `_db.list_articles()` 返回预制列表                  |
| `VectorDocumentRetriever`    | 注入 mock VectorStoreService                          | `retriever.invoke()` 返回预制 LangchainDocument    |
| `PostgresDB`                 | 连接测试用 PostgreSQL 实例或用 `unittest.mock.patch`  | `psycopg2.connect`                                 |
| `PubMedRetriever`            | mock `Bio.Entrez.esearch` / `efetch`                  | 返回预制 XML/StringIO                              |
| `VectorStoreService`         | 连接临时 ChromaDB 目录或用 mock                        | ChromaDB / embedding                               |
| `RuleBasedKeywordExtractor`  | 纯函数，无需 mock                                      | 无                                                 |
| Router 层                    | FastAPI `TestClient` + 注入 mock ApplicationService   | 所有 Service                                       |

### 4.2 关键测试用例

#### 4.2.1 PubMedArticleIngester

| 用例 ID | 场景                           | 输入                                      | 预期输出                                                     |
| ------- | ------------------------------ | ----------------------------------------- | ------------------------------------------------------------ |
| TI-01   | 正常摄入                       | pmid="123", article 有完整数据             | status="ingested", chunk_count≥1                             |
| TI-02   | 重复摄入（幂等）               | pmid="123" 已 ingested, force=False        | status="already_ingested"                                    |
| TI-03   | 强制重摄入                     | pmid="123" 已 ingested, force=True         | status="ingested"，旧 chunks 先被删除                         |
| TI-04   | PMID 不存在于 PG              | pmid="xxx", PG 返回 None                   | status="failed", reason="not found"                          |
| TI-05   | 空摘要/文本                   | article 中 abstract 和 objectives 均为空   | status="failed", reason="Empty article text"                 |
| TI-06   | ChromaDB 写入失败              | `add_documents_direct` 抛异常               | status="failed", PG 状态更新为 failed                        |
| TI-07   | PG 状态更新失败（写入成功后） | `update_ingestion_status` 抛异常            | 仍返回 IngestResult("ingested")，异常被记录日志              |

#### 4.2.2 PubMedSearchAppService

| 用例 ID | 场景                           | 输入                                      | 预期输出                                                     |
| ------- | ------------------------------ | ----------------------------------------- | ------------------------------------------------------------ |
| TS-01   | 正常搜索入库索引               | query="test", max_results=3, auto_ingest=true | pmids_found=3, pmids_new=3, pmids_ingested=3                |
| TS-02   | 全部已存在                     | 3 个 PMID 全部 is_pmid_exist=True          | pmids_found=3, pmids_new=0, pmids_skipped=3                  |
| TS-03   | 部分失败                       | 第 2 篇 fetch 抛异常                       | pmids_found=3, pmids_new 含 1 个 failed，其余正常            |
| TS-04   | 不自动索引                     | auto_ingest=false                          | pmids_ingested=0，details 中 status 均为 "stored"            |
| TS-05   | PubMed API 完全不可用          | search_pubmed 抛异常                       | 异常向上抛出，Router 层转 503                                |

#### 4.2.3 KnowledgeManagementService

| 用例 ID | 场景                           | 输入                                      | 预期输出                                                     |
| ------- | ------------------------------ | ----------------------------------------- | ------------------------------------------------------------ |
| TK-01   | 正常列表查询                   | page=1, page_size=10                      | ArticleListData(total=N, page=1, articles len ≤ 10)          |
| TK-02   | 关键词搜索                     | search="vaccine"                          | 仅返回标题或摘要含 "vaccine" 的文献                           |
| TK-03   | 状态过滤                       | ingestion_status="uningested"             | 仅返回未索引文献                                             |
| TK-04   | 获取不存在的文献               | pmid="xxx"                                | 返回 None → Router 转 404                                    |
| TK-05   | 级联删除（两端都成功）         | pmid="123"                                | DeleteResultData(deleted_pg=True, deleted_vector=True)       |
| TK-06   | 级联删除（PG 失败）            | `delete_article` 抛异常                    | DeleteResultData(deleted_pg=False, deleted_vector=True)      |

#### 4.2.4 PostgresDB

| 用例 ID | 场景                           | 输入                                      | 预期输出                                                     |
| ------- | ------------------------------ | ----------------------------------------- | ------------------------------------------------------------ |
| TD-01   | 上下文管理器                   | `with PostgresDB() as db:`                | enter 时 connect, exit 时 close                              |
| TD-02   | 重复 connect                   | 连续调用 connect()                        | 先 close 旧连接再建立新连接                                  |
| TD-03   | 自动重连                       | 操作前 conn.closed=True                   | 自动调用 connect()                                           |
| TD-04   | SQL 注入防御                   | sort_by="; DROP TABLE--"                  | 白名单拦截，回退到默认 "created_at"                          |
| TD-05   | insert_article 重复 PMID       | 相同 PMID 插入两次                        | 第二次抛出唯一约束冲突异常                                   |

### 4.3 Mock 策略

```python
# 示例：测试 PubMedArticleIngester 的幂等性
from unittest.mock import MagicMock, patch

def test_ingest_already_ingested_returns_early():
    # 构建 mock 依赖
    mock_db = MagicMock()
    mock_db.get_article_by_pmid.return_value = {
        "pmid": "123",
        "ingestion_status": "ingested",
        "chunk_count": 3,
    }
    mock_vs = MagicMock()

    ingester = PubMedArticleIngester(postgres_db=mock_db, vector_store_service=mock_vs)
    result = ingester.ingest_article("123", force=False)

    assert result.status == "already_ingested"
    assert result.chunk_count == 3
    # 验证未调用写入相关方法
    mock_vs.add_documents_direct.assert_not_called()
    mock_db.update_ingestion_status.assert_not_called()
```

---

## 5. 性能优化细节

### 5.1 数据库查询优化

| 优化点                     | 方案                                                                           | 预期效果                         |
| -------------------------- | ------------------------------------------------------------------------------ | -------------------------------- |
| `list_articles` 分页       | 使用 `LIMIT / OFFSET`；先 `COUNT(*)` 再查数据                                  | 避免全表扫描返回                 |
| JSONB 字段查询             | GIN 索引：`CREATE INDEX idx_article_info_gin ON pubmed_articles USING GIN (article_info jsonb_path_ops)` | title/abstract ILIKE 模糊搜索加速 |
| `ingestion_status` 过滤    | B-tree 索引：`CREATE INDEX idx_ingestion_status ON pubmed_articles(ingestion_status)` | 状态过滤从 Seq Scan → Index Scan |
| `count_articles_by_status` | 单次查询使用 `COUNT(*) FILTER (WHERE ...)` 聚合                                | 1 次 Query vs 4 次 Query         |

### 5.2 PubMed API 调用优化

| 优化点                   | 方案                                                                  | 预期效果                         |
| ------------------------ | --------------------------------------------------------------------- | -------------------------------- |
| 请求间隔                 | `time.sleep(0.15)` 控制在 NCBI 10 req/s 限制内                       | 避免 HTTP 429 限流               |
| 批量 efetch              | 当 max_results > 5 时，单次 `efetch(id="1,2,3,...")` 替代多次单篇 fetch | API 调用量减少 N 倍              |
| Entrez.usehistory        | 已在 search_pubmed 中使用 `usehistory="y"`，efetch 使用 WebEnv/QueryKey | 大结果集下的稳定性和速度提升     |
| 指数退避重试             | 失败后 3s → 6s → 12s 三次重试                                        | 容忍网络抖动                     |

> **批量 efetch 优化详细方案**: `PubMedRetriever` 新增 `fetch_articles_batch(pmids: List[str]) → List[Dict]`，内部用 `Entrez.efetch(id=",".join(pmids))` 一次请求获取多篇文献。`PubMedSearchAppService.search_and_store()` 中当 `max_results > 5` 时自动切换为批量模式。

### 5.3 ChromaDB 写入优化

| 优化点                 | 方案                                                                      | 预期效果                     |
| ---------------------- | ------------------------------------------------------------------------- | ---------------------------- |
| 批量写入               | `add_documents_direct()` 一次写入所有 chunks（而非逐 chunk 调 add_document） | 减少 ChromaDB 内部 flush 次数 |
| 相同 metadata 批次     | 同一篇文献的所有 chunks 在一次 `add_documents` 中写入                      | 保证 chunk_index 连续         |
| 幂等保护               | `ingestion_status` 已 ingested → 跳过写入，零开销                          | 避免不必要的 embedding API 调用 |

### 5.4 Embedding API 成本控制

| 优化点               | 方案                                                                        |
| -------------------- | --------------------------------------------------------------------------- |
| 单批次上限           | `ingest_all_uningested()` 如果待处理文献 > 30 篇，分多批次执行，每批 ≤ 30 篇 |
| 预估 Token 数        | 每篇 PubMed 文献约 500-800 词 → 约 700-1100 tokens → 约 1-3 chunks          |
| 成本预警             | 在日志中记录每批次的总 token 数；若单批次 token > 50000，发出 WARNING 日志   |
| dry_run 模式         | 未来可扩展 `dry_run=True` 参数仅统计不实际写入，用于成本预估                  |

### 5.5 连接池

```python
# PostgresDB 可选连接池方案（后期优化）
# 当前通过单例 + 上下文管理器确保连接复用。
# 若并发量提升，可引入 psycopg2.pool.ThreadedConnectionPool：

from psycopg2.pool import ThreadedConnectionPool

class PostgresDB:
    _pool: Optional[ThreadedConnectionPool] = None

    @classmethod
    def init_pool(cls, minconn=1, maxconn=5):
        cls._pool = ThreadedConnectionPool(minconn, maxconn, **cls().conn_params)

    def __enter__(self):
        self.conn = self._pool.getconn()
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        return self

    def __exit__(self, *args):
        self.cur.close()
        self._pool.putconn(self.conn)
```

> **当前阶段不启用**，保留代码注释即可。等确认并发需求后再打开。

### 5.6 日志性能

- 批量索引时使用 `logger.debug()` 记录单篇进度，避免 INFO 级别日志洪水
- 统计性日志（批次开始/结束、成功/失败计数）使用 `logger.info()`
- 错误日志始终使用 `logger.error(exc_info=True)`，记录完整堆栈

---

## 附录 A: 配置文件变更速查

### A.1 config/pubmed.yml 新增项

```yaml
# 在现有字段后追加
auto_ingest: true              # 搜索后是否自动触发向量索引
request_interval: 0.15         # NCBI API 请求间隔 (秒)
ingestion_chunk_size: 800      # PubMed 文章分块大小（若与 chroma.yml 重复则可省略）
ingestion_chunk_overlap: 200   # PubMed 文章分块重叠
```

### A.2 config/chroma.yml 新增项

```yaml
# 在现有字段后追加
pubmed_chunk_size: 800
pubmed_chunk_overlap: 200
pubmed_separator: ["\n\n", "\n", ". ", "! ", "? ", "。", "！", "？", " ", ""]
```

### A.3 数据库 DDL

```sql
-- 新增字段（若不存在则添加）
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

---

## 附录 B: 关键方法签名速查表

| 模块                          | 方法                                                              | 返回值                     |
| ----------------------------- | ----------------------------------------------------------------- | -------------------------- |
| `PubMedSearchAppService`      | `search_and_store(query, max_results, auto_ingest)`               | `PubMedSearchData`         |
|                               | `ingest_all_uningested()`                                         | `IngestBatchData`          |
| `KnowledgeManagementService`  | `list_articles(page, page_size, search, status, sort, order)`     | `ArticleListData`          |
|                               | `get_article_detail(pmid)`                                        | `Optional[ArticleDetailData]` |
|                               | `delete_article(pmid)`                                            | `DeleteResultData`         |
|                               | `get_knowledge_stats()`                                           | `KnowledgeStatsData`       |
| `PubMedArticleIngester`       | `ingest_article(pmid, force=False)`                               | `IngestResult`             |
|                               | `batch_ingest(pmids, force=False)`                                | `List[IngestResult]`       |
|                               | `ingest_all_uningested(force=False)`                              | `List[IngestResult]`       |
|                               | `remove_from_vector_store(pmid)`                                  | `int`                      |
| `PostgresDB`                  | `get_article_by_pmid(pmid)`                                       | `Optional[Dict]`           |
|                               | `list_articles(...)`                                              | `Tuple[List[Dict], int]`  |
|                               | `update_ingestion_status(pmid, status, error, chunk_count, ...)`  | `None`                     |
|                               | `count_articles_by_status()`                                      | `Dict[str, int]`           |
|                               | `delete_article(pmid)`                                            | `bool`                     |
| `VectorStoreService`          | `add_documents_direct(documents)`                                 | `List[str]` (IDs)          |
|                               | `delete_by_metadata_filter(filter)`                               | `int`                      |
|                               | `get_collection_stats()`                                          | `Dict`                     |
|                               | `get_splitter(source_type)`                                       | `RecursiveCharacterTextSplitter` |
| `VectorDocumentRetriever`     | `format_documents_for_context(documents)`                         | `str`                      |
| `PubMedRetriever`             | `fetch_article_details(pmid)`                                     | `Dict`                     |
|                               | `search_pubmed(query)`                                            | `List[str]`                |
| `PubMedSearchPipeline`        | `run(query, max_results)`                                         | `List[Dict]`               |
