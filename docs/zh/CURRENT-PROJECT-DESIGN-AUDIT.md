# 当前项目设计审计与补偿开发清单

> 审计日期：2026-06-11  
> 范围：`cinematic-drama-app-frontend-source`、`drama-understanding-agent`、`sdd`  
> 目标：识别前后端功能不对齐、占位功能、上传入库与离线内容理解链路缺口，以及实现上不合理或后续迭代风险较高的位置。

## 1. 结论摘要

当前项目已经不是“纯前端假数据 + 后端离线孤岛”的状态。前端数据层已经接入 `/api/dramas`、`/api/dramas/:id`、`/api/dramas/:id/episodes/:number/interactions`、`/api/ai/search`、`/api/users/me/profile`，播放器和首页也已经能按 Manifest 渲染互动组件并上报事件。

但项目仍然没有形成完整产品闭环，核心断点在三处：

1. **新增剧目入库链路缺失**：没有前端管理端、没有上传 API、没有 multipart 文件接收、没有“上传后自动创建 project 并串联 understand -> interactions -> recreate”的编排。现在只能手动把视频放入目录，再手动调 pipeline 或 CLI。
2. **在线后端只是薄 API 层**：内容分发、Job、事件/profile 端点存在，但事件持久化是 JSON 文件，Job 是内存态，AI 搜索是逐请求嵌入计算 + 本地 fallback，不是稳定可运维的服务能力。
3. **前端有不少“能点但不成业务”的功能**：评论、更多、通知、设置、离线缓存、我的收藏、互动记录、互动统计反馈、管理端上传等，都还没有真实页面或后端闭环。

## 2. 当前已具备的能力

### 2.1 前端

- `src/data/catalog.ts` 已移除旧版硬编码剧目数据，改为调用在线 API：
  - `loadDramas()` -> `GET /api/dramas`
  - `loadDrama()` -> `GET /api/dramas/:id`
  - `loadEpisode()` -> `GET /api/dramas/:id/episodes/:number`
  - `loadEpisodeManifest()` -> `GET /api/dramas/:id/episodes/:number/interactions`
  - `requestAiSearch()` -> `POST /api/ai/search`
- `src/interaction/queue.ts` 已实现本地队列 + `POST /api/interactions` 上报，不再只是清空 localStorage。
- `HomePage.tsx` 和 `PlayerPage.tsx` 已经接入 `InteractionTimeline` + `renderInteraction()`，可根据后端 Manifest 触发互动。
- `ProfilePage.tsx` 已经从 `/api/users/me/profile` 拉取资料和统计，不再完全写死。
- `TopBar.tsx` 的分享已经接入 `navigator.share` / clipboard fallback。

### 2.2 后端

- `src/drama_agent/api/server.py` 已有内容服务端点：
  - `GET /api/dramas`
  - `GET /api/dramas/:id`
  - `GET /api/dramas/:id/episodes`
  - `GET /api/dramas/:id/episodes/:number`
  - `GET /api/dramas/:id/episodes/:number/interactions`
  - `GET/HEAD /api/videos/:id/:number`
- 视频流支持 Range 和分块返回。
- 已有 pipeline Job 端点：
  - `POST /api/pipelines/understand`
  - `POST /api/pipelines/interactions`
  - `POST /api/pipelines/recreate`
  - `GET /api/jobs`
  - `GET /api/jobs/:id`
- 已有互动事件接收端点：`POST /api/interactions`。
- 已有用户 profile 端点：`GET /api/users/me/profile`。
- 离线 CLI 有完整串联命令 `drama-agent full-pipeline`，能先跑视频理解，再生成互动 Manifest。

## 3. P0：新增剧目入库与上传链路缺失

### 3.1 没有上传服务

当前后端 `server.py` 的 POST 路由只包含 `/api/ai/search`、`/api/interactions`、`/api/pipelines/understand`、`/api/pipelines/interactions`、`/api/pipelines/recreate`，没有 `/api/admin/dramas/upload` 或任何 multipart/form-data 处理逻辑。

影响：

- 新剧不能通过产品界面加入。
- 不能自动把上传视频保存到 `content/videos/{dramaId}` 或 `projects/{projectId}/episodes`。
- 不能自动创建 `projects/{projectId}/project.json`。
- 不能保证每部剧加入后自动经过内容理解和互动编排。

建议补偿开发：

1. 新增 `POST /api/admin/dramas/upload`，支持多文件上传和基础元数据。
2. 上传成功后标准化命名为 `ep_001.mp4`、`ep_002.mp4` 等。
3. 写入 `projects/{projectId}/project.json`，包含 `project_id`、`drama_title`、`total_episodes`、`video_pattern`。
4. 自动启动 composite job：`understand -> interactions -> recreate(optional)`。
5. 返回一个总 job id，并提供阶段状态。

### 3.2 没有管理端前端

`src/App.tsx` 只有 `/home`、`/detail`、`/player`、`/search`、`/ai`、`/theater`、`/profile`，没有 `/admin` 路由。前端代码中也没有调用 `/api/pipelines/*` 或 `/api/jobs` 的页面。

影响：

- pipeline 端点只能由开发者手动 curl/脚本调用。
- 无法在页面上查看上传进度、理解进度、互动生成结果、失败日志。
- 无法重跑某一阶段或补跑单集。

建议补偿开发：

- 增加 `/admin` 页面，至少包含：
  - 新剧上传表单
  - 剧名、project id、集数、文件列表校验
  - 上传后 job 状态轮询
  - understand / interactions / recreate 三阶段状态
  - 失败日志展示和重试按钮

### 3.3 Pipeline 端点不是“完整入库流程”

后端已有三个 pipeline 端点，但它们是分离的低层触发器：

- `run_understanding()` 需要调用方传 `title`、`video_dir`、`episodes`、`pattern`。
- `run_interaction_design()` 需要调用方传 `project`、`output_dir`、`video_dir` 等。
- `run_recreation()` 需要调用方传 `project`、`interactions_dir` 等。

这些参数对普通上传流程不友好，也没有在后端内部做阶段间产物传递。

建议补偿开发：

- 在 `jobs.py` 增加 `run_full_ingest(payload, job)`。
- 由上传 API 构造统一 payload。
- 第一步保存视频与 project metadata。
- 第二步调用 `EpisodeLoop(config).run()`。
- 第三步调用 `InteractionDesignAgent(...).run()`。
- 第四步可选调用 `BranchNarrativeAgent(...).run()`。
- 每个阶段写入 job.logs 和结构化 `stage` 状态。

## 4. P0：前后端契约不一致或闭环不完整

### 4.1 事件上报响应契约不一致

SDD 期望：

```json
{ "accepted": ["evt_1"], "duplicated": [], "rejected": [] }
```

当前后端 `ActivityStore.add_events()` 返回：

```json
{ "accepted": 1, "duplicates": 0 }
```

`server.py` 再包一层：

```json
{ "status": "ok", "accepted": 1, "duplicates": 0 }
```

当前前端 `LocalEventQueue.flush()` 只检查 `response.ok`，所以短期不报错，但这会阻碍后续精确重试、部分失败处理和重复事件识别。

建议：

- 后端改为逐事件返回 accepted / duplicated / rejected 列表。
- 前端只移除 accepted 和 duplicated，保留 rejected 中可重试的事件。
- 事件字段统一成一套命名。当前前端用 `id/dramaId/episodeNumber/pointId/type/actionData/atMs`，SDD 用 `event_id/drama_id/episode_id/event_type/action_data/client_timestamp/device_id`。

### 4.2 互动统计没有真实聚合反馈

`HomePage.tsx` 和 `PlayerPage.tsx` 调用 `renderInteraction()` 时都传 `statsSnapshot: null`。`types.d.ts` 甚至把它固定声明为 `null`。

影响：

- 站队助威、预测卡、线索判断等组件无法显示真实参与人数、比例、热度。
- 互动只“上报”，没有“反馈”，体验上像单机动画。

建议：

- 新增 `GET /api/interactions/stats?dramaId=&episodeNumber=&pointId=`。
- 对需要聚合的组件返回选项计数、比例、最近热度。
- `renderInteraction` 类型把 `statsSnapshot` 改为结构化对象。
- 前端在互动触发前或触发后拉取统计，并做本地乐观更新。

### 4.3 收藏/喜欢没有状态回读

`HomePage.tsx` 的喜欢按钮只维护本地 `liked` state，同时上报一条 `like` 事件。刷新后状态丢失，`ProfilePage` 的收藏数则由后端统计 `type == "like"` 的 drama 数得到。

问题：

- 没有取消收藏语义。再次点击只是发送 `{ liked: false }`，但后端 favorites 只看 `type == "like"`，不会扣减。
- 没有 `GET /api/users/me/favorites`。
- “我的收藏”菜单只是跳到 `/theater`。

建议：

- 明确收藏事件类型：`favorite_add` / `favorite_remove`，或新增状态型 endpoint `PUT /api/users/me/favorites/:dramaId`。
- Profile 菜单跳转到真实收藏页。
- 首页初始化时回读收藏状态。

### 4.4 评论功能只是事件记录

`HomePage.tsx` 评论按钮只上报 `comment_open`，没有评论面板、输入框、评论列表、发送接口。

建议：

- 如果 MVP 不做评论，应将按钮改为不可见或明确“评论待开放”。
- 如果要保留按钮，应补 `GET/POST /api/comments` 和评论面板。

## 5. P1：前端占位功能清单

| 功能 | 当前位置 | 当前行为 | 问题 |
|---|---|---|---|
| 更多操作 | `TopBar.tsx` | 显示“更多操作待后续开放” | 无菜单、无举报/收藏/缓存等动作 |
| 设置 | `ProfilePage.tsx` | 显示“设置功能待后续开放” | 无设置页 |
| 通知 | `ProfilePage.tsx` | 显示“暂无新通知” | 无通知模型和接口 |
| 离线缓存 | `ProfilePage.tsx` | 菜单跳 `/theater`，文案待开放 | 无 Capacitor Filesystem、无下载队列 |
| 我的收藏 | `ProfilePage.tsx` | 跳 `/theater` | 无收藏列表页 |
| 互动记录 | `ProfilePage.tsx` | 跳 `/theater` | 无 history 接口和页面 |
| AI 对话搜索 | `AiSearchPage.tsx` | 只做一次检索并展示卡片 | 不是多轮理解，也不能回答“下一集怎么反转”这类生成型问题 |
| 剧场推荐 | `TheaterPage.tsx` | 使用全部 dramas 做“猜你喜欢” | 没有个性化推荐或排序依据 |
| 海报/封面 | `content.py` | `poster`/`cover` 直接返回视频 URL | 可工作但语义不对，列表页大量 video 当封面 |

## 6. P1：后端实现风险和不合理点

### 6.1 ActivityStore 用 JSON 文件承载用户行为

`ActivityStore` 把所有事件存到 `runtime/activity-events.json`。

风险：

- 事件量稍大后读写整文件，性能和可靠性都差。
- 没有分页 history。
- 没有按 drama/episode/point 的索引。
- 多进程部署会冲突。
- 当前 lock 只在单进程内有效。

建议：

- MVP 至少改 SQLite：`interaction_events`、`user_favorites`、`job_runs`。
- 增加唯一键或索引：`event_id`、`device_id`、`drama_id`、`episode_number`、`point_id`、`type`。

### 6.2 JobManager 是内存态

`JobManager` 使用内存 dict，服务重启后 job 消失。

影响：

- 上传或内容理解耗时很长，重启后前端无法恢复状态。
- 无法查历史失败原因。
- 无法做重试和阶段回放。

建议：

- 上传链路落地前，至少把 job metadata 和 logs 写入 `runtime/jobs/{jobId}.json` 或 SQLite。
- full ingest job 要持久化每个阶段状态。

### 6.3 AI 搜索不是稳定的向量检索

`ContentRepository.search()` 每次请求都会：

1. 扫描项目和 report。
2. 对 query 调 `EmbeddingClient.embed()`。
3. 对每个 doc 再现场 embed。
4. remote embedding 失败后静默切到 `stable_embedding()`。

问题：

- 没有预构建索引，剧目多后请求会变慢。
- remote embedding 第一次失败后 `_remote_failed=True`，当前 repository 生命周期内永久降级。
- fallback 是 hash embedding，语义质量有限。
- 没有使用已有 Qdrant 索引做在线检索。

建议：

- 离线 pipeline 完成后把 drama、episode summary、interaction point 写入 Qdrant 或 SQLite FTS。
- 在线搜索只查询索引，不逐文档 embed。
- embedding 服务不可用时健康检查明确暴露，而不是静默永久降级。

### 6.4 中文文案存在乱码风险

后端 `content.py`、`activity.py` 的部分中文字符串在源码读取时已经呈现乱码，例如剧集标题、默认 displayName/bio、genre 推断词。前端页面中文是正常的。

影响：

- API 返回给前端的 `heat`、`score`、`genre`、`episode.title`、profile 文案可能显示乱码。
- 旧审计报告也存在明显编码损坏，不能直接作为交付文档。

建议：

- 统一确认文件编码为 UTF-8。
- 修复后端源码中的乱码字符串。
- 增加一个 API smoke test，断言 `/api/dramas` 返回中文不乱码。

### 6.5 前端文档已经过时

`cinematic-drama-app-frontend-source/SERVER.md` 仍描述 `npm run server`、`server/data/catalog.json`、`server/storage/videos`，但当前项目后端在 `drama-understanding-agent`，启动脚本是 `START-BACKEND.ps1` 或 `python -m drama_agent.api.server`。

影响：

- 后续开发者按文档启动会走错方向。

建议：

- 重写 `SERVER.md`，指向当前 Python API、环境变量、Vite proxy、内容目录和新增上传流程。

### 6.6 App 封装还只是配置

`package.json` 有 Capacitor 依赖和脚本，但前端目录没有 `android/` 或 `ios/`，也没有 Haptics、Share、Filesystem 插件依赖。

影响：

- 当前只能算 Web SPA，不是已完成 Android App。
- 离线缓存、原生分享、触觉反馈都没有真正接入 Capacitor 插件。

建议：

- 明确 Android 是否本阶段交付。
- 若交付，执行 `cap:add:android`、补插件、处理真机 API base URL。

## 7. P2：离线内容理解系统的已知占位

### 7.1 分支叙事图片生成是 Stub

`branch_narrative/image_generator.py`：

- `PlaceholderGenerator` 返回 `status="skipped"`。
- `SeedreamGenerator` 直接 `raise NotImplementedError`。

如果后续产品需要角色立绘、徽章、分支剧情插图，这部分还不能算完成。

### 7.2 Qdrant/embedding 降级过于静默

`memory/vectors.py` 注释写明是 “no-op fallback for tests and offline runs”。结合 `EmbeddingClient` 的 hash fallback，当前系统在外部依赖不可用时会尽量跑完，但结果质量可能明显下降，且不容易被调用者发现。

建议：

- 区分 `dev/test fallback` 和 `production required`。
- 后台启动时输出依赖健康状态。
- Job result 中写入 `degraded: true` 和具体依赖。

## 8. 建议的补偿开发顺序

### Phase 1：先打通新增剧闭环

1. 后端新增上传 API。
2. 后端新增 full ingest composite job。
3. 前端新增 `/admin` 上传与 job 状态页。
4. 上传成功后自动创建 project、保存视频、触发 understand/interactions。
5. `/api/dramas` 能自动发现新剧并在前端展示。

### Phase 2：修前后端契约和用户闭环

1. 统一互动事件字段和响应契约。
2. ActivityStore 从 JSON 文件迁移到 SQLite。
3. 增加 favorites/history/stats API。
4. 前端补收藏列表、互动记录、互动统计反馈。
5. 评论按钮要么隐藏，要么补真实评论功能。

### Phase 3：搜索和体验质量

1. 搜索索引离线构建，在线只查索引。
2. Qdrant / embedding 健康检查显式化。
3. 修复后端中文乱码。
4. 重写过时文档。
5. 补 Capacitor Android 真机链路和插件。

## 9. 最小验收标准

新增剧目闭环完成后，应能满足：

1. 在 `/admin` 上传一部新剧的多集 MP4。
2. 后端生成 `projects/{projectId}/project.json` 和标准视频目录。
3. 一个 job 自动跑完内容理解和互动 Manifest 生成。
4. `GET /api/jobs/:id` 能看到阶段状态和失败日志。
5. `GET /api/dramas` 出现新剧。
6. 前端详情页可选集播放。
7. 播放器能拉取该集 Manifest 并触发互动。
8. 互动事件能持久化，并能在 profile/history/stats 中回读。

