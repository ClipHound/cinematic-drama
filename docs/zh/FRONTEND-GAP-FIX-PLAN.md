# 前端对接 — 差距清单与填补方案

> 2026-06-10 | 仅聚焦前端对接阶段的灰色地带问题

---

## 一、已验证的差距清单

### 🔴 P0 — 阻断性问题

#### 1. 所有页面用硬编码假数据初始化

| 页面 | 文件:行号 | 硬编码内容 | 修复 |
|:---|:---|:---|:---|
| HomePage | `HomePage.tsx:24` | `useState<DramaItem>(exampleDramaA)` — 初始状态是假剧 | 初始 `null`，`useEffect` 拉 API 后 `setDrama` |
| DetailPage | `DetailPage.tsx:13` | `getDrama(dramaId)` 返回硬编码数据 | 同上 |
| PlayerPage | `PlayerPage.tsx:22,26` | `getEpisode()` + `playerManifest` 硬编码 | 初始 `null` |
| SearchPage | `SearchPage.tsx:9` | `useState(fallbackDramas)` | 初始 `[]` |
| TheaterPage | `TheaterPage.tsx:9-10` | `useState(fallbackDramas)` + `exampleDramaA` 兜底 | 初始 `[]` |
| ProfilePage | `ProfilePage.tsx:5-9` | stats 全部写死 | 从 API `/api/users/me/profile` 加载 |
| **所有 6 页面** | `.catch(() => undefined)` | API 失败静默降级到假数据 | 改为 error state + 重试 UI |

#### 2. 首页视频全部静音

| 文件:行号 | 问题 |
|:---|:---|
| `HomePage.tsx:193` | `<video muted>` — 硬编码静音 |
| `DetailPage.tsx:33` | `<video muted>` — 海报视频也静音 |
| `SearchPage.tsx:49` | `<video muted>` |
| `TheaterPage.tsx:27,67` | `<video muted>` — 两处 |

**修复**：首页 feed 活跃视频取消静音，非活跃视频保持静音。详情页/搜索页/剧场页的海报视频因是缩略图用途可保留静音。

#### 3. 点赞/收藏全不可用

| 文件:行号 | 元素 | 状态 |
|:---|:---|:---|
| `HomePage.tsx:228` | `<Heart>` 点赞 | 无 onClick，纯装饰 |
| `HomePage.tsx:231` | `<MessageCircle>` 评论 | 无 onClick |
| `TopBar.tsx:18` | `<Share2>` 分享 | 无 onClick |
| `TopBar.tsx:21` | `<MoreHorizontal>` 更多 | 无 onClick |
| `ProfilePage.tsx:17` | `<Bell>` 通知 | 无 onClick |
| `ProfilePage.tsx:20` | `<Settings>` 设置 | 无 onClick |

#### 4. 互动事件全部丢弃

| 文件:行号 | 问题 |
|:---|:---|
| `HomePage.tsx:124-125` | `onInteract` 回调：仅处理 `emotion_buffer` 跳过 10 秒，其他 11 种组件的事件**全部丢弃** |
| `PlayerPage.tsx:84-85` | 同上 |
| `queue.ts:30-34` | `flush()` 只清空 localStorage，**不发 HTTP 请求**。注释写 "已模拟上报" |
| 全部页面 | `LocalEventQueue` 类**零引用** — 没有任何地方 import 或使用 |

#### 5. AI 搜索是假的

| 层级 | 问题 |
|:---|:---|
| 后端 `content.py:164-191` | `search()` 用 `if needle in haystack` 做子串匹配 |
| 前端 `AiSearchPage.tsx:28-31` | 后端不可用时 fallback `"AI 搜索服务暂时不可用。"` |
| 前端搜索热词 `SearchPage.tsx:77` | `item.slice(0, 4)` 把 "高燃反转" 截断成 "高燃反" |

#### 6. 视频入库流程完全缺失

| 缺失项 |
|:---|
| 无上传页面/API |
| 无管理端（`/admin` 路由） |
| 视频靠手动放到 `content/videos/` |
| 上传后无自动触发 Pipeline |

---

### 🟡 P1 — 功能残缺

#### 7. ProfilePage 全部是假数据

- 用户名硬编码 "短剧观众"，描述 "互动体验测试账号"
- 头像硬编码字母 "C"
- 统计写死 "12集 / 48次 / 6部"
- "互动记录" 副标题写 "本地事件队列预览"（开发者口吻）
- "离线缓存" 副标题写 "本地 MP4 资源"（无实现）

#### 8. 后端元数据返回假值

| 字段 | 当前返回值 | 应返回 |
|:---|:---|:---|
| `subtitle` | 永远 `"AI interactive short drama"` | 从 report.json 取中文描述 |
| `genre` | 永远 `["interactive", "short-drama"]` | 从 report mood/tags 推导 |
| `score` | 永远 `"8.4"` | 暂无真实数据可保留，但标注"暂无评分" |
| `title`(episode) | 永远 `"Episode {n}"` | `"第{n}集"` |

---

### 🧹 屎山/死代码

#### 9. 死代码文件

| 文件 | 说明 |
|:---|:---|
| `src/data/drama.ts` (93行) | 零引用 — 没有任何地方 import |

#### 10. Legacy 组件函数（`components.js` 内）

| 函数 (行号) | 状态 |
|:---|:---|
| `LegacySugarStorm` (653-699) | 未注册到 registry — 死代码 |
| `LegacyTeamCheer` (1149-1190) | 未注册 — 死代码 |
| `LegacyEmotionBuffer` (1568-1596) | 未注册 — 死代码 |
| `LegacyRealOptionCard` (1740-1780) | ⚠️ 仍被 `ClueJudgeCard`(1547行) 调用 — 需迁移 |
| `addAngerHit` (1930-1944) | 未被调用 |
| `addOriginalAngerHit` (1954-1967) | 未被调用 |
| `addOriginalAngerWord` (1969-1981) | 未被调用 |
| `addOriginalLaughWord` (1983-1996) | 未被调用 |
| `addOriginalEmoWord` (1998-2013) | 未被调用 |
| `addFloatingWord` (2015-2022) | 未被调用 |
| `addHearts` (2024-2038) | 未被调用 |
| `addOriginalHearts` (2040-2058) | 未被调用 |
| `holdAction` (2061-2098) | 未被调用 |
| `isControlEvent` (2100-2102) | 未被调用 |

**合计可清理：~600 行死代码**（`components.js` 从 2118 → ~1500 行）

---

## 二、填补方案（按执行顺序）

### Step 1: 死代码清理 (半天)

```
□ 删除 src/data/drama.ts
□ 删除 components.js 中 14 个未使用的 Legacy/helper 函数
□ ClueJudgeCard 从 LegacyRealOptionCard 迁移到 realOptionCard
□ 删除 catalog.ts:38-89 硬编码数据
□ 删除 manifest.ts:23-85 硬编码 playerManifest
```

### Step 2: 页面 loading/error 状态 (1天)

6 个页面逐个改：
```
□ HomePage: useState(null) + useEffect(loadDrama) + loading skeleton + error banner
□ DetailPage: 同上
□ PlayerPage: 同上
□ SearchPage: useState([]) + useEffect(loadDramas) + loading + error
□ TheaterPage: 同上
□ ProfilePage: useState(null) + useEffect(loadProfile) + loading + error
```

模式：
```tsx
// Before (❌)
const [drama, setDrama] = useState(exampleDramaA);
useEffect(() => { loadDrama(id).then(setDrama).catch(() => undefined); }, [id]);

// After (✅)
const [drama, setDrama] = useState<DramaItem | null>(null);
const [error, setError] = useState<string | null>(null);
useEffect(() => {
  loadDrama(id).then(setDrama).catch(e => setError(e.message));
}, [id]);
if (error) return <ErrorBanner message={error} onRetry={() => ...} />;
if (!drama) return <LoadingSkeleton />;
```

### Step 3: 视频声音修复 (半小时)

```
□ HomePage.tsx:193: 移除 muted → 改为仅当前活跃视频非静音
  方案：videoRefs.current[activeIndex]?.muted = false，其余 muted = true
```

### Step 4: 点赞/分享按钮对接 (1天)

```
□ HomePage 点赞按钮 → onClick: 本地动画 + queue.enqueue({type:"like"})
□ HomePage 评论按钮 → onClick: 弹出简单评论输入框（或先 toast "即将开放"）
□ TopBar 分享按钮 → onClick: navigator.share() 或 Capacitor Share
□ TopBar 更多按钮 → onClick: 弹出菜单（分享/收藏/举报占位）
□ ProfilePage 通知/设置 → onClick: toast "即将开放" 或跳转子页面
```

### Step 5: 互动事件接入队列 (1天)

```
□ LocalEventQueue.flush() 实现 HTTP POST → /api/interactions
□ HomePage onInteract: 移除 "仅处理 emotion_buffer" 限制
□ PlayerPage onInteract: 同上
□ 所有 12 种组件的交互结果 → queue.enqueue()
□ flush 时机: 定时10秒 / 满10条 / 页面隐藏(visibilitychange) / 切后台(pagehide)
```

### Step 6: AI 搜索对接 (1天)

```
□ 后端: 部署 Ollama BGE-M3 → 替换 content.py search() 为 Qdrant 向量搜索
□ 前端 AiSearchPage: 搜索结果展示为可点击卡片（非纯文本）
□ SearchPage: 修复热词截断 bug (slice(0,4))
```

### Step 7: 后端元数据中文化 (半天)

```
□ content.py:99 subtitle → 从 report.json 取首集摘要前20字
□ content.py:102 genre → 从 report mood 推导
□ content.py:114 title → f"第{number}集"
```

---

## 三、不在此阶段做的事

- ❌ 不重写后端框架 (http.server → FastAPI)
- ❌ 不迁移数据库 (SQLite → PostgreSQL)
- ❌ 不修改离线 Pipeline（它已可用）
- ❌ 不改动互动组件库（Lottie 动画/资产路径）
- ❌ 不加新互动组件
- ❌ 不搞视频上传管理端（P1 再做）
- ❌ 不做 WebSocket（P1 再做）

---

## 四、执行顺序依赖

```
Step 1 (死代码清理) → 无依赖，先做
Step 2 (loading/error) → 依赖 Step 1（删了硬编码数据后页面会崩，必须先加 loading 态）
Step 3 (视频声音) → 无依赖，快速修
Step 4 (点赞/分享) → 依赖 Step 2（页面结构稳定后加交互）
Step 5 (事件队列) → 依赖 Step 4（交互产生事件后入队）
Step 6 (AI 搜索) → 依赖后端嵌入服务就绪
Step 7 (元数据中文) → 无依赖，快速修
```

**预估总工时：4-5 天**
