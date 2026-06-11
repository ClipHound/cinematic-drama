# SDD-07-质量门控与测试规约

> 版本：v1.0  
> 定稿日期：2026-06-10

## 7.1 质量门控（Quality Gates）

### 7.1.1 离线产物门控

Pipeline 产出的 Manifest 必须通过以下门控。标记机制：
- **Hard Fail**：阻塞上线，必须修复
- **Soft Warn**：记录告警，不阻塞上线

| Gate | 类型 | 检查项 | 阈值 |
|:---|:---|:---|:---|
| **G1** | Hard | IP 时长范围 | `[5000ms, 20000ms]` |
| **G2** | Hard | IP 基本字段完整 | `id`, `start_ms`, `end_ms`, `component`, `title` 非空 |
| **G3** | Hard | 单集 IP 数量 | `[3, 20]` |
| **G4** | Hard | 相邻 IP 最小间隔 | `≥8000ms` |
| **G5** | Hard | Manifest JSON 合法 | `json.loads()` 不抛异常 |
| **G6** | Hard | component 有效 | 必须在 12 组件白名单中 |
| **G7** | Soft | 全剧组件多样性 | 使用 ≥5 种不同 component |
| **G8** | Soft | 情绪覆盖 | 覆盖 ≥3 种 emotion |
| **G9** | Soft | 连续 3 集不重复相同组件集合 | 相邻集 component set 不能完全相同 |
| **G10** | Hard | video_url 格式 | 以 `/api/videos/` 开头 |
| **G11** | Hard | duration_ms 合理 | `>30000ms` 且 `≤600000ms` |

### 7.1.2 前端门控

| Gate | 类型 | 检查项 |
|:---|:---|:---|
| **F1** | Hard | `npm run build` 零错误 |
| **F2** | Hard | TypeScript 编译零错误 (`tsc -b`) |
| **F3** | Hard | 无硬编码的 mock 数据进入生产构建 |
| **F4** | Soft | Lighthouse Performance ≥80 (Mobile) |
| **F5** | Soft | 首页加载 ≤3s (Fast 3G) |

### 7.1.3 API 门控

| Gate | 类型 | 检查项 |
|:---|:---|:---|
| **A1** | Hard | `GET /health` 返回 `{"status": "ok"}` |
| **A2** | Hard | `GET /api/dramas` 返回合法 JSON |
| **A3** | Hard | `GET /api/videos/{id}/{n}` 支持 Range 206 |
| **A4** | Hard | 所有 API 响应 `Content-Type: application/json` 或 `video/mp4` |

## 7.2 测试策略

### 7.2.1 后端测试

| 层级 | 范围 | 工具 | 当前覆盖 |
|:---|:---|:---|:---|
| 单元测试 | memory/store.py, action_plan.py, state_patch.py | pytest | `tests/` 目录（已有基础） |
| 集成测试 | EpisodeLoop 端到端 | pytest | `tests/test_episode_loop.py` |
| API 测试 | HTTP 端点 | curl / pytest + httpx | 无 |

**P0 测试清单**：
- [ ] `ContentRepository.list_dramas()` 返回正确结构
- [ ] `ContentRepository.load_manifest()` 返回正确 JSON
- [ ] `POST /api/interactions` 事件入库 + 去重
- [ ] `GET /api/videos/{id}/{n}` Range 请求返回 206

### 7.2.2 前端测试

| 层级 | 范围 | 当前覆盖 |
|:---|:---|:---|
| 类型检查 | TypeScript 编译 | ✅ `tsc -b` |
| 构建 | Vite build | ✅ `npm run build` |

当前无前端运行时测试。MVP 阶段以**手工验收**为主。

## 7.3 验收标准（Demo 脚本）

### 7.3.1 核心闭环演示（5 分钟）

| 步骤 | 操作 | 预期结果 | 验收点 |
|:---|:---|:---|:---|
| 1 | 启动后端 `python -m drama_agent.api.server` | 监听 8787 | A1 |
| 2 | 启动前端 `npm run dev` | 监听 5174 | — |
| 3 | 打开 `http://127.0.0.1:5174/home` | 显示剧目列表（非硬编码） | F3 |
| 4 | 滑动到视频 | 视频自动播放，有声音 | — |
| 5 | 等待互动浮层出现 | 播放到高光点时互动组件渲染 | G6 |
| 6 | 点击互动组件 | 动画播放，事件入队 | — |
| 7 | 点赞按钮 | 点赞动画，事件入队 | — |
| 8 | 切换到搜索页 | 显示剧集列表 | — |
| 9 | 打开 AI 搜索 | 输入查询 → 返回结果 | A1 |
| 10 | 打开个人页 | 显示互动统计（非硬编码） | F3 |

### 7.3.2 Android App 验收

| 步骤 | 操作 | 预期 |
|:---|:---|:---|
| 1 | 安装 APK | 成功安装 |
| 2 | 冷启动 | <3 秒进入首页 |
| 3 | 视频播放 | 首帧 <2 秒，有声音 |
| 4 | 互动组件 | 动画流畅，震动正常 |
| 5 | 切后台再回来 | 播放状态保持 |

## 7.4 降级策略

| 故障场景 | 降级行为 | 用户感知 |
|:---|:---|:---|
| 后端不可达 | 前端显示"网络不可用"错误页 | 明确提示 |
| 视频文件缺失 | 显示占位图，不崩溃 | 无法播放该集 |
| Manifest 缺失 | 仅播放视频，不触发互动 | 无互动体验 |
| Manifest interaction_points 为空 | 仅播放视频 | 无互动体验 |
| AI 搜索不可用 | 显示"AI 搜索暂不可用" | 明确提示 |
| 事件上报失败 | 保留在本地队列，下次重试 | 无感知 |
| 资产文件 404 (Lottie/图片) | 互动组件降级为简单 UI | 体验降级但不崩溃 |
| Qdrant 不可用 | 向量搜索返回空，降级为子串匹配 | 搜索结果质量下降 |
| 嵌入服务不可用 | 标记告警，不阻塞 API | AI 搜索降级 |

## 7.5 代码质量规约

### 7.5.1 前端

- 禁止 `console.log` 残留（用 `console.debug` 并在生产构建移除）
- 禁止 `.catch(() => undefined)` 静默吞错（必须设置 error state 或展示错误 UI）
- 禁止硬编码 mock 数据进入生产构建（mock 数据仅在 `import.meta.env.DEV` 下）
- 组件文件 ≤300 行（当前 `components.js` 2118 行需拆分）

### 7.5.2 后端

- 所有 Python 文件使用 `from __future__ import annotations`
- Pydantic 模型用于数据校验
- 外部 API 调用必须有 try/except + 日志
- 禁止在代码中硬编码 API Token（从环境变量读取）
