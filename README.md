# 生物药物资料检索知识库 - RAG 实习项目（芯筹科技）

基于 PubMed-RAG 整合的知识库系统：支持本地指导原则文档与 PubMed 期刊文献的混合检索、向量索引与 LLM 生成回答（含温哥华引文格式）。

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **向量数据库**: ChromaDB（单一 collection `agent`，`source_type` 区分 local_file / pubmed）
- **关系数据库**: PostgreSQL（`pubmed_articles` 表，JSONB 字段 + ingestion_status 追踪）
- **LLM / Embedding**: DashScope（`qwen3-max` 对话 / `text-embedding-v4` 向量）
- **PubMed API**: NCBI Entrez（Biopython）
- **代码质量**: ruff + mypy + pytest + pytest-cov

## 环境准备

```bash
conda env create -f environment.yml
conda activate medicine-rag
pip install -r requirements.txt

# 数据库迁移（幂等）
psql -U postgres -d medicineKB -f docs/ddl_migration.sql
```

> 环境变量 `DASHSCOPE_API_KEY` 为 LLM/Embedding 必需，未设置时仅启动、搜索、入库可用，RAG 生成回答不可用。

### DashScope key 配置（二选一）

1. **`.env` 文件（推荐）**：在项目根目录创建 `.env`（已被 `.gitignore` 忽略，不会提交）：
   ```bash
   # .env
   DASHSCOPE_API_KEY=sk-xxxx
   ```
   应用启动时会自动加载（config_handler 接入 python-dotenv，`override=False`：显式设置的环境变量优先于 `.env`）。
2. **系统环境变量**：设置 `DASHSCOPE_API_KEY` 后启动，两种方式效果相同。

## 启动

```bash
python main.py
# 服务默认监听 http://localhost:8000（详见 config/fastapi.yml）
# Swagger UI: http://localhost:8000/docs
```

### 前端界面

`frontend/index.html` 为单文件可视化界面（RAG 双源问答 + 引文证据账本 + PubMed 检索），对接上述 API：

```bash
python -m http.server 8080 --directory frontend
# 浏览器访问 http://localhost:8080/index.html
```

- 后端 CORS 已开放（`allow_origins=["*"]`），无需额外配置即可跨源调用。
- 回答中的引文标记（`[N]` 或上标 `¹²³`）渲染为按来源着色的可点击芯片（红=本地指导原则、青=PubMed 文献），点击定位到下方证据账本对应来源卡，引文可一键复制。
- 后端地址默认 `http://localhost:8000`，可通过 `localStorage["medicine-rag-api"]` 覆盖。

## API 端点

### RAG 查询（后向兼容）

| 方法 | 路径        | 说明                                             |
| ---- | ----------- | ------------------------------------------------ |
| POST | `/rag/query` | 混合来源 RAG 查询，返回温哥华格式引文回答（支持 local_file + pubmed） |

### PubMed 文献

| 方法   | 路径                          | 说明                                         |
| ------ | ----------------------------- | -------------------------------------------- |
| POST   | `/pubmed/search`              | 触发 PubMed 搜索并入库（可选 auto_ingest 向量索引） |
| GET    | `/pubmed/articles`            | 分页浏览/搜索本地 PubMed 文献库（支持 status/sort 过滤） |
| GET    | `/pubmed/articles/{pmid}`     | 获取单篇文献完整详情                         |
| POST   | `/pubmed/ingest/{pmid}`       | 手动索引单篇文献（`?force=true` 强制重索引） |
| POST   | `/pubmed/ingest/batch`        | 批量索引指定 PMID 列表                       |
| POST   | `/pubmed/ingest/all-uningested` | 一键索引所有未入库文献                     |
| DELETE | `/pubmed/articles/{pmid}`     | 删除文献（PostgreSQL 记录 + ChromaDB 向量块级联） |

### 知识库统计

| 方法 | 路径             | 说明                                             |
| ---- | ---------------- | ------------------------------------------------ |
| GET  | `/knowledge/stats` | 知识库总体统计（本地文档数、PubMed 文献数、向量块数、按来源分组） |

## 引文格式约定

| 来源类型      | 引文格式                                   |
| ------------- | ------------------------------------------ |
| 本地指导原则  | `[N] 《文件标题》.`                        |
| PubMed 文献   | `[N] Authors. Title. Journal. Year. PMID: xxxxx.` |

## 项目结构

```
api/routers/          表示层路由（rag / pubmed / knowledge）
application/services/ 应用服务层
domain/               领域实体与常量
infrastructure/       基础设施（persistence / services / utils / models）
pubmed/               PubMed 检索子系统
schemas/              Pydantic 请求/响应模型
prompts/              LLM Prompt 模板
config/               YAML 配置文件
tests/                单元测试（镜像源码目录结构）
docs/                 设计文档与任务进度
```

## 测试与代码质量

```bash
pytest tests/ -q --cov=. --cov-fail-under=70
ruff check --select E,F,I,N,UP .
mypy --ignore-missing-imports .
```
