# Iteration V2: 测试复盘改进方案

> 基于 TEST-REPORT-fullpipeline-5eps.md 的分析结果
> 日期: 2026-06-10
> 执行人: 代码助手

---

## 问题总结

从 5 集测试中发现以下需要改进的问题，按严重程度排序：

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| 1 | ASR segments 是字级(每段1字)，注入 Prompt 产生 500+ 行噪音 | **高** | VLM 每集浪费 ~5000 tokens 在无用的单字行上；模型难以从碎片中定位句子边界 |
| 2 | ASR 串行导致 GPU 反复加载卸载，638s 本可 <400s | **中** | 每部剧多等 4 分钟，规模化后不可接受 |
| 3 | Pass 1 全剧蓝图不持久化，无法审核/复用/调参 | **中** | 调试困难，无法追溯互动设计的全局策略依据 |
| 4 | 互动密度不可配置，固定 3-8 个 | **中** | 不同类型短剧/不同客户需求不一致 |
| 5 | Ep2/Ep5 覆盖率 43-45%（几乎一半时间有互动弹出） | **中** | 对于 75s/108s 的短集，4-5 个互动点过于密集 |
| 6 | emotion_segments 为空（ASR 服务未开 emotion2vec） | **低** | 非代码问题，但系统应在无情绪数据时有明确行为 |
| 7 | Ep1 的 candidate_interactions 中 Ep3 有 start=3000 end=34000 (31秒)，超出 20s 上限 | **低** | safety_rules 已修正为 [3000-12000]，系统容错已 work |

---

## 改进计划

### 改进 1: ASR Segments 句级合并 (P0)

**问题本质**: Qwen3-ASR 返回的是 forced-alignment 字级时间戳。每集 300-572 段，每段 1 个字。直接注入 Prompt 会产生：
- Ep1: 572 行 × ~23 chars/行 = 13,192 chars ≈ 5,700 tokens 
- 内容全是 `[00:12.880-00:12.880] 真` 这种单字行，对 VLM 理解无帮助

**目标**: 合并为句级 segments，使 Prompt 注入降至 30-60 行/集

**方案**: 利用 VAD (已有) + 标点/停顿 合并策略

```python
# src/drama_agent/asr/sentence_merger.py

def merge_to_sentences(
    segments: list[dict],      # 字级 segments [{text, start_ms, end_ms}, ...]
    vad_segments: list[dict],  # [{start_ms, end_ms, type}, ...]
    *,
    max_gap_ms: int = 300,     # 字间超过 300ms 视为句子边界
    punctuation: str = "。？！，；：、…",  # 句内标点也切分
) -> list[dict]:
    """
    将字级 segments 合并为句级。
    
    切分规则(按优先级):
    1. VAD speech boundary (non-speech gap > 0) → 必切
    2. 字间时间 gap > max_gap_ms → 切
    3. 遇到句末标点(。？！) → 切
    4. 累计超过 20 字且遇到逗号 → 切 (避免超长句)
    
    输出: [{text: "完整句子", start_ms, end_ms}, ...]
    """
```

**改动文件**:
1. 新建 `src/drama_agent/asr/sentence_merger.py` — 合并逻辑
2. 修改 `src/drama_agent/asr/client.py` — `normalize_asr_response()` 后追加 `merge_to_sentences()` 产出 `sentences` 字段
3. 修改 `src/drama_agent/asr/client.py` — `format_asr_for_prompt()` 改为读取 `sentences` (句级) 而非 `segments` (字级)
4. 保留原始 `segments` 字段不动（用于精确时间查询）

**新的 ASR JSON 结构**:
```json
{
  "text": "完整文本",
  "language": "Chinese",
  "segments": [...],          // 原始字级，保留
  "sentences": [              // 新增: 句级合并
    {"text": "真要嫁女儿，那几个蛮子过来凑什么热闹？", "start_ms": 12880, "end_ms": 15040},
    {"text": "去，把当初来招亲的人给我杀了。", "start_ms": 16960, "end_ms": 19200}
  ],
  "vad_segments": [...],
  "emotion_segments": [...],
  "audio_events": [...]
}
```

**新的 Prompt 注入效果** (从 573 行降至 ~40 行):
```
## Current Episode ASR (timestamped)
[00:12.880-00:15.040] 真要嫁女儿，那几个蛮子过来凑什么热闹？
[00:16.960-00:19.200] 去，把当初来招亲的人给我杀了。
[00:19.500-00:22.100] 哎，陛下息怒，小心别起火。
...
```

**验证标准**:
- Ep1 原 572 行 → 合并后 ≤60 行
- 每句 text 至少 2 字，至多 ~40 字
- 合并后 start_ms 取首字 start_ms，end_ms 取末字 end_ms
- format_asr_for_prompt 输出长度从 ~13000 chars 降至 ~2000 chars

---

### 改进 2: ASR 批量前置 (P1)

**问题本质**: 当前 `process_episode()` 逐集串行: ASR(ep1) → VLM(ep1) → ASR(ep2) → VLM(ep2)... VLM 调用 60-98s 期间 ASR GPU 空闲超时卸载，下一集重新加载 ~30s。

**方案**: 在 EpisodeLoop.run() 开始时，先批量完成所有 ASR

```python
# src/drama_agent/engine/episode_loop.py

def run(self) -> dict[str, Any]:
    self.project.initialize()
    self.memory.update_series_state(total_episodes=self.config.total_episodes)
    start = self._determine_start_episode()
    
    # === 新增: ASR 批量前置 ===
    self._batch_asr(start, self.config.total_episodes)
    
    results: list[ExecutionResult] = []
    failures = 0
    for episode_num in range(start, self.config.total_episodes + 1):
        result = self.process_episode(episode_num)
        ...

def _batch_asr(self, start: int, end: int) -> None:
    """Pre-run ASR for all episodes to keep the GPU model hot."""
    for episode_num in range(start, end + 1):
        self._ensure_asr(episode_num)
```

**改动文件**:
1. 修改 `src/drama_agent/engine/episode_loop.py` — 在 `run()` 中 VLM 循环前插入 `_batch_asr()`

**验证标准**:
- ASR 服务 docker logs 不再出现 "offloading GPU->CPU" 或 "Lazy-loading"
- 5 集总耗时下降 ~30%（从 638s 降至 ~450s）

---

### 改进 3: Pass 1 蓝图持久化 (P1)

**问题本质**: `run_global_pass()` 返回 dict 后仅在内存中传给 Pass 2，不写文件。无法：
- 人工审核全局策略
- 复用已有蓝图跑新的 Pass 2 (调参场景)
- 追溯互动设计的决策依据

**方案**:

```python
# src/interaction_designer/agent.py (修改 run 方法)

def run(self, ..., blueprint_path: Path | None = None) -> list[DesignResult]:
    ctx = load_project_context(project_dir)
    global_context = build_global_context(ctx)
    
    # 支持加载已有蓝图 或 生成新蓝图
    if blueprint_path and blueprint_path.exists():
        blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
    else:
        blueprint = run_global_pass(self.llm, global_context)
    
    # 持久化蓝图
    blueprint_out = output_dir / "rhythm_blueprint.json"
    blueprint_out.parent.mkdir(parents=True, exist_ok=True)
    blueprint_out.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
    
    ...
```

**CLI 扩展**:
```bash
# 使用已有蓝图 (跳过 Pass 1)
drama-agent design-interactions \
  --project projects/test-5eps-v2 \
  --blueprint outputs/example-drama-a/rhythm_blueprint.json \
  --output-dir outputs
```

**改动文件**:
1. 修改 `src/interaction_designer/agent.py` — 蓝图写入 + 可选加载
2. 修改 `src/drama_agent/cli.py` — `design_interactions` 命令新增 `--blueprint` 参数

**产出物**:
```json
// outputs/example-drama-a/rhythm_blueprint.json
{
  "drama_profile": {
    "genre": "古装爽剧",
    "core_emotion": "隐忍复仇 + 反转爽感",
    "audience_expectation": "..."
  },
  "rhythm_blueprint": [
    {
      "episode_num": 1,
      "positioning": "铺垫集",
      "interaction_density": "medium",
      "primary_emotion": "tense",
      "emphasis": "...",
      "end_interaction_type": "prediction"
    },
    ...
  ],
  "global_strategy": {...}
}
```

---

### 改进 4: 互动密度可配置 + 短集自动降频 (P1)

**问题本质**:
- Ep2 (75s) 有 4 个互动点，覆盖率 43.7% — 几乎每 18 秒就弹一次
- Ep5 (108s) 有 4 个互动点，覆盖率 45.0%
- 而 Ep1 (309s) 有 5 个互动点，覆盖率仅 14.6%

固定 "3-8 个" 的规则忽略了集时长差异。

**方案**: 引入密度配置 + 自动调节

```python
# src/interaction_designer/config.py (新建)

from dataclasses import dataclass

@dataclass(slots=True)
class DesignConfig:
    """互动设计全局配置，支持外部覆盖"""
    
    # 密度控制
    max_points_per_minute: float = 1.5     # 每分钟最多 1.5 个互动点
    min_points_per_episode: int = 2        # 每集最少 2 个
    max_points_per_episode: int = 8        # 每集最多 8 个
    max_coverage_ratio: float = 0.35       # 互动时间不超过总时长 35%
    min_gap_ms: int = 10000                # 相邻互动点最小间隔 10s
    
    # 时长约束
    min_duration_ms: int = 5000
    max_duration_ms: int = 20000
    
    # 组件多样性
    max_consecutive_same_component: int = 2
    min_unique_components: int = 2         # >=3 个点时至少用 2 种组件
    
    @classmethod
    def from_file(cls, path) -> "DesignConfig":
        """从 JSON 文件加载配置覆盖"""
        import json
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            return cls()
        overrides = json.loads(p.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in overrides.items() if k in cls.__dataclass_fields__})
    
    def max_points_for_duration(self, duration_ms: int) -> int:
        """根据时长计算该集允许的最大互动点数"""
        minutes = duration_ms / 60000
        by_rate = int(minutes * self.max_points_per_minute)
        return max(self.min_points_per_episode, min(by_rate, self.max_points_per_episode))
    
    def max_total_interaction_ms(self, duration_ms: int) -> int:
        """该集互动总时长上限"""
        return int(duration_ms * self.max_coverage_ratio)
```

**Pass 2 Prompt 注入变化**: 根据集时长动态调整指令

```python
# 在 pass2_episode.py 的 Prompt 中:
def _density_instruction(duration_ms: int, config: DesignConfig) -> str:
    max_points = config.max_points_for_duration(duration_ms)
    max_coverage_sec = config.max_total_interaction_ms(duration_ms) // 1000
    return f"""
本集时长: {duration_ms // 1000} 秒
互动点上限: {max_points} 个 (基于 {config.max_points_per_minute}/分钟)
互动总时长上限: {max_coverage_sec} 秒 (不超过总时长的 {int(config.max_coverage_ratio*100)}%)
相邻互动间隔: 至少 {config.min_gap_ms // 1000} 秒
"""
```

**Safety rules 联动**: `normalize_design_output` 接受 config，按密度裁剪

```python
# safety_rules.py 修改
def normalize_design_output(design, *, episode_id, duration_ms, config: DesignConfig = None):
    config = config or DesignConfig()
    max_allowed = config.max_points_for_duration(duration_ms)
    # ... 裁剪超限互动点 (按 priority 排序，保留 top-N)
```

**CLI 扩展**:
```bash
# 使用自定义密度配置
drama-agent design-interactions \
  --project projects/test-5eps-v2 \
  --config design_config.json \
  --output-dir outputs
```

**改动文件**:
1. 新建 `src/interaction_designer/config.py` — DesignConfig 数据类
2. 修改 `src/interaction_designer/pass2_episode.py` — Prompt 注入时长/密度指令
3. 修改 `src/interaction_designer/safety_rules.py` — 基于 config 裁剪
4. 修改 `src/interaction_designer/agent.py` — 接受 config 参数 + 传递 duration_ms
5. 修改 `src/drama_agent/cli.py` — 新增 `--config` 参数

**预期效果**:
- Ep2 (75s): max_points = max(2, int(1.25 * 1.5)) = 2 个 (从 4 降到 2)
- Ep5 (108s): max_points = max(2, int(1.8 * 1.5)) = 2 个 (从 4 降到 2-3)
- Ep1 (309s): max_points = max(2, int(5.15 * 1.5)) = 7 个 (保持上限 7)

---

### 改进 5: output_formatter 获取真实视频时长 (P2)

**问题本质**: 当前 `infer_duration_ms()` 在 ffprobe 不可用时用 `max(end_ms) + 12000` 估算。但 Ep2 报告 75s 的 `duration_ms`，而实际视频应该不止这么短（candidate_interactions 最大 end_ms 是 74000）。这说明 ffprobe 可能不在 PATH 中。

同时，Pass 2 需要视频时长来做密度计算 — 如果时长不准，密度限制就失效。

**方案**: 从 ASR 的 VAD 数据推算视频时长作为 fallback

```python
def infer_duration_ms(video_dir, video_pattern, episode_num, design, *, asr_data=None):
    # 优先: ffprobe
    if video_dir:
        d = _ffprobe_duration_ms(video_dir / video_pattern.format(num=episode_num))
        if d > 0:
            return d
    # 次优: ASR VAD 最后一段的 end_ms (语音到最后说明视频还在播)
    if asr_data and asr_data.get("vad_segments"):
        last_vad = max(asr_data["vad_segments"], key=lambda v: v.get("end_ms", 0))
        vad_end = int(last_vad.get("end_ms", 0))
        if vad_end > 0:
            return vad_end + 5000  # 最后一段语音结束后留 5s buffer
    # 最后: 从互动点推算
    max_end = max((int(p.get("end_ms") or 0) for p in design.get("interaction_points") or []), default=0)
    return max_end + 12000 if max_end else 0
```

**改动文件**:
1. 修改 `src/interaction_designer/output_formatter.py` — 增加 ASR fallback
2. 修改 `src/interaction_designer/agent.py` — 将 ASR data 传入 infer_duration_ms

---

### 改进 6: 视频时长提前注入 Pass 2 上下文 (P2)

**关联改进 4 和 5**。Pass 2 的 Prompt 目前不知道本集视频多长。需要在 `build_episode_context()` 阶段就确定时长，作为上下文传入。

**方案**: context_builder 计算时长并附加

```python
# context_builder.py
def build_episode_context(ctx, episode_num, blueprint, *, video_dir=None, video_pattern="", config=None):
    ...
    asr_data = _load_asr(project_dir / "asr" / f"ep{episode_num:02d}.json")
    duration_ms = _estimate_duration(video_dir, video_pattern, episode_num, asr_data)
    return {
        ...
        "duration_ms": duration_ms,
        "density_instruction": _density_instruction(duration_ms, config),
    }
```

---

## 执行顺序

```
改进 1 (ASR 句级合并)          ← 最高优先级，直接影响理解质量
    ↓
改进 2 (ASR 批量前置)          ← 紧随其后，一起改 ASR 相关代码
    ↓
改进 3 (Pass 1 蓝图持久化)     ← 简单，几行代码
    ↓
改进 5 (视频时长 fallback)     ← 改进 4 的前置依赖
    ↓
改进 6 (时长注入 Pass 2)       ← 改进 4 的前置依赖
    ↓
改进 4 (密度可配置)            ← 依赖 5+6 提供准确时长
```

---

## 逐步验证

### 改进 1 完成后验证:

```bash
# 重新跑 ASR (或删除旧文件让 pipeline 重新生成)
rm -rf projects/test-5eps-v2/asr

# 只跑 ASR 不跑 VLM (临时脚本)
python -c "
import sys; sys.path.insert(0, 'src')
from pathlib import Path
from drama_agent.asr.client import ASRClient, format_asr_for_prompt
import json

client = ASRClient('http://localhost:10000')
video_dir = Path(r'<project-root>/样例剧(测试使用)')
out_dir = Path('projects/test-5eps-v2/asr')
out_dir.mkdir(parents=True, exist_ok=True)

for i in range(1, 6):
    result = client.transcribe(video_dir / f'第{i}集.mp4')
    data = result.model_dump()
    (out_dir / f'ep{i:02d}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    sentences = data.get('sentences', [])
    formatted = format_asr_for_prompt(data)
    lines = formatted.split('\n')
    print(f'Ep{i}: {len(data.get(\"segments\",[]))} chars → {len(sentences)} sentences → {len(lines)} prompt lines')
"
```

**期望**:
```
Ep1: 572 chars → ~45 sentences → ~46 prompt lines
Ep2: 229 chars → ~20 sentences → ~21 prompt lines
...
```

### 改进 2 完成后验证:

```bash
# 清理旧数据，重新跑全流程
rm -rf projects/test-5eps-v3

time drama-agent run \
  --title "示例剧A" \
  --video-dir "<project-root>/样例剧(测试使用)" \
  --pattern "第{num}集.mp4" \
  --episodes 5 \
  --project-id test-5eps-v3

# 期望: 总耗时 < 450s (原 638s)
# docker logs 中不应出现 "offloading" 或 "Lazy-loading"
```

### 改进 3 完成后验证:

```bash
drama-agent design-interactions \
  --project projects/test-5eps-v3 \
  --output-dir outputs/v2 \
  --drama-id example-drama-a

# 检查蓝图文件
cat outputs/v2/example-drama-a/rhythm_blueprint.json | python -m json.tool

# 使用已有蓝图重跑 Pass 2 (不调 LLM Pass 1)
drama-agent design-interactions \
  --project projects/test-5eps-v3 \
  --output-dir outputs/v2-rerun \
  --blueprint outputs/v2/example-drama-a/rhythm_blueprint.json \
  --drama-id example-drama-a
```

### 改进 4+5+6 完成后验证:

```bash
# 用默认配置
drama-agent design-interactions \
  --project projects/test-5eps-v3 \
  --output-dir outputs/v3-default \
  --drama-id example-drama-a

# 用自定义高密度配置
echo '{"max_points_per_minute": 2.5, "max_coverage_ratio": 0.5}' > high_density.json
drama-agent design-interactions \
  --project projects/test-5eps-v3 \
  --output-dir outputs/v3-high \
  --drama-id example-drama-a \
  --config high_density.json

# 对比
python -c "
import json
from pathlib import Path
for label, d in [('default', 'outputs/v3-default'), ('high', 'outputs/v3-high')]:
    print(f'\\n=== {label} ===')
    for f in sorted(Path(d).rglob('*.interactions.json')):
        data = json.loads(f.read_text(encoding='utf-8'))
        pts = data.get('interaction_points', [])
        dur = data.get('duration_ms', 1)
        cov = sum(p['end_ms']-p['start_ms'] for p in pts) / dur * 100
        print(f'  {f.name}: {len(pts)} points, coverage={cov:.1f}%')
"
```

**期望 (default 配置)**:
- Ep2 (75s): 2 个点, coverage < 35%
- Ep5 (108s): 2-3 个点, coverage < 35%
- Ep1 (309s): 5-7 个点, coverage ~15%

---

## 改动文件汇总

| 文件 | 动作 | 对应改进 |
|------|------|---------|
| `src/drama_agent/asr/sentence_merger.py` | **新建** | #1 |
| `src/drama_agent/asr/client.py` | 修改 | #1 |
| `src/drama_agent/engine/episode_loop.py` | 修改 | #2 |
| `src/interaction_designer/config.py` | **新建** (注意: 这是 interaction_designer 的 config，不是 drama_agent 的) | #4 |
| `src/interaction_designer/agent.py` | 修改 | #3, #4, #5 |
| `src/interaction_designer/pass2_episode.py` | 修改 | #4, #6 |
| `src/interaction_designer/safety_rules.py` | 修改 | #4 |
| `src/interaction_designer/context_builder.py` | 修改 | #6 |
| `src/interaction_designer/output_formatter.py` | 修改 | #5 |
| `src/drama_agent/cli.py` | 修改 | #3, #4 |

---

## 注意事项

1. **改进 1 的句级合并不要破坏旧 ASR 文件兼容性** — `format_asr_for_prompt()` 应该能处理有 `sentences` 字段和没有 `sentences` 字段(旧格式)两种情况。没有时 fallback 到按 VAD 切分 `segments`。

2. **改进 4 的 DesignConfig 文件不要和 drama_agent 的 config.py 混淆** — interaction_designer 已经有自己独立的模块空间，config.py 放在 `src/interaction_designer/config.py` 下。注意当前这个路径没有被占用（现有的 `config.py` 在 `src/drama_agent/config.py`）。

3. **改进 2 的 _batch_asr 应有进度提示** — 用 rich 的 progress bar 或至少 print 每集 ASR 开始/完成。

4. **所有修改完成后跑一次完整的 5 集端到端测试**，对比改进前后:
   - ASR prompt 行数
   - 总耗时
   - 互动点分布 (短集是否降频)
   - 蓝图文件是否生成

5. **不要修改 `interaction_generator/` (旧规则转换器)** — 它是降级路径，保持不动。

---

> 执行完所有改进后，请重新生成 TEST-REPORT 并反馈结果。
