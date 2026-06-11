# Django 后端全量重写设计文档

> 决策日期：2026-06-11  
> 决策结论：当前 `drama-understanding-agent/src/drama_agent/api/` 下的 `http.server` 在线后端不再继续补丁式扩展。在线业务后端改为 Django 全量重写，离线内容理解 Pipeline 保留为可调用服务/任务模块。  
> 目标：建立正式的数据模型、后台管理、上传入库、用户行为、内容下发、互动统计和 Pipeline 编排闭环。

## 1. 为什么必须重写

当前在线后端的问题不是局部缺接口，而是架构边界错误：

- 剧目数据由 `ContentRepository` 扫描 `projects/`、`outputs/`、`content/videos/` 拼装，缺少正式剧目、集数、上架状态和审核状态模型。
- 用户行为写入 `runtime/activity-events.json`，没有数据库表、索引、分页、并发安全和数据治理。
- 收藏、评论、互动记录、互动统计没有完整模型。
- Pipeline Job 是内存态，服务重启即丢失。
- 没有管理后台，新增剧只能手动放文件和手动触发任务。
- 当前 SQLite 主要服务离线内容理解记忆库，不是在线业务数据库。
- 前端需要的“剧、集、播放、互动、用户、收藏、评论、后台管理”没有统一数据源。

因此后续不再以当前 `http.server` 为主干继续扩展。新主干使用 Django + Django REST Framework。

## 2. 新后端技术栈

| 层级 | 选型 | 说明 |
|---|---|---|
| Web 框架 | Django 5.x | 正式模型、Admin、ORM、迁移体系 |
| API | Django REST Framework | 对前端提供 REST API |
| 数据库 | PostgreSQL 16 | 正式业务数据持久化 |
| 异步任务 | Celery + Redis | 视频理解、互动生成、分支叙事、转码/封面等耗时任务 |
| 文件存储 MVP | 本地 `media/` | 上传视频、封面、生成物 |
| 文件存储后续 | S3/MinIO/对象存储 | 线上部署替换 |
| 鉴权 MVP | Device ID + Admin 登录 | 前端用户以设备标识，后台用 Django Admin |
| 后台管理 | Django Admin | 剧目、集数、任务、用户行为、评论审核 |
| 搜索 | PostgreSQL FTS + 后续 pgvector/Qdrant | MVP 先可用，后续接语义向量 |

## 3. Django 项目结构

建议新建目录：

```text
django-backend/
  manage.py
  pyproject.toml
  config/
    settings.py
    urls.py
    celery.py
  apps/
    accounts/
    catalog/
    media_assets/
    interactions/
    comments/
    pipeline/
    search/
    analytics/
  media/
  static/
```

离线系统 `drama-understanding-agent` 保留，但不再直接承载在线 API。Django 通过 Celery task 或 service adapter 调用其 Pipeline 能力。

## 4. 核心应用划分

### 4.1 `accounts`

负责设备用户、后台用户扩展、用户画像。

模型：

- `DeviceUser`
  - `id`
  - `device_id`
  - `display_name`
  - `avatar_text`
  - `created_at`
  - `last_seen_at`
  - `metadata`

MVP 不做手机号/密码登录，用户端以 `X-Device-Id` 识别。

### 4.2 `catalog`

负责剧目、集数、上架状态、封面、播放地址。

模型：

- `Drama`
  - `id`
  - `slug`
  - `title`
  - `subtitle`
  - `description`
  - `status`: `draft | processing | ready | published | archived | failed`
  - `genre_tags`
  - `score_label`
  - `heat_label`
  - `poster`
  - `cover`
  - `source`
  - `created_at`
  - `updated_at`
  - `published_at`

- `Episode`
  - `id`
  - `drama`
  - `episode_number`
  - `title`
  - `description`
  - `duration_ms`
  - `video_file`
  - `video_status`: `uploaded | processing | ready | failed`
  - `manifest_status`: `missing | generating | ready | failed`
  - `is_published`
  - `created_at`
  - `updated_at`

约束：

- `Drama.slug` 唯一。
- `(drama, episode_number)` 唯一。
- 只有 `Drama.status=published` 且 `Episode.is_published=true` 的内容对用户端列表可见。

### 4.3 `media_assets`

负责视频、封面、互动素材引用、生成图等资产记录。

模型：

- `MediaAsset`
  - `id`
  - `owner_type`
  - `owner_id`
  - `asset_type`: `video | poster | cover | frame | character | evidence | generated_image | lottie | other`
  - `file`
  - `url`
  - `mime_type`
  - `size_bytes`
  - `checksum`
  - `metadata`
  - `created_at`

用途：

- 避免 poster/cover 继续用视频 URL 伪装。
- 支持后续对象存储迁移。

### 4.4 `interactions`

负责 Manifest、互动点、用户互动事件、聚合统计。

模型：

- `InteractionManifest`
  - `id`
  - `episode`
  - `version`
  - `schema_version`
  - `duration_ms`
  - `raw_json`
  - `source_path`
  - `generated_by`
  - `status`: `draft | ready | invalid | failed`
  - `created_at`
  - `updated_at`

- `InteractionPoint`
  - `id`
  - `manifest`
  - `point_key`
  - `component`
  - `title`
  - `emotion`
  - `start_ms`
  - `end_ms`
  - `priority`
  - `highlight_reason`
  - `config`
  - `sort_order`

- `InteractionEvent`
  - `id`
  - `event_id`
  - `device_user`
  - `drama`
  - `episode`
  - `interaction_point`
  - `event_type`
  - `action_data`
  - `at_ms`
  - `client_timestamp`
  - `received_at`

- `InteractionAggregate`
  - `id`
  - `interaction_point`
  - `event_type`
  - `bucket`
  - `count`
  - `payload`
  - `updated_at`

约束：

- `InteractionEvent.event_id` 唯一，用于幂等去重。
- 事件必须能按 `device_user`、`drama`、`episode`、`interaction_point` 查询。

### 4.5 `comments`

负责评论区。

模型：

- `Comment`
  - `id`
  - `device_user`
  - `drama`
  - `episode`
  - `parent`
  - `content`
  - `status`: `visible | pending | hidden | deleted`
  - `like_count`
  - `created_at`
  - `updated_at`

MVP 可先只做单层评论，后台支持隐藏/删除。

### 4.6 `pipeline`

负责上传入库、内容理解、互动生成、任务状态。

模型：

- `PipelineJob`
  - `id`
  - `job_type`: `ingest | understand | interactions | recreate | reindex | transcode`
  - `status`: `queued | running | succeeded | failed | canceled`
  - `drama`
  - `episode`
  - `request_payload`
  - `result_payload`
  - `error_message`
  - `logs`
  - `started_at`
  - `finished_at`
  - `created_at`
  - `updated_at`

- `PipelineStage`
  - `id`
  - `job`
  - `stage_key`: `upload | project_init | understand | interaction_design | branch_narrative | publish`
  - `status`
  - `order`
  - `input_payload`
  - `output_payload`
  - `error_message`
  - `started_at`
  - `finished_at`

### 4.7 `search`

负责普通搜索和语义搜索。

模型：

- `SearchDocument`
  - `id`
  - `object_type`: `drama | episode | interaction_point`
  - `object_id`
  - `title`
  - `body`
  - `tags`
  - `embedding_status`
  - `embedding_vector` 后续可用 pgvector
  - `updated_at`

MVP 可先用 PostgreSQL 文本搜索，后续接 pgvector 或 Qdrant。

### 4.8 `analytics`

负责观看进度、收藏、历史。

模型：

- `Favorite`
  - `id`
  - `device_user`
  - `drama`
  - `created_at`
  - 唯一约束 `(device_user, drama)`

- `WatchProgress`
  - `id`
  - `device_user`
  - `drama`
  - `episode`
  - `progress_ms`
  - `duration_ms`
  - `updated_at`
  - 唯一约束 `(device_user, episode)`

- `UserActivity`
  - `id`
  - `device_user`
  - `activity_type`
  - `drama`
  - `episode`
  - `payload`
  - `created_at`

## 5. API 设计

前端已有路径可尽量兼容，但实现改为 Django。

### 5.1 内容下发

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/dramas` | 已发布剧目列表 |
| `GET` | `/api/dramas/{slug}` | 剧目详情 |
| `GET` | `/api/dramas/{slug}/episodes` | 选集列表 |
| `GET` | `/api/dramas/{slug}/episodes/{number}` | 单集详情 |
| `GET` | `/api/dramas/{slug}/episodes/{number}/interactions` | 单集 Manifest |
| `GET` | `/api/videos/{slug}/{number}` | 视频流或重定向到文件 URL |

### 5.2 用户与行为

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/users/me/profile` | 当前设备用户资料 |
| `GET` | `/api/users/me/history` | 观看/互动历史 |
| `GET` | `/api/users/me/favorites` | 收藏列表 |
| `PUT` | `/api/users/me/favorites/{drama_slug}` | 收藏 |
| `DELETE` | `/api/users/me/favorites/{drama_slug}` | 取消收藏 |
| `PUT` | `/api/users/me/progress/{episode_id}` | 更新播放进度 |

### 5.3 互动

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/interactions` | 批量上报互动事件 |
| `GET` | `/api/interactions/stats/{point_id}` | 单互动点聚合统计 |
| `GET` | `/api/episodes/{episode_id}/interaction-stats` | 单集互动统计 |

`POST /api/interactions` 响应必须采用列表式幂等结果：

```json
{
  "accepted": ["evt_1"],
  "duplicated": ["evt_2"],
  "rejected": [
    { "event_id": "evt_3", "reason": "invalid point" }
  ]
}
```

### 5.4 评论

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/comments?drama=&episode=` | 评论列表 |
| `POST` | `/api/comments` | 创建评论 |
| `DELETE` | `/api/comments/{id}` | 删除自己的评论或后台删除 |

### 5.5 搜索

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/search?q=` | 普通搜索 |
| `POST` | `/api/ai/search` | 语义搜索，兼容现前端 |

### 5.6 管理端与 Pipeline

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/admin/dramas/upload` | 上传新剧和多集视频 |
| `POST` | `/api/admin/dramas/{id}/publish` | 上架 |
| `POST` | `/api/admin/dramas/{id}/unpublish` | 下架 |
| `POST` | `/api/admin/pipeline/ingest` | 创建完整入库任务 |
| `POST` | `/api/admin/pipeline/{job_id}/retry` | 重试 |
| `GET` | `/api/admin/pipeline/jobs` | 任务列表 |
| `GET` | `/api/admin/pipeline/jobs/{job_id}` | 任务详情 |

用户端前端不直接调用 admin API。Web 管理端 `/admin` 可使用 Django Admin，后续再做 React 管理页。

## 6. 上传入库闭环

新剧加入必须走统一流程：

1. 管理员在 Django Admin 或 React `/admin` 上传剧目元数据和多集 MP4。
2. Django 创建 `Drama`，状态为 `draft`。
3. Django 创建 `Episode`，保存视频文件，状态为 `uploaded`。
4. 创建 `PipelineJob(job_type=ingest)`。
5. Celery 执行：
   - `project_init`
   - `understand`
   - `interaction_design`
   - `branch_narrative` 可选
   - `manifest_import`
   - `search_index`
   - `publish_ready`
6. Pipeline 产物导入数据库：
   - `InteractionManifest.raw_json`
   - `InteractionPoint`
   - `SearchDocument`
   - 关键帧/角色资产进入 `MediaAsset`
7. 管理员审核后发布。
8. 前端 `/api/dramas` 只下发 published 内容。

## 7. 离线 Pipeline 接入方式

保留 `drama-understanding-agent` 的核心理解能力，但从在线服务中抽离。

推荐封装：

```text
django-backend/apps/pipeline/services/offline_agent.py
```

职责：

- 根据 `Drama` / `Episode` 构造临时 project workspace。
- 调用现有 `EpisodeLoop`、`InteractionDesignAgent`、`BranchNarrativeAgent`。
- 收集产物路径。
- 将 JSON 产物导入 Django 模型。

禁止：

- Django API 请求线程中直接跑长耗时理解。
- 前端直接传本地路径触发 Pipeline。
- 新剧绕过数据库，仅放文件后靠扫描发现。

## 8. Django Admin 必须覆盖的管理能力

后台至少注册：

- `DramaAdmin`
  - 搜索 title/slug
  - 过滤 status/genre
  - 动作：发布、下架、重跑 Pipeline

- `EpisodeAdmin`
  - inline 展示在 Drama 下
  - 查看视频状态、时长、Manifest 状态

- `InteractionManifestAdmin`
  - 查看 raw_json
  - 校验状态

- `InteractionPointAdmin`
  - 按 episode、component、时间排序

- `PipelineJobAdmin`
  - 查看阶段、日志、错误
  - 重试失败任务

- `DeviceUserAdmin`
  - 查看设备用户、最近活跃

- `InteractionEventAdmin`
  - 按用户、剧、集、互动点过滤

- `FavoriteAdmin`

- `CommentAdmin`
  - 审核、隐藏、删除

## 9. 前端需要同步调整

当前 React 前端可保留页面结构，但需要修正能力边界：

1. 首页播放：
   - 默认静音自动播放，用户点击后再解除静音。
   - 中央播放按钮只在真实暂停时显示。

2. 收藏：
   - 不再用本地 `liked` 作为唯一状态。
   - 页面初始化拉取收藏状态。
   - 调用 `PUT/DELETE /api/users/me/favorites/{drama}`。

3. 评论：
   - 评论按钮打开真实评论面板。
   - 调用 `GET/POST /api/comments`。

4. 播放页遮挡：
   - 互动触发时底部信息栏收起或降层级。
   - `statsSnapshot` 改为真实聚合数据。

5. Profile：
   - “我的收藏”跳收藏页。
   - “互动记录”跳 history 页。
   - “离线缓存”若不做，应移除入口或明确禁用。

6. 管理端：
   - MVP 可直接使用 Django Admin。
   - 若需要移动端同仓管理页，再新增 React `/admin`。

## 10. 迁移策略

### 阶段 1：Django 基础工程

- 创建 `django-backend`。
- 配置 PostgreSQL、DRF、Celery、Redis。
- 建立上述 models 和 migrations。
- 配置 Django Admin。

### 阶段 2：兼容现有前端 API

- 实现 `/api/dramas` 等内容下发接口。
- 实现 `/api/interactions`、profile、favorites。
- 前端无需一次性大改即可切换 API base。

### 阶段 3：上传与 Pipeline

- 实现上传入库。
- 实现 Celery full ingest job。
- 导入现有离线产物到 Django 模型。

### 阶段 4：替换旧后端

- 停止使用 `python -m drama_agent.api.server` 作为在线服务。
- 旧 API 仅作为参考或调试工具保留。
- 文档和启动脚本指向 Django。

### 阶段 5：清理旧文件扫描逻辑

- 不再依赖 `ContentRepository` 扫文件下发剧目。
- `projects/`、`outputs/` 只作为 Pipeline 工作区和历史产物，不作为在线真实数据源。

## 11. 验收标准

重写完成必须满足：

1. Django Admin 能创建、编辑、发布、下架剧目。
2. 管理员上传一部多集短剧后，系统自动创建剧和集。
3. Pipeline Job 可持久化查看状态、日志和错误。
4. Pipeline 完成后，Manifest 被导入 `InteractionManifest` 和 `InteractionPoint` 表。
5. 前端首页、剧场、详情、播放器全部从 Django API 获取数据。
6. 点赞/收藏可刷新后保留。
7. 评论按钮打开真实评论区。
8. 互动事件写入数据库，重复事件幂等处理。
9. Profile 的已看、互动、收藏来自数据库查询。
10. 播放页不再被底部信息层遮挡关键互动。
11. 旧 `runtime/activity-events.json` 不再作为行为数据源。
12. 旧 `ContentRepository` 不再作为剧目列表的数据源。

## 12. 明确废弃项

以下内容不再作为正式在线后端继续扩展：

- `drama_agent.api.server.DramaApiServer`
- `drama_agent.api.content.ContentRepository` 作为在线剧目数据源
- `drama_agent.api.activity.ActivityStore`
- 内存态 `JobManager`
- `runtime/activity-events.json`
- 靠扫描 `projects/outputs/content/videos` 自动组成用户端内容列表的方式

离线内容理解相关模块继续保留：

- `EpisodeLoop`
- `InteractionDesignAgent`
- `BranchNarrativeAgent`
- memory.db 作为离线理解工作区
- outputs manifest 作为中间产物

最终在线系统必须以 Django 数据库模型为准。

