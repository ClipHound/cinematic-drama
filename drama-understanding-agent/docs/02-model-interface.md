# 02 - 模型接口层设计

> 封装 Doubao-Seed-2.0-lite 的全模态理解能力。系统中唯一与 LLM API 通信的模块。

---

## 2.1 模型能力边界

| 能力 | 支持情况 | 使用方式 |
|------|---------|---------|
| 视频原生理解 | ✅ | 整集视频直传（2-3分钟 MP4） |
| 音频理解 | ✅ | 视频中内含音轨，模型自动处理 |
| 图像理解 | ✅ | 截帧后可单独分析 |
| 长文本输出 | ✅ | max_tokens 设为 8192 |
| 结构化输出 | ✅ | 通过 Prompt 约束输出 JSON |
| 推理能力 | ✅ | reasoning_tokens 表明有 CoT |

**模型参数**:
- 端点: `https://ark.cn-beijing.volces.com/api/v3/chat/completions`
- 模型: `doubao-seed-2-0-lite-260428` (或对应的 endpoint ID)
- 协议: OpenAI-compatible

---

## 2.2 API 请求格式

### 视频理解请求

```python
{
    "model": "doubao-seed-2-0-lite-260428",
    "messages": [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "video_url",
                    "video_url": {
                        "url": "data:video/mp4;base64,{base64_encoded_video}"
                    }
                },
                {
                    "type": "text",
                    "text": EPISODE_PROMPT
                }
            ]
        }
    ],
    "temperature": 0.3,
    "max_tokens": 8192
}
```

> **注**: 如果 base64 编码导致请求过大，需确认火山方舟是否支持 file_id 方式。
> 从实验数据看，5 分钟视频（prompt_tokens=47069, audio_tokens=1930）已成功调用，
> 说明 2-3 分钟视频在 API 限制内。

### 备选：file_id 方式（如 base64 超限）

```python
{
    "type": "video_url",
    "video_url": {
        "url": "tos://{bucket}/{file_id}"  # 火山方舟 TOS 存储
    }
}
```

---

## 2.3 Prompt 设计

### System Prompt (固定)

```
你是一个专业的短剧剧情分析 Agent。你正在逐集观看一部短剧，并持续构建结构化剧情记忆。

你的任务是：
1. 观看当前集的视频内容
2. 结合已有的角色档案和剧情记忆，分析本集内容
3. 输出一个 Action Plan（JSON格式），告诉系统需要执行哪些操作

你必须严格按照指定的 JSON Schema 输出 Action Plan。不要输出任何其他内容。
```

### Episode Prompt 模板

```
## 当前状态

当前正在观看: 第 {episode_num} 集 / 共 {total_episodes} 集
剧名: {drama_title}

## 已知信息

### 已有角色 ({character_count} 个)
{character_summaries}

### 未解决伏笔 ({thread_count} 条)
{open_threads}

### 上集摘要
{previous_summary}

### 本集 ASR 文本 (辅助参考)
{asr_text}

## 任务

请观看本集视频，输出以下 Action Plan (JSON格式):

```json
{
  "episode_summary": "本集剧情摘要（150-300字）",
  "mood": "本集整体情绪基调",
  "cliffhanger": "本集结尾悬念/hook（如果有）",
  
  "actions": [
    // 按需输出以下类型的 action，只输出有变化的部分
    // 具体 schema 见下方
  ]
}
```

### Action 类型与 Schema:

1. **upsert_character** - 新增或更新角色
```json
{
  "action": "upsert_character",
  "name": "角色名",
  "match_existing": "已有角色名（如果认为是同一人）或 null",
  "match_confidence": 0.95,
  "description": "完整角色描述",
  "aliases": ["别名1", "别名2"],
  "emotion": "本集情绪状态",
  "goal": "本集目标/动机",
  "identity_change": "身份变化（如果有）",
  "appearance": "外貌/穿着"
}
```

2. **update_relationship** - 更新人物关系
```json
{
  "action": "update_relationship",
  "character_a": "角色A名",
  "character_b": "角色B名",
  "relation": "关系描述",
  "direction": "a_to_b | b_to_a | bidirectional",
  "is_new": true
}
```

3. **append_plot_event** - 添加关键剧情事件
```json
{
  "action": "append_plot_event",
  "start_time": "MM:SS",
  "end_time": "MM:SS",
  "event_type": "setup|conflict|climax|resolution|reveal|twist",
  "description": "事件描述",
  "characters": ["角色名1", "角色名2"],
  "importance": 0.8
}
```

4. **update_plot_thread** - 更新/新建伏笔线索
```json
{
  "action": "update_plot_thread",
  "title": "伏笔标题",
  "description": "详细描述",
  "thread_type": "foreshadow|mystery|subplot|mainplot",
  "status": "open|resolved",
  "resolution": "解决方式（如果resolved）",
  "characters": ["相关角色"]
}
```

5. **capture_frame** - 请求截取关键帧
```json
{
  "action": "capture_frame",
  "timestamp": "MM:SS",
  "purpose": "character_anchor|evidence|key_scene",
  "target": "关联的角色名或证据描述",
  "description": "这帧展示了什么"
}
```

6. **update_series_state** - 更新全局剧情状态
```json
{
  "action": "update_series_state",
  "field": "main_plot_summary|genre|setting|tone",
  "value": "更新值"
}
```

7. **mark_uncertain** - 标记不确定项
```json
{
  "action": "mark_uncertain",
  "category": "identity|contradiction|timeline",
  "description": "不确定的内容描述",
  "related_characters": ["相关角色"]
}
```

注意事项:
- 只输出有变化的内容，不要重复已知信息
- 角色名保持一致，如果是已有角色请用 match_existing 指明
- 时间戳使用 MM:SS 格式
- importance 在 0-1 之间
- 如果发现前几集的信息有误，使用 mark_uncertain 标记
```

---

## 2.4 客户端封装

```python
class DoubaoClient:
    """Doubao Seed 2.0 Lite API 客户端"""
    
    def __init__(self, endpoint: str, token: str, model: str):
        self.endpoint = endpoint
        self.token = token
        self.model = model
        self.timeout = 180.0  # 视频理解需要较长超时
    
    def understand_episode(
        self,
        video_path: Path,
        episode_prompt: str,
        system_prompt: str,
    ) -> dict:
        """
        发送视频+prompt，返回解析后的 Action Plan。
        
        Returns:
            解析后的 Action Plan dict，或包含 _error 的 dict
        """
        ...
    
    def analyze_frame(
        self,
        image_path: Path,
        prompt: str,
    ) -> str:
        """图像分析（用于精细角色识别等辅助场景）"""
        ...
```

---

## 2.5 容错策略

| 错误场景 | 处理方式 |
|---------|---------|
| API 超时 (>180s) | 重试 1 次，超时加倍到 360s |
| HTTP 429 (限流) | 等待 60s 后重试，最多 3 次 |
| HTTP 5xx | 等待 30s 后重试，最多 2 次 |
| JSON 解析失败 | json_repair 尝试修复；失败则用正则提取 |
| 输出截断 | 检测 JSON 是否完整，不完整则补充调用 |
| 空响应 | 记录错误，跳过本集标记 failed |
| Token 超限 | 压缩 prompt（减少角色数、缩短摘要） |

---

## 2.6 Token 估算

| 组件 | 估算 tokens |
|------|------------|
| 视频 (2-3分钟) | ~40,000-50,000 |
| System prompt | ~500 |
| Episode prompt (含上下文) | ~2,000-5,000 |
| 输出 (Action Plan) | ~2,000-4,000 |
| **单集总计** | **~45,000-60,000** |
| **60集总计** | **~3,000,000-3,600,000** |

按火山方舟定价估算，整部剧的理解成本在可接受范围内。
