# SDD-09-实施任务拆分与AI开发规约

> 版本：v1.0  
> 定稿日期：2026-06-10  
> **核心原则：后端离线 Pipeline 已经可用，仅做周边修补，不做重构。**

## 9.1 总览

融合升级分 6 个阶段，按 P0→P1→P2 优先级执行。每阶段产出独立的可验证增量。

| 阶段 | 名称 | 优先级 | 预估工时 | 产出 |
|:---|:---|:---|:---|:---|
| Phase 1 | 数据链路打通 | **P0** | 3-5 天 | 前端从 API 加载真实数据 |
| Phase 2 | 死代码清理 | **P0** | 1-2 天 | 代码库瘦身，消除屎山 |
| Phase 3 | 交互闭环 | **P0** | 5-7 天 | 事件上报/用户系统/点赞收藏 |
| Phase 4 | 后端周边修补 | **P0** | 3-4 天 | 嵌入修复/AI搜索/元数据中文 |
| Phase 5 | 视频入库管线 | **P1** | 3-5 天 | 上传→Pipeline→上架 |
| Phase 6 | App 封装 + 体验增强 | **P1** | 5-7 天 | APK 构建/原生插件/热力推送 |

**总预估**：20-30 天（单人全职）

## 9.2 Phase 1: 数据链路打通 (P0, 3-5 天)

**目标**：前端所有页面从后端 API 加载真实数据，消灭硬编码占位。

### 任务 1.1：前端数据层改造（2 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 1.1.1 | 删除 `catalog.ts` 硬编码数据 | `src/data/catalog.ts:38-89` | 删除 `exampleDramaA` 和 `example-drama-b` 常量，`dramas` 数组改为空 |
| 1.1.2 | 删除 `drama.ts` 死代码 | `src/data/drama.ts` | 整文件删除 |
| 1.1.3 | 替换 `manifest.ts` 硬编码 | `src/data/manifest.ts:23-85` | `playerManifest` 替换为空兜底（`interaction_points: []`, `duration_ms: 0`） |
| 1.1.4 | 各页面增加 loading/error 状态 | 6 个 page 文件 | 替换 `.catch(() => undefined)` 为明确的 error state + 重试按钮 |
| 1.1.5 | 修复 HomePage 静音问题 | `HomePage.tsx:193` | 移除硬编码 `muted`，改为活跃视频有声/非活跃静音 |

**验收标准**：
- 后端 API 正常时，前端全部从 API 加载数据
- 后端不可达时，前端显示"网络不可用"错误信息（而非展示硬编码假数据）
- 首页视频活跃时有声音

### 任务 1.2：后端 API 数据对齐（1 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 1.2.1 | `subtitle` 中文化 | `content.py:99` | 从 `report.json` 的 `drama_title` 或首集摘要推导 |
| 1.2.2 | `genre` 从数据推导 | `content.py:102` | 从 report.json mood/tags 推导题材（如 mood 含 tension→权谋, 含 sweet→甜宠） |
| 1.2.3 | Episode title 中文化 | `content.py:114` | `f"第 {number} 集"` |
| 1.2.4 | poster/cover 修复 | `content.py:100-101` | poster 应指向静态图而非视频 URL；无静态图时用占位图 |

**验收标准**：
- `GET /api/dramas` 返回中文 subtitle/genre/title
- 前端展示的剧目信息完整且正确

### 任务 1.3：前后端联调（1 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 1.3.1 | 确保视频文件存在且可播放 | `content/videos/example-drama-a/ep_*.mp4` |
| 1.3.2 | 确保 Manifest 文件可加载 | `outputs/example-drama-a-final/ep_*.interactions.json` |
| 1.3.3 | 端到端测试：6 个页面全部通过 | 手动走一遍 Demo 脚本 |

## 9.3 Phase 2: 死代码清理 (P0, 1-2 天)

**目标**：清除审计发现的全部死代码，降低维护负担。

### 任务清单

| # | 文件 | 操作 | 行数 |
|:---|:---|:---|:---|
| 2.1 | `src/interaction/components.js` | 删除 Legacy 函数（15 个） | ~600 行 |
| 2.2 | `src/interaction/components.js:1547` | `ClueJudgeCard` 从 Legacy 迁移到新版 `realOptionCard` | — |
| 2.3 | `src/interaction/components.js` | 删除未使用的 helper 函数（6 个） | ~80 行 |
| 2.4 | `drama-understanding-agent/src/drama_agent/engine/state_patch.py:60-66` | 删除未使用的 `_apply_patch` 方法 | 7 行 |
| 2.5 | 所有 `__pycache__/` | 加入 `.gitignore` + 删除已提交的 | — |
| 2.6 | `frames_ep01/` | 移出仓库或加入 `.gitignore` | — |

**验收标准**：
- `components.js` 从 2118 行缩减到 ≤1500 行
- 前端 `npm run build` 通过
- 后端 Pipeline 可正常运行

## 9.4 Phase 3: 交互闭环 (P0, 5-7 天)

**目标**：让点赞、收藏、互动全部产生实际效果，事件上报到后端。

### 任务 3.1：后端新增事件端点（1 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 3.1.1 | 执行 `interaction_events` 建表 SQL | 在 `ContentRepository` 初始化时建表 |
| 3.1.2 | 新增 `POST /api/interactions` 路由 | 接收批量事件，写入 SQLite，event_id 去重 |
| 3.1.3 | 新增 `GET /api/users/me/profile` | 基于 device_id 聚合统计 |

### 任务 3.2：前端事件系统改造（2 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 3.2.1 | `flush()` 实现 HTTP POST | `interaction/queue.ts` | 发送到 `POST /api/interactions` |
| 3.2.2 | 所有 `onInteract` 回调接入队列 | `HomePage.tsx`, `PlayerPage.tsx` | 当前仅处理 `emotion_buffer` 跳过，需覆盖全部 12 种组件 |
| 3.2.3 | 点赞按钮添加 handler | `HomePage.tsx:228` | 点击 → 本地动画 + 入队 (`event_type: "like"`) |
| 3.2.4 | 分享按钮添加 handler | `TopBar.tsx:18` | 点击 → `navigator.share()` 或 Capacitor Share |
| 3.2.5 | flush 时机 | `queue.ts` | 定时 10s / 满 10 条 / 页面隐藏 / 切后台 |

### 任务 3.3：个人页真实化（1 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 3.3.1 | 从 API 加载用户统计 | `ProfilePage.tsx` | 替换硬编码 stats |
| 3.3.2 | `X-Device-Id` 生成与管理 | 新增工具函数 | 首启生成 UUID → localStorage → 所有写请求携带 |

### 任务 3.4：互动统计展示（1 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 3.4.1 | 互动组件展示实时操作计数 | 如：撒糖组件显示"甜蜜度 N%"后加"共 N 人参与" |
| 3.4.2 | 站队组件展示阵营比分 | 从 Manifest config 初始化，本地累加 |

**验收标准**：
- 点击互动组件 → 事件入队 → 10 秒内 POST 到后端 → 后端入库
- 点赞按钮有点击反馈 + 事件记录
- 个人页显示真实互动统计
- 分享按钮打开系统分享面板

## 9.5 Phase 4: 后端周边修补 (P0, 3-4 天)

**目标**：修复嵌入系统、AI 搜索、Qdrant 静默失败等已知问题。**不做框架级重构。**

### 任务 4.1：嵌入系统修复（1 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 4.1.1 | Ollama BGE-M3 部署 | — | `ollama pull bge-m3`，确认 `http://localhost:11434` 可访问 |
| 4.1.2 | 修复嵌入降级逻辑 | `memory/embeddings.py:29` | 远程嵌入失败时**记录错误日志**而非静默切换到 SHA-256 |
| 4.1.3 | 添加嵌入健康检查 | `embeddings.py` | 新增 `health_check()` 方法，启动时验证 |

### 任务 4.2：Qdrant 容错修复（0.5 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 4.2.1 | Qdrant 连接失败显式报错 | `memory/vectors.py:66-67` | 构造函数内 `except` 时打印清晰错误信息（而非静默 `enabled=False`） |
| 4.2.2 | 向量操作 disabled 时日志告警 | `vectors.py:96,125,111` | `upsert_point/search/delete_point` 在 disabled 时打印 warning |

### 任务 4.3：AI 搜索升级（1 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 4.3.1 | 接入 Qdrant 向量搜索 | `api/content.py:164-191` | 替换子串匹配为 `VectorStore.search()` |
| 4.3.2 | 搜索范围扩展 | `content.py:search()` | 搜索 characters、plot_events、episode_summaries 的向量 |

### 任务 4.4：前端 AI 搜索完善（0.5 天）

| # | 任务 | 文件 | 说明 |
|:---|:---|:---|:---|
| 4.4.1 | 搜索结果展示为卡片 | `AiSearchPage.tsx` | 当前只显示纯文本 message，改为可点击的剧目/剧集卡片 |
| 4.4.2 | 修复搜索热词截断 | `SearchPage.tsx:77` | `item.slice(0, 4)` → 使用完整的搜索词 |

**验收标准**：
- Ollama BGE-M3 运行正常
- AI 搜索返回语义相关结果（而非子串匹配）
- Qdrant 不可用时打印清晰错误（而非静默失败）

## 9.6 Phase 5: 视频入库管线 (P1, 3-5 天)

**目标**：建立视频上传 → Pipeline 触发 → 前端可见的完整流程。

### 任务 5.1：管理端上传页（2 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 5.1.1 | 新增 `/admin` 路由 + AdminPage | React 页面：表单（剧名、总集数、体裁） + 多文件拖拽上传 |
| 5.1.2 | 新增 `POST /api/admin/dramas/upload` | multipart 接收，存入 `content/videos/{drama_id}/` |
| 5.1.3 | 自动创建 `project.json` | 上传后写入 `projects/{drama_id}/project.json` |

### 任务 5.2：Pipeline 触发与状态展示（1-2 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 5.2.1 | 上传后回调 Pipeline | 上传完成 → `POST /api/pipelines/understand` |
| 5.2.2 | Pipeline 状态面板 | `/admin` 页展示 Job 列表 + 进度 |
| 5.2.3 | Manifest 热加载 | Pipeline 完成后 `GET /api/dramas` 能发现新剧 |

**验收标准**：
- 管理页上传 3 集测试短剧 → 存入视频目录 → 自动触发 Pipeline
- Pipeline 完成后前端剧目列表出现新剧

## 9.7 Phase 6: App 封装 + 体验增强 (P1, 5-7 天)

**目标**：产出可安装的 Android APK，补充原生能力和实时体验。

### 任务 6.1：Capacitor 构建（2 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 6.1.1 | `npm run cap:add:android` | 创建 `android/` 工程 |
| 6.1.2 | 配置包名/版本号/签名 | `capacitor.config.ts` + `android/app/build.gradle` |
| 6.1.3 | 调试 APK 构建 | Android Studio → Build → Build APK |
| 6.1.4 | 真机安装测试 | 安装 APK → 验证播放/互动 |

### 任务 6.2：原生插件接入（1 天）

| # | 插件 | 用途 |
|:---|:---|:---|
| 6.2.1 | `@capacitor/haptics` | 互动组件震动反馈（guardian_shield 长按蓄力、shatter_strike 碎屏） |
| 6.2.2 | `@capacitor/share` | 分享剧目链接 |
| 6.2.3 | `@capacitor/status-bar` | 播放页全屏沉浸 |

### 任务 6.3：触觉反馈接入（1 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 6.3.1 | guardian_shield 长按震动 | `Haptics.impact({ style: ImpactStyle.Medium })` |
| 6.3.2 | shatter_strike 连击震动 | `Haptics.impact({ style: ImpactStyle.Heavy })` |
| 6.3.3 | emotion_buffer 缓冲震动 | `Haptics.vibrate({ duration: 2000 })` |
| 6.3.4 | Capacitor 环境检测 | Web 模式降级（不调用 Haptics API） |

### 任务 6.4：体验增强（1-2 天）

| # | 任务 | 说明 |
|:---|:---|:---|
| 6.4.1 | 首页视频声音控制 | 活跃视频有声 + 非活跃静音 + 静音切换按钮 |
| 6.4.2 | 设备分级检测 | `navigator.hardwareConcurrency` + `deviceMemory` → LOW/MEDIUM/HIGH |
| 6.4.3 | 粒子数量随设备分级 | HIGH:80, MEDIUM:50, LOW:25 |
| 6.4.4 | 详情页"更多"菜单 | 分享/收藏/缓存 操作 |

**验收标准**：
- Android 真机可安装 APK，冷启动 ≤3 秒
- 互动组件有触觉反馈（仅在真机，Web 降级）
- 播放页全屏沉浸
- 粒子/动画跟随设备性能自适应

## 9.8 AI 开发使用指南

### 9.8.1 给 AI Coding 工具的任务说明

1. **一次只做一个 Phase** — 不要试图跨阶段修改
2. **先读对应的 SDD 文档** — 每模块的规格都在本文档集中
3. **遵循现有代码风格** — 匹配命名、注释密度、缩进
4. **不引入新依赖** — 除非 SDD 明确要求
5. **每个任务完成后验证** — 见各任务的验收标准

### 9.8.2 红线（绝对不能做的）

- ❌ **不要重构后端离线 Pipeline**（episode_loop, action_plan, state_patch, memory）— 它已经可用
- ❌ **不要迁移后端框架**（http.server → FastAPI）— 不在当前范围
- ❌ **不要迁移数据库**（SQLite → PostgreSQL）— 不在当前范围
- ❌ **不要删除 `interaction_generator/`**（规则驱动的降级方案）— 作为备份保留
- ❌ **不要引入新的互动组件**（当前 12 种已经足够）— 除非 SPEC 明确要求
- ❌ **不要在 `.env` 中硬编码 API Token** — 始终从环境变量读取

### 9.8.3 建议的 AI Coding 工作流

```
1. 读本 SDD 文档对应的章节
2. 读要修改的源文件
3. 提出具体修改方案 → 用户确认
4. 执行修改（Edit/Write 工具）
5. 验证：npm run build / python -m pytest
6. 汇报结果
```

### 9.8.4 文件修改上限

- 单次修改 ≤200 行新增代码
- 单文件 ≤500 行（`components.js` 除外，但需逐步拆分）
- 超出上述限制时，拆分为多个子任务
