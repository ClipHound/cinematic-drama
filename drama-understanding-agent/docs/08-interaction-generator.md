# 视频理解 → 前端互动点对接方案设计

> 日期: 2026-06-05
> 状态: 方案设计
> 上游: drama-understanding-agent (当前系统)
> 下游: 前端互动播放页 (通过后端 API 消费)
> 交接面文档: `OFFLINE_VIDEO_UNDERSTANDING_OUTPUT_SPEC.md` + `SDD-06 §6.1`

---

## 一、问题定义

### 1.1 当前系统产出什么

drama-understanding-agent 当前产出:

```
projects/{project_id}/output/
├── report.json          ← 全剧报告 (角色/关系/事件/伏笔/摘要)
├── report.md            ← 人类可读报告
├── characters.json      ← 角色档案
├── relationships.json   ← 人物关系网
├── plot_events.json     ← 剧情事件时间线
└── plot_threads.json    ← 伏笔线索
```

每集 action_plan 含:
- `episode_summary` (150-300字剧情摘要)
- `mood` (本集情绪基调)
- `cliffhanger` (悬念点)
- `actions[]` (角色更新/关系/事件/伏笔/截帧)

### 1.2 前端需要什么

前端需要的是 `Episode Interaction Manifest`:

```json
{
  "schema_version": "1.0",
  "drama_id": "xxx",
  "episode_id": "ep_001",
  "video_duration_ms": 180000,
  "interaction_points": [
    {
      "id": "ip_ep_001_0001",
      "start_ms": 21000,
      "end_ms": 30000,
      "component": "anger_release",      ← 触发什么组件
      "emotion": "angry",                 ← 情绪类型
      "intensity": 0.86,                  ← 强度
      "confidence": 0.91,                 ← 置信度
      "highlight_reason": "角色被欺负，观众适合点击宣泄",
      "config": {}
    }
  ]
}
```

### 1.3 核心差距

| 维度 | 当前系统有的 | 前端需要的 | 差距 |
|------|-------------|-----------|------|
| 时间精度 | plot_event.start_time = "01:23" (分:秒字符串) | start_ms / end_ms (毫秒整数) | 格式转换 + 精度提升 |
| 事件类型 | 6种 event_type (setup/conflict/climax/reveal/twist/resolution) | 10种 highlight_type → component 映射 | 需增加情绪维度分类 |
| 情绪标注 | mood (全集级) + character.emotion (角色级) | 每个互动点独立 emotion + intensity | 粒度不够 |
| 互动组件 | 无 | shatter_strike/anger_release/sugar_rain 等 | **完全缺失**,需新增 |
| 信号来源 | 纯视觉模型 | ASR + Visual + Audio 三路融合 | 缺 ASR 独立分析和 Audio 分析 |
| 关键台词 | 无 (仅有 ASR 原文注入 Prompt) | key_line (代表性台词) | 需从 ASR 中提取 |
| 集尾互动 | cliffhanger + 伏笔 | predictions[] + character_voices[] + clue_summary | 需新增生成逻辑 |

---

## 二、对接架构设计

### 2.1 总体思路

**不修改 drama-understanding-agent 的核心循环**,而是在其产出基础上,新增一个 `InteractionGenerator` 后处理模块,将剧情理解数据转化为前端需要的互动点。

```
┌─────────────────────────────────────────────────────────────┐
│  drama-understanding-agent (已有,不动)                       │
│  输入: 视频 → 输出: report.json + action_plans/ + memory.db │
└──────────────────────────────┬──────────────────────────────┘
                               │ (产物作为输入)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  interaction-generator (新增模块)                            │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐       │
│  │ HighlightDet│  │ Interaction │  │  Expansion    │       │
│  │ ector       │──│ Orchestrator│──│  Generator    │       │
│  └─────────────┘  └─────────────┘  └───────────────┘       │
│        │                │                  │                │
│        ▼                ▼                  ▼                │
│  highlight_points  interaction_points  expansion.json       │
│                                                             │
│  输出: outputs/{drama_id}/ep_{N}.interactions.json          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 为什么不直接让 drama-understanding-agent 输出互动点?

三个原因:
1. **关注点分离**: 理解"剧情是什么"和"用户应该在哪里互动"是两个不同的问题
2. **可独立迭代**: 互动点策略频繁调整(组件增减、阈值调参),不应影响理解系统稳定性
3. **输入更丰富**: 互动点生成需要 ASR 时间戳 + 音频分析,这些不是理解系统的核心输入

---

## 三、InteractionGenerator 详细设计

### 3.1 模块结构

```
src/interaction_generator/
├── __init__.py
├── config.py                 ← 配置 (阈值、权重、组件映射)
├── pipeline.py               ← 主编排: drama_understanding → interaction_points
├── highlight_detector.py     ← 高光点检测 (三路融合)
├── interaction_orchestrator.py ← 高光点 → 互动点映射
├── expansion_generator.py    ← 集尾扩写 (预测题/角色心声/线索)
├── asr_analyzer.py           ← ASR 信号分析 (情绪词、对峙模式)
├── audio_analyzer.py         ← 音频信号分析 (能量突变、BGM)
├── quality_gate.py           ← 质量门控 (G1-G17)
└── manifest_writer.py        ← 输出 Manifest JSON
```

### 3.2 数据流

```
输入:
  ├── drama-understanding-agent/output/report.json     (角色/关系/事件/伏笔)
  ├── drama-understanding-agent/action_plans/ep{N}.json (每集action详情)
  ├── drama-understanding-agent/memory.db              (结构化记忆)
  ├── asr/ep{N}.json                                   (ASR时间戳)
  └── 视频文件 (用于音频分析)

处理流:
  1. 加载剧情理解数据 → 解析 plot_events (已有时间线)
  2. ASR 信号分析 → 产出 ASR 候选高光
  3. 音频信号分析 → 产出 Audio 候选高光
  4. 视觉信号 (直接从 plot_events 转化) → 产出 Visual 候选高光
  5. 三路融合 → 合并去重 → 产出 HighlightPoints
  6. 高光点 → 互动点 (InteractionPoint) 映射
  7. 集尾互动生成 (预测题/角色心声)
  8. 质量门控
  9. 写出 Manifest JSON

输出:
  outputs/{drama_id}/
    ├── ep_001.interactions.json
    ├── ep_002.interactions.json
    └── ...
```

### 3.3 核心转换逻辑: PlotEvent → HighlightPoint

这是最关键的桥接——把 drama-understanding-agent 的 plot_events 转化为前端需要的互动点。

#### 3.3.1 时间转换

当前 plot_events 的时间是 `"00:13"` 格式:

```python
def parse_time_to_ms(time_str: str) -> int:
    """将 'MM:SS' 或 'HH:MM:SS' 转为毫秒"""
    parts = time_str.split(":")
    if len(parts) == 2:
        return (int(parts[0]) * 60 + int(parts[1])) * 1000
    elif len(parts) == 3:
        return (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
    return 0
```

#### 3.3.2 事件类型 → 高光类型 → 组件映射

| drama-agent event_type | → highlight_type | → component | 前端效果 |
|------------------------|-----------------|-------------|---------|
| `conflict` | `face_slap` / `conflict` | `shatter_strike` / `camp_cheer` | 碎屏暴击 / 站队助威 |
| `climax` | `face_slap` | `shatter_strike` | 碎屏暴击 |
| `twist` | `reversal` | `plot_predict` | 剧情预测卡 |
| `reveal` | `reveal` | `plot_predict` | 剧情预测卡 |
| `setup` | `suspense` | `clue_judge` | 线索判断卡 |
| `resolution` | (视情绪定) | (视情绪定) | 按情绪分类 |

**仅靠 event_type 不够**——需要结合 emotion 做精细判断:

```python
def classify_highlight(event: dict, episode_mood: str, char_emotions: dict) -> str:
    """
    综合 event_type + 角色情绪 + 全集氛围 → 10类高光类型
    """
    event_type = event["event_type"]
    characters = event.get("characters", [])
    description = event.get("description", "")
    
    # 情绪关键词检测
    sweet_keywords = ["表白", "拥抱", "甜蜜", "亲", "牵手", "心动"]
    sad_keywords = ["哭", "离别", "死", "泪", "悲"]
    anger_keywords = ["欺负", "羞辱", "打", "怒", "嚣张", "欺压"]
    
    if any(kw in description for kw in sweet_keywords):
        return "sweet"
    if event_type == "climax" and any(kw in description for kw in anger_keywords):
        return "face_slap"
    if event_type == "twist":
        return "reversal"
    if event_type == "reveal":
        return "reveal"
    if event_type == "conflict":
        if any(kw in description for kw in anger_keywords):
            return "face_slap"
        return "conflict"
    if any(kw in description for kw in sad_keywords):
        return "sad"
    if event_type == "setup":
        return "suspense"
    
    return "conflict"  # 默认
```

#### 3.3.3 从 ASR 提取 key_line

```python
def extract_key_line(asr_segments: list, start_ms: int, end_ms: int) -> str:
    """从 ASR 中找到该时间窗内最具情绪冲击力的台词"""
    candidates = [
        seg for seg in asr_segments
        if seg["start_ms"] >= start_ms and seg["end_ms"] <= end_ms
    ]
    if not candidates:
        return ""
    # 选最短但有情绪词的句子，或选最后一句（通常是高潮句）
    # 后续可用 LLM 打分
    return candidates[-1]["text"]
```

### 3.4 三路信号融合增强

drama-understanding-agent 当前只用了视觉模型，但前端需要更密集的互动点。需要补充:

#### 3.4.1 ASR 信号分析器

```python
class ASRAnalyzer:
    """分析 ASR 文本产出候选高光点"""
    
    EMOTION_DICT = {
        "angry": ["你敢", "放肆", "该死", "竟然", "混账"],
        "satisfying": ["哈哈", "活该", "打得好", "痛快"],
        "sweet": ["喜欢你", "我爱", "永远"],
        "shocking": ["不可能", "怎么会", "你说什么"],
    }
    
    def analyze(self, asr_path: Path) -> list[CandidateHighlight]:
        """
        返回基于台词的候选高光:
        - 情绪词典命中
        - 对白密度突变 (快速对峙)
        - 关键短语模式 ("你……竟然……")
        """
```

#### 3.4.2 音频信号分析器

```python
class AudioAnalyzer:
    """分析视频音轨产出候选高光 (librosa, 无AI调用)"""
    
    def analyze(self, video_path: Path) -> list[CandidateHighlight]:
        """
        返回基于音频的候选高光:
        - 能量突变 (前后2秒标准差比>2)
        - 静默→音乐突起
        - BGM段变化点
        """
```

#### 3.4.3 融合权重

```python
FUSION_WEIGHTS = {
    "asr": 0.5,      # ASR信号权重最高 (短剧以对话推进剧情)
    "visual": 0.3,   # 视觉信号 (来自 drama-agent 的 plot_events)
    "audio": 0.2,    # 音频信号
}

CONFIDENCE_THRESHOLD = 0.65  # 综合置信度阈值
```

### 3.5 集尾互动生成

drama-understanding-agent 已有 `cliffhanger` 和 `plot_threads`，可以直接转化:

#### 3.5.1 预测题 (反向出题)

```python
def generate_predictions(
    current_episode: dict,    # 当前集摘要
    next_episode: dict,       # 下一集摘要 (已知)
    characters: list,         # 角色档案
    plot_threads: list,       # 未解伏笔
) -> list[Prediction]:
    """
    基于当前集的 cliffhanger + 下一集的事件,
    反向生成 3-5 个预测题
    
    LLM Prompt:
    - 当前集悬念: {cliffhanger}
    - 下一集实际发生: {next_episode.summary}
    - 要求: 生成3个二选一预测, 答案在下集揭晓
    """
```

#### 3.5.2 角色心声

```python
def generate_character_voice(
    character: dict,          # 角色档案 (来自 characters.json)
    episode_summary: str,     # 本集摘要
    character_state: dict,    # 本集角色状态 (emotion/goal)
) -> CharacterVoice:
    """
    基于角色在本集的状态, 生成第一人称心声独白
    100-250字, 符合角色人设
    """
```

#### 3.5.3 线索回顾

```python
def generate_clue_summary(
    plot_threads: list,       # 全部伏笔线
    current_episode: int,     # 当前集数
) -> list[ClueSummary]:
    """
    直接从 drama-agent 的 plot_threads 转化:
    - status=open 且 opened_at <= current_episode → "planted"
    - status=resolved → "recycled" 
    """
```

---

## 四、关键映射表

### 4.1 emotion 映射

| drama-agent 角色 emotion 关键词 | → 前端 emotion 类型 |
|-------------------------------|-------------------|
| 暴怒/震怒/愤怒 | `angry` |
| 错愕/震惊/惊恐 | `shocking` |
| 轻浮/享乐/嬉皮 | `satisfying` |
| 心动/甜蜜/温柔 | `sweet` |
| 压抑/悲伤/隐忍 | `sad` |
| 紧张/凝重/忧虑 | `tense` |
| 凌厉/强势/反转 | `satisfying` |
| 神秘/未知/暗藏 | `mysterious` |

### 4.2 component 映射表

| highlight_type | component | 组件效果 | 适用场景 |
|---------------|-----------|---------|---------|
| `face_slap` | `shatter_strike` | 碎屏暴击 | 反派被打脸/复仇/打脸 |
| `sweet` | `sugar_rain` | 满屏撒糖 | 表白/撒糖/甜蜜时刻 |
| `conflict` | `camp_cheer` | 站队助威 | 对峙/争吵/阵营对立 |
| `rescue` | `shield_guard` | 守护加持 | 救援/护人/挡刀 |
| `reversal` | `plot_predict` | 剧情预测卡 | 反转/真相大白 |
| `suspense` | `clue_judge` | 线索判断卡 | 悬念/伏笔/暗示 |
| `sad` | `emotion_buffer` | 情绪缓冲 | 哭泣/压抑 (MVP降级) |
| `reveal` | `plot_predict` | 剧情预测卡 | 身份揭露 |
| `cliffhanger` | `episode_end_predict` | 剧尾预测 | 集尾悬念 |
| `catchup_end` | `episode_end_expand` | 剧尾预测+扩写入口 | 最后一集结尾 |

### 4.3 score_type 映射

| 互动行为 | score_type | 说明 |
|---------|-----------|------|
| 碎屏暴击 | `resonance` | 情绪共鸣 |
| 站队助威 | `guard` | 守护角色 |
| 剧情预测 | `insight` | 洞察力 |
| 线索判断 | `insight` | 洞察力 |
| 角色心声 | `cocreate` | 共创 |
| 满屏撒糖 | `resonance` | 情绪共鸣 |

---

## 五、从 5 集实测数据推演

以 `test-5eps` (示例剧A) 的实际产出为例,推演转换效果:

### Ep01 转换示例

原始 plot_events:
```
event_1: setup,     "00:13"-"00:56", importance=0.9, "比武招亲告示..."
event_2: conflict,  "01:23"-"03:10", importance=0.85, "角色X当众撒钱..."  
event_3: climax,    "03:20"-"04:53", importance=0.9, "蛮人当街强抢..."
event_4: twist,     "04:47"-"05:09", importance=0.95, "暗处高手出手..."
```

转换为 interaction_points:
```json
[
  {
    "id": "ip_ep_001_0001",
    "start_ms": 83000,
    "end_ms": 190000,
    "component": "camp_cheer",
    "emotion": "angry",
    "intensity": 0.85,
    "confidence": 0.82,
    "highlight_reason": "角色X当众挥金如土嚣张跋扈，皇帝怒不可遏",
    "key_line": "全场所有人的消费，苏爷我全包了！"
  },
  {
    "id": "ip_ep_001_0002",
    "start_ms": 200000,
    "end_ms": 293000,
    "component": "shatter_strike",
    "emotion": "angry",
    "intensity": 0.9,
    "confidence": 0.88,
    "highlight_reason": "蛮人当街侮辱示例王朝皇室，观众适合点击宣泄",
    "key_line": "你们示例王朝皇帝见了我们，也要毕恭毕敬！"
  },
  {
    "id": "ip_ep_001_0003",
    "start_ms": 287000,
    "end_ms": 309000,
    "component": "plot_predict",
    "emotion": "shocking",
    "intensity": 0.95,
    "confidence": 0.92,
    "highlight_reason": "暗处高手隔空击倒蛮人，身份成谜，角色X露出异样神情",
    "key_line": ""
  }
]
```

### Ep05 集尾互动

基于 cliffhanger "角色X展露绝顶轻功，放话要么留下玉佩要么留下性命":

```json
{
  "episode_end_interaction": {
    "predictions": [
      {
        "prediction_id": "pred_ep05_001",
        "question": "角色X和黑衣侍卫的对决结果会如何？",
        "options": [
          {"option_key": "A", "label": "角色X轻松取胜，彻底碾压"},
          {"option_key": "B", "label": "势均力敌，双方互相试探后停手"}
        ],
        "answer_key": "B",
        "reveal_episode_id": "ep_006",
        "reveal_ms": 45000,
        "hint": "示例王朝第一高手可不是浪得虚名..."
      }
    ],
    "character_voices": [
      {
        "voice_id": "cv_ep05_suyu",
        "character_id": "char-69a6...",
        "voice_text": "十五年了。十五年来我把自己活成一个所有人唾弃的废物，喝花酒、欠赌债、被全城耻笑。可今晚，当这个黑衣人偷走娘亲留给我唯一的东西，我连一秒都忍不下去了。我不在乎暴露——谁碰我的玉佩，我就碰他的命。",
        "emotion": "cold_fury"
      }
    ],
    "clue_summary_enabled": true
  }
}
```

---

## 六、实施计划

### Phase 1: 基础转换器 (最小可用)

**目标**: 把 drama-understanding-agent 的 plot_events 直接转为 interaction_points

```
新增文件:
  src/interaction_generator/
    ├── pipeline.py            ← 主入口
    ├── event_to_highlight.py  ← plot_event → HighlightPoint 转换
    ├── highlight_to_ip.py     ← HighlightPoint → InteractionPoint 映射
    ├── manifest_writer.py     ← 输出标准 Manifest JSON
    └── config.py              ← 映射表+阈值
```

**输入**: `projects/{id}/output/report.json` + `action_plans/ep{N}.json`
**输出**: `outputs/{drama_id}/ep_{N}.interactions.json`

这个阶段只用 visual 信号 (plot_events),不做 ASR/Audio 融合。

### Phase 2: ASR 信号增强

**目标**: 利用 ASR 时间戳提取 key_line + 情绪词候选高光

```
新增:
  src/interaction_generator/
    └── asr_analyzer.py
```

**输入**: 额外读取 `asr/ep{N}.json`
**效果**: 互动点数量从 3-5 个/集增加到 5-8 个/集,每个点都有 key_line

### Phase 3: 集尾扩写

**目标**: 生成预测题 + 角色心声 + 线索回顾

```
新增:
  src/interaction_generator/
    └── expansion_generator.py
```

**输入**: report.json 中的 characters + plot_threads + episode_summaries
**输出**: 每集增加 `episode_end_interaction` 字段

### Phase 4: 音频分析 + 质量门控

**目标**: 补全音频信号路径 + 全部 17 条门控规则

```
新增:
  src/interaction_generator/
    ├── audio_analyzer.py
    └── quality_gate.py
```

### Phase 5: 全管线集成

把 drama-understanding-agent + interaction-generator 串联为一条完整管线:

```bash
# 一条命令完成全流程
drama-agent run --title "示例剧A" --video-dir ./videos --episodes 24
drama-agent generate-interactions --project test-5eps --output ./outputs
```

---

## 七、对 drama-understanding-agent 的小幅改进建议

为了更好地服务下游互动点生成,建议在 drama-agent 的 Prompt 中增加以下输出字段:

### 7.1 plot_event 增加 emotion 和 key_line

在 `model/prompts.py` 的 action schema 中, `append_plot_event` 增加:

```json
{
  "action": "append_plot_event",
  "start_time": "01:23",
  "end_time": "03:10",
  "event_type": "conflict",
  "description": "...",
  "characters": ["角色X", "君主B"],
  "importance": 0.85,
  "emotion": "angry",              // 新增: 该事件的主要情绪
  "key_line": "全场消费苏爷包了!", // 新增: 代表性台词 (从ASR中选)
  "interaction_hint": "face_slap"  // 新增: 建议的互动类型
}
```

这样模型在理解视频时就能直接输出互动提示,减少后处理的推测工作。

### 7.2 时间精度从分:秒升级为毫秒

当前 start_time = "01:23" (分秒字符串),建议改为:
```json
"start_ms": 83000,
"end_ms": 190000
```

但这需要模型输出更精确的时间——短期内可以在后处理中用 ASR 对齐精修。

---

## 八、交付标准

Phase 1 完成后,对 `test-5eps` 项目运行 interaction generator,预期产出:

```
outputs/示例剧A/
├── ep_001.interactions.json   (3-5 个互动点)
├── ep_002.interactions.json   (3-5 个互动点)
├── ep_003.interactions.json   (3-5 个互动点)
├── ep_004.interactions.json   (3-5 个互动点)
└── ep_005.interactions.json   (3-5 个互动点)
```

每个文件符合 `OFFLINE_VIDEO_UNDERSTANDING_OUTPUT_SPEC.md` 定义的 schema,可以直接被后端入库、被前端消费。

---

## 九、AI Coding 指令模板

```
请按照 docs/08-interaction-generator.md 中的 Phase 1 进行实施。

具体任务:
1. 在 drama-understanding-agent 项目中新建 src/interaction_generator/ 目录
2. 实现 pipeline.py — 主入口,读取 report.json 和 action_plans
3. 实现 event_to_highlight.py — 将 plot_events 转为 HighlightPoints (含时间转换+类型映射+情绪分类)
4. 实现 highlight_to_ip.py — 将 HighlightPoints 转为 InteractionPoints (含组件映射+config填充)
5. 实现 manifest_writer.py — 输出标准 JSON
6. 实现 config.py — 所有映射表和阈值常量
7. 在 CLI 中新增 generate-interactions 命令

用 test-5eps 项目的数据测试,确保输出符合 OFFLINE_VIDEO_UNDERSTANDING_OUTPUT_SPEC.md 格式。
新增测试: test_event_to_highlight.py, test_manifest_output.py
```
