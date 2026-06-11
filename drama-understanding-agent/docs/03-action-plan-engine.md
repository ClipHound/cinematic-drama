# 03 - Action Plan 引擎设计

> Action Plan 是模型与系统之间的通信协议。模型输出意图（"做什么"），引擎负责将意图转化为系统操作（"怎么做"）。

---

## 3.1 设计哲学

```
模型职责: 理解视频 → 判断变化 → 规划操作 → 输出 Action Plan
引擎职责: 解析 Plan → 校验合法性 → 执行工具 → 收集 State Patches
```

模型不直接操作数据库，不直接访问文件系统。它只输出一份声明式的操作清单。

---

## 3.2 Action Plan JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["episode_summary", "actions"],
  "properties": {
    "episode_summary": {
      "type": "string",
      "description": "本集剧情摘要，150-300字"
    },
    "mood": {
      "type": "string",
      "description": "本集整体情绪基调"
    },
    "cliffhanger": {
      "type": "string",
      "description": "本集结尾悬念"
    },
    "actions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["action"],
        "properties": {
          "action": {
            "type": "string",
            "enum": [
              "upsert_character",
              "update_relationship",
              "append_plot_event",
              "update_plot_thread",
              "capture_frame",
              "update_series_state",
              "mark_uncertain"
            ]
          }
        }
      }
    }
  }
}
```

---

## 3.3 Action 类型完整清单

### A. 资产类

| Action | 输入 | 产出 | 说明 |
|--------|------|------|------|
| `capture_frame` | timestamp, purpose, target, description | 截图文件 + DB记录 | 从视频中截取指定时间的帧 |

### B. 记忆更新类

| Action | 输入 | 产出 | 说明 |
|--------|------|------|------|
| `upsert_character` | name, description, aliases, emotion, goal... | State Patch | 新增或更新角色 |
| `update_relationship` | character_a, character_b, relation... | State Patch | 更新人物关系 |
| `append_plot_event` | start_time, end_time, event_type, description... | State Patch | 添加剧情事件 |
| `update_plot_thread` | title, description, status... | State Patch | 更新伏笔线索 |
| `update_series_state` | field, value | State Patch | 更新全局状态 |

### C. 标记类

| Action | 输入 | 产出 | 说明 |
|--------|------|------|------|
| `mark_uncertain` | category, description, related_characters | 标记记录 | 标记不确定/可能冲突的信息 |

---

## 3.4 引擎执行流程

```python
class ActionPlanEngine:
    """解析并执行模型输出的 Action Plan"""
    
    def execute(self, plan: dict, ctx: EpisodeContext) -> ExecutionResult:
        """
        执行流程:
        1. 校验 plan 结构合法性
        2. 提取 episode_summary → 直接写入 episode_summaries
        3. 遍历 actions 列表:
           a. 对每个 action 调用对应的 tool
           b. 收集 state patches
           c. 记录执行日志
        4. 批量提交 state patches
        5. 返回执行结果
        """
        
    def _resolve_character(self, name: str, match_existing: str | None, confidence: float) -> str:
        """
        角色解析逻辑:
        1. 如果 match_existing 不为 null:
           a. 在已有角色中查找 name == match_existing
           b. 计算 embedding 相似度作为二次验证
           c. 如果相似度 > 0.85 且 confidence > 0.8: 合并
           d. 否则: 创建新角色，标记 mark_uncertain
        2. 如果 match_existing 为 null:
           a. 在已有角色中搜索 embedding 相似度
           b. 如果 top1 相似度 > 0.9: 提示可能是同一人，标记
           c. 否则: 创建新角色
        """
```

---

## 3.5 Action 执行器映射

```python
ACTION_HANDLERS = {
    "upsert_character":    handle_upsert_character,
    "update_relationship": handle_update_relationship,
    "append_plot_event":   handle_append_plot_event,
    "update_plot_thread":  handle_update_plot_thread,
    "capture_frame":       handle_capture_frame,
    "update_series_state": handle_update_series_state,
    "mark_uncertain":      handle_mark_uncertain,
}
```

每个 handler 签名:

```python
def handle_xxx(action: dict, ctx: EpisodeContext, memory: MemoryStore) -> list[StatePatch]:
    """
    Args:
        action: 单个 action dict (来自模型输出)
        ctx: 当前集上下文 (episode_num, video_path, ...)
        memory: 记忆存储实例 (用于读取已有数据做比对)
    
    Returns:
        产生的 State Patch 列表
    """
```

---

## 3.6 JSON 容错解析

模型输出不保证 100% 合法 JSON。引擎需要处理:

```python
def parse_action_plan(raw_text: str) -> dict:
    """
    解析策略 (按优先级):
    1. 直接 json.loads
    2. 去除 markdown code fence (```json ... ```)
    3. json_repair 库修复常见错误
    4. 正则提取 {...} 最外层 JSON
    5. 逐字段正则提取 (最后手段)
    
    任何一步成功即返回。全部失败则返回 {"_error": "parse_failed", "raw": raw_text}
    """
```

---

## 3.7 执行结果

```python
@dataclass
class ExecutionResult:
    episode_num: int
    summary: str                    # 本集摘要
    actions_total: int              # 总 action 数
    actions_succeeded: int          # 成功执行数
    actions_failed: int             # 失败数
    patches_generated: int          # 生成的 patch 数
    patches_committed: int          # 已提交的 patch 数
    patches_flagged: int            # 被标记需审核的 patch 数
    uncertainties: list[dict]       # 不确定标记列表
    errors: list[str]               # 错误信息
    duration_sec: float             # 执行耗时
```
