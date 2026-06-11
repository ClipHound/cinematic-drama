# AI API 接入 & RAG 语义搜索 —— 工程实施计划

> 状态：RAG 基础版已实施；当前本地库 238 条 SearchDocument 已生成 embedding  
> 日期：2026-06-11  
> 目标：接入 AI API，利用 RAG 实现"用自然语言搜剧"——用户描述剧情/情绪/角色关系，系统返回可点击播放的匹配剧集。

---

## 0. 本次落地结果（2026-06-11）

### 0.1 已完成

| 项 | 状态 | 说明 |
|----|------|------|
| Rich Document Builder | ✅ 已完成 | 新增 `django-backend/apps/search/document_builder.py`，从 full-delivery zip/解压目录读取 `episode_summaries`、`characters_index`、`understanding_report`、逐集 `understanding/interactions`，生成剧级/集级 rich body。 |
| SearchDocument 入库命令 | ✅ 已完成 | 新增 `python manage.py build_search_documents --source <zip-or-dir> --all`，支持全量/单剧、dry-run、缺 catalog 自动创建、变更后自动把 embedding 状态置为 `pending` 并清空旧向量。 |
| 旧导入链路复用 builder | ✅ 已完成 | `import_legacy_content` 不再写浅层 summary，而是复用同一套 rich document 逻辑。 |
| Embedding 构建命令 | ✅ 已增强 | `build_search_embeddings` 新增 `--sleep` 参数；provider 调用支持 429/5xx 重试退避，用于硅基流动/其他 OpenAI 兼容服务的批量限流。 |
| AI 对话搜索 | ✅ 已有并调优 | `/api/ai/chat` 已支持 SSE、工具检索、推荐卡片；system prompt 已约束不得编造，需基于工具结果推荐。 |
| 关键词降级搜索 | ✅ 已增强 | 无 embedding 或 embedding 服务不可用时，按多关键词/中文 n-gram 打分排序，不再只做整句 `icontains`。 |
| 测试 | ✅ 已补充 | 新增交付 zip → SearchDocument 的 Django 集成测试；`python manage.py test` 已通过。 |

### 0.2 已对真实数据执行

数据源：

```powershell
./drama-understanding-agent/outputs/full-delivery/full-delivery-all.zip
```

执行结果：

```text
10 部剧
228 集
238 条 SearchDocument（10 drama + 228 episode）
embedding_status = ready（238/238）
```

抽样验证：

- `示例剧A 第 3 集` 的 body 已包含 `【本集摘要】`、`【情绪基调】`、`【悬念钩子】`、`【出场角色】`、`【关键事件】`、`【相关线索】`、`【互动看点】`。
- 无 embedding 状态下，`角色X 继母 复仇` 可通过关键词降级检索把《示例剧A》第 3 集排到第一；`继母 陷害 复仇` 这类泛化查询会优先返回全库中词频更高的复仇剧集，后续 embedding 上线后再用语义相似度提升泛化查询排序。

### 0.3 API 配置与重建命令

硅基流动是 OpenAI 兼容接口，官方文档给出的 CN Base URL 是：

```powershell
https://api.siliconflow.cn/v1
```

当前环境已检测到 Chat/Embedding 配置可用。后续如果换 key、换模型或重新部署，配置：

```powershell
$env:AI_CHAT_BASE_URL="https://api.siliconflow.cn/v1"
$env:AI_CHAT_API_KEY="<your-key>"
$env:AI_CHAT_MODEL="<支持 chat/completions 与 tools 的模型>"

$env:AI_EMBEDDING_BASE_URL="https://api.siliconflow.cn/v1"
$env:AI_EMBEDDING_API_KEY="<your-key>"
$env:AI_EMBEDDING_MODEL="<embedding 模型>"
$env:AI_EMBEDDING_DIMENSIONS="0"
$env:AI_HTTP_MAX_RETRIES="2"
$env:AI_HTTP_RETRY_BASE_SECONDS="0.8"
```

如果 `SearchDocument` body 变化、embedding 模型变化，或要强制重建向量，执行：

```powershell
cd django-backend
python manage.py build_search_embeddings --all --sleep 0.2
```

参考：

- 硅基流动 Chat Completions 官方文档：`https://docs.siliconflow.cn/en/api-reference/chat-completions/chat-completions`
- 硅基流动 Embeddings 官方文档：`https://docs.siliconflow.cn/en/api-reference/embeddings/create-embeddings`
- 硅基流动模型列表官方文档：`https://docs.siliconflow.cn/en/api-reference/models/get-model-list`

---

## 1. 当前实现盘点

### 1.1 已有的东西

| 层次 | 组件 | 文件 | 成熟度 |
|------|------|------|--------|
| **AI API 配置** | OpenAI 兼容的 Chat + Embedding 端点配置，支持 `.env`、embedding dimensions、provider 重试参数 | `config/settings.py` | ✅ 就绪 |
| **Embedding 调用** | `embed_text()` 调用 `/embeddings` API | `apps/search/services.py:41-52` | ✅ 就绪 |
| **语义搜索** | `cosine_similarity()` + `search_catalog()` —— embedding 搜索 + 多关键词回退 | `apps/search/services.py` | ✅ 就绪 |
| **Hybrid 排序** | 向量相似度 + 关键词覆盖加权 + 多词剧情 query 的 episode 轻微优先 | `apps/search/services.py` | ✅ 就绪 |
| **Function Calling** | `choose_search_query()` —— LLM 决定搜索 query，调用 `search_catalog` tool | `apps/search/services.py` | ✅ 就绪 |
| **Streaming Chat** | `iter_chat_text()` —— SSE 流式生成 + 推荐卡片 | `apps/search/services.py` | ✅ 就绪 |
| **API 端点** | `POST /api/ai/chat` SSE 流、`POST /api/ai/search` 语义/降级检索 | `config/api.py` | ✅ 就绪 |
| **前端页面** | AiSearchPage —— starter 快捷词、流式对话、推荐卡片 | `src/pages/AiSearchPage.tsx` | ✅ 就绪 |
| **SearchDocument 模型** | `embedding_status` + `embedding_vector` 字段 | `apps/search/models.py` | ✅ 就绪 |
| **Rich 文档构建命令** | `build_search_documents` —— 从 full-delivery zip/目录刷新剧级与集级 SearchDocument | `apps/search/management/commands/build_search_documents.py` | ✅ 就绪 |
| **Embedding 构建命令** | `build_search_embeddings` —— 批量生成向量，支持 `--sleep` 节流 | `apps/search/management/commands/build_search_embeddings.py` | ✅ 就绪 |
| **理解数据** | full-delivery zip —— 角色、关系、剧情事件、线索、摘要、互动点、分支叙事 | `./outputs/full-delivery/full-delivery-all.zip` | ✅ 已入库 |

### 1.2 之前断点与当前状态

```
理解 Agent 产出                       SearchDocument 当前内容
─────────────────────────────────    ────────────────────────
characters (角色名/描述/状态)    →    ✅ 已进入剧级和集级 body/tags
relationships (角色关系网)       →    ✅ 已进入剧级 body
plot_events (剧情事件)           →    ✅ 已进入对应集级 body
plot_threads (主线/支线/伏笔)    →    ✅ 已进入剧级和相关集级 body/tags
episode_summaries (摘要/悬念)    →    ✅ 已进入集级 body
InteractionPoint (互动点)        →    ✅ 已进入剧级和集级 body
branch_narrative (分支叙事)      →    ✅ 已进入剧级 body/tags
                                      
SearchDocument.body 实际内容:         分层结构化 rich text
SearchDocument.tags 实际内容:         题材 + 角色 + 情绪 + 线索 + 互动组件
```

当前本地库 `embedding_vector` 已完成。无 key 时系统仍能用 rich body 做关键词降级检索；有 key 且文档状态为 `ready` 时，会优先走语义向量检索。

---

## 2. 当前架构

```
                              ┌──────────────────────────────┐
  full-delivery-all.zip       │  离线理解交付包                │
                              │  摘要/角色/关系/事件/互动点    │
        │                     └──────────────┬───────────────┘
        │ 读取交付数据                        │
        ▼                                    ▼
  ┌──────────────────┐          ┌──────────────────────────┐
  │ document_builder │          │ import_legacy_content     │
  │ 解析 zip/目录      │──────────► 调用 builder 填充 body    │
  │ 构建 rich text    │          │ build_search_documents    │
  └──────────────────┘          └──────────┬───────────────┘
                                           │
                                           ▼
                              ┌──────────────────────────┐
                              │  SearchDocument (Django)  │
                              │  body = 结构化 rich text  │
                              │  tags = 题材+角色+情绪    │
                              │  embedding_status=pending │
                              └──────────┬───────────────┘
                                         │
                                         ▼
                              ┌──────────────────────────┐
                              │ build_search_embeddings   │
                              │ (已有) embed_text() 生成  │
                              │ embedding_vector          │
                              └──────────┬───────────────┘
                                         │
                                         ▼
                              ┌──────────────────────────┐
                              │  search_catalog() (已有)  │
                              │  query → embed → cosine   │
                              │  → Top-K Drama/Episode    │
                              └──────────┬───────────────┘
                                         │
                                         ▼
                              ┌──────────────────────────┐
                              │  POST /api/ai/chat (已有) │
                              │  LLM tool call → search   │
                              │  → SSE 流式回复 + 卡片    │
                              └──────────────────────────┘
```

---

## 3. 执行手册

### 3.1 刷新 RAG 文档

```powershell
cd django-backend
python manage.py build_search_documents --source "../drama-understanding-agent/outputs/full-delivery/full-delivery-all.zip" --all
```

常用参数：

- `--drama-slug example-drama-a`：只刷新单部剧。
- `--dry-run`：只查看会改哪些文档，不写库。
- `--no-create-catalog`：只更新已有 catalog，不自动创建缺失剧/集。

### 3.2 配置硅基流动

PowerShell 示例：

```powershell
$env:AI_CHAT_BASE_URL="https://api.siliconflow.cn/v1"
$env:AI_CHAT_API_KEY="<your-key>"
$env:AI_CHAT_MODEL="<chat-model-with-tools>"

$env:AI_EMBEDDING_BASE_URL="https://api.siliconflow.cn/v1"
$env:AI_EMBEDDING_API_KEY="<your-key>"
$env:AI_EMBEDDING_MODEL="<embedding-model>"
```

模型选择建议：

- Chat 模型必须支持 OpenAI 兼容 `/chat/completions`，最好支持 `tools` / function calling；不支持 tools 时系统仍会退回使用用户原始 query 检索。
- Embedding 模型必须支持 `/embeddings`，所有 `SearchDocument` 要用同一个 embedding 模型生成向量；切换 embedding 模型后必须 `--all` 重建。
- 具体模型名从硅基流动模型列表复制完整 id。

### 3.3 构建 embedding

```powershell
cd django-backend
python manage.py build_search_embeddings --all --sleep 0.2
```

构建后检查：

```powershell
python manage.py shell -c "from django.db.models import Count; from apps.search.models import SearchDocument; print(list(SearchDocument.objects.values('embedding_status').annotate(c=Count('id'))))"
```

当前本地库已达到：`ready` 数量 238，`failed` 数量 0。

### 3.4 验证搜索质量

建议固定 10 条 query 做 recall@3 人工评估：

| 类别 | 示例 query | 期望匹配 |
|------|-----------|----------|
| 角色名 | "皇帝身边的谋士" | 包含谋士角色的剧集 |
| 关系 | "师徒之间反目成仇" | 有师徒关系冲突的剧集 |
| 剧情事件 | "朝堂上被陷害" | 包含朝堂 conflict 事件的剧集 |
| 情绪 | "虐心的离别场景" | mood=悲伤 或有离别事件的剧集 |
| 类型+剧情 | "古装爽剧打脸反转" | 古装+爽剧标签、有 twist 事件的剧集 |
| 悬念 | "结尾留了悬念的那集" | cliffhanger 非空的剧集 |
| 互动点 | "能投票预测的剧情" | 有 prediction 类型交互点的剧集 |
| 模糊描述 | "主角身份被揭穿" | reveal 类型的剧情事件 |
| 混合 | "想看比武招亲那集" | 特定剧情事件 + 特定集数 |
| 冷门 | "有没有科幻题材" | 标签匹配 + 语义匹配 |

当前 smoke 结果：

| Query | Top 结果概览 |
|-------|--------------|
| `角色X 继母 复仇` | 《示例剧A》第 14、3、19 集进入前列，剧级文档降到具体集数之后 |
| `想看比武招亲反转` | 《示例剧A》第 7、8、9、10 集连续命中 |
| `农民工骑摩托回东北过年` | 《示例剧C》第 1 集 Top-1 |
| `古墓盗墓遇到毒虫` | 《示例剧D》第 67、76、68 集 Top-3 |
| `女主葬礼后复仇` | 《示例剧E》第 1 集 Top-1 |
| `修仙爽剧` | 《示例剧F》相关集数 Top-5 |

### 3.5 端到端测试

```powershell
cd ./django-backend
python manage.py runserver 127.0.0.1:8787
```

另开一个终端：

```powershell
cd cinematic-drama-app-frontend-source
npm run dev
```

打开前端 `/ai` 页面后测试：

1. 输入 starter 快捷词 → 应返回推荐卡片
2. 输入自定义描述 → AI 应调用工具搜索
3. 输入"你好"等非搜索类消息 → AI 应普通回复
4. 输入完全不存在的剧情 → AI 应说明未找到

验收标准：

- 用户输入 → AI 自动决定是否调用 search_catalog → 卡片展示
- 卡片点击后跳转到正确的播放页/详情页
- 报错时有友好的降级提示

---

## 4. 后续优化

**目标：** 性能、监控、可维护性。

### 4.1 短期优化

| 项 | 说明 |
|----|------|
| Retry / Backoff | `build_search_embeddings` 当前有 `--sleep`，还可加入 429/503 指数退避 |
| 增量更新 | 理解数据变更时自动重建对应 SearchDocument → embedding |
| Embedding 缓存 | 相同的 body 文本不重复调用 API（用 body 的 hash 做去重） |
| 批量 API | 如果 API 支持 `/embeddings` 的数组输入，改为批量调用 |
| Rerank | 可选接入硅基流动 `/rerank`，对 Top-N 语义结果做二次排序 |

### 4.2 中期优化

| 项 | 说明 |
|----|------|
| **向量数据库迁移** | 当 SearchDocument > 1000 条时，JSON + Python cosine_sim 会成为瓶颈。建议迁移到 pgvector（PostgreSQL 扩展，原地升级）或 Milvus/Qdrant（独立部署） |
| **Hybrid Search** | 融合 embedding 语义分数 + BM25 关键词分数的混合检索（pgvector 可做） |
| **搜索结果缓存** | 热门 query 的结果缓存 5-10 分钟 |
| **A/B 测试框架** | 对比不同 embedding 模型 / chunk 策略的搜索效果 |

### 4.3 监控指标

| 指标 | 采集方式 |
|------|----------|
| 搜索转化率 | 搜索 → 点击播放 的比例 |
| 无结果率 | 搜索返回 0 结果的比例 |
| AI chat 延迟 | SSE 首字时间 / 完整回复时间 |
| Embedding API 调用量 & 费用 | API provider dashboard |
| 人工评估 recall@K | 定期（每周）用固定 query set 评估 |

---

## 5. 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新建** | `apps/search/document_builder.py` | 从 full-delivery zip/目录构建剧级与集级 rich text |
| **新建** | `apps/search/management/commands/build_search_documents.py` | 批量重建 SearchDocument 的管理命令 |
| **新建** | `django-backend/.env.example` | AI/RAG 环境变量示例 |
| **修改** | `apps/catalog/management/commands/import_legacy_content.py` | 集成 document_builder，替换浅层 body |
| **修改** | `apps/search/services.py` | 优化 system prompt；增强关键词降级检索 |
| **修改** | `apps/search/management/commands/build_search_embeddings.py` | 添加 `--sleep` 节流 |
| **修改** | `config/api.py` | `POST /api/ai/search` 复用 `search_catalog` |
| **修改** | `config/settings.py` | 增加 `.env` 加载、AI API、embedding dimensions、HTTP retry 配置 |
| **修改** | `apps/search/tests.py` | 增加 RAG 文档构建和 AI 搜索接口测试 |
| **修改** | `django-backend/README.md` | 增加 RAG 刷新、embedding 构建和硅基流动配置说明 |
| **不变** | `apps/search/models.py` | 现有字段足够 |
| **不变** | 前端所有文件 | 现有前端适配 SSE 事件流，无需改动 |

---

## 6. 风险 & 注意事项

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Chat 模型不支持 tools | 中 | 中 | `choose_search_query` 失败时自动退回用户原始 query，仍可搜索 |
| body 超过 embedding token 限制 | 低 | 中 | 已做字符截断：剧级约 12000 字，集级约 5200 字 |
| 中文 embedding 质量差 | 中 | 高 | 优先选中文强的 embedding；保留关键词降级路径 |
| API 费用超预期 | 低 | 中 | 批量构建前先算数量；`--sleep` 节流；provider 429/5xx 自动重试退避 |
| 向量维度不一致 | 低 | 高 | 配置中显式声明维度；切换模型时全部重建 |
| 增量更新遗漏 | 中 | 低 | 监听 pipeline 的 search_index stage 完成事件 |

---

## 7. 当前剩余事项

1. 用 10 条固定 query 评估 Top-3 命中率，必要时调 body 权重或接 rerank。
2. 如果更换 embedding 模型，执行 `python manage.py build_search_embeddings --all --sleep 0.2` 全量重建。
3. 如数据量超过 1000 条 SearchDocument，再迁移到 pgvector 或独立向量库。
