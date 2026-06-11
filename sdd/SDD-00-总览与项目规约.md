# SDD-00-总览与项目规约

> 版本：v1.0  
> 定稿日期：2026-06-10  
> 适用范围：cinematic-drama-app (React 19 + Capacitor) + drama-understanding-agent (Python)  
> 融合基准：基于 2026-06-10 审计报告 (AUDIT-REPORT.md) 的发现与建议

## 0.1 文档目的

为"短剧即时互动激发系统"（Cinematic Drama Interactive System）提供软件设计文档（SDD），作为 AI 代码助手与人工开发者实现融合与升级的**唯一权威依据**。

本文档集解决"做什么、做到什么程度、怎么对接、如何验证"的问题，不解决"具体代码怎么写"的问题。

## 0.2 项目定位（一句话）

> **内容理解驱动的短剧即时互动激发闭环系统**：上传短剧后，离线 Agent 系统用 VLM/LLM 逐集理解剧情、生成互动资产包（Manifest）；前端 App 按时间轴精准触发 12 种低打扰互动组件，用视觉动画、触觉反馈完成本地即时响应；用户行为被后端沉淀为互动历史与身份资产。

## 0.3 前置参考文档

在阅读本 SDD 前，建议先了解以下前置文档：

| 文档 | 提供内容 |
|:---|:---|
| `AUDIT-REPORT.md` (2026-06-10) | 当前两个项目的融合审计，共 73 个问题，含差距矩阵和升级建议 |
| `FRONTEND-HANDOFF.md` | 前端技术栈、本地运行、API 依赖说明 |
| `drama-understanding-agent/PLAN.md` | 后端 Agent 设计目标、代码结构、实现顺序 |
| `drama-understanding-agent/API.md` | 后端 API 端点、视频服务、环境变量 |
| `drama-understanding-agent/SPEC-interaction-component-standard.md` | 互动组件标准规范（12 组件 × P1-P5 维度） |
| `drama-understanding-agent/docs/` (14 份) | 记忆系统、模型接口、Action Plan 引擎、State Patch 等详细设计 |

## 0.4 范围与非目标

### 在范围内（本 SDD 必须覆盖）

- 离线视频理解 Agent Pipeline 的阶段、产物、质量门控
- 互动设计 Agent（interaction_designer）的编排规则与输出规范
- 分支叙事 Agent（branch_narrative）的 DAG 规划与扩写生成
- 在线后端的 API 路由、数据模型、与前端契约
- React 19 前端的 6 页面 + 12 互动组件 + 事件队列
- Capacitor Android App 封装与原生能力接入
- 离线/在线交接面的 Manifest JSON Schema
- 融合升级的分阶段实施计划
- 质量门控、降级策略、测试与验收标准
- 单机部署方案（含 Docker Compose 目标态）

### 不在范围内（本 SDD 不覆盖）

- 具体代码实现（交由 AI 代码助手按本 SDD 执行）
- 短剧物料的版权、法务、内容审核流程
- 商业化策略、运营策略
- 大规模分布式部署（K8s 集群级）
- 完整用户账号体系（MVP 用设备 ID + localStorage）
- iOS 客户端（预留 Capacitor iOS 构建能力，但不做 iOS 专属适配）
- Android 应用商店正式上架流程

## 0.5 术语表（Glossary）

| 术语 | 英文 | 定义 |
|:---|:---|:---|
| 高光点 | Highlight Point / HL | 一段 5-20 秒的剧情精彩区间，是互动触发的最小单元 |
| 互动点 | Interaction Point / IP | 高光点 + 对应互动组件类型与配置的组合，客户端按 IP 触发 |
| 互动清单 | Interaction Manifest | 一集的所有 IP 集合（JSON），离线系统产物，前端播放时消费 |
| 资产包 | Project Asset Pack | 一部剧的专属视觉/音效资产集合（CSS、Lottie、图片） |
| 扩写包 | Episode Expansion Package | 每集剧尾的 AI 生成内容（心声、预测题、分支叙事） |
| 全局模板 | Global Template Pack | 兜底资产，所有剧默认可用 |
| 三路融合 | Tri-Signal Fusion | ASR / 视觉(VLM) / 音频三路信号的高光识别策略 |
| 组件成长 | Component Growth (G0-G4) | 互动组件随用户行为强化的视觉状态机 |
| 质量门控 | Quality Gate | 离线产物上线前的强制校验规则集 |
| Manifest 就绪 | is_ready | Pipeline 完成全部门控后置 true，是否可上线的唯一开关 |
| 伪交互 | Pseudo-interaction | 用户操作触发视觉反馈，产生"推进了剧情"的因果错觉，但不改变实际播出的内容 |
| 触觉反馈 | Haptic Feedback | 手机线性马达的精细震动模式，通过 Capacitor Haptics 插件调用 |
| 离线预生成 | Offline Pre-generation | 所有 AI 生成内容均在短剧入库时提前完成，播放时不依赖实时 AI 调用 |
| Action Plan | — | 每集理解后模型输出的结构化操作计划（JSON），含角色更新、事件记录、互动候选 |
| State Patch | — | 对记忆系统的增量更新缓冲，经置信度检查后提交 |
| Project | — | 一部短剧的完整工作空间（视频、ASR、记忆库、产物） |
| Doubao | — | 字节跳动豆包大模型（Seed 系列），本系统使用其 VLM 能力进行视频理解 |

## 0.6 角色与读者

| 角色 | 关注的文档 |
|:---|:---|
| 项目负责人 | 00, 01, 07, 08 |
| 离线系统开发 | 00, 01, 02, 06, 07 |
| 后端开发 | 00, 01, 03, 05, 06, 07 |
| 前端/App 开发 | 00, 01, 04, 05, 06, 07 |
| QA / 测试 | 00, 05, 06, 07 |
| 答辩/演示 | 00, 01, 07, 08（Demo 脚本） |

## 0.7 文档版本约定

- 版本号：`vMAJOR.MINOR`，本 SDD 起始为 `v1.0`
- 字段级修改：MINOR +1
- 接口/Schema 不兼容修改：MAJOR +1，需显式声明并通知所有读者
- 每份文档头部维护版本号和日期

## 0.8 优先级标记约定

- **P0 必做**：MVP 核心闭环必备，缺失即无法 Demo
- **P1 建议做**：增强体验，时间允许必做
- **P2 可选**：锦上添花，时间不够可砍
- **OUT**：明确不做

## 0.9 SDD 文档集索引

| 序号 | 文件名 | 主题 | 主要读者 |
|:---|:---|:---|:---|
| 00 | `SDD-00-总览与项目规约.md` | 项目目标、术语、文档地图、前置参考 | 全员 |
| 01 | `SDD-01-系统架构设计.md` | 双链路架构、技术栈、ADR、跨系统契约 | 架构/全员 |
| 02 | `SDD-02-离线系统设计.md` | 视频理解 Agent Pipeline、互动设计、分支叙事、质量门控 | 离线开发 |
| 03 | `SDD-03-在线后端设计.md` | API 服务、数据模型、视频分发、Job 管理 | 后端开发 |
| 04 | `SDD-04-客户端设计.md` | React 前端、12 互动组件、事件队列、Capacitor App 封装 | 前端/App 开发 |
| 05 | `SDD-05-接口契约.md` | HTTP API、错误码、Manifest Schema、前后端数据契约 | 全员 |
| 06 | `SDD-06-数据模型与Schema.md` | 数据库表、Manifest/AssetPack JSON Schema、Redis 键空间 | 全员 |
| 07 | `SDD-07-质量门控与测试规约.md` | Gate 规则、测试策略、验收标准、Demo 脚本 | QA/全员 |
| 08 | `SDD-08-部署与运维规约.md` | 环境配置、Docker Compose、日志、降级、监控 | 运维/全员 |
| 09 | `SDD-09-实施任务拆分与AI开发规约.md` | 融合升级 6 阶段任务拆分、时间线、验收标准 | 全员 |

## 0.10 当前项目基线

本 SDD 基于以下两个独立项目的融合：

| 项目 | 路径 | 技术栈 | 当前状态 |
|:---|:---|:---|:---|
| 前端 App | `cinematic-drama-app-frontend-source/` | React 19, Vite 8, TypeScript, Tailwind CSS 4, Capacitor 8 | UI 完整，数据全部硬编码占位 |
| 后端 Agent | `drama-understanding-agent/` | Python 3.11, http.server, SQLite, Qdrant, Doubao VLM API | 离线 Pipeline 完整，在线服务欠缺 |

**关键事实**：
- 前端 6 个页面（首页/详情/播放/搜索/AI搜索/剧场/个人）+ 12 种互动组件均已实现 UI
- 前端所有剧名、集数、互动点、用户数据均为硬编码 mock
- 后端离线 Pipeline（视频理解 + 互动设计 + 分支叙事）完整可运行
- 后端在线 API 缺少用户系统、事件接收、WebSocket、管理端
- 嵌入向量使用 SHA-256 哈希伪嵌入（需替换为真实嵌入服务）
- 图像生成为空壳 Stub（PlaceholderGenerator）
- `.env` 包含真实 API Token，需立即轮换

详细问题清单见 `AUDIT-REPORT.md`（73 个问题）。
