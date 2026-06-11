# Drama Understanding Agent — V2 迭代计划

> 版本: v2.0
> 日期: 2026-06-05
> 状态: 设计完成，待实施
> 前置: V1 全部 14 测试通过，2 集端到端跑通

---

## 1. V1 当前状态总结

### 1.1 已完成且正常工作

| 模块 | 状态 | 说明 |
|------|------|------|
| Project 隔离 | ✅ | 每部剧独立目录、DB、快照 |
| SQLite 结构化记忆 | ✅ | 10 张表，CRUD 完整 |
| Doubao API 封装 | ✅ | base64 直传 + file upload 双路径 |
| Action Plan 解析 | ✅ | JSON 容错（3种候选 + json_repair） |
| 逐集处理循环 | ✅ | 断点续跑、3连败熔断 |
| CLI 入口 | ✅ | run/status/export 三命令 |
| 帧截取工具 | ✅ | ffmpeg 截帧 + 重试 |
| 测试 | ✅ | 14 测试全部通过 (0.88s) |
| 实际运行 | ✅ | 2 集完整跑通，产出高质量数据 |

### 1.2 从实际数据观察到的问题

从 `sample-two-episodes-envtest` 的产出数据中，确认了以下真实问题：

| 问题 | 严重性 | 实测表现 |
|------|--------|---------|
| **plot_threads 重复 INSERT** | 🔴 P0 | "示例王朝比武招亲危机" 出现了 2 条记录（ep01 + ep02 各 INSERT 一次） |
| **relationships 重复 INSERT** | 🔴 P0 | 君主B-禁军统领 关系出现了 2 条记录 |
| **Patch 无事务保护** | 🔴 P0 | 代码层确认，每个 patch 独立 connection |
| **_resolve_character_id 绕过 Patch** | 🟡 P1 | "蛮人"和"普通百姓" 以 confidence=0.6、空 description 直写入 DB |
| **VectorStore 从未被使用** | 🟡 P1 | 注入了但所有方法都是死代码 |
| **report.md 内容空洞** | 🟡 P1 | 只有数字统计，无叙事内容 |
| **君主B last_seen 未更新到 ep02** | 🟡 P1 | ep02 引用了但角色的 last_seen 仍为 1 |
| **Qdrant point_id 格式不兼容** | 🟡 P1 | `"char-xxx"` 非合法 Qdrant ID |

### 1.3 V1 实际产出质量评价

**优点**：
- 角色跨集识别正确：禁军统领在 ep02 正确 match 到 ep01 的记录
- 剧情事件粒度合理：7 个事件覆盖两集，时间戳准确
- 模型输出质量极高：summary、mood、cliffhanger 都是高质量中文叙事
- Action Plan 结构完整：ep01 产出 15 个 action，ep02 产出 10 个

**问题**：
- 伏笔/关系去重是唯一影响数据正确性的 bug
- 部分角色（配角/群众）被 `_resolve_character_id` 静默创建

---

## 2. V2 迭代目标

### 核心主题：**数据正确性 + 向量检索激活 + 产出丰富化**

V2 不新增功能，专注于：
1. 修复 V1 的所有数据完整性 bug
2. 激活 VectorStore 使角色匹配更智能
3. 丰富最终产出报告，使其对人和下游系统有用

---

## 3. 变更清单

### 3.1 P0 修复：关系和伏笔去重

**文件**: `src/drama_agent/tools/memory_tools.py`

**问题**: `handle_update_relationship` 和 `handle_update_plot_thread` 每次都创建新 UUID、INSERT 新行，从不查重。

**修复方案**:

```python
# handle_update_relationship 修复逻辑
def handle_update_relationship(action, ctx, memory):
    char_a_id = _resolve_character_id(action.get("character_a", ""), ctx, memory)
    char_b_id = _resolve_character_id(action.get("character_b", ""), ctx, memory)
    
    # 查重：按角色对查找已有关系
    existing = memory.find_relationship(char_a_id, char_b_id)
    
    if existing:
        # UPDATE 已有关系
        updated_data = {
            "relation": action.get("relation", existing.relation),
            "direction": action.get("direction", existing.direction),
            "updated_at": utc_now(),
        }
        return [StatePatch(
            table="relationships",
            operation="update",
            record_id=existing.id,
            field_changes=updated_data,
            ...
        )]
    else:
        # INSERT 新关系
        relationship = Relationship(...)
        return [StatePatch(operation="insert", ...)]
```

```python
# handle_update_plot_thread 修复逻辑
def handle_update_plot_thread(action, ctx, memory):
    title = action.get("title", "")
    
    # 查重：按标题模糊匹配
    existing = memory.find_plot_thread_by_title(title)
    
    if existing:
        # UPDATE: 更新描述、状态、角色
        updated_data = {
            "description": action.get("description", existing.description),
            "status": action.get("status", existing.status),
            "resolution": action.get("resolution", "") or existing.resolution,
            "resolved_at": ctx.episode_num if action.get("status") == "resolved" else existing.resolved_at,
            "characters": ...,  # 合并新旧角色列表
            "updated_at": utc_now(),
        }
        return [StatePatch(operation="update", record_id=existing.id, ...)]
    else:
        # INSERT 新伏笔
        thread = PlotThread(opened_at=ctx.episode_num, ...)
        return [StatePatch(operation="insert", ...)]
```

**需要在 MemoryStore 中新增的方法**:

```python
def find_relationship(self, char_a_id: str, char_b_id: str) -> Relationship | None:
    """查找两个角色之间的已有关系（双向查找）"""
    row = self._fetchone(
        """SELECT * FROM relationships
           WHERE (character_a = ? AND character_b = ?)
              OR (character_a = ? AND character_b = ?)""",
        (char_a_id, char_b_id, char_b_id, char_a_id),
    )
    return self._row_to_model(row, Relationship, "relationships") if row else None

def find_plot_thread_by_title(self, title: str) -> PlotThread | None:
    """按标题查找已有伏笔线索"""
    row = self._fetchone(
        "SELECT * FROM plot_threads WHERE title = ? AND status != 'abandoned'",
        (title,),
    )
    return self._row_to_model(row, PlotThread, "plot_threads") if row else None
```

---

### 3.2 P0 修复：Patch 事务安全

**文件**: `src/drama_agent/engine/state_patch.py` + `src/drama_agent/memory/store.py`

**问题**: 每个 patch 独立打开 connection，中间失败无回滚。

**修复方案**:

在 MemoryStore 中新增事务上下文管理器：

```python
# store.py 新增
from contextlib import contextmanager

class MemoryStore:
    @contextmanager
    def transaction(self):
        """提供事务上下文，失败自动回滚"""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def apply_insert_tx(self, conn, table: str, data: dict) -> None:
        """在给定 connection 上执行 INSERT (事务内使用)"""
        self._validate_table(table)
        encoded = self._encode_json_fields(table, data)
        fields = list(encoded)
        placeholders = ", ".join(f":{f}" for f in fields)
        conn.execute(
            f"INSERT OR REPLACE INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
            encoded,
        )

    def apply_update_tx(self, conn, table: str, record_id: str, changes: dict) -> None:
        """在给定 connection 上执行 UPDATE (事务内使用)"""
        self._validate_table(table)
        encoded = self._encode_json_fields(table, changes)
        set_clause = ", ".join(f"{k} = :{k}" for k in encoded)
        encoded["_id"] = record_id
        conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = :_id", encoded)

    def apply_delete_tx(self, conn, table: str, record_id: str) -> None:
        self._validate_table(table)
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))

    ALLOWED_TABLES = {
        "characters", "character_states", "relationships",
        "plot_events", "plot_threads", "episode_summaries",
        "series_state", "character_assets", "evidence_assets",
        "state_patches", "operation_logs",
    }

    def _validate_table(self, table: str) -> None:
        if table not in self.ALLOWED_TABLES:
            raise ValueError(f"Invalid table name: {table}")
```

PatchCommitter 改用事务：

```python
# state_patch.py 修改
def commit_episode_patches(self, patches: list[StatePatch]) -> CommitResult:
    if not patches:
        return CommitResult(episode_num=0)
    episode_num = patches[0].episode_num
    result = CommitResult(episode_num=episode_num, patches_total=len(patches))

    deduped = OrderedDict()
    for patch in patches:
        deduped[(patch.table, patch.record_id)] = patch

    with self.memory.transaction() as conn:
        for patch in deduped.values():
            status = "committed"
            if patch.confidence < self.CONFIDENCE_THRESHOLD or patch.conflicts:
                status = "committed_flagged"
                result.patches_flagged += 1
            try:
                self._apply_patch_tx(conn, patch)
                self._record_patch_tx(conn, patch, status)
                result.patches_committed += 1
            except Exception as exc:
                result.errors.append(f"{patch.id}: {exc}")
                raise  # 触发事务回滚

    self._write_patch_log(episode_num, patches)
    return result

def _apply_patch_tx(self, conn, patch: StatePatch) -> None:
    if patch.operation == "insert":
        self.memory.apply_insert_tx(conn, patch.table, patch.field_changes)
    elif patch.operation == "update":
        self.memory.apply_update_tx(conn, patch.table, patch.record_id, patch.field_changes)
    elif patch.operation == "delete":
        self.memory.apply_delete_tx(conn, patch.table, patch.record_id)
```

这同时解决了 **SQL table 名白名单** 问题（`_validate_table`）。

---

### 3.3 P1 修复：_resolve_character_id 不再绕过 Patch

**文件**: `src/drama_agent/tools/memory_tools.py`

**问题**: 当一个 action 引用了未知角色名（如 plot_event.characters 里的"围观百姓"），`_resolve_character_id` 直接写入 DB。

**修复方案**: 改为返回额外的 StatePatch 而不是直写 DB。

```python
# 修改 _resolve_character_id 签名，增加 pending_patches 参数
def _resolve_character_id(
    name: str,
    ctx: EpisodeContext,
    memory: MemoryStore,
    pending_patches: list[StatePatch],  # 新增: 收集未知角色的 patch
) -> str:
    if not name:
        return ""
    if name in ctx.character_name_map:
        return ctx.character_name_map[name]
    
    existing = _find_character(memory, name)
    if existing:
        ctx.character_name_map[name] = existing.id
        return existing.id
    
    # 创建新角色但通过 Patch 系统
    character = Character(
        name=name or "unknown",
        first_seen=ctx.episode_num,
        last_seen=ctx.episode_num,
        confidence=0.6,
        description="",  # 模型未详细描述的配角/群众
    )
    ctx.character_name_map[name] = character.id
    
    pending_patches.append(StatePatch(
        episode_num=ctx.episode_num,
        table="characters",
        operation="insert",
        record_id=character.id,
        field_changes=character.model_dump(),
        confidence=0.6,
        reason=f"Auto-created from reference in action (name='{name}')",
        source_action="auto_resolve",
    ))
    return character.id
```

所有调用 `_resolve_character_id` 的 handler 需要传入 `pending_patches` 列表，最终将这些 patch 追加到 handler 返回值中。

---

### 3.4 P1 修复：激活 VectorStore

**文件**: `src/drama_agent/engine/state_patch.py` + `src/drama_agent/memory/vectors.py` + `src/drama_agent/engine/episode_loop.py`

**问题**:
1. VectorStore 在 EpisodeLoop 中默认为 None
2. PatchCommitter 注入了 vectors 但从不调用
3. Qdrant point_id 格式不兼容（"char-xxx" 不是合法 UUID）

**修复方案**:

A) 修复 point_id 格式：

```python
# vectors.py 修改
import uuid

class VectorStore:
    def _to_qdrant_id(self, point_id: str) -> str:
        """将内部 ID 转为合法 Qdrant UUID"""
        # 用内部 ID 的哈希生成确定性 UUID
        return str(uuid.uuid5(uuid.NAMESPACE_OID, point_id))
```

B) 在 EpisodeLoop 中默认创建 VectorStore：

```python
# episode_loop.py 修改
class EpisodeLoop:
    def __init__(self, config, *, model=None, memory=None, vectors=None):
        ...
        self.vectors = vectors or VectorStore(
            collection_prefix=config.project_id,
            host=config.qdrant_host,
            port=config.qdrant_port,
        )
        ...
```

C) 在 PatchCommitter 中，角色 insert/update 时同步向量：

```python
# state_patch.py 修改
def _sync_vectors(self, patch: StatePatch) -> None:
    if not self.vectors or not self.vectors.enabled:
        return
    if patch.table == "characters" and patch.operation in ("insert", "update"):
        description = patch.field_changes.get("description", "")
        name = patch.field_changes.get("name", "")
        if description:
            text = f"{name}: {description}"
            embedding = self._get_embedding(text)
            if embedding:
                self.vectors.upsert_point(
                    collection=f"{self.vectors.collection_prefix}_characters",
                    point_id=patch.record_id,
                    vector=embedding,
                    payload={"name": name, "episode": patch.episode_num},
                )
```

D) Embedding 获取需要封装一个轻量调用（复用 config 中已有的 embed_endpoint + embed_model）。

---

### 3.5 P1 修复：角色 last_seen 更新

**文件**: `src/drama_agent/tools/memory_tools.py`

**问题**: 君主B在 ep02 被 `_resolve_character_id` 引用时 last_seen 未更新。

**修复方案**: 在 `_resolve_character_id` 找到已有角色时，生成一个 update patch 更新 last_seen：

```python
# _resolve_character_id 中，找到已有角色后
existing = _find_character(memory, name)
if existing:
    ctx.character_name_map[name] = existing.id
    # 更新 last_seen
    if existing.last_seen < ctx.episode_num:
        pending_patches.append(StatePatch(
            episode_num=ctx.episode_num,
            table="characters",
            operation="update",
            record_id=existing.id,
            field_changes={"last_seen": ctx.episode_num, "updated_at": utc_now()},
            confidence=0.95,
            reason=f"Character referenced in episode {ctx.episode_num}",
            source_action="auto_resolve",
        ))
    return existing.id
```

---

### 3.6 P1 改进：report.md 丰富化

**文件**: `src/drama_agent/engine/episode_loop.py`

**问题**: report.md 只有数字，没有叙事内容。

**修复方案**: 重写 `_render_markdown_report`：

```python
def _render_markdown_report(self, payload: dict) -> str:
    lines = [
        f"# {payload['drama_title']} — 剧情理解报告",
        "",
        f"> Project: `{payload['project_id']}`",
        f"> Episodes: {payload['episodes_processed']}",
        f"> Generated: {utc_now()}",
        "",
        "---",
        "",
        "## 剧集概览",
        "",
    ]
    for result in payload["results"]:
        lines.extend([
            f"### 第 {result['episode_num']} 集",
            "",
            f"**摘要**: {result['summary']}",
            "",
            f"**基调**: {result.get('mood', '')}",
            "",
            f"**悬念**: {result.get('cliffhanger', '')}",
            "",
            f"- Actions: {result['actions_succeeded']}/{result['actions_total']}",
            f"- Patches committed: {result['patches_committed']}",
            "",
        ])

    lines.extend(["---", "", "## 角色档案", ""])
    for char in payload["characters"]:
        if char["confidence"] < 0.7:
            continue  # 跳过配角/群众
        aliases = ", ".join(char["aliases"]) if char["aliases"] else ""
        lines.extend([
            f"### {char['name']}" + (f" ({aliases})" if aliases else ""),
            "",
            f"{char['description']}",
            "",
            f"- 首次出现: 第{char['first_seen']}集 | 最近出现: 第{char['last_seen']}集",
            f"- 置信度: {char['confidence']}",
            "",
        ])

    lines.extend(["---", "", "## 主要剧情线索", ""])
    for thread in payload["plot_threads"]:
        status_icon = "🔓" if thread["status"] == "open" else "✅"
        lines.extend([
            f"- {status_icon} **{thread['title']}** (第{thread['opened_at']}集起)",
            f"  {thread['description']}",
            "",
        ])

    lines.extend(["---", "", "## 人物关系", ""])
    for rel in payload.get("relationships", []):
        lines.append(f"- {rel.get('char_a_name', '?')} ↔ {rel.get('char_b_name', '?')}: {rel['relation']}")

    return "\n".join(lines) + "\n"
```

`generate_final_report` 中需要额外查询角色名并填入关系记录。

---

### 3.7 P2 修复：代码去重

**文件**: 新建 `src/drama_agent/tools/utils.py`

```python
"""Shared utilities for tool handlers."""

from drama_agent.memory.store import MemoryStore


def find_character_fuzzy(memory: MemoryStore, name: str):
    """模糊查找角色：精确匹配 → 去除常见前缀后子串匹配"""
    if not name:
        return None
    exact = memory.find_character_by_name(name)
    if exact:
        return exact
    normalized = normalize_name(name)
    for candidate in memory.get_active_characters():
        for known in [candidate.name, *candidate.aliases]:
            known_n = normalize_name(known)
            if known_n and (known_n in normalized or normalized in known_n):
                return candidate
    return None


def normalize_name(value: str) -> str:
    """去除中文短剧中常见的称谓前缀/后缀"""
    for token in ("示例王朝", "王朝", "皇帝", "陛下", "公子", "姑娘", "贴身", "近卫", "将军", "侯爷"):
        value = value.replace(token, "")
    return value.strip()
```

然后 `memory_tools.py` 和 `asset_tools.py` 都 import 这个公共函数。

---

## 4. 新增测试清单

| 测试文件 | 测试场景 | 对应修复 |
|---------|---------|---------|
| `test_relationship_dedup.py` | 同一角色对在两集中出现→只有一条 relationship | 3.1 |
| `test_thread_dedup.py` | 同标题伏笔在两集中提到→UPDATE 而非 INSERT | 3.1 |
| `test_transaction_rollback.py` | 模拟中间 patch 失败→全部回滚 | 3.2 |
| `test_resolve_character_via_patch.py` | 未知角色名→通过 patch 创建，非直写 | 3.3 |
| `test_vector_sync.py` | 角色 insert/update 后 Qdrant 被同步调用 | 3.4 |
| `test_last_seen_update.py` | 角色被引用时 last_seen 更新 | 3.5 |
| `test_report_markdown.py` | 检查 report.md 包含摘要和角色信息 | 3.6 |

---

## 5. 实施顺序

```
Phase A: 数据正确性 (1 session)
  ├── 3.1 关系/伏笔去重 (store.py + memory_tools.py)
  ├── 3.2 事务安全 (store.py + state_patch.py)
  └── 3.3 _resolve_character_id 改造 (memory_tools.py)

Phase B: 向量激活 (1 session)
  ├── 3.4 VectorStore 激活 (vectors.py + state_patch.py + episode_loop.py)
  └── 3.5 last_seen 更新 (memory_tools.py)

Phase C: 产出丰富化 (1 session)
  ├── 3.6 report.md 重写 (episode_loop.py)
  └── 3.7 代码去重 (新建 tools/utils.py)

Phase D: 测试补全 (1 session)
  └── 7 个新测试文件
```

---

## 6. 不改的东西

以下在 V2 中明确 **不动**：
- `cli.py` — 入口稳定
- `config.py` — 配置足够
- `project.py` — 项目管理正确
- `model/client.py` — API 封装工作正常
- `model/prompts.py` — Prompt 模板质量已验证
- `action_plan.py` 的解析逻辑 — 已通过测试
- `episode_loop.py` 的主循环结构 — 只改 report 渲染

---

## 7. AI Coding 使用指南

给 Claude Code 的指令模板：

```
请按照 docs/06-v2-iteration.md 中的 Phase A 进行实施。

具体任务：
1. 在 store.py 中新增 find_relationship() 和 find_plot_thread_by_title() 方法
2. 在 store.py 中新增 transaction() 上下文管理器和 apply_*_tx() 方法
3. 在 store.py 中新增 _validate_table() 白名单方法
4. 修改 memory_tools.py 中的 handle_update_relationship —— 先查重再决定 INSERT/UPDATE
5. 修改 memory_tools.py 中的 handle_update_plot_thread —— 先查重再决定 INSERT/UPDATE
6. 修改 state_patch.py 中的 commit_episode_patches —— 使用 transaction 包裹
7. 修改 memory_tools.py 中的 _resolve_character_id —— 不直写 DB，改为收集 pending_patches

每个修改完成后运行 pytest 确保现有 14 个测试仍然通过。
修改完成后新增测试：test_relationship_dedup.py, test_thread_dedup.py, test_transaction_rollback.py, test_resolve_character_via_patch.py
```

---

## 8. 预期效果

V2 完成后，对同一部 2 集短剧重新跑一次：
- `plot_threads` 表中"示例王朝比武招亲危机"只有 1 条记录（ep02 更新 ep01 的记录）
- `relationships` 表中每对角色最多 1 条记录
- 所有角色（包括配角）都通过 patch 系统创建，可追溯
- `report.md` 包含完整的角色档案、剧情摘要、人物关系
- 如果 Qdrant 运行中，角色向量会被同步写入
