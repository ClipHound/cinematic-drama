# SDD-01-系统架构设计

> 版本：v1.0  
> 定稿日期：2026-06-10  
> 客户端决策：React 19 + Capacitor Android App（非 Flutter）；Web 端同时承担管理端和调试辅助

## 1.1 架构总览

系统采用**事件驱动的双链路、C/S 架构**：

- **离线生产链路**（Build-time）：短剧入库 → Doubao VLM 视频理解 → 互动编排 → 分支叙事 → 产出三类产物
- **在线运行链路**（Runtime）：前端 App 拉取产物 → 客户端时间轴驱动互动触发 → 本地视觉/触觉反馈 → 异步回传事件 → 服务端记录

两条链路通过 **Manifest JSON 文件**作为唯一交接面，离线产物只读、版本化、Schema 校验通过后才允许在线消费。

## 1.2 架构视图

### 1.2.1 部署视图（Deployment View）

```
┌──────────────────────────────────────────────────────────────┐
│                    单机服务端                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Python   │  │ SQLite   │  │ Qdrant   │  │ 静态文件     │ │
│  │ API Srv  │  │ (记忆库) │  │ (向量)   │  │ (视频/资产) │ │
│  │ :8787    │  │          │  │ :6333    │  │ /api/videos │ │
│  └────┬─────┘  └──────────┘  └──────────┘  └─────────────┘ │
│       │         data/ 卷 (共享存储)                           │
│       │         projects/ + outputs/ + content/videos/       │
└───────┼──────────────────────────────────────────────────────┘
        │ HTTP (局域网或公网)
┌───────┼──────────────────────────────────────────────────────┐
│       │              客户端设备                               │
│  ┌────┴─────┐                                                │
│  │ Android  │  React 19 SPA → Capacitor WebView              │
│  │   App    │  + 原生 Haptics / Share / Filesystem           │
│  └──────────┘                                                │
│  ┌──────────┐                                                │
│  │ Web 管理  │  React 同一代码库 /admin 路由                   │
│  │   端      │  + 上传 / Pipeline 状态 / 手工标注              │
│  └──────────┘                                                │
└──────────────────────────────────────────────────────────────┘
```

**关键组件**：

| 组件 | 技术选型 | 角色 |
|:---|:---|:---|
| API 服务 | Python `http.server` (当前) → FastAPI (目标) | 在线 API：剧目列表、详情、视频流、Manifest 下发、事件接收 |
| 主数据库 | SQLite (当前) → PostgreSQL + pgvector (目标) | 结构化数据、用户、事件 |
| 向量存储 | Qdrant (当前) | 语义搜索、角色/事件相似检索 |
| 嵌入服务 | Ollama + BGE-M3 (目标) | 文本嵌入向量生成 |
| 任务队列 | 无 (当前) → Celery + Redis (目标) | Pipeline 编排、异步任务 |
| 静态服务 | Python API 内联 (当前) → Nginx (目标) | 视频 Range 请求、资产托管 |
| 主客户端 | React 19 + Capacitor (Android WebView) | 播放、互动、事件回传 |
| 管理端 | React 同一代码库 `/admin` 路由 | 上传、Pipeline 触发、手工标注 |

### 1.2.2 逻辑视图（Logical View）

```
┌─────────────────────────────────────────────────────────────┐
│                     离线生产链路                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ ASR 转录  │→ │ VLM 理解  │→ │ 互动编排  │→ │ 质量门控  │   │
│  │ (FunASR) │  │ (Doubao) │  │ (Designer)│  │ (17 rules)│   │
│  └──────────┘  └──────────┘  └────┬─────┘  └────┬─────┘    │
│                                   │             ↓           │
│                  ┌────────────────┴────┐  is_ready=true     │
│                  ↓                     ↓                    │
│           ┌──────────┐          ┌──────────┐                │
│           │ 分支叙事  │          │ 资产引用  │               │
│           │ (Branch)  │          │ (Lottie等)│               │
│           └────┬─────┘          └────┬─────┘                │
│                └──────────┬──────────┘                      │
└───────────────────────────┼─────────────────────────────────┘
                            ↓
                ┌────────────────────────┐
                │  交接面：Manifest JSON  │
                │  ep_*.interactions.json│
                │  + rhythm_blueprint.json│
                │  + project.json         │
                └───────────┬────────────┘
                            ↓
┌───────────────────────────┼─────────────────────────────────┐
│                     在线运行链路                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ REST API │  │ 视频流    │  │ 静态资产  │                 │
│  │ /api/*   │  │ Range 206 │  │ /assets/* │                 │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                  │
│       └─────────────┴─────────────┘                          │
│                            ↕ HTTP                            │
│                   ┌─────────────────┐                        │
│                   │ React 19 App     │                       │
│                   │ 播放/12组件/动画/ │                       │
│                   │ 队列/剧尾/记录页  │                       │
│                   │ + Capacitor 原生  │                       │
│                   └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2.3 数据流视图（Data-Flow View）

| 流向 | 数据 | 频率 | 通道 |
|:---|:---|:---|:---|
| 离线 → 文件系统 | Manifest JSON / Blueprint / 中间产物 | 每剧一次（处理时） | 写文件 |
| 文件系统 → 后端内存 | ContentRepository 扫描 project.json + manifest | 每次 API 请求 | 文件读 |
| 后端 → 前端 | 剧目列表、详情、Manifest（含 IP 列表） | 用户进入页面 | HTTP GET |
| 后端 → 前端 | 视频流（MP4 Range 请求） | 播放时持续 | HTTP 206 |
| 前端 → 后端 | 互动事件（批量） | 互动发生 / 定时 flush | HTTP POST |
| 前端 → localStorage | 事件队列持久化 | 每事件 | 浏览器 API |

## 1.3 技术栈最终决策

| 层 | 选型 | 版本基线 | 说明 |
|:---|:---|:---|:---|
| 后端语言 | Python | 3.11+ | 与 Doubao SDK 生态对齐 |
| 后端框架 (当前) | `http.server` 标准库 | — | 轻量，路由手动分发 |
| 后端框架 (目标) | FastAPI | 0.110+ | 自动 OpenAPI、Pydantic 校验、异步 |
| 主数据库 (当前) | SQLite | — | 文件级，单机友好 |
| 主数据库 (目标) | PostgreSQL 16 + pgvector | 16.x + 0.6+ | 结构化 + 向量二合一 |
| 向量存储 | Qdrant | 1.9+ | 已集成，需确保可用 |
| 嵌入模型 | BGE-M3 (via Ollama) | — | 1024 维，中文友好 |
| 任务队列 (目标) | Celery + Redis | 5.3+ / 7.x | Pipeline 编排、失败重试 |
| ORM (目标) | SQLAlchemy 2.x + Alembic | — | 异步支持、迁移管理 |
| 前端框架 | React 19 | 19.2+ | 组件化、hooks、生态成熟 |
| 构建工具 | Vite 8 | 8.0+ | 快速 HMR、TypeScript 原生支持 |
| 样式 | Tailwind CSS 4 | 4.1+ | 原子化、设计系统 |
| 路由 | React Router 7 | 7.10+ | SPA 路由 |
| 图标 | Lucide React | 0.560+ | 一致性图标集 |
| App 封装 | Capacitor 8 | 8.0+ | WebView + 原生插件桥接 |
| 原生触觉 | `@capacitor/haptics` | — | Android VibrationEffect |
| 原生分享 | `@capacitor/share` | — | 系统分享面板 |
| 原生文件 | `@capacitor/filesystem` | — | 离线缓存 |
| AI 模型 (VLM) | Doubao Seed (via 方舟 API) | ep-20260514111117 | 视频理解、剧情摘要、互动设计 |
| AI 模型 (ASR) | FunASR (自部署) | — | 词级时间戳 + 情绪 + VAD |
| AI 模型 (Embedding) | BGE-M3 (via Ollama) | — | 语义搜索 |
| 音视频处理 | FFmpeg | 6.x | 关键帧提取、视频时长探测 |
| 容器编排 (目标) | Docker Compose | v2 | 单机部署 |

## 1.4 关键技术决策（ADR 摘要）

| 决策 ID | 决策 | 选项 | 决定 | 理由 |
|:---|:---|:---|:---|:---|
| **D-001** | 主客户端平台 | Flutter / React+Capacitor / 纯 Web | **React 19 + Capacitor** | 前端已用 React 开发完成；Capacitor 可封装为 Android APK 并调用原生能力；如答辩严格要求原生性能再评估 Flutter 迁移 |
| **D-001A** | Web 定位 | 主客户端 / 管理端 / 两者兼备 | **两者兼备** — 同一代码库，Capacitor 构建 App，Web 路由承担管理端 | 降低维护成本 |
| **D-002** | 后端框架演进 | 保持 http.server / 迁移 FastAPI | **分阶段**：MVP 保持 http.server 先跑通闭环，P1 迁移 FastAPI | 降低阶段性风险 |
| **D-003** | 数据库 | SQLite / PostgreSQL+pgvector | **分阶段**：MVP 保持 SQLite+Qdrant，P1 统迁 PostgreSQL+pgvector | Qdrant 已集成，先确保可用 |
| **D-004** | 触发模型 | 客户端时间轴 / 服务端下发 | **客户端时间轴驱动** | 毫秒级精度、无网络依赖 |
| **D-005** | 反馈时序 | 先服务端确认 / 先本地反馈 | **先本地反馈，事件异步回传** | 用户体验优先 |
| **D-006** | Manifest 加载 | 启动全量 / 按需加载 | **按需加载**（进入播放页时拉取单集 Manifest） | React SPA 模式，减少首屏体积 |
| **D-007** | 文件存储 | 本地文件 / MinIO / 云 OBS | **本地文件（MVP）** | 部署最简 |
| **D-008** | Pipeline 编排 | Celery / 直接同步调用 | **直接同步调用（MVP）**，后续迁移 Celery | MVP 全自动批量处理，无需队列 |
| **D-009** | 用户体系 | 完整账号 / 设备 ID | **localStorage + 可选设备 ID** | MVP 本地存储即可 |
| **D-010** | 扩写生成时机 | 离线预生成 / 在线实时 | **全部离线预生成** | 质量可控、播放时无延迟 |
| **D-011** | 嵌入向量方案 | SHA-256 伪嵌入 / 真实 BGE-M3 | **立即切换到真实 BGE-M3** | 伪嵌入导致语义搜索完全失效 |
| **D-012** | 图像生成 | Placeholder / Seedream / 文生图 API | **MVP 使用占位图**（全局模板兜底），P2 接入文生图 | 降低 MVP 复杂度 |

## 1.5 AI 模型接入约束

| 用途 | 模型 | 调用方 | 调用形态 |
|:---|:---|:---|:---|
| 全片转录 (ASR) | FunASR (Paraformer-large) | 离线 Agent | 批处理，词级时间戳 + 情绪 + VAD |
| 视频理解 (VLM) | Doubao Seed 1.5 (via 方舟 Ark API) | 离线 Agent | base64 视频 (≤50MB) 或 File API (>50MB) |
| 剧情摘要/互动设计 | Doubao Seed 1.5 (via 方舟 Ark API) | 离线 Agent | 文本对话，含视频帧引用 |
| 嵌入向量 | BGE-M3 (via Ollama) | 离线 Agent + 在线 API | 批处理文本嵌入 |
| 角色立绘/徽章 (P2) | 文生图 API (Seedream) | 离线 Agent | 批处理（可选 P2） |

**约束**：
1. 所有 AI 调用集中在离线 Agent，**在线服务严禁实时调用 AI**
2. 模型版本号写入 Manifest 的 `model_version` 字段，便于追溯
3. 同一短剧固定 `temperature` 和 `seed`，保证可重现
4. 调用失败有重试策略（Doubao API 429→60s 重试×3，5xx→30s 重试×2）

## 1.6 跨系统契约（核心约束）

### 离线系统的承诺
- **C-01**：产物以 UTF-8 JSON 输出，符合 SDD-06 定义的 Schema
- **C-02**：manifest 中 `interaction_points` 非空时所有必要字段完整
- **C-03**：资产文件路径以**相对路径**写入 Manifest（如 `/assets/sweet-demo/...`）
- **C-04**：Pipeline 失败时不输出半成品，中间文件保留在 action_plans/ 和 patches/ 目录
- **C-05**：同一 `drama_id + episode_id` 的 manifest 覆写须原子（先写临时文件再 rename）
- **C-06**：Manifest 的 `client_hints.asset_base_url` 默认为 `/assets/`

### 在线系统的承诺
- **C-07**：不修改任何离线产物文件
- **C-08**：manifest 缺失或 interaction_points 为空时，前端仅播放视频，不触发互动
- **C-09**：资产文件 404 时使用全局默认占位，不影响核心播放
- **C-10**：视频 Range 请求必须返回 206 Partial Content，支持拖动进度
- **C-11**：前端不依赖 WebView 承载主播放体验；播放页、互动组件均为原生 DOM 渲染
- **C-12**：前端必须支持后端 Base URL 配置（`VITE_API_BASE_URL` 环境变量）

## 1.7 横切关注点（Cross-cutting Concerns）

| 关注点 | 设计决策 |
|:---|:---|
| **日志** | 后端：Python `print()` / `logging` 到 stdout，按请求输出；前端：`console` 分级，生产构建移除 debug |
| **错误码** | 统一错误码体系，见 SDD-05 §5.5 |
| **配置** | 12-factor 风格：`.env` 文件 + 环境变量；前端 `VITE_*` 前缀；后端 `DRAMA_*` 前缀 |
| **国际化** | MVP 仅中文，文案内联在组件中 |
| **时间** | 视频时间：毫秒整数；系统时间：ISO 8601 UTC |
| **安全** | MVP 不做认证；`.env` 不入库（已发现泄露需轮换）；管理端用 `X-Admin-Token` 头 |
| **降级** | 任何外部依赖（AI API、Qdrant、Ollama、视频文件）失败均有明确降级路径 |
| **版本化** | Manifest `manifest_version` 语义版本号；API 当前无版本前缀，目标态加 `/api/v1` |

## 1.8 性能与容量基线

| 指标 | 基线值 | 说明 |
|:---|:---|:---|
| 单部剧总集数 | ≤30 集（当前最大 62 集） | 单集 2-7 分钟 |
| 单集高光点数 | 5-12 个 | 由互动设计 Agent 自动编排 |
| 单集 Manifest 大小 | <50 KB | JSON，含 5-12 个 IP |
| 离线 Pipeline 单集耗时 | 10-30 分钟 | ASR(5min) + VLM(10min) + LLM编排(5min) |
| 在线 API P95 延迟 | <500 ms（MVP 目标） | 文件扫描 + JSON 序列化 |
| 视频首字节延迟 | <2 秒（局域网） | Range 请求 206 |
| 前端首屏加载 | <3 秒（中端机） | Vite build + code splitting |
| 前端播放首帧 | <2 秒 | 视频预加载 metadata |
| 前端播放中帧率 | ≥30fps（LOW）/ ≥45fps（MEDIUM） | 互动组件动画 |

## 1.9 演进路线图

```
Phase 1 (MVP 融合)        Phase 2 (交互闭环)       Phase 3 (体验增强)
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ 前后端数据链路    │ →   │ 事件上报+用户系统│ →   │ WebSocket 热力   │
│ 消除硬编码        │     │ 点赞/收藏/分享   │     │ FastAPI 迁移     │
│ AI 搜索接入向量   │     │ 视频上传管理端   │     │ PostgreSQL 迁移  │
│ BGE-M3 替换伪嵌入 │     │ App APK 构建     │     │ Docker 部署      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
      P0 (3-5天)              P0 (5-7天)             P1 (7-10天)
```

详细任务拆分见 SDD-09。
