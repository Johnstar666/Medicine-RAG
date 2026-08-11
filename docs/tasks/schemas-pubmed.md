# 模块: schemas/pubmed.py — PubMed 接口 Schema

**文件路径**: `schemas/pubmed.py` (新增)  
**优先级**: P0 (Phase 1 — Schema 层)  
**前置依赖**: `schemas/common.py` (复用 `ApiResponse` 概念，但不直接 import)  
**被依赖模块**: `pubmed_router.py`, `pubmed_search_service.py`

---

## 子任务清单

### 文件创建

- [ ] **T01** — 创建 `schemas/pubmed.py` 文件，添加文件头注释和 import 语句（`pydantic.BaseModel`, `Field`, `field_validator`, `Optional`, `List`, `Dict`, `Any`, `datetime`）

### Pydantic 模型定义（按依赖顺序）

- [ ] **T02** — 定义 `PubMedSearchRequest(BaseModel)`：
  - `query: str` (min_length=1, max_length=500)
  - `max_results: int` (default=5, ge=1, le=30)
  - `auto_ingest: bool` (default=True)
  - `@field_validator("query")` — 校验不能为空白字符串
- [ ] **T03** — 定义 `SearchDetailItem(BaseModel)`：
  - `pmid: str`, `status: str`, `title: str=""`, `reason: str=""`
- [ ] **T04** — 定义 `PubMedSearchData(BaseModel)`：
  - `query: str`, `pmids_found: int`, `pmids_new: int`, `pmids_ingested: int`, `pmids_skipped: int`, `pmids_failed: int`, `details: List[SearchDetailItem]`
- [ ] **T05** — 定义 `ArticleSummary(BaseModel)`：
  - `pmid: str`, `title: str=""`, `authors: List[str]=[]`, `journal: str=""`, `publish_date: str=""`, `abstract_preview: str=""`, `is_free_download: bool=False`, `ingestion_status: str="uningested"`, `ingested_at: Optional[datetime]=None`, `study_groups: List[str]=[]`, `created_at: Optional[datetime]=None`
- [ ] **T06** — 定义 `ArticleListData(BaseModel)`：
  - `total: int`, `page: int`, `page_size: int`, `articles: List[ArticleSummary]`
- [ ] **T07** — 定义 `ArticleDetailData(BaseModel)`：
  - `pmid: str`, `article_info: Dict[str, Any]={}`, `study_groups: List[str]=[]`, `results_info: Dict[str, Any]={}`, `objectives: str=""`, `is_free_download: bool=False`, `ingestion_status: str="uningested"`, `chunk_count: Optional[int]=None`, `vector_ids: Optional[List[str]]=None`, `ingested_at: Optional[datetime]=None`, `created_at: Optional[datetime]=None`, `updated_at: Optional[datetime]=None`, `search_query: Optional[str]=None`, `ingestion_error: Optional[str]=None`
- [ ] **T08** — 定义 `IngestResultItem(BaseModel)`：
  - `pmid: str`, `status: str`, `chunk_count: int=0`, `reason: str=""`
- [ ] **T09** — 定义 `IngestBatchData(BaseModel)`：
  - `total_uningested: int=0`, `ingested: int=0`, `failed: int=0`, `details: List[IngestResultItem]=[]`
- [ ] **T10** — 定义 `DeleteResultData(BaseModel)`：
  - `pmid: str`, `deleted_pg: bool`, `deleted_vector: bool`

### 辅助模型

- [ ] **T11** — 定义 `IngestBatchRequest(BaseModel)`（用于 POST /pubmed/ingest/batch 请求体）：
  - `pmids: List[str]` (min_length=1, max_length=50), `force: bool=False`

### 自测验证

- [ ] **T12** — 编写自测脚本：
  - 用合法数据实例化每个模型，验证 `.model_dump()` 成功
  - 用非法数据（空 query、max_results=0）实例化 `PubMedSearchRequest`，验证 `ValidationError`
  - 验证 `query` 的 `field_validator` 能正确拒绝仅含空白的字符串
- [ ] **T13** — 验证 `IngestBatchRequest.pmids` 的长度边界（空列表拒绝、51 个元素拒绝、50 个元素通过）
