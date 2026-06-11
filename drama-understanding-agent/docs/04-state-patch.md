# 04 - State Patch 机制

> State Patch 是模型输出与持久化记忆之间的缓冲层。任何记忆变更必须经过 Patch 机制，保证数据质量和可追溯性。

---

## 4.1 核心原则

1. **模型永远不直接写入长期记忆** - 所有写操作先生成 Patch
2. **Patch 是原子性的** - 一个 episode 的所有 patch 要么全部提交，要么全部回滚
3. **Patch 有置信度** - 高置信自动提交，低置信标记
4. **Patch 可审计** - 所有历史 patch 持久化，支持回溯
5. **Patch 支持回滚** - 基于 snapshot 机制回滚到任意集后的状态

---

## 4.2 Patch 数据结构

```python
@dataclass
class StatePatch:
    """单个状态变更"""
    id: str                        # UUID
    episode_num: int               # 产生此 patch 的集号
    table: str                     # 目标表名
    operation: str                 # insert / update / delete
    record_id: str                 # 目标记录 ID
    field_changes: dict            # {field: new_value} 或完整记录(insert)
    confidence: float              # 0-1 置信度
    reason: str                    # 产生原因描述
    source_action: str             # 来源 action 类型
    conflicts: list[str]           # 与已有数据的冲突描述
```

---

## 4.3 置信度规则

| 操作类型 | 默认置信度 | 可能降低的情况 |
|---------|-----------|--------------|
| 新增角色 (首次出现) | 0.95 | — |
| 角色合并 (match_existing) | model 给出的 confidence | embedding 相似度 < 0.85 时降为 0.5 |
| 新增事件 | 0.9 | — |
| 更新伏笔状态 | 0.9 | 从 open → resolved 时如无明确证据降为 0.7 |
| 更新关系 | 0.85 | 与已有关系冲突时降为 0.6 |
| 全局状态变更 | 0.85 | — |
| mark_uncertain | 标记本身不需要置信度 | — |

---

## 4.4 提交策略 (full_auto 模式)

```python
class PatchCommitter:
    """State Patch 提交器"""
    
    CONFIDENCE_THRESHOLD = 0.7  # 高于此值自动提交
    
    def commit_episode_patches(self, patches: list[StatePatch]) -> CommitResult:
        """
        full_auto 模式提交流程:
        
        1. 按 table 分组 patches
        2. 冲突检测:
           a. 同一 record_id 的多次更新 → 取最后一次
           b. 新角色与已有角色名完全相同 → 自动合并
           c. 关系更新与已有关系冲突 → 标记但仍提交新的
        3. 置信度过滤:
           a. confidence >= THRESHOLD → 直接提交
           b. confidence < THRESHOLD → 提交但标记 flagged
        4. 事务性写入 SQLite
        5. 同步更新 Qdrant 向量
        6. 记录 patch 历史
        """
    
    def rollback_episode(self, episode_num: int):
        """
        回滚某集的所有变更:
        1. 从 snapshots/ 恢复上一集结束时的 DB
        2. 删除该集之后的所有 Qdrant 记录
        3. 标记该集 patches 为 rolled_back
        """
```

---

## 4.5 冲突检测

```python
class ConflictDetector:
    """检测 patch 与已有数据的冲突"""
    
    def detect(self, patch: StatePatch, memory: MemoryStore) -> list[Conflict]:
        """
        冲突类型:
        1. DUPLICATE_CHARACTER: 新角色与已有角色 embedding 相似度 > 0.9
        2. RELATIONSHIP_CONTRADICTION: 新关系与已有关系语义矛盾
        3. TIMELINE_VIOLATION: 事件时间线不合理
        4. CHARACTER_STATE_JUMP: 角色状态跳变过大(如突然从活着变为死亡没有过渡)
        5. THREAD_RESOLUTION_WITHOUT_EVIDENCE: 伏笔被标记为resolved但缺少充分描述
        """
```

冲突不阻止提交（在 full_auto 模式下），但会：
- 降低 patch confidence
- 在 operation_logs 中记录冲突
- 在最终报告中高亮

---

## 4.6 快照机制

```python
def create_snapshot(project_path: Path, episode_num: int):
    """
    每集处理完成后创建快照:
    1. 复制 memory.db → snapshots/after_ep{num:02d}.db
    2. 记录 Qdrant 中的最大 point_id
    3. 快照文件名: after_ep{episode_num:02d}.db
    
    快照用途:
    - 回滚到任意集后的状态
    - 对比两集之间的变化
    - 调试时从中间某集重新开始
    """

def restore_snapshot(project_path: Path, episode_num: int):
    """
    恢复到指定集后的状态:
    1. 删除当前 memory.db
    2. 复制 snapshots/after_ep{num:02d}.db → memory.db
    3. 在 Qdrant 中删除 episode_num 之后的所有 points
    4. 更新 series_state.current_episode
    """
```

---

## 4.7 Patch 日志格式

每集处理完后，patch 历史写入 `logs/patches/ep{num:02d}.json`:

```json
{
  "episode_num": 3,
  "processed_at": "2026-06-05T14:30:00",
  "model_response_tokens": 3500,
  "patches": [
    {
      "id": "patch-uuid-1",
      "table": "characters",
      "operation": "update",
      "record_id": "char-uuid-suyu",
      "field_changes": {
        "description": "镇北侯二公子，表面纨绔实则深藏不露的绝顶高手...(更新后)",
        "last_seen": 3
      },
      "confidence": 0.95,
      "reason": "角色在第3集中展现新能力",
      "conflicts": [],
      "status": "committed"
    },
    {
      "id": "patch-uuid-2",
      "table": "relationships",
      "operation": "insert",
      "record_id": "rel-uuid-new",
      "field_changes": {
        "character_a": "char-uuid-suyu",
        "character_b": "char-uuid-princess",
        "relation": "比武招亲的潜在对象",
        "direction": "bidirectional"
      },
      "confidence": 0.7,
      "reason": "模型推测，尚未明确",
      "conflicts": ["可能与皇帝不知道角色A实力的设定冲突"],
      "status": "committed_flagged"
    }
  ]
}
```

---

## 4.8 与 HITL 模式的接口预留

虽然 MVP 只做 full_auto，但设计上预留 HITL 接口:

```python
class PatchReviewer(Protocol):
    """审核器接口 (未来实现)"""
    
    def review(self, patches: list[StatePatch]) -> list[PatchDecision]:
        """
        返回每个 patch 的审核决定:
        - approve: 直接提交
        - reject: 丢弃
        - modify: 修改后提交
        """
        ...

class AutoReviewer:
    """full_auto 模式: 全部自动通过"""
    def review(self, patches):
        return [PatchDecision(patch.id, "approve") for patch in patches]

# 未来:
# class CLIReviewer: ...
# class WebReviewer: ...
```
