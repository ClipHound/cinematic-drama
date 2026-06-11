# SDD-06-数据模型与Schema

> 版本：v1.0  
> 定稿日期：2026-06-10

## 6.1 离线产物 Schema：Interaction Manifest

### 6.1.1 顶层结构

**文件**：`outputs/{drama_id}/ep_{NNN}.interactions.json`

| 字段 | 类型 | 必选 | 说明 |
|:---|:---|:---|:---|
| `drama_id` | string | 是 | 剧目唯一标识（如 `example-drama-a`） |
| `episode_id` | string | 是 | 集标识（如 `ep_001`） |
| `title` | string | 是 | 显示标题（如 `富饶大地 · 第1集`） |
| `video_url` | string | 是 | 视频相对路径（如 `/api/videos/example-drama-a/1`） |
| `duration_ms` | int | 是 | 视频总时长（毫秒） |
| `manifest_version` | string | 是 | 语义版本（如 `1.0.0`） |
| `client_hints` | object | 是 | 客户端运行配置 |
| `interaction_points` | array | 是 | 互动点列表 |

### 6.1.2 client_hints

| 字段 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `asset_base_url` | string | `"/assets/"` | 前端资产根路径 |
| `ws_enabled` | bool | `false` | 是否开启 WebSocket（当前未实现） |
| `tick_ms` | int | `100` | 时间轴检查间隔 |

### 6.1.3 interaction_point（互动点）

| 字段 | 类型 | 必选 | 说明 |
|:---|:---|:---|:---|
| `id` | string | 是 | 全局唯一 ID（如 `ip_celebrate`） |
| `start_ms` | int | 是 | 触发起始时间（毫秒） |
| `end_ms` | int | 是 | 触发结束时间（毫秒），建议 `start_ms + 9000` |
| `component` | string | 是 | 组件 ID（见 §6.1.4） |
| `title` | string | 是 | 中文标题 |
| `emotion` | string | 是 | 情绪标签（`happy/angry/sad/funny/satisfying/sweet/guard/support/curious/insight/buffer/cliffhanger`） |
| `priority` | float | 是 | [0, 1]，用于抢占决策 |
| `highlight_reason` | string | 否 | 设计理由（供调试用） |
| `config` | object | 是 | 组件特定配置（见 §6.1.5） |

### 6.1.4 组件 ID 枚举

| component | 中文名 | 交互模式 |
|:---|:---|:---|
| `celebrate_confetti` | 开心放彩带 | 点击 |
| `anger_release` | 怒火宣泄 | 点击 |
| `tear_resonance` | 泪光共鸣 | 长按 |
| `laugh_burst` | 笑出声 | 点击 |
| `shatter_strike` | 碎屏暴击 | 连点 |
| `sugar_storm` | 满屏撒糖 | 连点 |
| `guardian_shield` | 守护加持 | 长按 |
| `team_cheer` | 站队助威 | 选择+连点 |
| `prediction_card` | 剧情预测卡 | 选择 |
| `clue_judge_card` | 线索判断卡 | 选择 |
| `episode_end_prediction` | 剧尾预测卡 | 选择 |
| `emotion_buffer` | 情绪缓冲通道 | 长按 |

### 6.1.5 config（组件特定配置）

**通用字段**（所有组件可选）：
```json
{
  "auto_dismiss_ms": 5000
}
```

**team_cheer 特有**：
```json
{
  "team_options": [
    { "team_key": "hero", "label": "支持女主", "color": "#ff5a66" },
    { "team_key": "rival", "label": "支持对方", "color": "#36c6d3" }
  ],
  "timer_text": "00:05:27",
  "prompt_text": "选择阵营，为TA助威"
}
```

**prediction_card / episode_end_prediction 特有**：
```json
{
  "prediction_id": "pred_mid_001",
  "question": "她会说出真相吗？",
  "options": [
    { "option_key": "yes", "label": "会" },
    { "option_key": "no", "label": "不会" }
  ]
}
```

**clue_judge_card 特有**：
```json
{
  "clue_id": "clue_photo_001",
  "question": "这张照片是重要线索吗？",
  "options": [
    { "option_key": "yes", "label": "是线索" },
    { "option_key": "no", "label": "只是道具" }
  ]
}
```

## 6.2 Project 元数据

**文件**：`projects/{project_id}/project.json`

```json
{
  "project_id": "example-drama-a",
  "drama_title": "富饶大地",
  "total_episodes": 20,
  "created_at": "2026-06-10T00:00:00Z",
  "updated_at": "2026-06-10T12:00:00Z"
}
```

## 6.3 理解报告

**文件**：`projects/{project_id}/output/report.json`

```json
{
  "project_id": "example-drama-a",
  "drama_title": "富饶大地",
  "episodes_processed": 20,
  "results": [{
    "episode_num": 1,
    "summary": "少年被迫卷入比武招亲...",
    "actions_total": 15,
    "actions_succeeded": 14,
    "actions_failed": 1,
    "patches_committed": 12,
    "errors": [],
    "candidate_interactions": [
      { "start_ms": 8000, "end_ms": 17000, "type": "achievement", "component": "celebrate_confetti" }
    ]
  }],
  "characters": [{
    "id": 1, "name": "主角名", "aliases": [], "role": "protagonist",
    "traits": {}, "status": "active", "first_appearance_ep": 1
  }],
  "relationships": [{ "character_a": "A", "character_b": "B", "relation_type": "ally" }],
  "plot_events": [{
    "episode_num": 1, "description": "比武招亲开始",
    "start_time": "00:08", "end_time": "00:17", "event_type": "conflict"
  }],
  "plot_threads": [{ "id": 1, "name": "身世之谜", "status": "open" }],
  "episode_summaries": [{
    "episode_num": 1, "summary": "...", "mood": "tension", "cliffhanger": "..."
  }]
}
```

## 6.4 数据库表（SQLite）

### 6.4.1 记忆系统表（离线 Pipeline 使用）

| 表名 | 说明 | 关键字段 |
|:---|:---|:---|
| `characters` | 角色 | id, name, aliases(JSON), role, traits(JSON), status, first_appearance_ep, last_appearance_ep |
| `relationships` | 角色关系 | id, character_a, character_b, relation_type, intimacy_level, description |
| `plot_events` | 剧情事件 | id, episode_num, description, start_time, end_time, event_type, characters_involved, confidence |
| `plot_threads` | 剧情线程 | id, name, description, status(open/closed), opened_ep, closed_ep |
| `episode_summaries` | 集摘要 | episode_num, summary, mood, cliffhanger |
| `series_state` | 系列状态 | current_episode, total_episodes, updated_at |
| `action_plans` | Action Plan 日志 | episode_num, plan_json, parsed_at |

### 6.4.2 在线服务表（待新增）

| 表名 | 说明 | 关键字段 |
|:---|:---|:---|
| `interaction_events` | 互动事件 | event_id (UNIQUE), device_id, drama_id, episode_id, point_id, event_type, action_data(JSON), client_timestamp, created_at |
| `user_profiles` | 用户档案 | device_id (UNIQUE), episodes_watched, interactions_total, favorites_count, created_at, updated_at |

**interaction_events 建表语句**（待执行）：
```sql
CREATE TABLE IF NOT EXISTS interaction_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    device_id TEXT NOT NULL,
    drama_id TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    point_id TEXT,
    event_type TEXT NOT NULL,
    action_data TEXT DEFAULT '{}',
    client_timestamp INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_device ON interaction_events(device_id);
CREATE INDEX IF NOT EXISTS idx_events_drama_ep ON interaction_events(drama_id, episode_id);
```

## 6.5 Qdrant Collections

| Collection | 向量维度 | 用途 | 当前同步状态 |
|:---|:---|:---|:---|
| `{project_id}_characters` | 1024 | 角色语义搜索 | ✅ 已实现 |
| `{project_id}_events` | 1024 | 剧情事件语义搜索 | 🔴 未同步（`state_patch.py:73` 硬编码跳过） |
| `{project_id}_episode_contexts` | 1024 | 集上下文语义搜索 | 🔴 未同步 |

## 6.6 事件队列（前端 localStorage）

**Key**：`cinematic-drama-events`

```typescript
type EventRecord = {
  id: string;           // UUID
  pointId: string;      // IP ID
  type: string;         // event_type
  actionData: Record<string, unknown>;
  atMs: number;         // 播放位置
  createdAt: string;    // ISO 8601
};
```

## 6.7 交互组件资产目录

```
public/assets/
├── qingzhu-demo/        # celebrate_confetti 资产
│   ├── src/styles/app.css
│   ├── images/{x.png, tong-cutout.png}
│   └── videos/lipao.json     # Lottie 动画
├── angry-demo/          # anger_release 资产
│   ├── src/styles/app.css
│   ├── images/{angry.png, hand-cutout.png, texiao-cutout.png, x.png}
│   └── videos/angry.json
├── gandong-demo/        # tear_resonance 资产
├── laugh-demo/          # laugh_burst 资产
├── crack-demo/          # shatter_strike 资产
├── sweet-demo/          # sugar_storm 资产
├── guard-demo/          # guardian_shield 资产
├── zhandui-demo/        # team_cheer 资产
├── yuce-demo/           # prediction_card 资产
├── xiansuo-demo/        # clue_judge_card 资产
├── yuce-end-demo/       # episode_end_prediction 资产
├── huanchong-demo/      # emotion_buffer 资产
├── app-overrides/       # 全局样式覆盖
│   └── effect-lift.css
└── vendor/              # 第三方库
    └── lottie/          # Lottie Web 运行库
```
