# SDD-03-在线后端设计

> 版本：v1.0  
> 定稿日期：2026-06-10  
> 实现模块：`drama-understanding-agent/src/drama_agent/api/`  
> **原则：后端视频理解系统已经可用，仅做周边修补和必要端点补充，不做框架级重构。**

## 3.1 在线后端职责边界

在线后端是一层薄 API 网关，负责：
- 将离线 Pipeline 产出的 Manifest/Report/视频文件**对前端暴露为 HTTP API**
- 接收前端回传的互动事件并持久化
- 提供视频文件的分片流式传输（Range 206）
- 管理 Pipeline Job 的触发与状态查询

**不负责**：
- 任何 AI 模型调用（完全在离线 Pipeline 中完成）
- 视频处理/转码
- 复杂业务逻辑

## 3.2 当前技术实现

| 项 | 选型 | 说明 |
|:---|:---|:---|
| HTTP 框架 | `http.server` (标准库) | 轻量，无额外依赖，路由手动分发 |
| 并发模型 | `ThreadingHTTPServer` | 每请求一线程，适合 MVP 规模 |
| 序列化 | `json.dumps` + gzip | 手动构建 JSON 响应 |
| 视频流 | 手动 Range 解析 + 文件 chunk 读取 | 支持 206 Partial Content |
| Job 管理 | 内存 `dict` + 守护线程 | 服务重启丢失（已知限制） |

## 3.3 API 端点清单

### 3.3.1 内容服务（已实现）

| 方法 | 路径 | 功能 | 实现 |
|:---|:---|:---|:---|
| `GET` | `/health` | 健康检查 | ✅ |
| `GET` | `/api/dramas` | 剧目列表 | ✅ `ContentRepository.list_dramas()` |
| `GET` | `/api/dramas/:id` | 剧目详情 | ✅ `ContentRepository.get_record()` |
| `GET` | `/api/dramas/:id/episodes` | 选集列表 | ✅ |
| `GET` | `/api/dramas/:id/episodes/:number` | 单集信息 | ✅ |
| `GET` | `/api/dramas/:id/episodes/:number/interactions` | 单集互动清单 | ✅ `ContentRepository.load_manifest()` |
| `GET/HEAD` | `/api/videos/:id/:number` | 视频流 (Range) | ✅ `_send_video()` |
| `POST` | `/api/ai/search` | AI 搜索 | 🟡 当前为子串匹配，需升级为向量搜索 |

### 3.3.2 Pipeline 管理（已实现）

| 方法 | 路径 | 功能 | 实现 |
|:---|:---|:---|:---|
| `POST` | `/api/pipelines/understand` | 触发视频理解 | ✅ `run_understanding()` |
| `POST` | `/api/pipelines/interactions` | 触发互动设计 | ✅ `run_interaction_design()` |
| `POST` | `/api/pipelines/recreate` | 触发分支叙事 | ✅ `run_recreation()` |
| `GET` | `/api/jobs` | 任务列表 | ✅ 内存存储 |
| `GET` | `/api/jobs/:id` | 任务状态 | ✅ |

### 3.3.3 互动事件（需新增 — P0）

| 方法 | 路径 | 功能 | 状态 |
|:---|:---|:---|:---|
| `POST` | `/api/interactions` | 批量接收互动事件 | 🔴 需新增 |

**请求体**：
```json
{
  "events": [{
    "event_id": "uuid",
    "point_id": "ip_001_celebrate",
    "drama_id": "example-drama-a",
    "episode_id": "ep_001",
    "event_type": "celebrate_click",
    "action_data": { "click_count": 3 },
    "client_timestamp": 1718000000000,
    "device_id": "device-uuid"
  }]
}
```

**响应**：`{ "accepted": ["uuid1"], "duplicated": [], "rejected": [] }`

**实现方案**：
- 事件写入 SQLite 新表 `interaction_events`
- `event_id` 唯一约束防重复
- 上限 50 条/批

### 3.3.4 用户服务（需新增 — P1）

| 方法 | 路径 | 功能 | 状态 |
|:---|:---|:---|:---|
| `GET` | `/api/users/me/profile` | 用户档案 | 🔴 需新增 |
| `GET` | `/api/users/me/history` | 互动历史 | 🔴 需新增 |

**实现方案**：
- 基于 `X-Device-Id` 请求头识别设备
- MVP 阶段数据量小，直接用 SQLite 查询
- 统计字段：已看集数、互动次数、各类事件计数

### 3.3.5 管理端（需新增 — P1）

| 方法 | 路径 | 功能 | 状态 |
|:---|:---|:---|:---|
| `POST` | `/api/admin/dramas/upload` | 上传短剧 | 🔴 需新增 |

## 3.4 数据层模块

### 3.4.1 ContentRepository（已实现）

**文件**：`drama_agent/api/content.py`

核心逻辑：
- 扫描 `projects/` 目录下的 `project.json` → 构建 `DramaRecord` 列表
- 扫描 `outputs/` 目录下 `ep_*.interactions.json` → 匹配 Manifest
- 视频文件发现：`content/videos/{id}/` → `projects/{id}/episodes/` 多路径搜索
- 搜索：当前为子串匹配 → 需升级为 Qdrant 向量搜索

### 3.4.2 待修复问题

| 问题 | 文件:行号 | 修复方案 |
|:---|:---|:---|
| `subtitle` 返回固定英文 | `content.py:99` | 从 report.json 取 `drama_title` 或生成中文描述 |
| `genre` 返回固定 `["interactive", "short-drama"]` | `content.py:102` | 从 report.json 的 mood/tags 推导题材 |
| `score` 返回固定 `"8.4"` | `content.py:104` | 暂无真实数据，保持占位但标注为"暂无评分" |
| `title` 返回英文 `"Episode {n}"` | `content.py:114` | 改为 `"第{n}集"` |
| AI 搜索是子串匹配 | `content.py:164-191` | 接入 Qdrant 向量搜索（需先修复嵌入服务） |

### 3.4.3 JobManager（已实现）

**文件**：`drama_agent/api/jobs.py`

当前实现：
- 内存 `dict` 存储 Job 状态
- 通过 `Thread` 异步执行 Pipeline
- 支持 `queued → running → succeeded/failed` 状态转换

已知限制（可接受，不重构）：
- 服务重启丢失 Job 历史
- 无并发限制
- 无重试机制

## 3.5 视频服务

### 3.5.1 视频分发（已实现）

**文件**：`drama_agent/api/server.py:_send_video()`

- 支持 HTTP Range 请求（`Range: bytes=start-end`）
- 206 Partial Content 响应
- 返回 `Accept-Ranges`, `Content-Range`, `Content-Length`, `ETag`
- 未指定 Range 时默认返回前 2MB（`DRAMA_API_MAX_VIDEO_CHUNK_BYTES`）
- 长期缓存头：`Cache-Control: public, max-age=31536000, immutable`

**视频文件搜索顺序**：
1. `$DRAMA_API_VIDEO_ROOT/{drama_id}/`
2. `$DRAMA_API_VIDEO_ROOT/{project_id}/`
3. `{project}/episodes/`
4. `{project}/videos/`
5. `{project}/`

**视频文件命名**（自动匹配）：`ep_001.mp4`, `ep001.mp4`, `ep01.mp4`, `episode_1.mp4`, `1.mp4`

### 3.5.2 视频入库流程（待建立）

当前视频文件靠手动放置到 `content/videos/` 目录。需补充：
1. 管理端上传 API（`POST /api/admin/dramas/upload`）
2. 上传后自动创建 `projects/{id}/project.json`
3. 可选：上传后自动触发 Pipeline

## 3.6 环境变量

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `DRAMA_API_HOST` | `127.0.0.1` | 监听地址 |
| `DRAMA_API_PORT` | `8787` | 监听端口 |
| `DRAMA_API_PROJECTS_ROOT` | `./projects` | Project 目录 |
| `DRAMA_API_OUTPUTS_ROOT` | `./outputs` | Manifest 输出目录 |
| `DRAMA_API_VIDEO_ROOT` | `./content/videos` | 视频文件目录 |
| `DRAMA_API_MAX_VIDEO_CHUNK_BYTES` | `2097152` (2MB) | 无 Range 请求的默认响应大小 |
| `DRAMA_API_ACCESS_LOG` | `0` | 设为 `1` 开启请求日志 |
| `DRAMA_API_PUBLIC_BASE_URL` | (空) | 公网部署时的外部 URL 前缀 |

## 3.7 周边修补清单（不重构）

按优先级排列：

| 优先级 | 任务 | 说明 |
|:---|:---|:---|
| **P0** | 修复 `to_drama_item/to_episode_item` 元数据 | 中文 title、从 report 取真实数据 |
| **P0** | 新增 `POST /api/interactions` | 事件接收端点 + SQLite 表 |
| **P0** | AI 搜索接入 Qdrant | 先修复嵌入服务（BGE-M3），再改 search() 用向量 |
| **P1** | 新增 `GET /api/users/me/profile` | 用户统计（基于 device_id + SQLite 聚合） |
| **P1** | 新增 `GET /api/users/me/history` | 互动历史分页 |
| **P1** | 新增 `POST /api/admin/dramas/upload` | 视频上传 + 自动创建 project |
| **P2** | Job 持久化 | 可选：写入 SQLite job 表 |
| **OUT** | 迁移 FastAPI | 不在此阶段进行 |
| **OUT** | 迁移 PostgreSQL | 不在此阶段进行 |
| **OUT** | 添加 Celery | 不在此阶段进行 |
