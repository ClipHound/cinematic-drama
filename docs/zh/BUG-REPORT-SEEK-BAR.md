# Bug Report：首页进度条点击/拖动将时间重置为 0，无法 Seek

**状态**：待确认  
**影响页面**：首页（`HomePage.tsx`）  
**影响功能**：视频进度条点击 / 拖动 seek  

---

## 1. 现象

- 首页播放剧集时，进度条显示当前进度（例如 ~1.64%）
- 点击或拖动进度条任意位置后，视频时间**跳回 0**（从头播放）
- "我没法拖动时间条"——seek 功能完全不可用

关联 DOM 元素（用户截图）：

```html
<div data-video-control="true"
     class="absolute inset-x-0 bottom-20 z-[60] flex h-2.5 touch-none cursor-pointer items-center"
     role="slider"
     aria-valuenow="2"
     tabindex="0">
  <div class="relative h-[3px] w-full ...">
    <div style="width: 1.64091%;"></div>   <!-- 填充条 -->
    <span style="left: 1.64091%;"></span>   <!-- 拖拽手柄 -->
  </div>
</div>
```

---

## 2. 代码位置

| 文件 | 行号 | 说明 |
|---|---|---|
| `src/pages/HomePage.tsx` | 172-183 | `seekFromPointer`——seek 核心逻辑 |
| `src/pages/HomePage.tsx` | 364-434 | 进度条 JSX（role="slider"） |
| `src/pages/HomePage.tsx` | 192-239 | `activate()`——创建 InteractionTimeline |
| `src/pages/HomePage.tsx` | 299-301 | `onTimeUpdate`——视频时间更新回调 |
| `src/interaction/timeline.js` | 31-46 | `seek()` / `sync()`——时间钳制逻辑 |

---

## 3. 已确认的代码缺陷

### 3.1 Timeline 的 `duration_ms` 从未从 `<video>` 同步

这是**确定性 bug**——对比两个页面可以清楚地看到差异：

**PlayerPage.tsx（line 161-163）——有同步：**
```tsx
onLoadedMetadata={(event) => {
    const duration = event.currentTarget.duration;
    if (Number.isFinite(duration) && duration > 0)
        manifest.duration_ms = Math.round(duration * 1000);  // ✅ 同步了
}}
```

**HomePage.tsx（line 303）——没有同步：**
```tsx
onLoadedMetadata={(event) => updateProgress(index, event.currentTarget)}
// ❌ 只更新了 progress，没有同步 timeline.manifest.duration_ms
```

**HomePage.tsx 创建 Timeline 时（line 207-208）——直接使用后端 manifest：**
```tsx
const manifest = await loadEpisodeManifest(...);  // 后端返回，duration_ms 极大概率为 0
const timeline = new InteractionTimeline({
    manifest: manifest as InteractionManifest,    // 直接传入，duration_ms === 0
});
```

**后果**：

`timeline.js` 的 `seek()` 和 `sync()` 每次都将时间钳制在 `duration_ms` 以内：

```js
// timeline.js line 32
seek(ms) {
    this.offsetMs = Math.max(0, Math.min(ms, this.manifest.duration_ms));
    // duration_ms === 0 → Math.min(50000, 0) === 0 → this.currentMs = 0
}
```

整个交互系统（interaction points）因为 `currentMs` 恒为 0 而全部失效。

### 3.2 事件竞态：`onPointerDown` 内 `timeupdate` 同步触发

`seekFromPointer` 中 `video.currentTime = time`（line 178）会**同步**触发 `onTimeUpdate`：

```tsx
// line 299-301
onTimeUpdate={(event) => {
    updateProgress(index, event.currentTarget);
    // 此时 setDraggingIndex(index) 还未被 React 提交
    // draggingIndex 仍然是 null
    // null !== index → true → 进入 sync 流程
    if (index === activeIndex && draggingIndex !== index)
        timelineRef.current?.sync(event.currentTarget.currentTime * 1000);
}}
```

这意味着一次点击会同时触发 `seek()`（line 179）和 `sync()`（line 301），两者在 `duration_ms === 0` 时都把 timeline 内部状态钳制为 0。

注意：`sync()` 本身不写 `video.currentTime`，但它触发的 `matchCurrentPoint()` → `onActivate` → `renderInteraction` 路径可能在特定条件下产生副作用。

---

## 4. 待排查的浏览器层面嫌疑

即使修复了 3.1，仍可能存在移动端特有的问题：

**iOS Safari 对 HLS 流 seek 的限制**：当 `video.currentTime = time` 跳转到尚未缓冲的位置时，浏览器可能静默拒绝赋值，将 `currentTime` 拉回最近的可播放位置（通常就是 0，如果只缓冲了开头很小一段）。

这与"进度约 2%，点击后回到 0"的症状吻合——视频只缓冲了开头部分，seek 到 50% 的点实际上不可达。

**验证方法**：在 `seekFromPointer` 中 `video.currentTime = time` 之后加一行：

```tsx
console.log('seek target:', time, 'actual currentTime:', video.currentTime);
```

如果两个值严重不一致，就是浏览器层面的问题。

---

## 5. 建议的修复方案

### 5.1 必做：修复 `duration_ms` 同步（代码缺陷）

1. **在 Timeline 创建时注入真实 duration**（`activate` 函数中）：
   ```tsx
   const durationFromVideo = videoRefs.current[activeIndex];
   const durationMs = durationFromVideo && Number.isFinite(durationFromVideo.duration)
     ? Math.round(durationFromVideo.duration * 1000)
     : manifest.duration_ms;

   const timeline = new InteractionTimeline({
       manifest: { ...manifest, duration_ms: durationMs || manifest.duration_ms },
   });
   ```

2. **在 `onLoadedMetadata` 中增加同步**，与 PlayerPage 对齐：
   ```tsx
   onLoadedMetadata={(event) => {
       const v = event.currentTarget;
       const d = v.duration;
       if (Number.isFinite(d) && d > 0 && timelineRef.current) {
           timelineRef.current.manifest.duration_ms = Math.round(d * 1000);
       }
       updateProgress(index, event.currentTarget);
   }}
   ```

3. **在 `seekFromPointer` 中 seek 前兜底**：
   ```tsx
   if (timelineRef.current && Number.isFinite(video.duration) && video.duration > 0) {
       timelineRef.current.manifest.duration_ms = Math.round(video.duration * 1000);
   }
   timelineRef.current?.seek(Math.round(video.currentTime * 1000));
   ```

### 5.2 建议：防御移动端 seek 失败

在 `seekFromPointer` 末尾增加校验：

```tsx
video.currentTime = time;
// 验证 seek 是否实际生效（移动端 HLS 可能静默失败）
if (Math.abs(video.currentTime - time) > 0.5) {
    // seek 未生效，跳过本次 seek 的后续处理
    return null;
}
```

---

## 6. 不影响修复的结论

- `event.preventDefault()` + `setPointerCapture` 的调用顺序**不影响** seek 行为（两者独立）
- `inset-x-0` 的布局**不影响** `getBoundingClientRect()` 的坐标计算
- `onTimeUpdate` 的热路径**不应**增加额外操作（曾尝试加 `syncTimelineDuration` 导致卡顿）
