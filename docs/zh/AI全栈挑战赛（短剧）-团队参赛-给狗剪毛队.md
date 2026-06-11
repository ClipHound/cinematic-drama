# AI全栈挑战赛（短剧）-团队参赛-给狗剪毛队

课题：AI全栈项目--基于短剧剧情的即时互动激发（宣讲）

提交日期：2026 年 6 月 11 日

## 参赛队伍名称和成员

| 项目 | 内容 |
| --- | --- |
| 项目名称 | 短剧即时互动激发系统（Cinematic Drama Interactive System） |
| 队伍名称 | 给狗剪毛队 |
| 成员姓名 | 陈梓岩、马泽群、陈孟麟 |
| 技术栈 | 客户端：React 19、TypeScript、Vite 8、Tailwind CSS 4、React Router 7、Capacitor 8、Android WebView，并通过 Web Vibration/Share API 提供震动与系统分享。<br>在线后端：Django 5、Django REST Framework、SQLite（开发）/ PostgreSQL（生产）、Celery/Redis。<br>AI 核心：Python Agent、Doubao-Seed-2.0-Lite / 火山方舟 OpenAI-compatible API、FunASR（可选 ASR）、Qdrant、Qwen3-Embedding / Ollama、Pydantic、json-repair。<br>数据与产物：Interaction Manifest JSON、rhythm_blueprint.json、Branch Narrative Package、用户互动事件、评论、收藏、搜索文档。 |

## 项目概述

### 项目思路

本项目面向“基于短剧剧情的即时互动激发”课题，构建一套内容理解驱动的短剧互动系统：短剧入库后，AI 核心层逐集观看并理解视频，持续维护角色、关系、事件、伏笔和剧情状态；互动设计层基于全剧节奏与本集高光点生成互动 Manifest；播放时，React/Capacitor 客户端按时间轴触发低打扰互动组件，并把用户行为回传至 Django 后端。

系统目标不是把短剧改造成实时游戏，而是在关键剧情高光处提供“轻交互、强反馈、低延迟”的观看增强体验。观众在愤怒、解气、心疼、好笑、嗑糖、站队、预测等心理动作出现时，可以立即点击、长按、选择或判断，形成参与感。

### 核心功能介绍

- 短剧内容理解：Drama Understanding Agent 逐集读取视频、ASR 时间戳和累积记忆，通过 Doubao VLM/LLM 输出 Action Plan，并写入 SQLite + Qdrant 记忆系统。

- 互动方案生成：Interaction Design Agent 采用 Pass 1 全剧节奏蓝图 + Pass 2 逐集精细设计。它消费剧情摘要、候选互动点、ASR 毫秒时间戳和组件规范，输出可供前端直消费的 ep_N.interactions.json。

- 端上即时渲染：React 播放页按 currentTime 调度 Interaction Manifest，同一时间只激活一个主互动组件，支持点击、长按、选择、关闭、超时清理、跳集清理和事件队列回传。

- AI 搜索与推荐：Django 后端从离线理解产物中构建搜索文档，本地数据集包含 10 部短剧、228 集、238 份可检索文档；配置模型 Provider 时支持 AI 问答/推荐，未配置密钥时提供关键词兜底。

- 分支叙事：剧终后可进入预生成分支剧情体验。Branch Narrative Agent 基于整部剧的世界模型生成静态 DAG 分支包，用户通过 4-5 次选择到达 3 个不同结局之一。

### 产品亮点与创新点

- 理解-设计分离双 Agent：理解层负责视觉感知和剧情记忆，设计层负责互动节奏和组件选择，避免端到端方案在 token、职责和质量上互相干扰。

- LLM 自主互动设计 + 规则安全兜底：组件选择不是硬编码情绪映射，而是由 LLM 基于场景叙事功能判断，再由 P1-P5 组件规范、硬排除规则和代码后处理兜底。

- State Patch 缓冲与置信度门控：模型输出不直接写库，先进入 Patch 暂存区；按置信度自动提交或标记审核，并在每集后创建数据库快照，降低 LLM 输出不可靠带来的风险。

- 全剧节奏蓝图先行：Pass 1 先分析全剧情绪弧线、高潮集、互动密度和集尾策略，Pass 2 再逐集设计，避免每集孤立设计导致互动节奏单调。

- ASR 毫秒级锚定：ASR 结果以 [00:47.230-00:48.900] 的形式注入 Prompt，互动点直接输出 start_ms / end_ms，解决“AI 生成互动时间不准”的问题。

- 离线预生成保证播放体验：AI 推理集中在短剧入库阶段，播放阶段只读取 Manifest 与静态资产，降低实时模型延迟、失败和成本波动。

## 项目实机演示

### 实机演示链接

[https://litmoon.cn/Demo-ByteDance/Video](https://litmoon.cn/Demo-ByteDance/Video)

### 演示内容建议

- 启动 Django API 与 React/Capacitor 前端，进入首页加载短剧列表。

- 打开剧集详情页，展示剧集、封面、推荐、评论、收藏等在线数据。

- 进入播放页，展示视频播放过程中按时间轴触发的互动组件，包括点击、长按、选择和关闭。

- 展示 AI 搜索页面，输入自然语言需求并返回可播放推荐。

- 展示剧终分支叙事页，选择不同分支并进入不同结局。

- 展示 Android App 源码/构建产物和在线 API 配置方式。

## 项目技术文档

### 模块拆解和整体流程

系统分为离线生产链路与在线运行链路。离线链路负责短剧内容理解、互动设计、分支叙事和 Manifest 生成；在线链路负责内容分发、视频播放、端上互动渲染、用户行为记录和 AI 搜索。

离线流程：短剧视频入库 -> ASR 转录（可选 FunASR）-> Doubao VLM/LLM 剧情理解 -> Action Plan 结构化输出 -> State Patch 更新记忆系统 -> Interaction Design Agent 生成 Interaction Manifest -> Branch Narrative Agent 生成分支包 -> Schema 校验与质量门控。

在线流程：React/Capacitor App -> Django REST API 拉取剧目、剧集、视频地址和互动 Manifest -> 播放器 currentTime 驱动时间轴调度 -> 12 种互动组件即时渲染 -> 本地事件队列记录点击/长按/选择/关闭 -> POST /api/interactions 批量回传。

### AI 核心模块

- Drama Understanding Agent（编剧）：逐集观看视频，构建世界模型，维护角色、关系、事件、伏笔、每集摘要和候选互动点。

- Interaction Design Agent（互动导演）：消费世界模型，先做全剧节奏建模，再逐集设计互动点，输出前端可消费的 Manifest JSON。

- Branch Narrative Agent：基于剧情世界模型生成多分支叙事树，采用固定结局数的 DAG 收敛结构控制内容规模。

- Interaction Generator：当 LLM 不可用时提供纯规则降级路径，将 plot_events 转换为 highlights，再转换为基础互动 Manifest。

### 12 种互动组件

- 情绪宣泄：shatter_strike（碎屏暴击）、anger_release（生气宣泄）、tear_resonance（泪点共鸣）、laugh_burst（大笑互动）。

- 立场表达：team_cheer（站队助威）、guardian_shield（守护加持）。

- 认知参与：prediction_card（剧情预测）、clue_judge_card（线索判断）。

- 氛围渲染：celebrate_confetti（庆祝礼炮）、sugar_storm（撒糖风暴）。

- 节奏过渡与集尾结构：emotion_buffer（情绪缓冲）、episode_end_prediction（剧尾预测）。

## 核心技术选型

| 项目 | 内容 |
| --- | --- |
| 客户端/App | React 19 + TypeScript + Vite 8 + Tailwind CSS 4 + React Router 7 + Capacitor 8。复用 Web UI，封装 Android，并通过插件桥接触觉、分享、文件系统等能力。 |
| 在线后端 | Django 5 + Django REST Framework。承载剧目、剧集、视频、评论、收藏、互动事件、搜索文档和管理接口。 |
| 离线 AI Pipeline | Python Agent + Pydantic + Qdrant + Doubao/方舟 API。适合模型调用、结构化校验、状态管理和语义检索。 |
| 数据存储 | SQLite 用于本地开发与离线记忆快照；PostgreSQL 作为生产目标；Qdrant 用于角色、事件和剧集上下文向量检索。 |
| 模型与 AI 服务 | Doubao-Seed-2.0-Lite 负责视频理解和文本推理；Qwen3-Embedding/Ollama 负责中文语义向量；FunASR 可提供毫秒级 ASR、VAD 和情绪标记。 |
| 交接协议 | Interaction Manifest JSON、rhythm_blueprint.json、Branch Narrative Package。通过 Schema 和质量门控降低模型输出对前端运行时的影响。 |

## 大模型 / AI 能力使用说明

### 模型调用与 Prompt 设计

视频理解阶段使用 Doubao-Seed-2.0-Lite 原生视频理解能力，支持视频直传或 File API 上传。模型输入包含已知角色卡、未解决伏笔、上集摘要、当前集 ASR 时间戳文本、情绪标记和结构化输出要求。

互动设计阶段使用同一模型的文本推理能力。Pass 1 输入全剧摘要、角色弧线、伏笔和情绪弧线，输出 rhythm_blueprint.json；Pass 2 输入本集候选点、ASR 时间戳、节奏蓝图和组件库说明，输出 ep_N.interactions.json。

Prompt 强制模型输出 Action Plan JSON 或 Manifest JSON，并通过 5 层容错解析：直接 json.loads、去除 code fence、json_repair 修复、正则提取最外层对象、失败记录原文并标记错误。

### 工程容错

- API 超时、429 限流、5xx 错误均有重试策略；视频超过阈值时切换上传模式。

- 所有模型写操作通过 State Patch 进入暂存区，执行角色重复、关系矛盾、时间线违规、角色状态跳变、伏笔无证据解决等冲突检测。

- 互动 Manifest 经过组件白名单、时间窗口、重叠移除、必填 config、组件多样性和安全规则后处理。

## 工程难点与解决方案

| 项目 | 内容 |
| --- | --- |
| LLM 输出不可靠 | 模型可能输出矛盾角色、关系或伏笔状态。解决方案：State Patch 缓冲、置信度门控、冲突检测、事务提交和每集 DB 快照。 |
| 互动时间精度 | LLM 直接看视频常只能给粗时间。解决方案：ASR 先行生成毫秒级时间戳和情绪标记，Prompt 中显式注入，互动点输出 start_ms / end_ms。 |
| 组件选择语义漂移 | 第一轮运行中出现 laugh_burst 误用于荒诞场景、team_cheer 误用于正邪对立等问题。解决方案：12 组件 P1-P5 精确定义、叙事功能分类、硬排除规则和代码层 G1-G9 后处理。 |
| 播放体验稳定性 | 播放、暂停、拖动、跳集、关闭组件都会改变互动状态。解决方案：统一时间轴调度器、单主组件激活、组件生命周期清理和本地事件队列。 |

## 工作项拆分 + 排期

| 项目 | 内容 |
| --- | --- |
| 陈梓岩 | AI Pipeline 与系统架构：离线 Agent、Doubao/VLM 调用、Prompt 组织、State Patch、Manifest Schema、分支叙事与整体方案整合。 |
| 马泽群 | 前端/App 与互动渲染：React 页面、播放器时间轴、12 种互动组件接入、事件队列、Capacitor Android 封装与真机体验调试。 |
| 陈孟麟 | 在线后端、搜索与部署：Django API、数据模型、视频服务、互动事件、收藏评论、AI 搜索/RAG、部署说明、演示链路与文档整理。 |
| 2026-06-08 至 2026-06-09 | 梳理课题、确认双链路架构、整理 SDD 与数据契约。 |
| 2026-06-10 | 打通前端播放页、Django API、离线产物和互动 Manifest。 |
| 2026-06-11 | 完成 Android 源码交付包、演示视频、参赛文档与部署说明。 |
| 后续优化 | 完善生产数据库、任务队列、监控、更多剧集自动评测、AB 测试和个性化推荐。 |

## 项目代码和产物

### 代码链接

GitHub 开源仓库：[ClipHound/cinematic-drama](https://github.com/ClipHound/cinematic-drama)

### 仓库内容

- Android 原生工程：[`cinematic-drama-app-frontend-source/android/`](../../cinematic-drama-app-frontend-source/android/)

- Android 源码说明：[`ANDROID-SOURCE-README.md`](ANDROID-SOURCE-README.md)

- 前端与 Android 工程：[`cinematic-drama-app-frontend-source/`](../../cinematic-drama-app-frontend-source/)

- 在线 Django 后端：[`django-backend/`](../../django-backend/)

- 离线短剧理解 Agent：[`drama-understanding-agent/`](../../drama-understanding-agent/)

- 系统设计文档：[`sdd/SDD-00` 至 `sdd/SDD-09`](../../sdd/README.md)

- HTTPS 部署说明：[`HTTPS-DEPLOYMENT.md`](HTTPS-DEPLOYMENT.md)

### 主要 API

- 内容与播放：`GET /api/dramas`、`GET /api/dramas/<slug>`、`GET /api/dramas/<slug>/episodes`、`GET /api/dramas/<slug>/episodes/<number>`、`GET /api/videos/<slug>/<number>`。
- 互动与分支：`GET /api/dramas/<slug>/episodes/<number>/interactions`、`GET /api/dramas/<slug>/branch-narrative`、`POST /api/interactions`。
- 用户与社区：`GET /api/users/me/profile`、`GET/PUT/DELETE /api/users/me/favorites`、`GET/POST /api/comments`。
- 搜索与 AI：`GET /api/search?q=`、`POST /api/ai/search`、`POST /api/ai/chat`（SSE）。
- 内容管理：`POST /api/admin/dramas/upload`、`GET /api/admin/pipeline/jobs`。

## 项目总结和自评

### 总结

对照课题要求，本项目完成了从“短剧内容理解”到“互动方案生成”再到“端上即时渲染”的核心闭环：AI 在离线阶段理解剧情并生成可校验产物，前端在播放阶段按时间轴精准触发互动，后端负责内容服务、搜索推荐和用户行为沉淀。

项目的主要价值在于把大模型能力放在最适合的位置：模型负责理解剧情和生成结构化互动方案，客户端负责低延迟渲染和用户反馈，后端负责稳定分发与数据闭环。这样的架构既保留 AI 生成的灵活性，也避免播放时依赖实时模型调用导致体验不稳定。

### 自评与不足

- 优势：架构完整度较高，覆盖视频输入、剧情理解、互动设计、Manifest、Web/Android 渲染、Django API、AI 搜索和分支叙事；工程化细节包括 State Patch、快照回滚、JSON 容错、API 重试和规则兜底。

- 不足：生产数据库、任务队列和监控仍需进一步完善；图像生成、更多剧集自动评测、互动热力统计、AB 测试和个性化推荐仍有提升空间。
