# SDD-08-部署与运维规约

> 版本：v1.0  
> 定稿日期：2026-06-10

## 8.1 部署形态

### 8.1.1 当前部署（MVP 开发模式）

```
┌──────────────────────────────────────┐
│           开发机器 (Windows/macOS)    │
│                                      │
│  Terminal 1:                         │
│    cd drama-understanding-agent      │
│    $env:PYTHONPATH="src"             │
│    python -m drama_agent.api.server  │
│    → http://127.0.0.1:8787           │
│                                      │
│  Terminal 2:                         │
│    cd cinematic-drama-app-frontend   │
│    npm run dev                       │
│    → http://127.0.0.1:5174           │
│    → Vite proxy /api → :8787         │
│                                      │
│  外部依赖 (需单独启动):              │
│    Qdrant :6333                      │
│    Ollama :11434 (BGE-M3)            │
│    FunASR :10000 (可选)              │
└──────────────────────────────────────┘
```

### 8.1.2 目标部署（Docker Compose — P1）

```
┌──────────────────────────────────────┐
│         Docker Compose 单机           │
│                                      │
│  ┌─────────┐  ┌─────────┐           │
│  │ Python   │  │ Qdrant   │           │
│  │ API :8787│  │ :6333    │           │
│  └────┬─────┘  └─────────┘           │
│       │                               │
│  ┌────┴─────┐  ┌─────────┐           │
│  │ Ollama    │  │ Nginx    │           │
│  │ :11434    │  │ :80      │           │
│  └──────────┘  └────┬─────┘           │
│       │              │                │
│  共享卷: data/ (projects + outputs + videos + assets) │
└──────────────────────────────────────┘
```

## 8.2 环境配置

### 8.2.1 后端环境变量

**文件**：`drama-understanding-agent/.env`

```bash
# --- 项目路径 ---
DRAMA_AGENT_PROJECTS_ROOT=./projects

# --- AI 模型 (Doubao 方舟 API) ---
DRAMA_AGENT_MODEL_ENDPOINT=https://ark.cn-beijing.volces.com/api/v3
DRAMA_AGENT_MODEL_TOKEN=<YOUR_ARK_API_KEY>
DRAMA_AGENT_MODEL_NAME=<YOUR_ENDPOINT_ID>

# --- 嵌入服务 ---
DRAMA_AGENT_QDRANT_HOST=localhost
DRAMA_AGENT_QDRANT_PORT=6333
DRAMA_AGENT_EMBED_ENDPOINT=http://localhost:11434
DRAMA_AGENT_EMBED_MODEL=bge-m3

# --- ASR (可选) ---
DRAMA_AGENT_ASR_ENDPOINT=http://localhost:10000

# --- 运行模式 ---
DRAMA_AGENT_MODE=full_auto
```

**API 服务环境变量**（可覆盖或在 shell 中设置）：
```bash
DRAMA_API_HOST=127.0.0.1
DRAMA_API_PORT=8787
DRAMA_API_PROJECTS_ROOT=./projects
DRAMA_API_OUTPUTS_ROOT=./outputs
DRAMA_API_VIDEO_ROOT=./content/videos
DRAMA_API_MAX_VIDEO_CHUNK_BYTES=2097152
DRAMA_API_ACCESS_LOG=0
DRAMA_API_PUBLIC_BASE_URL=
```

### 8.2.2 前端环境变量

**文件**：`cinematic-drama-app-frontend-source/.env`

```bash
# 本地开发留空，使用 Vite proxy
# 生产构建时填写后端 HTTPS 地址
VITE_API_BASE_URL=
```

### 8.2.3 安全约束

- `.env` 文件**必须加入 `.gitignore`**，只提交 `.env.example` 模板
- API Token 只能通过环境变量注入，不得写入代码或配置文件
- 生产构建的 Android APK 不得包含后端 API Token
- 管理端接口需 `X-Admin-Token` 头校验

## 8.3 视频文件管理

### 8.3.1 目录约定

```
content/videos/
└── {drama_id}/
    ├── ep_001.mp4
    ├── ep_002.mp4
    ├── ...
    └── ep_NNN.mp4
```

### 8.3.2 文件命名

系统自动识别以下命名格式（优先级从高到低）：
1. `ep_001.mp4`, `ep_002.mp4` ...（推荐）
2. `ep001.mp4`, `ep002.mp4` ...
3. `ep01.mp4`, `ep02.mp4` ...
4. `episode_1.mp4`, `episode_2.mp4` ...
5. `1.mp4`, `2.mp4` ...

支持扩展名：`.mp4`, `.webm`, `.mov`, `.m4v`

### 8.3.3 视频上传（待实现）

- 管理端 Web 页面上传 MP4 文件
- 自动存入 `content/videos/{drama_id}/` 目录
- 自动创建 `projects/{drama_id}/project.json`
- 可选自动触发 Pipeline

## 8.4 日志

### 8.4.1 后端日志

- API 请求日志：设置 `DRAMA_API_ACCESS_LOG=1` 启用
- Pipeline 日志：`print()` 到 stdout + Job.logs 列表
- 错误日志：异常 traceback 记录到 Job.error

### 8.4.2 前端日志

- 开发模式：`console.debug` / `console.error`
- 生产构建：Vite 自动移除 `console.debug`

## 8.5 监控（最小化）

| 检查项 | 方法 | 频率 |
|:---|:---|:---|
| API 健康 | `GET /health` | 按需 |
| Pipeline 进度 | `GET /api/jobs/:id` | 轮询 5s |
| 视频可用 | `HEAD /api/videos/{id}/1` | 按需 |
| Qdrant 可用 | Python 客户端 ping | 启动时 |
| 嵌入服务可用 | `curl http://localhost:11434/api/tags` | 启动时 |

## 8.6 启动检查清单

### 开发环境启动

```powershell
# 1. 外部依赖
ollama serve                          # 启动 Ollama
ollama pull bge-m3                    # 拉取嵌入模型
qdrant                               # 启动 Qdrant

# 2. 后端
cd ./drama-understanding-agent
$env:PYTHONPATH="src"
python -m drama_agent.api.server

# 3. 前端
cd ./cinematic-drama-app-frontend-source
npm install
npm run dev
```

### Android APK 构建

```powershell
cd ./cinematic-drama-app-frontend-source
npm run build                         # Vite 生产构建
npx cap add android                  # 首次需要
npx cap sync                         # 同步 Web 资源
npx cap open android                 # Android Studio 打开 → Build APK
```
