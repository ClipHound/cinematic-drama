<!-- PROJECT-META
name: 基于短剧剧情的即时互动激发
english-name: Cinematic Drama Interactive System
type: fullstack-application
language: Python, TypeScript, JavaScript
framework: Django, Django REST Framework, React, Vite, Capacitor
ai-features: VLM video understanding, ASR, LLM plot analysis, embedding retrieval, Qdrant vector memory, multi-agent interaction design
domain: interactive-entertainment, short-drama, video-understanding
license: Apache-2.0
repository: https://github.com/ClipHound/cinematic-drama
END-META -->

# 基于短剧剧情的即时互动激发

> 面向短剧高光、反转、名场面与剧集结尾等情绪峰值场景，通过 AI 内容理解自动识别剧情高光，在准确时间点下发互动组件，让用户无需输入文字、不中断观看，也能即时表达情绪并参与剧情。

**Cinematic Drama Interactive System** 是“AI 全栈项目——基于短剧剧情的即时互动激发”赛题的完整工程实现。项目覆盖 **短剧内容理解、高光点打标与存储、服务端下发、客户端时间轴触发、互动效果渲染、用户行为回传与数据分析**，并进一步实现剧情分支续写、AI 检索问答和 Android 应用交付。

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-0C4B33)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-19-149ECA)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6)](https://www.typescriptlang.org/)
[![Android](https://img.shields.io/badge/Android-Capacitor-3DDC84)](https://capacitorjs.com/)

## 在线实机演示

**演示地址：[https://litmoon.cn/Demo-ByteDance/Video](https://litmoon.cn/Demo-ByteDance/Video)**

演示覆盖短剧列表与播放、剧情高光时间点互动、动画反馈、AI 搜剧和分支剧情等核心场景。

由 **给狗剪毛** 团队开发，开源身份为 **ClipHound**。

## 项目要解决的问题

短剧用户在冲突、反转、甜蜜、搞笑、破局和剧终等时刻往往有强烈表达欲，但传统弹幕和评论需要输入文字，会提高表达门槛并打断沉浸式观看。

本项目把互动能力直接放进剧情时间轴：

1. AI 离线理解视频、语音和剧情上下文，识别高光类型与准确时间窗口。
2. 服务端存储高光点和互动清单，并随剧集信息下发给客户端。
3. 播放器根据当前进度自动唤起适合剧情的互动组件。
4. 用户点击即可获得动画、粒子和触觉反馈，无需暂停或输入文字。
5. 互动事件批量回传，用于热度统计、用户反馈和后续策略优化。

## 赛题要求实现对照

| 宣讲文档要求 | 本项目实现 | 完成情况 |
| --- | --- | --- |
| 短剧列表和基础播放 | 首页、剧场、详情页和播放器；支持播放/暂停、进度控制、选集与连续观看 | 必选闭环 |
| 剧情高光点打标和存储 | VLM + ASR + 多阶段 Agent 提取剧情、情绪和视觉信号，生成结构化剧集记忆与高光点 | 完整实现 |
| 高光点信息下发 | Django 提供剧集、媒体文件及互动 Manifest API，互动配置与业务数据解耦 | 完整实现 |
| 对应时间展示互动组件 | 时间轴运行时按视频时间精确触发组件，并进行配置校验和冲突过滤 | 完整实现 |
| 触发后产生互动效果 | 12 类剧情互动组件，支持动画、粒子效果、连续点击和移动端触觉反馈 | 完整实现 |
| 客户端与服务端闭环 | React/Capacitor 客户端 + Django API + 数据库存储 + 互动事件回传与分析 | 完整实现 |
| 剧情分支或拓展 | 基于预生成 DAG 的剧情选择、分支推进和多结局体验 | 创新扩展 |
| 用户互动能力 | 设备用户、积分、收藏、评论、互动聚合与热度数据 | 扩展实现 |
| 服务部署 | 支持个人 PC Local Server；前端可构建为 Web，也可打包为 Android/iOS | 必选闭环 |
| AI 辅助与自由探索 | AI 搜剧、RAG 问答、流式回答、可播放推荐卡片和无模型降级策略 | 创新扩展 |

## 核心互动能力

系统目前提供 12 类可配置互动组件，覆盖宣讲材料提出的高光剧情与剧尾场景：

| 剧情场景 | 互动示例 |
| --- | --- |
| 胜利、逆袭、打脸 | 庆祝礼花、全队助威 |
| 冲突、愤怒、压抑 | 怒气释放、情绪缓冲 |
| 悲伤、感动 | 泪光共鸣、守护护盾 |
| 搞笑名场面 | 笑点爆发 |
| 甜蜜撒糖 | 心动风暴 |
| 危机、破局 | 碎屏出击、线索判断 |
| 悬念、剧尾 | 剧情预测、结局预测 |

组件标识：

`celebrate_confetti`, `anger_release`, `tear_resonance`, `laugh_burst`, `shatter_strike`, `sugar_storm`, `guardian_shield`, `team_cheer`, `prediction_card`, `clue_judge_card`, `episode_end_prediction`, `emotion_buffer`

## 可演示的完整闭环

```text
选择短剧 -> 进入详情/选集 -> 播放剧集
    -> 到达剧情高光时间点
    -> 自动展示匹配的互动组件
    -> 用户点击触发视觉与触觉反馈
    -> 客户端回传互动事件
    -> 服务端聚合互动热度与用户数据
```

除主闭环外，项目还可演示剧尾剧情分支、多结局探索、AI 搜剧问答、收藏评论与 Android 端运行。

## 系统架构

```text
短剧视频
   |
   v
离线 AI 内容理解管线
VLM + ASR -> 结构化剧情记忆 -> 高光识别 -> 互动设计
   |
   v
校验后的互动 Manifest（JSON）
   |
   +-----------------------> Django 内容与搜索 API
   |                                  |
   v                                  v
React 时间轴播放器 <---------- 剧集、用户与互动数据
   |
   v
本地动画/触觉反馈 -> 互动事件批量回传 -> 数据分析
```

离线内容理解与在线播放相互解耦：高成本的视频分析在内容发布前完成，播放时只需读取已生成的 Manifest 并记录用户行为，从而保证响应效率、模块边界和扩展能力。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript 5.9、React Router 7、Tailwind CSS 4、Vite 8 |
| 移动端 | Capacitor 8，支持 Android/iOS 打包 |
| 在线服务 | Python 3.11+、Django 5、Django REST Framework |
| 后台任务 | Celery 5、Redis |
| AI 管线 | OpenAI-compatible VLM/LLM API、多阶段 Agent、ASR 接口 |
| 检索与记忆 | SQLite 结构化记忆、Qdrant、Embedding、余弦相似度 |
| 应用数据库 | 本地开发使用 SQLite，生产环境支持 PostgreSQL |

## 项目结构

```text
cinematic-drama-app-frontend-source/  React/Vite 播放器与 Capacitor 壳
  src/pages/                          首页、详情、播放、AI 搜索、分支剧情等页面
  src/interaction/                    时间轴运行时与互动组件渲染器
django-backend/                       Django REST API
  apps/catalog/                       短剧与剧集元数据
  apps/interactions/                  Manifest、积分、事件与聚合数据
  apps/search/                        混合检索、Embedding 与 AI 对话
  apps/pipeline/                      离线处理任务记录
drama-understanding-agent/            离线内容理解与互动设计管线
  src/drama_agent/                    VLM、ASR、记忆、API 与编排
  src/interaction_designer/           两阶段互动规划与校验
  src/interaction_generator/          高光点到 Manifest 的生成
  src/branch_narrative/               分支剧情规划
sdd/                                  中文软件设计文档
docs/zh/                              中文计划、审计与发布说明
releases/                             可交付构建产物
```

## 快速启动

### 环境要求

- Python 3.11+
- Node.js 22+
- Redis（仅在运行 Celery Worker 时需要）
- 离线 AI 功能可按需配置 VLM、Embedding、ASR、Ollama 和 Qdrant

### 后端

```bash
cd django-backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
cp .env.example .env
python manage.py migrate
python manage.py runserver 127.0.0.1:8787
```

本地默认使用 SQLite，可通过 `DATABASE_URL` 切换到 PostgreSQL。

### 前端

```bash
cd cinematic-drama-app-frontend-source
cp .env.example .env
npm ci
npm run dev
```

开发环境中 Vite 会将 `/api` 代理到 `http://127.0.0.1:8787`。

### 离线 Agent

```bash
cd drama-understanding-agent
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env
drama-agent --help
```

模型凭据只应写入本地 `.env`，请勿提交 API Key。

## 验证

```bash
# Django 检查与测试
cd django-backend
python manage.py check
python manage.py test

# 离线 Agent 测试
cd ../drama-understanding-agent
pytest

# 前端类型检查与生产构建
cd ../cinematic-drama-app-frontend-source
npm run build
```

## 评分维度对应

- **整体功能完整性（40%）**：完成从短剧浏览、播放、高光下发、互动触发到事件回传的端到端 MVP，并提供 Android 产物。
- **技术选型和实现（30%）**：前后端与离线 AI 管线解耦；Manifest 驱动互动；支持任务化处理、结构化存储、向量检索和跨端打包。
- **创新与自由探索（20%）**：12 类剧情语义互动、剧情分支多结局、AI 搜剧/RAG、动画与触觉联动、模型不可用时降级。
- **文档与表达能力（10%）**：仓库包含架构说明、模块设计、接口文档、测试审计、发布记录与中文软件设计文档。

## 文档

- [Django 后端](django-backend/README.md)
- [离线 AI 管线](drama-understanding-agent/README.md)
- [前端与移动端打包](cinematic-drama-app-frontend-source/README.md)
- [软件设计文档](sdd/README.md)
- [中文项目文档](docs/zh/)

## 开源协作

参与贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [Code of Conduct](CODE_OF_CONDUCT.md)。

安全问题请按照 [SECURITY.md](SECURITY.md) 私下报告。

本项目基于 [Apache License 2.0](LICENSE) 开源。
