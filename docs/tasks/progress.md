# 项目任务进度总览

> **项目**: Medicine_RAG_Project — PubMed-RAG 系统整合  
> **最后更新**: 2026-08-11  
> **总模块数**: 21  
> **总子任务数**: ~210

---

## 全局进度条

```
Phase 1  Schema & Config     ░░░░░░░░░░░░░░░░░░░░   0 / 6  模块完成
Phase 2  基础设施             ░░░░░░░░░░░░░░░░░░░░   0 / 7  模块完成
Phase 3  应用服务             ░░░░░░░░░░░░░░░░░░░░   0 / 2  模块完成
Phase 4  API 路由             ░░░░░░░░░░░░░░░░░░░░   0 / 2  模块完成
Phase 5  组装                 ░░░░░░░░░░░░░░░░░░░░   0 / 2  模块完成
Phase 6  Prompt               ░░░░░░░░░░░░░░░░░░░░   0 / 1  模块完成
Phase 7  集成测试             ░░░░░░░░░░░░░░░░░░░░   0 / 1  模块完成
═══════════════════════════════════════════════════════════════
总计                          ░░░░░░░░░░░░░░░░░░░░   0 / 21 模块完成
```

---

## Phase 1: Schema & Config（基础依赖）

| #   | 模块                        | 类型 | 优先级 | 子任务数 | 状态 | 依赖                                     |
| --- | --------------------------- | ---- | ------ | -------- | ---- | ---------------------------------------- |
| 1.1 | domain-constants            | 新增 | P0     | 8        | ⬜   | 无                                       |
| 1.2 | schemas-common              | 新增 | P0     | 6        | ⬜   | 无                                       |
| 1.3 | schemas-pubmed              | 新增 | P0     | 13       | ⬜   | schemas-common                           |
| 1.4 | schemas-knowledge           | 新增 | P0     | 5        | ⬜   | 无                                       |
| 1.5 | config-files                | 修改 | P1     | 12       | ⬜   | 无                                       |
| 1.6 | database-ddl                | 新增 | P1     | 17       | ⬜   | 无                                       |

## Phase 2: 基础设施

| #   | 模块                        | 类型 | 优先级 | 子任务数 | 状态 | 依赖                                     |
| --- | --------------------------- | ---- | ------ | -------- | ---- | ---------------------------------------- |
| 2.1 | postgres-db                 | 重构 | P0     | 27       | ⬜   | database-ddl, config-files               |
| 2.2 | vector-store                | 修改 | P1     | 15       | ⬜   | config-files                             |
| 2.3 | pubmed-ingester             | 新增 | P0     | 23       | ⬜   | postgres-db, vector-store, domain-constants, config-files |
| 2.4 | pubmed-retriever            | 修改 | P1     | 16       | ⬜   | 无                                       |
| 2.5 | document-retriever-impl     | 修改 | P2     | 12       | ⬜   | 无                                       |
| 2.6 | paper-search                | 重构 | P2     | 12       | ⬜   | postgres-db, pubmed-retriever             |
| 2.7 | (rag_router — 无代码变更)   | -    | -      | 0        | ✅   | 行为由下游模块自动增强                    |

## Phase 3: 应用服务

| #   | 模块                        | 类型 | 优先级 | 子任务数 | 状态 | 依赖                                     |
| --- | --------------------------- | ---- | ------ | -------- | ---- | ---------------------------------------- |
| 3.1 | pubmed-search-service       | 新增 | P1     | 16       | ⬜   | postgres-db, pubmed-ingester, pubmed-retriever, domain-constants |
| 3.2 | knowledge-management-service | 新增 | P1     | 19       | ⬜   | postgres-db, vector-store, pubmed-ingester, schemas-pubmed, schemas-knowledge |

## Phase 4: API 路由

| #   | 模块                        | 类型 | 优先级 | 子任务数 | 状态 | 依赖                                     |
| --- | --------------------------- | ---- | ------ | -------- | ---- | ---------------------------------------- |
| 4.1 | pubmed-router               | 新增 | P1     | 20       | ⬜   | schemas-pubmed, schemas-common, pubmed-search-service, knowledge-management-service |
| 4.2 | knowledge-router            | 新增 | P2     | 10       | ⬜   | schemas-knowledge, schemas-common, knowledge-management-service |

## Phase 5: 组装

| #   | 模块                        | 类型 | 优先级 | 子任务数 | 状态 | 依赖                                     |
| --- | --------------------------- | ---- | ------ | -------- | ---- | ---------------------------------------- |
| 5.1 | service-factory             | 修改 | P1     | 14       | ⬜   | 所有被注入模块 (Phase 2-3)               |
| 5.2 | main-py                     | 修改 | P1     | 12       | ⬜   | service-factory + 所有 Router (Phase 4)  |

## Phase 6: Prompt

| #   | 模块                        | 类型 | 优先级 | 子任务数 | 状态 | 依赖                                     |
| --- | --------------------------- | ---- | ------ | -------- | ---- | ---------------------------------------- |
| 6.1 | prompt-enhancement          | 修改 | P3     | 9        | ⬜   | document-retriever-impl                  |

## Phase 7: 集成测试与收尾

| #   | 模块                        | 类型 | 优先级 | 子任务数 | 状态 | 依赖                                     |
| --- | --------------------------- | ---- | ------ | -------- | ---- | ---------------------------------------- |
| 7.1 | integration-test            | 新增 | P1     | 15       | ⬜   | main-py (全系统可启动)                   |

---

## 依赖拓扑图

```
Phase 1                 Phase 2                  Phase 3              Phase 4           Phase 5       Phase 6  Phase 7
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

domain-constants ─────────────────────────────────────────────┐
                                                               │
schemas-common ────────────────────────────────────────────────┤
                                                               │
schemas-pubmed ────────────────────────────────────────────────┤
                                                               │
schemas-knowledge ─────────────────────────────────────────────┤
                                                               │
config-files ──────┬──► vector-store ──► pubmed-ingester ──────┼──► pubmed-search-service ──► pubmed-router ──┐
                   │                     │                     │                                           │
                   │                     │                     │                                           │
database-ddl ──────┼──► postgres-db ─────┘                     │                                           │
                   │         │                                  │                                           │
                   │         │                                  ├──► knowledge-mgmt-service ──┬──► pubmed-router ──┤
                   │         │                                  │                              │                    │
                   │         │                                  │                              ├──► knowledge-router │
                   │         │                                  │                              │                    │
pubmed-retriever ──┴─────────┼──► paper-search                  │                              │                    │
                             │                                  │                              │                    │
document-retriever-impl ─────┼──────────────────────────────────┤                              │                    │
                             │                                  │                              │                    │
                             │                                  │                              │                    │
                             └──────────────────────────────────┴──────────────────────────────┴────────────────────┤
                                                                                                                    │
service-factory ◄── 所有 Phase 2-3 模块 ─────────────────────────────────────────────────────────────────────────────┤
       │                                                                                                            │
main-py ◄── service-factory + 所有 Router ──────────────────────────────────────────────────────────────────────────┤
       │                                                                                                            │
       └──────────────────────────────────────────────────────────────────► prompt-enhancement                      │
                                                                                                                    │
                                                                                                     integration-test ◄── main-py
```

---

## 并行开发建议

同一 Phase 内无直接依赖的模块可并行开发：

### 第 1 波（可并行 6 路）
```
Agent A → domain-constants
Agent B → schemas-common
Agent C → schemas-pubmed
Agent D → schemas-knowledge
Agent E → config-files
Agent F → database-ddl
```

### 第 2 波（第 1 波完成后，可并行 4 路）
```
Agent A → pubmed-retriever
Agent B → postgres-db（依赖 database-ddl, config-files）
Agent C → vector-store（依赖 config-files）
Agent D → document-retriever-impl
```

### 第 3 波（第 2 波完成后，可并行 2 路）
```
Agent A → pubmed-ingester（依赖 postgres-db, vector-store, domain-constants）
Agent B → paper-search（依赖 postgres-db, pubmed-retriever）
```

### 第 4 波（第 3 波完成后，可并行 2 路）
```
Agent A → pubmed-search-service（依赖 postgres-db, pubmed-ingester, pubmed-retriever）
Agent B → knowledge-management-service（依赖 postgres-db, vector-store, pubmed-ingester）
```

### 第 5 波（第 4 波完成后，可并行 2 路）
```
Agent A → pubmed-router（依赖 schemas-pubmed, pubmed-search-service, knowledge-management-service）
Agent B → knowledge-router（依赖 schemas-knowledge, knowledge-management-service）
```

### 第 6 波（第 5 波完成后，1 路）
```
Agent A → service-factory → main-py
```

### 第 7 波（第 6 波完成后，可并行 2 路）
```
Agent A → prompt-enhancement
Agent B → integration-test
```

---

## 验收检查点

### 检查点 1: Schema 层可用 ✓
- [ ] 所有 Pydantic 模型可实例化且校验正确
- [ ] `domain/constants.py` 枚举值完整

### 检查点 2: 基础设施层可用 ✓
- [ ] `postgres_db.py` 所有 CRUD 方法可独立测试通过
- [ ] `pubmed_ingester.py` 幂等性和异常处理测试通过
- [ ] `vector_store.py` 新增 4 个方法测试通过
- [ ] `pubmed_retriever.py` 返回结构含全部扩展字段

### 检查点 3: 应用服务层可用 ✓
- [ ] `PubMedSearchAppService` 单篇失败不中断批次
- [ ] `KnowledgeManagementService` 跨源统计聚合正确

### 检查点 4: API 层可用 ✓
- [ ] 所有 9 个端点 HTTP 响应格式符合 ApiResponse 规范
- [ ] Swagger UI 完整显示所有端点

### 检查点 5: 全系统集成 ✓
- [ ] `python main.py` 启动无错误
- [ ] `POST /pubmed/search` → 搜索入库索引全链路成功
- [ ] `POST /rag/query` → 返回混合来源结果 + 温哥华引文格式
- [ ] `GET /knowledge/stats` → 统计数据正确
- [ ] `DELETE /pubmed/articles/{pmid}` → PG + ChromaDB 级联删除
