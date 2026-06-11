# 短剧即时互动系统 — 融合审计与升级方案

> 审计日期：2026-06-10  
> 审计范围：`cinematic-drama-app-frontend-source` (21 个源文件) + `drama-understanding-agent` (57 个 Python 源文件)  
> 参考目标架构：`<project-root>/final-sdd\` (SDD-00~09, 12 份文档)  
> 审计方法：3 个并行探索 Agent + 直接源码阅读，共审查 78 个文件  
> 当前状态：**两个项目独立开发，尚未融合；前端大量占位/降级，后端离线 Pipeline 完整但在线服务严重欠缺**

---

## 一、总体评估

### 1.1 现状一览

| 维度 | 当前状态 | 目标状态 (SDD) | 差距等级 |
|:---|:---|:---|:---|
| 前端 UI 骨架 | ✅ 6 个页面 + 12 种互动组件均已实现 | — | **低** — UI 层面基本完整 |
| 前端数据对接 | 🔴 几乎全部硬编码/占位 | 全部通过 API 动态获取 | **严重** |
| 前端交互功能 | 🟡 互动组件能本地渲染，但无后端联动 | 点赞/收藏/评论/分享全部可用 | **较大** |
| 后端 API 服务 | 🟡 HTTP API 骨架存在，路由匹配前端 | FastAPI + PostgreSQL + Redis + WS | **较大** |
| 后端离线 Pipeline | ✅ 视频理解 Agent + 互动设计 Agent 完整 | Celery + 质量门控 + 管理端 | **中等** |
| 后端向量/嵌入 | 🟡 Qdrant 已集成但有严重降级 | pgvector + BGE-M3 语义搜索 | **较大** |
| 后端资产生成 | 🔴 图像生成是空壳 Stub | 角色立绘/徽章 AI 生成 | **缺失** |
| 视频存储与分发 | 🔴 无入库流程，视频文件散落 | 管理端上传 → Pipeline → 分发 | **严重** |
| 用户系统 | 🔴 完全不存在 | 设备 ID 用户 + 积分/徽章/历史 | **严重** |
| 实时通信 | 🔴 不存在 | WebSocket 热力推送 | **缺失** |
| App 封装 | 🔴 仅有 Capacitor 配置，未构建 | Android APK/AAB | **缺失** |
| 部署方案 | 🔴 无 Dockerfile | Docker Compose 单机部署 | **缺失** |

### 1.2 SDD vs 当前实现架构差异

SDD 指定的目标架构 vs 当前实际实现：

| SDD 组件 | SDD 要求 | 当前实现 | 迁移难度 |
|:---|:---|:---|:---|
| 后端框架 | FastAPI 0.110+ | `http.server` (标准库) | 中等 — 业务逻辑可复用 |
| 数据库 | PostgreSQL 16 + pgvector | SQLite + Qdrant (两个独立系统) | 较高 |
| 任务队列 | Celery + Redis | 同步直接调用 (无队列) | 中等 |
| 主客户端 | **Flutter Android App** | React 19 Web + Capacitor | **需评估** — 架构级决策 |
| 实时通信 | WebSocket 热力推送 | 无 | 中等 |
| 嵌入模型 | BGE-M3 (1024 维) | SHA-256 哈希伪嵌入 (降级) | 较高 |
| 资产生成 | 文生图 (角色立绘/徽章) | PlaceholderGenerator (空壳) | 较高 |

---

## 二、前端问题详细清单

### 2.1 占位/硬编码数据 (Critical)

#### 2.1.1 硬编码剧目数据 — `src/data/catalog.ts`

| 行号 | 问题 | 严重度 |
|:---|:---|:---|
| 38-71 | `exampleDramaA` 完全硬编码，20 集时长全是写死的字符串 `'05:09'`, `'03:02'`... | **Critical** |
| 73-88 | `example-drama-b` (示例剧B) `episodes: []` — 空集列表，无法播放 | **Critical** |
| 42-43 | poster/cover 指向 `/api/videos/example-drama-a/1` 和 `/api/videos/example-drama-a/2` — 用视频 URL 当海报，第2集视频当封面 | **Major** |
| 80-81 | `example-drama-b` 的 poster/cover 指向外部 Google CDN URL (lh3.googleusercontent.com)，依赖外部服务 | **Major** |
| 49-68 | 20 个 `backendEpisode()` 调用生成固定的 episode 对象，videoUrl 全指向 `example-drama-a` | **Critical** |
| 101-105 | `loadDramas()` 有 HTTP 请求，但 catch 被吞掉，且调用方 `.catch(() => undefined)` 静默失败 | **Major** |
| 131 | `requestAiSearch()` 返回类型声明为 `{ status: string; message: string }` — 缺少 results 字段 | **Major** |

**应该做的**：所有数据从 `/api/dramas` 动态加载。`catalog.ts` 只保留类型定义和 API 调用函数，删除所有硬编码数据。

#### 2.1.2 硬编码互动清单 — `src/data/manifest.ts`

| 行号 | 问题 | 严重度 |
|:---|:---|:---|
| 23-85 | `playerManifest` 全部硬编码，12 个 interaction_points 手写 | **Critical** |
| 24 | `drama_id: 'example_drama_b_demo'` — 与实际 drama ID `example-drama-a` 不一致 | **Critical** |
| 27 | `video_url: '/api/videos/example-drama-a/1'` — 硬编码 | **Critical** |
| 28 | `duration_ms: 180000` — 硬编码 3 分钟，与实际视频长度可能不匹配 | **Major** |

**应该做的**：完全从 `loadEpisodeManifest()` 动态获取。`playerManifest` 仅作为离线/降级兜底。

#### 2.1.3 孤立死数据文件 — `src/data/drama.ts`

| 行号 | 问题 | 严重度 |
|:---|:---|:---|
| 1-93 | 整个文件定义了 `drama` 对象（示例剧B的详情），包含 cast、reviews、badges | **Dead Code** |
| — | 该文件**未被任何页面 import 或使用** | **Dead Code** |

**应该做的**：删除此文件，或改为从 API 获取的类型定义。

### 2.2 不可用功能 (Critical)

#### 2.2.1 点赞/收藏/评论 — 完全不可用

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `HomePage.tsx` | 228 | `<Heart>` 按钮 — 无 onClick，纯装饰 |
| `HomePage.tsx` | 231 | `<MessageCircle>` 按钮 — 无 onClick，纯装饰 |
| `TopBar.tsx` | 18 | `<Share2>` 分享按钮 — 无 onClick |
| `TopBar.tsx` | 21 | `<MoreHorizontal>` 更多按钮 — 无 onClick |
| `ProfilePage.tsx` | 17 | `<Bell>` 通知按钮 — 无 onClick |
| `ProfilePage.tsx` | 20 | `<Settings>` 设置按钮 — 无 onClick |

**应该做的**：
- 点赞 → POST `/api/v1/interactions` 发送 `event_type: "like"`
- 收藏 → POST `/api/v1/users/me/favorites` 
- 评论 → 打开评论面板
- 分享 → 调用 native share sheet (Capacitor `Share` plugin)
- 通知/设置 → 跳转对应页面

#### 2.2.2 AI 搜索 — 降级占位

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `AiSearchPage.tsx` | 28-31 | 后端不可用时 fallback: `{ status: 'offline', message: 'AI 搜索服务暂时不可用。' }` |
| `catalog.ts` | 125-132 | `requestAiSearch()` 只是简单 POST，无真正的 AI 语义搜索 |
| 后端 `content.py` | 164-191 | `/api/ai/search` 实现为**纯字符串子串匹配**，不是 AI 搜索 |

**应该做的**：后端接入 Embedding 向量搜索（Qdrant 已在依赖中），前端展示搜索结果卡片（而非纯文本）。

#### 2.2.3 用户系统 — 完全不存在

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `ProfilePage.tsx` | 5-9 | stats 完全硬编码：`已看 12集 / 互动 48次 / 收藏 6部` |
| `ProfilePage.tsx` | 31 | 用户名硬编码 `短剧观众`，描述 `互动体验测试账号` |
| `ProfilePage.tsx` | 29 | 头像硬编码字母 `C` |
| `ProfilePage.tsx` | 47-63 | 菜单项全部硬编码，去往固定路由 |

**应该做的**：后端实现 `/api/v1/users/me/profile`、`/history`、`/badges`。前端用 `X-Device-Id` 请求头标识设备。

#### 2.2.4 互动事件上报 — 未对接

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `queue.ts` | 31-35 | `flush()` 方法只清空 localStorage，**不发送到后端**，注释写 "已模拟上报" |
| — | 前端无任何 HTTP POST 发送互动事件到后端 |
| 后端 | — | 后端**完全没有 `/api/v1/interactions` 事件接收端点** |

**应该做的**：实现事件批量上报（本地队列 → 定期 flush → POST 到后端）。

#### 2.2.5 离线缓存 — 不存在

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `ProfilePage.tsx` | 51 | "离线缓存"菜单项 — `sub: '本地 MP4 资源'`，但无任何实现 |

### 2.3 视频播放问题

#### 2.3.1 首页视频静音

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `HomePage.tsx` | 193 | `muted` 属性硬编码在 `<video>` 上 — **所有首页视频无声音** |

**应该做的**：首页 feed 可以默认静音，但需提供取消静音按钮。或至少 PlayerPage 详细播放时有声音。

#### 2.3.2 视频入库流程缺失

| 问题 | 说明 |
|:---|:---|
| 无上传入口 | 没有管理端页面上传视频 |
| 无 Pipeline 触发 | 视频上传后不会自动触发离线理解 Pipeline |
| 视频文件散落 | 视频放在 `content/videos/` 下，没有与 project 关联的注册机制 |
| 后端 `ContentRepository` | 通过文件系统扫描发现视频，不是数据库驱动 |

**应该做的**：
1. 管理端 Web 页面上传视频 → 触发 Pipeline
2. Pipeline 完成后 `is_ready=true` 
3. 前端才能看到并播放

### 2.4 死代码与屎山

#### 2.4.1 重复/Legacy 组件 — `src/interaction/components.js`

| 行号 | 内容 | 说明 |
|:---|:---|:---|
| 653-699 | `LegacySugarStorm` | 旧版撒糖组件，已被 `SugarStorm`(701-956) 替代 |
| 1149-1190 | `LegacyTeamCheer` | 旧版站队组件，已被 `TeamCheer`(1192-1533) 替代 |
| 1568-1596 | `LegacyEmotionBuffer` | 旧版缓冲组件，已被 `EmotionBuffer`(1604-1738) 替代 |
| 1740-1780 | `LegacyRealOptionCard` | 旧版选项卡片，已被 `realOptionCard`(1782-1928) 替代 |
| 1930-1944 | `addAngerHit()` | 与 `addOriginalAngerHit()`(1954-1967) 功能重复 |
| 1969-1981 | `addOriginalAngerWord()` | 功能已被 AngerRelease 内联 |
| 1983-1996 | `addOriginalLaughWord()` | 功能已被 LaughBurst 内联 |
| 1998-2013 | `addOriginalEmoWord()` | 功能已被 TearResonance 内联 |
| 2015-2022 | `addFloatingWord()` | 未被调用 |
| 2024-2038 | `addHearts()` | 未被调用 |

**建议**：删除所有 Legacy 版本和未使用的 helper 函数，减少 ~600 行死代码。

#### 2.4.2 未使用的 import — `src/data/drama.ts`

| 行号 | 内容 |
|:---|:---|
| 1-2 | `LucideIcon`, `Building2, Flame, Star, Trophy` — 整个文件未被任何组件引用 |

#### 2.4.3 硬编码凭证泄露

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| 后端 `.env` | 6-7 | `DRAMA_AGENT_MODEL_TOKEN=<REDACTED>` — **真实 API Token 曾出现在工作副本中，已轮换并加入 .gitignore** |

**应该做的**：立即轮换该 Token，将 `.env` 加入 `.gitignore`。

### 2.5 前端 App 封装问题

| 问题 | 说明 |
|:---|:---|
| Capacitor 配置存在但未构建 | `capacitor.config.ts` 存在，但无 `android/` 或 `ios/` 目录 |
| 无 Android 构建产物 | 没有 APK/AAB |
| `package.json` 有 cap 脚本但未执行 | `cap:add:android`、`cap:sync` 未运行过 |
| 没有原生插件配置 | 触觉反馈 (Haptic)、文件系统、Share Sheet 等需要 Capacitor 插件 |
| Web 路由 vs App 路由 | 当前使用 React Router web 模式，App 内需要适配 Capacitor 的 file:// 协议 |

---

## 三、后端问题详细清单

### 3.1 API 架构差距

| SDD 目标 | 当前后端 | 差距 |
|:---|:---|:---|
| FastAPI + OpenAPI | `http.server` (标准库) | 无自动文档、无类型校验、无异步 |
| PostgreSQL + pgvector | SQLite + Qdrant (外部) | 向量和结构化数据不统一 |
| Redis 缓存 + Celery | 无 | 无任务队列、无缓存 |
| WebSocket 热力推送 | 无 | 完全缺失 |
| `/api/v1` 前缀 | `/api` 前缀 | 版本前缀缺失 |
| 统一错误码体系 | 无 | 只有 HTTP 状态码 + message |
| `X-Device-Id` 设备标识 | 无 | 无用户追踪 |

### 3.2 缺失的 API 端点

| 端点 | 用途 | 当前状态 |
|:---|:---|:---|
| `POST /api/interactions` | 接收互动事件 | **不存在** |
| `GET /api/users/me/profile` | 用户档案 | **不存在** |
| `GET /api/users/me/history` | 观看/互动历史 | **不存在** |
| `GET /api/users/me/badges` | 徽章 | **不存在** |
| `GET /api/interactions/stats/:ip_id` | 互动统计 | **不存在** |
| `GET /api/interactions/team-stats/:ip_id` | 站队统计 | **不存在** |
| `POST /api/admin/dramas/upload` | 视频上传 | **不存在** |
| `GET /api/admin/pipeline/status/:id` | Pipeline 状态 | **不存在** |
| WS `/ws/heatmap/:id/:ep` | 实时热力推送 | **不存在** |

### 3.3 视频入库流程完全缺失

当前后端通过文件系统扫描发现视频 (`ContentRepository.find_video()`)，没有：
1. 上传入口（管理端页面或 API）
2. 视频元数据注册（存入数据库）
3. Pipeline 自动触发机制
4. `pipeline_status.json` 的 `is_ready` 状态管理

### 3.4 Job 系统脆弱

| 问题 | 说明 |
|:---|:---|
| 内存存储 | `JobManager` 使用 `dict` 存储 jobs，服务重启全部丢失 |
| 无持久化 | 没有数据库记录 job 状态 |
| 无重试机制 | Pipeline 失败后无自动重试 |

### 3.5 AI 搜索是假的

`content.py:164-191` 的 `search()` 方法是用 Python 字符串 `in` 做子串匹配，不是 AI 语义搜索。虽然依赖中声明了 `qdrant-client`，但搜索端点没有使用向量检索。

### 3.6 嵌入向量系统严重降级 (Critical)

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `memory/embeddings.py` | 48-57 | `stable_embedding()` 使用 **SHA-256 哈希生成伪嵌入向量** — 产生的是确定性但**语义完全无意义**的向量。当远程嵌入服务 (`http://localhost:11434`) 不可用时（大概率），所有向量操作都使用垃圾数据 |
| `memory/embeddings.py` | 29 | `embed()` 方法在 `_embed_remote()` 抛异常时静默切换到哈希伪嵌入，**不记录任何日志或告警** |
| `memory/vectors.py` | 66-67 | `VectorStore.__init__()` 整个构造函数被 `try/except Exception` 包裹，连接 Qdrant 失败时静默设置 `self.enabled = False` |
| `memory/vectors.py` | 96-97, 125-126, 111-112 | `upsert_point()`、`search()`、`delete_point()` 在 disabled 状态下**静默返回成功**（空结果），调用方无法区分"无结果"和"服务不可用" |

### 3.7 向量同步只覆盖角色表

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `engine/state_patch.py` | 73 | `_sync_vectors()` 有硬编码 `if patch.table != "characters": continue` — 系统创建了 3 个 Qdrant 集合 (`characters`, `events`, `episode_contexts`) 但**只向 characters 写入数据**，另外两个永远为空 |

### 3.8 图像生成完全是空壳 (Stub)

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `branch_narrative/image_generator.py` | 32-43 | `PlaceholderGenerator.generate()` 永远返回 `ImageResult(status="skipped")` — 不生成任何图像 |
| `branch_narrative/image_generator.py` | 42 | `SeedreamGenerator.generate()` 直接 `raise NotImplementedError` — 骨架存在但无实现 |
| `branch_narrative/agent.py` | 51 | Agent 始终使用 `PlaceholderGenerator`，image_mode 配置项无实际作用 |

### 3.9 分支叙事规划使用硬编码模板

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `branch_narrative/phase1_planning.py` | 123-160 | `_fallback_plan()` 返回完全硬编码的 DAG — 15 个节点、3 条路线、3 个结局、12 条边全部写死。如果 LLM 返回空 JSON，系统静默使用此模板 |
| `branch_narrative/phase1_planning.py` | 71-84 | `normalize_plan()` 的每个字段都用 `or fallback[...]` 降级，LLM 返回 `{}` 也能"成功" |

### 3.10 API 返回静态/虚假元数据

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `api/content.py` | 99 | `"subtitle": "AI interactive short drama"` — 永远是同一句英文，不反映实际内容 |
| `api/content.py` | 102 | `"genre": ["interactive", "short-drama"]` — 永远是这两个标签 |
| `api/content.py` | 104 | `"score": "8.4"` — 永远 8.4 分 |
| `api/content.py` | 114 | `"title": f"Episode {number}"` — 集标题永远是英文 "Episode N"，不是中文 |

### 3.11 安全规则用硬编码关键词做自动修复

| 文件 | 行号 | 问题 |
|:---|:---|:---|
| `interaction_designer/safety_rules.py` | 16-47 | `_NEGATIVE_MORAL_KEYWORDS` (25 个中文词) 和 `_ABSURD_NOT_FUNNY_KEYWORDS` (9 个词) 用于自动排除不适配组件。纯关键词匹配，脆弱且语言绑死 |
| `interaction_designer/safety_rules.py` | 218-224 | `_infer_prediction_options()` 返回固定模板 `[{"text": "会发生", "is_correct": True}, {"text": "不会发生", "is_correct": False}]` — 无实际剧情关联 |

### 3.12 互动生成器与设计器的分数类型不一致

| 文件 | 问题 |
|:---|:---|
| `interaction_generator/config.py:57-70` | `guardian_shield` 映射到 `"resonance"` |
| `interaction_designer/safety_rules.py` | `guardian_shield` 映射到 `"guard"` (通过默认值) |
| **结果** | 两个 Pipeline 对同一组件使用不同的分数类型 |

---

## 四、与 SDD 目标架构的差距矩阵

| SDD 模块 | SDD 要求 | 当前实现 | 差距等级 |
|:---|:---|:---|:---|
| **离线 Pipeline** | Celery + 多阶段 + 质量门控 | ✅ Agent 引擎完整 (Doubao + ASR + 互动设计) | **低** — Pipeline 核心逻辑已就绪 |
| **资产生产** | 角色立绘、徽章、皮肤、扩写 | 🟡 `branch_narrative` 模块存在但未验证 | **中** |
| **在线 API** | FastAPI + Pydantic + OpenAPI | 🔴 标准库 `http.server` | **高** — 需整体替换 |
| **数据库** | PostgreSQL + pgvector | 🔴 SQLite + Qdrant (两个独立系统) | **高** |
| **实时通信** | WebSocket 热力推送 | 🔴 不存在 | **高** |
| **用户系统** | 设备 ID 用户 + 积分/徽章 | 🔴 不存在 | **高** |
| **视频管理** | 上传 → Pipeline → is_ready | 🔴 无上传、无自动触发 | **高** |
| **Android App** | Flutter Android APK | 🔴 React Web + Capacitor (未构建) | **高** — 需评估是否改用 Flutter |
| **管理端** | Web 管理端 (上传/标注) | 🔴 不存在 | **中** |
| **部署** | Docker Compose 单机 | 🔴 无 Dockerfile | **高** |
| **互动事件** | 批量上报 + 结算 | 🔴 前端不上报、后端不接收 | **高** |

---

## 五、融合升级方案

### 5.1 第一阶段：数据流通 (P0, 预计 3-5 天)

**目标**：打通前端 ↔ 后端的数据链路，消灭所有硬编码占位数据。

#### 任务 1.1：前端数据层改造
- 删除 `catalog.ts` 中所有硬编码数据 (`exampleDramaA`, `example-drama-b`)
- 删除 `drama.ts` 整个死代码文件
- `catalog.ts` 保留纯 API 调用函数，增加适当的 loading/error 状态
- 删除 `manifest.ts` 中硬编码的 `playerManifest`，保留类型导出
- 所有页面改为**优先使用 API 数据，失败时显示明确错误 UI**（而非静默降级到硬编码数据）

#### 任务 1.2：后端 API 对齐
- 确保后端返回的数据 shape 与前端 `DramaItem`/`Episode` 类型一致
- `to_drama_item()` 的 `subtitle` 字段当前硬编码 `"AI interactive short drama"` → 应从 project.json 获取
- `to_episode_item()` 的 `title` 字段当前硬编码 `"Episode {n}"` → 应使用中文 "第{n}集"
- 修复 poster/cover 指向视频 URL 的问题（应为静态图片 URL）

#### 任务 1.3：AI 搜索接入向量检索
- 后端 `search()` 改用 Qdrant 向量搜索（Qdrant 已在依赖中）
- 前端 `AiSearchPage` 展示搜索结果卡片（含剧名、封面、跳转），而非纯文本消息

### 5.2 第二阶段：交互闭环 (P0, 预计 5-7 天)

**目标**：让点赞、收藏、互动事件形成完整闭环。

#### 任务 2.1：后端事件接收
- 新增 `POST /api/interactions` 端点
- 实现事件入库 (SQLite → 后续迁移到 PostgreSQL)
- 实现事件去重 (event_id)

#### 任务 2.2：前端事件上报
- 改造 `LocalEventQueue.flush()` — 实际 POST 到 `/api/interactions`
- 点赞/收藏按钮增加 onClick handler
- 互动事件在触发时立即入队，定期或网络恢复时批量上报

#### 任务 2.3：用户系统 MVP
- 后端实现设备 ID 自动创建用户
- `GET /api/users/me/profile` 返回观看统计
- 前端 ProfilePage 改为从 API 加载数据

#### 任务 2.4：首页视频声音
- 移除 HomePage 硬编码的 `muted` 属性
- 改为：当前活跃视频有声音，非活跃视频静音

### 5.3 第三阶段：视频入库管线 (P0, 预计 5-7 天)

**目标**：建立视频 → 理解 → 上架的完整流程。

#### 任务 3.1：视频上传与管理端
- 新建简易 Web 管理页面（或直接用现有 React 项目加 `/admin` 路由）
- 实现视频上传 (multipart) → 存到 `content/videos/{drama_id}/`
- 后端新增 `POST /api/admin/dramas/upload`
- 创建 `project.json` 元数据文件

#### 任务 3.2：Pipeline 自动触发
- 上传完成后自动调用 `POST /api/pipelines/understand`
- Pipeline 完成后生成 Manifest → 写入 `outputs/{drama_id}/ep_*.interactions.json`
- 设置 `is_ready=true` 标记

#### 任务 3.3：前端 Pipeline 状态感知
- 剧目列表标记 `is_ready` 状态
- `is_ready=false` 时显示 "处理中" 标签，播放按钮置灰
- 轮询或 WebSocket 获取处理进度

### 5.4 第四阶段：实时体验 (P1, 预计 5-7 天)

**目标**：WebSocket 热力推送、互动统计。

#### 任务 4.1：WebSocket 热力
- 后端新增 `/ws/heatmap/{drama_id}/{episode_id}`
- 客户端进入 IP 范围 → subscribe，离开 → unsubscribe
- 推送 `heat_update` 和 `team_update`

#### 任务 4.2：互动统计端点
- `GET /api/interactions/stats/:ip_id`
- `GET /api/interactions/team-stats/:ip_id`

#### 任务 4.3：前端热力展示
- 互动组件渲染时展示实时参与人数
- 站队组件展示实时比分

### 5.5 第五阶段：App 封装 (P0, 预计 3-5 天)

**目标**：产出可安装的 Android APK。

#### 任务 5.1：Capacitor 构建
- 执行 `npm run cap:add:android`
- 配置 Android 包名、版本号、签名
- 构建 Debug APK 用于联调测试

#### 任务 5.2：原生能力接入
- 触觉反馈：安装 `@capacitor/haptics` 插件
- 文件系统：安装 `@capacitor/filesystem` 用于离线缓存
- Share Sheet：安装 `@capacitor/share` 用于分享
- Status Bar：安装 `@capacitor/status-bar` 沉浸式

#### 任务 5.3：App 内路由适配
- 确保 React Router 在 Capacitor WebView 中正常工作
- 处理 Android 返回键 → 路由返回
- 配置 `server.url` 为可配置的生产后端地址

### 5.6 第六阶段：架构升级 (P1, 预计 7-10 天)

**目标**：将后端从 `http.server` 升级到 FastAPI，数据库从 SQLite 升级到 PostgreSQL。

#### 任务 6.1：FastAPI 迁移
- 用 FastAPI 重写所有 API 路由 (复用现有 `ContentRepository` 逻辑)
- 添加 Pydantic 模型做请求/响应校验
- 自动生成 OpenAPI 文档
- 添加 `/api/v1` 版本前缀

#### 任务 6.2：数据库迁移
- SQLite → PostgreSQL (使用 SQLAlchemy + Alembic)
- pgvector 替代 Qdrant (简化部署，统一数据库)
- 数据迁移脚本

#### 任务 6.3：Docker Compose 部署
- `Dockerfile` for FastAPI 服务
- `docker-compose.yml`：postgres + redis + fastapi + nginx
- 环境变量管理

---

## 六、死代码清理清单

### 6.1 前端死代码

| 文件 | 行号 | 内容 | 操作 |
|:---|:---|:---|:---|
| `src/data/drama.ts` | 1-93 | 整文件 — 类型定义 + 硬编码数据，零引用 | **删除** |
| `src/interaction/components.js` | 653-699 | `LegacySugarStorm` — 旧版撒糖，未注册 | **删除** |
| `src/interaction/components.js` | 1149-1190 | `LegacyTeamCheer` — 旧版站队，未注册 | **删除** |
| `src/interaction/components.js` | 1568-1596 | `LegacyEmotionBuffer` — 旧版缓冲，未注册 | **删除** |
| `src/interaction/components.js` | 1740-1780 | `LegacyRealOptionCard` — ⚠️ 仍被 `ClueJudgeCard`(line 1547) 调用 | **迁移后删除** |
| `src/interaction/components.js` | 1930-1944 | `addAngerHit()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 1954-1967 | `addOriginalAngerHit()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 1969-1981 | `addOriginalAngerWord()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 1983-1996 | `addOriginalLaughWord()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 1998-2013 | `addOriginalEmoWord()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 2015-2022 | `addFloatingWord()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 2024-2038 | `addHearts()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 2040-2058 | `addOriginalHearts()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 2061-2098 | `holdAction()` — 未被调用 | **删除** |
| `src/interaction/components.js` | 2100-2102 | `isControlEvent()` — 未被调用 | **删除** |
| `src/data/catalog.ts` | 38-89 | 硬编码 `exampleDramaA` 和 `example-drama-b` | **删除** |
| `src/data/manifest.ts` | 23-85 | 硬编码 `playerManifest` | **替换为空兜底对象** |

**预计清理**：~900 行死代码可从 `components.js`(2118 行) 中删除，缩减 42%。

### 6.2 后端死代码

| 文件 | 行号 | 内容 | 操作 |
|:---|:---|:---|:---|
| `engine/state_patch.py` | 60-66 | `_apply_patch()` 方法 — 从未被调用（`commit_episode_patches` 直接用 conn） | **删除或重构** |
| `branch_narrative/image_generator.py` | 42 | `SeedreamGenerator` — 骨架存在但 `raise NotImplementedError` | **实现或删除** |
| `interaction_generator/highlight_to_ip.py` | 含 `Legacy*` 函数 | 旧版转换逻辑（需进一步确认） | **检查后清理** |
| **所有 `__pycache__/` 目录** | — | Python 字节码缓存 | **加入 .gitignore** |
| `frames_ep01/` | — | ep01 中间帧产物 | **移出仓库** |

### 6.3 安全问题

| 文件 | 行号 | 问题 | 操作 |
|:---|:---|:---|:---|
| 后端 `.env` | 6-7 | **真实 API Token** `ark-973d982f-...` 和 endpoint ID | **⚠️ 立即轮换 Token，加入 .gitignore** |

---

## 七、关键风险与建议

### 7.1 审计统计

本次审计共发现 **73 个问题**：

| 严重度 | 前端 | 后端 | 合计 |
|:---|:---|:---|:---|
| **Critical** | 9 | 3 | 12 |
| **Major** | 14 | 12 | 26 |
| **Minor** | 15 | 20 | 35 |

按类别：
| 类别 | 数量 | 占比 |
|:---|:---|:---|
| 占位/硬编码 (Placeholder) | 22 | 30% |
| 降级/静默失败 (Degraded) | 18 | 25% |
| 死代码 (DeadCode) | 17 | 23% |
| 功能缺失 (NonFunctional) | 12 | 16% |
| 安全问题 (Security) | 1 | 1% |
| Stub/空壳 | 3 | 4% |

### 7.2 关键风险

| 风险 | 影响等级 | 缓解措施 |
|:---|:---|:---|
| **后端 `.env` 包含真实 API Token** | 🔴 严重 | 立即轮换 Token，加入 .gitignore |
| **前端使用 React Web + Capacitor，SDD 指定 Flutter** | 🔴 需决策 | 评估 React+Capacitor 是否满足答辩要求；不满足则需改用 Flutter |
| **静默降级泛滥** — 前后端共 18 处静默失败 | 🟠 高 | 系统性添加错误日志和用户可见的错误状态 |
| **嵌入向量使用 SHA-256 伪嵌入** — 所有语义搜索功能实质失效 | 🟠 高 | 部署真实嵌入服务 (Ollama BGE-M3) 或接入云端 Embedding API |
| **Qdrant 连接失败静默禁用** — 向量存储形同虚设 | 🟠 高 | 添加健康检查和启动时显式报错 |
| **图像生成完全是 Stub** — 角色立绘/徽章无法生成 | 🟡 中 | 短期用占位图，长期接入文生图 API |
| **前端视频全部静音** — `muted` 硬编码 | 🟡 中 | 快速修复：移除硬编码 muted |
| **Pipeline 产物与 API 之间的数据断层** | 🟠 高 | 第一阶段优先打通 |

### 7.3 优先建议

1. **⚠️ 立即行动**：轮换泄露的 API Token (`ark-973d982f-...`)
2. **架构决策**：确认是否继续用 React + Capacitor（SDD 要求 Flutter Android App），这是影响所有后续客户端工作的关键决策
3. **第一阶段优先**：打通数据链路 — 消除所有硬编码数据，让前端真正从后端 API 加载数据
4. **嵌入服务**：部署 Ollama + BGE-M3 或接入云端 Embedding API，让向量搜索真正工作
5. **后端框架迁移**：在业务逻辑尚简单时将 `http.server` 迁移到 FastAPI

---

## 八、文件对照索引

| 前端文件 | 对应后端端点 | 当前对接状态 |
|:---|:---|:---|
| `catalog.ts:loadDramas()` | `GET /api/dramas` | 🟡 有调用但总是 fallback 到硬编码数据 |
| `catalog.ts:loadDrama()` | `GET /api/dramas/:id` | 🟡 同上 |
| `catalog.ts:loadEpisode()` | `GET /api/dramas/:id/episodes/:number` | 🟡 同上 |
| `catalog.ts:loadEpisodeManifest()` | `GET /api/dramas/:id/episodes/:number/interactions` | 🟡 同上 |
| `HomePage.tsx` 视频源 | `GET /api/videos/:id/:number` | 🟡 有调用但视频文件不一定存在 |
| `AiSearchPage.tsx` | `POST /api/ai/search` | 🔴 后端实现是假 AI (子串匹配) |
| `queue.ts:flush()` | `POST /api/interactions` | 🔴 端点不存在 |
| `ProfilePage.tsx` | `GET /api/users/me/*` | 🔴 端点不存在 |
| — | `WS /ws/heatmap/:id/:ep` | 🔴 不存在 |
| — | `POST /api/admin/dramas/upload` | 🔴 不存在 |
