# SDD-04-客户端设计

> 版本：v1.0  
> 定稿日期：2026-06-10  
> 实现路径：`cinematic-drama-app-frontend-source/src/`  
> 技术栈：React 19 + Vite 8 + TypeScript + Tailwind CSS 4 + Capacitor 8

## 4.1 客户端范围

### 4.1.1 交付形态

| 形态 | 优先级 | 说明 |
|:---|:---|:---|
| Web 开发模式 | P0 | `npm run dev` → `http://127.0.0.1:5174`，Vite 代理 `/api` 到后端 |
| Android APK | P0 | Capacitor 构建，WebView 承载 React SPA + 原生插件桥接 |
| Web 管理端 | P1 | 同一代码库 `/admin` 路由（上传、Pipeline 状态） |
| iOS | P2 | 预留 Capacitor iOS 构建能力 |

### 4.1.2 功能覆盖

- 短剧 Feed 流（竖屏滑动，自动播放）
- 短剧详情页（作品介绍 + 选集）
- 播放页（全屏视频 + 互动浮层 + 进度控制）
- 搜索页（关键词搜索 + 情绪标签）
- AI 搜索页（对话式搜索）
- 剧场页（发现 + 推荐）
- 个人页（观看统计 + 互动记录 + 设置入口）
- 12 种互动组件（本地渲染 + 事件入队）
- 底部导航栏（5 Tab）

## 4.2 技术栈详情

| 层 | 选型 | 版本 | 角色 |
|:---|:---|:---|:---|
| UI 框架 | React | 19.2 | 组件化、Hooks |
| 构建 | Vite | 8.0 | 开发 HMR、生产构建 |
| 类型 | TypeScript | 5.9 | 类型安全 |
| 样式 | Tailwind CSS | 4.1 | 原子化 + 设计 Token |
| 路由 | React Router | 7.10 | SPA 路由 |
| 图标 | Lucide React | 0.560 | 一致性图标 |
| App 封装 | Capacitor | 8.0 | Android WebView + 原生桥 |
| 触觉 | `@capacitor/haptics` | — | Android 震动 |
| 分享 | `@capacitor/share` | — | 系统分享 |
| 文件 | `@capacitor/filesystem` | — | 离线缓存 |

## 4.3 源码目录结构

```
src/
├── main.tsx                # 入口：StrictMode + BrowserRouter
├── App.tsx                 # 路由表 (7 routes)
├── styles.css              # 全局样式 + 设计 Token (Tailwind)
├── pages/
│   ├── HomePage.tsx        # 首页 Feed（竖屏滑动 + 视频自动播放）
│   ├── DetailPage.tsx      # 剧目详情（介绍 + 选集网格）
│   ├── PlayerPage.tsx      # 播放页（全屏 + 互动浮层 + 进度条）
│   ├── SearchPage.tsx      # 搜索页（关键词 + 情绪标签）
│   ├── AiSearchPage.tsx    # AI 对话搜索
│   ├── TheaterPage.tsx     # 剧场页（推荐 + 全部剧集）
│   └── ProfilePage.tsx     # 个人页（统计 + 记录）
├── components/
│   ├── BottomNav.tsx       # 底部 5 Tab 导航
│   ├── TopBar.tsx          # 顶部导航栏（返回 + 分享 + 更多）
│   └── SectionTitle.tsx    # 分区标题组件
├── data/
│   ├── catalog.ts          # API 调用层 + 类型定义（需清理硬编码数据）
│   └── manifest.ts         # Manifest 类型（需清理硬编码 playerManifest）
├── interaction/
│   ├── types.d.ts          # InteractionManifest / InteractionPoint / Timeline 类型
│   ├── components.js       # 12 种互动组件渲染器（需清理 Legacy 代码）
│   ├── timeline.js         # InteractionTimeline — 客户端时间轴引擎
│   ├── queue.ts            # LocalEventQueue — 本地事件队列（需对接后端）
│   └── styles.css          # 互动组件专用样式
└── (管理端 — 待新增)
    └── pages/AdminPage.tsx # 视频上传 + Pipeline 触发
```

## 4.4 页面与路由

| 路由 | 页面 | P0 | 当前数据来源 | 目标数据来源 |
|:---|:---|:---|:---|:---|
| `/` → `/home` | HomePage | 是 | 硬编码 `exampleDramaA` | `GET /api/dramas` |
| `/detail?drama=:id` | DetailPage | 是 | 硬编码 + API fallback | `GET /api/dramas/:id` |
| `/player?drama=:id&episode=:n` | PlayerPage | 是 | 硬编码 + API fallback | `GET /api/dramas/:id/episodes/:n/interactions` |
| `/search` | SearchPage | 是 | 硬编码 + API fallback | `GET /api/dramas` |
| `/ai` | AiSearchPage | 是 | API (但后端是子串匹配) | `POST /api/ai/search` (需升级为向量搜索) |
| `/theater` | TheaterPage | 是 | 硬编码 + API fallback | `GET /api/dramas` |
| `/profile` | ProfilePage | 是 | 全部硬编码 | `GET /api/users/me/profile` |
| `/admin` (待新增) | AdminPage | P1 | — | `POST /api/admin/dramas/upload` |

## 4.5 播放器与时间轴

### 4.5.1 双播放器模式

**首页 Feed** (`HomePage.tsx`)：
- 竖屏全页滑动（`snap-y snap-mandatory`）
- 每个视频占满一屏（`h-dvh`）
- IntersectionObserver 检测可见视频 → 自动播放
- 非活跃视频自动暂停
- **当前问题**：`muted` 硬编码 → 需改为活跃视频有声、非活跃静音

**播放页** (`PlayerPage.tsx`)：
- 单视频全屏播放
- 手动播放/暂停控制
- 进度条拖动 + 键盘左右键 ±5s
- 互动浮层渲染在视频上层

### 4.5.2 时间轴引擎

**实现**：`interaction/timeline.js` — `InteractionTimeline` 类

```
InteractionTimeline
├── manifest: InteractionManifest    # 当前集互动清单
├── currentMs: number                # 当前播放位置 (ms)
├── running: boolean                 # 是否运行中
├── activePoint: InteractionPoint    # 当前激活的 IP
├── completed: Set<string>           # 已完成的 IP ID
│
├── play(externalClock?)  # 启动内部时钟 (rAF loop)
├── pause()               # 暂停
├── seek(ms)              # 跳转 + 解除当前激活
├── sync(ms)              # 外部时钟同步 (video.ontimeupdate)
├── matchCurrentPoint()   # 匹配当前时刻的 IP
│   ├── activePoint 过期 → dismiss('timeout')
│   ├── 新 IP 进入范围 → activate()
│   └── 高优先级抢占 → dismiss('preempted') → activate()
├── activate(point)       # 激活 IP → 调用 renderInteraction()
└── dismissActive(reason) # 解除激活 → clearInteraction()
```

**关键行为**：
- `sync()` 由 `video.ontimeupdate` 每帧调用
- 新 IP 需 `priority >= activePoint.priority + 0.2` 才能抢占
- IP 结束后自动 dismiss

### 4.5.3 视频源配置

- HomePage：`episode.videoUrl` → `/api/videos/example-drama-a/{N}`
- PlayerPage：`manifest.video_url` → 同
- Vite 代理 `/api` → `http://127.0.0.1:8787`
- 生产构建：`VITE_API_BASE_URL` 环境变量

## 4.6 互动组件系统

### 4.6.1 组件注册表

**实现**：`interaction/components.js` — `registry` 对象

| 组件 key | 渲染函数 | 交互模式 | 反馈 |
|:---|:---|:---|:---|
| `celebrate_confetti` | `CelebrateConfetti` | 点击 → Lottie 礼花 | 视觉 |
| `anger_release` | `AngerRelease` | 点击人物泄愤 | 视觉 + 浮动文字 |
| `tear_resonance` | `TearResonance` | 长按释放 emo | 视觉 + 浮动文字 |
| `laugh_burst` | `LaughBurst` | 点击 → 笑声动画 | 视觉 + "哈哈" |
| `shatter_strike` | `ShatterStrike` | 连点碎屏 | 视觉 (7帧裂纹) |
| `sugar_storm` | `SugarStorm` | 连续点击 → 甜度升级 | 视觉 (心形粒子) |
| `guardian_shield` | `GuardianShield` | 长按蓄力 2 秒 | 视觉 + 震动 (via Capacitor) |
| `team_cheer` | `TeamCheer` | 选择阵营 + 助威 | 视觉 + 阵营分数动画 |
| `prediction_card` | `PredictionCard` | 选择选项 + 倒计时 | 视觉 + 记录提示 |
| `clue_judge_card` | `ClueJudgeCard` | 选择判断 | 视觉 |
| `episode_end_prediction` | `EpisodeEndPrediction` | 选择预测 | 视觉 |
| `emotion_buffer` | `EmotionBuffer` | 长按 2 秒 → 跳过 10 秒 | 视觉 + 跳过进度 |

### 4.6.2 渲染流程

```
InteractionTimeline.activate(point)
  → renderInteraction(layer, {
      interactionPoint: point,
      assetBaseUrl: '/assets/',
      deviceTier: 'MEDIUM',
      onInteract: (event) => { ... },   // 用户交互回调
      onDismiss: (reason) => { ... },   // 用户关闭/超时回调
    })
  → registry[point.component](container, props)
  → 创建 Shadow DOM (样式隔离)
  → 渲染组件 UI
  → 绑定事件监听
  → 返回 cleanup 函数
```

### 4.6.3 待修复问题

| 问题 | 位置 | 修复 |
|:---|:---|:---|
| `LegacyRealOptionCard` 仍被 `ClueJudgeCard` 调用 | `components.js:1547` | 迁移到新版 `realOptionCard` |
| 互动事件结果仅处理 `emotion_buffer` 跳过 | `HomePage.tsx:125-134`, `PlayerPage.tsx:84-93` | 所有组件都入队 LocalEventQueue |
| `onInteract` 回调未接入队列 | 全部 | 在回调中调用 `queue.enqueue()` |
| 15 个 Legacy/死函数 | `components.js` 多个位置 | 逐个清理（见审计报告 §2.4） |
| 硬编码 `playerManifest` 兜底 | `manifest.ts:23-85` | 替换为空兜底（interaction_points: []） |

## 4.7 事件队列

**实现**：`interaction/queue.ts` — `LocalEventQueue`

```typescript
class LocalEventQueue {
  events: EventRecord[]      // 内存队列
  enqueue(event)              // 入队 + localStorage 持久化
  flush()                     // 清空 + POST /api/interactions (当前未实现)
}
```

**待修复**：
- `flush()` 当前只清空 localStorage，需实现 HTTP POST
- 需接入所有互动组件的 `onInteract` 回调
- flush 时机：定时 10 秒、进入剧尾页、切后台前、满 10 条

## 4.8 App 封装（Capacitor）

### 4.8.1 构建流程

```bash
npm run build                    # Vite 生产构建 → dist/
npx cap add android             # 创建 android/ 工程
npx cap sync                    # 同步 Web 资源到 Android
npx cap open android            # Android Studio 打开
# Android Studio → Build → Build APK
```

### 4.8.2 原生插件接入

| 插件 | 用途 | npm 包 |
|:---|:---|:---|
| Haptics | 互动组件震动反馈 | `@capacitor/haptics` |
| Share | 分享剧目 | `@capacitor/share` |
| Filesystem | 离线视频缓存 | `@capacitor/filesystem` |
| StatusBar | 全屏沉浸式 | `@capacitor/status-bar` |

### 4.8.3 App 配置

**文件**：`capacitor.config.ts`
```typescript
{
  appId: 'com.demo.cinematicdrama',
  appName: 'Cinematic Drama',
  webDir: 'dist',
  server: {
    url: 'http://192.168.x.x:5174',  // 开发时热重载
    cleartext: true                   // 允许 HTTP
  }
}
```

生产构建时删除 `server.url`，使用打包的 `dist/` 静态文件。

## 4.9 设备分级

| 等级 | 判定 | 互动组件配置 |
|:---|:---|:---|
| HIGH | 旗舰机 (8+ core, ≥6GB RAM) | 全粒子、全震动、模糊特效 |
| MEDIUM | 中端机 (4-8 core) | 粒子 60%、震动简化 |
| LOW | 低端机 (<4 core) | 粒子 30%、无震动、无光效 |

当前前端固定使用 `MEDIUM`，后续可基于 `navigator.hardwareConcurrency` 和 `deviceMemory` 自动检测。

## 4.10 待清理清单

| 文件 | 操作 |
|:---|:---|
| `src/data/drama.ts` | **删除**（零引用死代码） |
| `src/data/catalog.ts:38-89` | **删除**硬编码数据 `exampleDramaA` 和 `example-drama-b` |
| `src/data/manifest.ts:23-85` | **替换**硬编码 `playerManifest` 为空兜底 |
| `src/interaction/components.js` Legacy 函数 (15 个) | **删除**（约 600 行） |
| `src/interaction/components.js:1547` | **修复** ClueJudgeCard 从 Legacy 迁移到新版 |
| `src/pages/*.tsx` 中所有 `.catch(() => undefined)` | **替换**为明确的 error state |
