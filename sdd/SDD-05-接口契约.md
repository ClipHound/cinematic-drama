# SDD-05-接口契约

> 版本：v1.0  
> 定稿日期：2026-06-10  
> 主消费端：React 19 前端 (Web + Capacitor Android App)

## 5.1 总览

本文档定义在线后端对外暴露的所有 HTTP API 接口的契约。所有请求/响应使用 UTF-8 JSON。当前 API 无版本前缀（`/api/`），未来迁移 FastAPI 时加 `/api/v1/`。

## 5.2 通用规约

### 5.2.1 通用请求头

| 头 | 必选 | 说明 |
|:---|:---|:---|
| `Content-Type: application/json` | 写接口必选 | — |
| `X-Device-Id` | 写接口必选 | 客户端首启生成的设备 UUID（localStorage 持久化） |
| `Accept-Encoding: gzip` | 可选 | 服务端对 >1KB 的 JSON 响应启用 gzip |

### 5.2.2 通用响应

**成功**：
- HTTP 2xx
- Body：直接返回业务 JSON 对象

**错误**：
```json
{
  "status": "error",
  "message": "人类可读错误描述"
}
```

### 5.2.3 时间格式

- 视频时间（duration_ms, start_ms, end_ms）：**毫秒整数**
- 系统时间（createdAt, updatedAt）：ISO 8601 UTC 字符串

## 5.3 HTTP REST 接口

### 5.3.1 内容服务

#### `GET /api/dramas`

获取剧目列表。

**响应**：
```json
{
  "dramas": [{
    "id": "example-drama-a",
    "title": "富饶大地",
    "subtitle": "古装扮猪吃虎权谋爽剧",
    "poster": "/api/videos/example-drama-a/1",
    "cover": "/api/videos/example-drama-a/2",
    "genre": ["古装", "权谋", "爽剧"],
    "heat": "658万",
    "score": "8.4",
    "description": "众人眼中的纨绔少年...",
    "episodes": [{ "id": "ep_001", "episodeNumber": 1, "title": "第1集", "durationLabel": "05:09", "videoUrl": "/api/videos/example-drama-a/1", "interactionUrl": "/api/dramas/example-drama-a/episodes/1/interactions" }]
  }]
}
```

**前端类型** (`catalog.ts:DramaItem`)：
```typescript
type DramaItem = {
  id: string; title: string; subtitle: string;
  poster: string; cover: string; genre: string[];
  heat: string; score: string; description: string;
  episodes: Episode[];
};
type Episode = {
  id: string; episodeNumber: number; title: string;
  durationLabel: string; videoUrl: string; interactionUrl?: string;
};
```

#### `GET /api/dramas/:id`

获取单个剧目详情。

**响应**：同上 `DramaItem` 对象。

**错误**：
- 404：`{"status": "error", "message": "content not found"}`

#### `GET /api/dramas/:id/episodes`

获取选集列表。

**响应**：
```json
{ "episodes": [/* Episode[] */] }
```

#### `GET /api/dramas/:id/episodes/:number`

获取单集信息。

**响应**：单个 `Episode` 对象。

#### `GET /api/dramas/:id/episodes/:number/interactions`

**这是前端播放核心接口**，返回单集互动清单。

**响应** (`InteractionManifest`)：
```json
{
  "drama_id": "example-drama-a",
  "episode_id": "ep_001",
  "title": "富饶大地 · 第1集",
  "video_url": "/api/videos/example-drama-a/1",
  "duration_ms": 309000,
  "manifest_version": "1.0.0",
  "client_hints": {
    "asset_base_url": "/assets/",
    "ws_enabled": false,
    "tick_ms": 100
  },
  "interaction_points": [
    {
      "id": "ip_celebrate",
      "start_ms": 8000,
      "end_ms": 17000,
      "component": "celebrate_confetti",
      "title": "开心放彩带",
      "emotion": "happy",
      "priority": 0.75,
      "highlight_reason": "主角目标达成，点击释放庆祝礼花",
      "config": {}
    }
  ]
}
```

**前端类型** (`interaction/types.d.ts:InteractionManifest`)：
```typescript
type InteractionManifest = {
  drama_id: string; episode_id: string; title: string;
  video_url: string; duration_ms: number; manifest_version: string;
  client_hints?: { asset_base_url?: string; ws_enabled?: boolean; tick_ms?: number };
  interaction_points: InteractionPoint[];
};
```

#### `GET/HEAD /api/videos/:id/:number`

视频流端点。必须支持 HTTP Range 请求。

**请求头**（前端自动发送）：
```
Range: bytes=0-
```

**响应**：
- `206 Partial Content`（有 Range 头时）
- `Content-Type: video/mp4`
- `Accept-Ranges: bytes`
- `Content-Range: bytes 0-2097151/52428800`
- `Content-Length: 2097152`
- `Cache-Control: public, max-age=31536000, immutable`
- `ETag: W/"...-..."`

**无 Range 头时**：返回前 2MB（`DRAMA_API_MAX_VIDEO_CHUNK_BYTES`）。

### 5.3.2 AI 搜索

#### `POST /api/ai/search`

**请求体**：
```json
{ "query": "扮猪吃虎爽剧", "limit": 8 }
```

**响应**（目标态 — 接入向量搜索后）：
```json
{
  "status": "ok",
  "message": "Found 2 matching item(s).",
  "results": [
    { "type": "drama", "dramaId": "example-drama-a", "title": "富饶大地" },
    { "type": "episode", "dramaId": "example-drama-a", "episodeNumber": 3, "title": "第3集", "snippet": "少年在比武招亲中..." }
  ]
}
```

**当前实现**：子串匹配。**目标实现**：Qdrant 向量搜索（需先修复嵌入服务）。

### 5.3.3 互动事件（待新增 — P0）

#### `POST /api/interactions`

**请求体**：
```json
{
  "events": [
    {
      "event_id": "evt_abc123",
      "point_id": "ip_celebrate",
      "drama_id": "example-drama-a",
      "episode_id": "ep_001",
      "event_type": "celebrate_click",
      "action_data": { "click_count": 3, "growth_level_reached": 1 },
      "client_timestamp": 1718000000000,
      "device_id": "device-uuid-from-localstorage"
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 必选 | 说明 |
|:---|:---|:---|:---|
| `event_id` | string | 是 | 客户端生成 UUID，幂等去重 |
| `point_id` | string | 是 | 对应 Manifest 中的 `ip_*` ID |
| `drama_id` | string | 是 | 剧目 ID |
| `episode_id` | string | 是 | 集 ID (`ep_001`) |
| `event_type` | string | 是 | 事件类型（见下表） |
| `action_data` | object | 是 | 自由 JSON，含具体交互参数 |
| `client_timestamp` | number | 是 | 客户端 Unix 毫秒 |
| `device_id` | string | 是 | 设备标识 |

**事件类型**（`event_type`）：

| event_type | 触发组件 | 说明 |
|:---|:---|:---|
| `celebrate_click` | celebrate_confetti | 庆祝点击 |
| `anger_tap` | anger_release | 泄愤点击 |
| `tear_hold` | tear_resonance | 泪光长按 |
| `laugh_click` | laugh_burst | 笑声点击 |
| `emotion_burst_click` | shatter_strike | 碎屏连点 |
| `sweet_tap` | sugar_storm | 撒糖连点 |
| `shield_hold` | guardian_shield | 守护长按 |
| `team_choose` | team_cheer | 阵营选择 |
| `team_cheer` | team_cheer | 阵营助威 |
| `prediction_submit` | prediction_card / episode_end_prediction | 预测提交 |
| `clue_judge` | clue_judge_card | 线索判断 |
| `emotion_buffer_enter` | emotion_buffer | 缓冲进入 |
| `ip_skip` | — | 用户跳过 IP |
| `ip_timeout` | — | IP 自动超时 |

**响应**：
```json
{
  "accepted": ["evt_abc123"],
  "duplicated": [],
  "rejected": []
}
```

### 5.3.4 用户服务（待新增 — P1）

#### `GET /api/users/me/profile`

**请求头**：`X-Device-Id: device-uuid`

**响应**：
```json
{
  "device_id": "device-uuid",
  "stats": {
    "episodes_watched": 12,
    "interactions_total": 48,
    "favorites": 6
  },
  "recent_activity": [
    { "drama_id": "example-drama-a", "episode_id": "ep_001", "event_type": "celebrate_click", "timestamp": "2026-06-10T..." }
  ]
}
```

#### `GET /api/users/me/history?page=1&page_size=20`

分页互动历史。

### 5.3.5 Pipeline 管理

#### `POST /api/pipelines/understand`

触发视频理解 Pipeline。

**请求体**：
```json
{
  "title": "富饶大地",
  "video_dir": "/path/to/videos",
  "episodes": 20,
  "pattern": "ep{num:02d}.mp4",
  "project_id": "example-drama-a"
}
```

**响应** (`202 Accepted`)：
```json
{
  "id": "job-uuid",
  "kind": "understand",
  "status": "queued",
  "createdAt": "2026-06-10T...",
  "request": { ... }
}
```

#### `POST /api/pipelines/interactions`

触发互动设计 Pipeline。

#### `GET /api/jobs`

任务列表。

#### `GET /api/jobs/:id`

单个任务状态。

### 5.3.6 管理端（待新增 — P1）

#### `POST /api/admin/dramas/upload`

multipart/form-data：
- `title`：剧名
- `episodes`：MP4 文件（多文件上传）
- `total_episodes`：总集数

**响应**：
```json
{ "drama_id": "new-drama", "status": "uploaded", "message": "N files stored" }
```

## 5.4 错误码

| 错误场景 | HTTP 状态 | message |
|:---|:---|:---|
| 路由未找到 | 404 | `"route not found"` |
| 内容未找到 | 404 | `"content not found"` |
| 视频文件缺失 | 404 | `"video file not found; ..."` |
| Manifest 缺失 | 404 | `"manifest missing for ..."` |
| 参数无效 | 400 | `"invalid id: ..."` |
| Range 无效 | 416 | (自动处理) |
| 服务端异常 | 500 | `"Internal error message"` |
| 请求体过大 | 400 | `"request body too large"` |

## 5.5 前端 API 调用层

**实现文件**：`src/data/catalog.ts`

| 函数 | 端点 | 返回类型 |
|:---|:---|:---|
| `loadDramas()` | `GET /api/dramas` | `Promise<DramaItem[]>` |
| `loadDrama(id)` | `GET /api/dramas/:id` | `Promise<DramaItem>` |
| `loadEpisode(dramaId, epNum)` | `GET /api/dramas/:id/episodes/:number` | `Promise<Episode>` |
| `loadEpisodeManifest(dramaId, epNum)` | `GET /api/dramas/:id/episodes/:number/interactions` | `Promise<InteractionManifest \| null>` |
| `requestAiSearch(query)` | `POST /api/ai/search` | `Promise<{status, message, results?}>` |
| `submitEvents(events)` | `POST /api/interactions` (待新增) | `Promise<{accepted, duplicated, rejected}>` |
| `loadProfile(deviceId)` | `GET /api/users/me/profile` (待新增) | `Promise<UserProfile>` |

**关键约定**：
- `configuredApiBase` 从 `VITE_API_BASE_URL` 环境变量读取，为空时使用 Vite 代理
- 所有 API 调用失败时，调用方应展示错误 UI 而非静默降级到硬编码数据

## 5.6 前后端数据对齐规则

| 前端期望字段 | 后端来源 | 对齐状态 |
|:---|:---|:---|
| `DramaItem.id` | `ContentRepository.to_drama_item()["id"]` | ✅ |
| `DramaItem.title` | `project.json: drama_title` 或 `report.json: drama_title` | ✅ |
| `DramaItem.subtitle` | `to_drama_item` 固定返回英文 → **需修复** | 🔴 |
| `DramaItem.poster` | `to_drama_item` 返回视频 URL → 应返回静态图 URL | 🟡 |
| `DramaItem.genre` | `to_drama_item` 固定返回 `["interactive","short-drama"]` → **需修复** | 🔴 |
| `DramaItem.score` | `to_drama_item` 固定返回 `"8.4"` → 暂无真实数据，可保留 | 🟡 |
| `Episode.title` | `to_episode_item` 返回 `"Episode {n}"` → 应返回 `"第{n}集"` | 🔴 |
| `Episode.videoUrl` | `to_episode_item` 拼接 `/api/videos/{id}/{n}` | ✅ |
| `Episode.interactionUrl` | `to_episode_item` 拼接 `/api/dramas/{id}/episodes/{n}/interactions` | ✅ |
| `InteractionManifest.interaction_points` | `load_manifest()` 从 ep_*.interactions.json 读取 | ✅ |
