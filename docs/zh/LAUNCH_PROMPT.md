# 🚀 开源发布最终任务 — 给 AI 助手的提示词

> **团队**: 给狗剪毛 → **ClipHound**  
> **发布时间**: 2026-06-11 今晚  
> **当前状态**: 代码已脱敏完毕，Git 仓库已初始化，待最终打磨和推送  

---

## 你可以直接把这个文件的内容发给 AI 助手（Claude Code / Cursor / Copilot 等），让它逐项执行。

---

## 📋 任务清单

### 第一阶段：GitHub 仓库创建（5 分钟）

1. 在 GitHub 上创建新组织/用户下的仓库：
   - **组织名建议**: `ClipHound`（给狗剪毛 → Dog Grooming → ClipHound，简短好记）
   - **仓库名建议**: `cinematic-drama` 或 `interactive-drama-engine`
   - **可见性**: Public
   - **不要**勾选 "Initialize with README"（我们已经有了）

2. 本地推送：
   ```bash
   cd <repository-root>
   git add .
   git commit -m "🎬 Initial open-source release: Cinematic Drama Interactive System v0.1.0"
   git remote add origin https://github.com/ClipHound/cinematic-drama.git
   git push -u origin main
   ```

3. 推送后在 GitHub 仓库 Settings 中设置：
   - **Description**: `AI-powered interactive short-drama system. Upload videos → AI understands plot → generates real-time interactive components for viewers. React + Django + AI Agents.`
   - **Topics/Tags**: `react` `django` `ai` `llm` `rag` `video-understanding` `interactive-storytelling` `short-drama` `capacitor` `multimodal`
   - **Website**: 留空（暂无在线 demo）
   - 勾选 "Releases" 下的 "Create a release" — 创建 `v0.1.0` tag

---

### 第二阶段：AI 评分优化（重点！）⭐⭐⭐

评委可能使用 ChatGPT/Claude 等 AI 工具来评估项目。以下是让 AI 评分更高必须做的优化：

#### 2.1 创建顶级 `README.md`（英文主 README）

当前项目缺少英文 README。AI 评分时会提取 README 作为项目摘要。必须包含：

```markdown
# Cinematic Drama Interactive System

> AI-powered interactive short-drama platform. Upload videos → AI understands plot → generates real-time interactive components.

## What It Does

- **AI Video Understanding**: Offline multi-agent pipeline analyzes short-drama episodes using VLM (Vision Language Model) for visual perception and LLM for plot memory / interaction design
- **12 Interactive Components**: Real-time overlays triggered at precise timeline moments — anger release, plot voting, emotional resonance, team cheering, etc.
- **RAG Semantic Search**: Natural language search across all drama content ("show me the episode where the hero reveals his true identity")
- **Cross-Platform**: React Web + Capacitor (Android/iOS)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Tailwind CSS 4, Vite 8, Capacitor 8 |
| Backend API | Django 5, Django REST Framework, Celery + Redis |
| AI Pipeline | Python, Multi-Agent Architecture, VLM + LLM |
| Search | OpenAI-compatible Embeddings, Cosine Similarity, Hybrid Keyword+Semantic |
| Database | SQLite (dev) / PostgreSQL 16 (prod) |
| Vector Store | Qdrant |
| ASR | FunASR (Paraformer) |

## Quick Start

```bash
# Backend
cd django-backend
cp .env.example .env   # then edit .env with your API keys
pip install -e .
python manage.py migrate
python manage.py runserver 127.0.0.1:8787

# Frontend
cd cinematic-drama-app-frontend-source
cp .env.example .env
npm install
npm run dev
```

## Project Structure

```
├── cinematic-drama-app-frontend-source/  # React + Vite + Capacitor frontend
│   ├── src/pages/         # 6 route pages (Home, Detail, Player, Search, AI Search, Profile, Theater)
│   └── src/interaction/   # 12 interactive component types with Lottie animations
├── django-backend/                     # Django REST API backend (8 apps)
│   ├── apps/search/       # AI RAG semantic search with LLM function calling
│   ├── apps/catalog/      # Drama & episode metadata
│   ├── apps/interactions/ # Interaction manifests & event tracking
│   └── config/            # Django settings, API routes
├── drama-understanding-agent/          # Offline AI pipeline
│   └── src/drama_agent/   # Video understanding, memory system, interaction design agents
└── sdd/                               # 10 Software Design Documents (Chinese)
```

## Key Features

- **Multi-Agent Pipeline**: Understanding Agent (visual + plot) → Design Agent (interaction timing + component selection)
- **12 Interaction Types**: anger_release, plot_vote, team_cheer, tear_resonance, laugh_burst, candy_storm, shatter_strike, guardian_shield, emotion_buffer, real_option_card, clue_judge_card, prediction
- **Device-Based Identity**: No registration required — UUID-based device identification
- **SSE Streaming AI Chat**: Real-time AI search with function calling and recommendation cards
- **Offline-First Interaction**: Interactions trigger locally with haptic feedback, batch-sync events to backend

## Architecture

```
User Upload Video → Offline Pipeline (VLM + LLM) → Interaction Manifest (JSON)
                                                          ↓
User Opens App → Load Manifest → Render 12 Component Types at Timeline Events
                                                          ↓
User Interacts → Local Feedback (Haptic + Animation) → Batch Sync to Backend
```

## License

Apache 2.0 — see [LICENSE](LICENSE)

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and workflow.

---

*Built by [ClipHound](https://github.com/ClipHound) 🐕✂️*
```

#### 2.2 AI 可发现性优化

1. **在 README 顶部添加 AI 友好的结构化元数据**:
   ```markdown
   <!-- PROJECT-META
   name: Cinematic Drama Interactive System
   type: fullstack-application
   language: Python, TypeScript
   framework: Django, React
   ai-features: VLM video understanding, LLM plot analysis, RAG semantic search, embedding-based retrieval, multi-agent pipeline
   domain: interactive-entertainment, short-drama, video-understanding
   license: Apache-2.0
   END-META -->
   ```

2. **确保每个子目录都有 README**（简要说明该目录的作用）：
   - `django-backend/README.md` — 已有，但翻译为英文并补充
   - `drama-understanding-agent/README.md` — 创建，说明离线管道架构
   - `cinematic-drama-app-frontend-source/README.md` — 创建，说明前端构建和 Capacitor 打包
   - `sdd/README.md` — 创建，列出所有设计文档索引

3. **`CONTRIBUTING.md` 中的 GitHub 链接**: 确认链接指向 `ClipHound/cinematic-drama`

#### 2.3 代码质量信号（AI 评分加分项）

1. **GitHub Actions CI 徽章**: 在 README 顶部添加（即使暂时没有 CI，也预留位置）
   ```markdown
   [![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
   [![Python](https://img.shields.io/badge/python-3.11+-blue)](https://python.org)
   [![Node](https://img.shields.io/badge/node-22+-green)](https://nodejs.org)
   ```

2. **测试覆盖率占位**: 如有测试命令，注明 `python manage.py test` / `pytest`

3. **架构图**: 当前 README 中的 ASCII 架构图很直观，保持它

---

### 第三阶段：最后检查和修复（30 分钟）

#### 3.1 已知待修复问题

1. **`django-backend/README.md`** — 补充英文版本，开头加上英文项目说明
2. **`CONTRIBUTING.md`** — 确认仓库链接和联系渠道均指向实际项目
3. **根目录文件整理** — 考虑把中文文档（`AI-RAG-实施计划.md`、`AI全栈挑战赛...md` 等）移到一个 `docs/zh/` 目录下，让根目录更整洁
4. **确认没有遗漏的硬编码路径** — 搜索开发机盘符或工作区名称进行快速自查
5. **删除 `.gitattributes` 中的非必要内容**（如果有 `export-ignore` 规则可能影响文件导出）

#### 3.2 可选优化

- [ ] 在 `django-backend/pyproject.toml` 中补充 `[project]` 元数据（名称、描述、依赖）
- [ ] 在 `cinematic-drama-app-frontend-source/package.json` 中补充 `description`、`keywords`、`repository` 字段
- [ ] 创建一个 GitHub Release `v0.1.0` 并附上简短 Changelog
- [ ] 给仓库加一个 Social Preview 图片（Open Graph 图，1200x630px）

---

### 第四阶段：发布后（今晚做完即可）

- [ ] 在硅基流动后台：删除旧 API Key `sk-pyqzaz...`，生成新 Key
- [ ] 在火山方舟后台：删除旧 Token `ark-973d...`，生成新 Token
- [ ] 更新你本地原始项目的 `.env` 使用新密钥
- [ ] Enable GitHub Secret Scanning (Settings → Security → Secret scanning)
- [ ] 设置 Branch Protection on `main`:
  - Require pull request before merging
  - Require status checks to pass

---

## 🤖 把这个发给 AI 助手时这样说

> 我准备开源一个项目到 GitHub。项目代码在当前仓库根目录。  
> 请按 `LAUNCH_PROMPT.md` 中的清单逐项执行。  
> 第一步：把根目录的 22 个散落文件整理到 `docs/` 目录下，只保留 README.md、LICENSE、SECURITY.md、CONTRIBUTING.md、CODE_OF_CONDUCT.md 在根目录。  
> 第二步：创建英文主 README.md（参考清单中的模板，但要基于项目实际代码核实所有细节）。  
> 第三步：补充所有子目录的 README。  
> 第四步：帮我 Git commit 并告诉我 push 命令。  
> GitHub 组织名: ClipHound，仓库名: cinematic-drama。  
> 我是队长，今晚必须上线，不要让我手动编辑任何文件，全部由你完成。

---

## 📝 附：ClipHound 名称说明

"给狗剪毛" → **ClipHound**

- **Clip**: 修剪/剪辑（双关：代码剪辑 + 狗毛修剪 + 视频剪辑）
- **Hound**: 猎犬（代表团队敏锐、追踪问题的能力）
- 简短（10 字符以内）、好记、GitHub 用户名可用概率高
- Logo 概念：一只叼着剪刀的猎犬 🐕✂️

备选（如果 ClipHound 已被注册）:
- **TrimDog** — 简洁直白
- **ShearHound** — 更专业的 grooming 术语
- **GroomDog** — 最直白

---

*此文件是给 AI 助手的启动提示词。保存后可以直接复制内容发给 Claude Code / Cursor / Copilot。*
