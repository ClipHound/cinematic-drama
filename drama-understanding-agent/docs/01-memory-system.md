# 01 - 记忆系统设计

> 记忆系统是 Agent 的核心状态管理层。它负责持久化所有理解产物，支持高效检索，并通过 State Patch 机制保护数据一致性。

---

## 1.1 存储架构

```
projects/{project_id}/
├── memory.db              # SQLite 主数据库
├── qdrant/                # Qdrant 本地持久化目录
├── assets/                # 图像/视频片段资产
│   ├── characters/        # 角色参考图
│   ├── evidence/          # 证据截图
│   └── frames/            # 关键帧
├── snapshots/             # 每集结束后的 DB 快照
│   ├── after_ep01.db
│   ├── after_ep02.db
│   └── ...
└── logs/                  # 操作日志
    └── patches/           # State Patch 历史记录
```

---

## 1.2 SQLite Schema

### characters (角色档案)

```sql
CREATE TABLE characters (
    id          TEXT PRIMARY KEY,          -- UUID
    name        TEXT NOT NULL,             -- 主要名称
    aliases     TEXT DEFAULT '[]',         -- JSON数组: 别名列表
    description TEXT DEFAULT '',           -- 当前完整描述
    first_seen  INTEGER NOT NULL,          -- 首次出现的集号
    last_seen   INTEGER DEFAULT 0,         -- 最近出现的集号
    status      TEXT DEFAULT 'active',     -- active/dead/unknown/merged
    merged_into TEXT DEFAULT NULL,         -- 如被合并，指向目标ID
    confidence  REAL DEFAULT 1.0,         -- 身份置信度 0-1
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

### character_states (角色状态快照 - 每集一条)

```sql
CREATE TABLE character_states (
    id           TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES characters(id),
    episode_num  INTEGER NOT NULL,
    emotion      TEXT DEFAULT '',           -- 本集情绪状态
    goal         TEXT DEFAULT '',           -- 本集目标/动机
    identity     TEXT DEFAULT '',           -- 身份变化（如揭露真实身份）
    appearance   TEXT DEFAULT '',           -- 外貌/穿着描述
    notes        TEXT DEFAULT '',           -- 其他状态备注
    created_at   TEXT NOT NULL,
    UNIQUE(character_id, episode_num)
);
```

### relationships (人物关系)

```sql
CREATE TABLE relationships (
    id           TEXT PRIMARY KEY,
    character_a  TEXT NOT NULL REFERENCES characters(id),
    character_b  TEXT NOT NULL REFERENCES characters(id),
    relation     TEXT NOT NULL,             -- 关系类型描述
    direction    TEXT DEFAULT 'bidirectional', -- a_to_b / b_to_a / bidirectional
    established  INTEGER NOT NULL,          -- 建立关系的集号
    ended        INTEGER DEFAULT NULL,      -- 关系结束的集号
    confidence   REAL DEFAULT 1.0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
```

### plot_events (剧情事件)

```sql
CREATE TABLE plot_events (
    id           TEXT PRIMARY KEY,
    episode_num  INTEGER NOT NULL,
    start_time   TEXT DEFAULT '',           -- 时间戳 (HH:MM:SS)
    end_time     TEXT DEFAULT '',
    event_type   TEXT NOT NULL,             -- setup/conflict/climax/resolution/reveal/twist
    description  TEXT NOT NULL,
    characters   TEXT DEFAULT '[]',         -- JSON数组: 相关角色ID列表
    importance   REAL DEFAULT 0.5,         -- 0-1 重要度
    created_at   TEXT NOT NULL
);
```

### plot_threads (伏笔/剧情线)

```sql
CREATE TABLE plot_threads (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,             -- 伏笔标题
    description  TEXT NOT NULL,             -- 详细描述
    thread_type  TEXT DEFAULT 'foreshadow', -- foreshadow/mystery/subplot/mainplot
    status       TEXT DEFAULT 'open',       -- open/resolved/abandoned
    opened_at    INTEGER NOT NULL,          -- 开始集号
    resolved_at  INTEGER DEFAULT NULL,      -- 解决集号
    resolution   TEXT DEFAULT '',           -- 解决方式描述
    characters   TEXT DEFAULT '[]',         -- 相关角色
    confidence   REAL DEFAULT 1.0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
```

### episode_summaries (剧集摘要)

```sql
CREATE TABLE episode_summaries (
    episode_num  INTEGER PRIMARY KEY,
    summary      TEXT NOT NULL,             -- 剧集摘要
    key_events   TEXT DEFAULT '[]',         -- JSON: 关键事件ID列表
    mood         TEXT DEFAULT '',           -- 整集情绪基调
    cliffhanger  TEXT DEFAULT '',           -- 悬念/hook
    created_at   TEXT NOT NULL
);
```

### series_state (全局剧情状态 - 单行表)

```sql
CREATE TABLE series_state (
    id                  INTEGER PRIMARY KEY DEFAULT 1,
    current_episode     INTEGER DEFAULT 0,
    total_episodes      INTEGER DEFAULT 0,
    main_plot_summary   TEXT DEFAULT '',    -- 主线剧情至今的总结
    genre               TEXT DEFAULT '',    -- 识别出的剧种
    setting             TEXT DEFAULT '',    -- 世界观/背景设定
    tone                TEXT DEFAULT '',    -- 整体风格基调
    updated_at          TEXT NOT NULL
);
```

### character_assets (角色图片资产)

```sql
CREATE TABLE character_assets (
    id           TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES characters(id),
    asset_type   TEXT NOT NULL,             -- anchor/reference/costume
    file_path    TEXT NOT NULL,             -- 相对于 assets/ 的路径
    episode_num  INTEGER NOT NULL,
    timestamp    TEXT DEFAULT '',           -- 视频中的时间戳
    description  TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);
```

### evidence_assets (证据资产)

```sql
CREATE TABLE evidence_assets (
    id           TEXT PRIMARY KEY,
    episode_num  INTEGER NOT NULL,
    asset_type   TEXT NOT NULL,             -- letter/contract/chat/object/scene
    file_path    TEXT NOT NULL,
    description  TEXT NOT NULL,
    related_thread TEXT DEFAULT NULL,       -- 关联的 plot_thread ID
    timestamp    TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);
```

### state_patches (Patch 历史记录)

```sql
CREATE TABLE state_patches (
    id           TEXT PRIMARY KEY,
    episode_num  INTEGER NOT NULL,
    patch_data   TEXT NOT NULL,             -- JSON: 完整 patch 内容
    status       TEXT DEFAULT 'committed',  -- pending/committed/rejected/rolled_back
    confidence   REAL DEFAULT 1.0,
    created_at   TEXT NOT NULL,
    committed_at TEXT DEFAULT NULL
);
```

### operation_logs (操作日志)

```sql
CREATE TABLE operation_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_num  INTEGER NOT NULL,
    action_type  TEXT NOT NULL,
    action_data  TEXT DEFAULT '{}',         -- JSON: 操作详情
    result       TEXT DEFAULT '',           -- 执行结果
    created_at   TEXT NOT NULL
);
```

---

## 1.3 Qdrant 向量存储

### Collection: `characters`
- **向量**: 角色描述的 embedding (768d, BGE/Qwen)
- **Payload**: `{id, name, aliases, description, status}`
- **用途**: 新角色出现时，检索已有角色库计算相似度，辅助判断是否为同一人

### Collection: `events`
- **向量**: 事件描述的 embedding
- **Payload**: `{id, episode_num, event_type, description, characters}`
- **用途**: 查询历史事件、查找伏笔关联

### Collection: `episode_contexts`
- **向量**: 每集摘要的 embedding
- **Payload**: `{episode_num, summary, key_events}`
- **用途**: 跨集语义检索

---

## 1.4 记忆上下文构建

每次调用模型前，系统从记忆中构建上下文注入 Prompt：

```python
def build_memory_context(project: Project, episode_num: int) -> str:
    """构建注入Prompt的记忆上下文"""
    sections = []
    
    # 1. 已知角色卡 (所有 active 角色的简要信息)
    characters = project.memory.get_active_characters()
    if characters:
        char_lines = [f"- {c.name}: {c.description[:100]}" for c in characters]
        sections.append("## 已知角色\n" + "\n".join(char_lines))
    
    # 2. 上一集摘要
    prev_summary = project.memory.get_episode_summary(episode_num - 1)
    if prev_summary:
        sections.append(f"## 上集摘要\n{prev_summary.summary}")
    
    # 3. 未解决伏笔
    open_threads = project.memory.get_open_threads()
    if open_threads:
        thread_lines = [f"- {t.title}: {t.description[:80]}" for t in open_threads]
        sections.append("## 未解决伏笔/悬念\n" + "\n".join(thread_lines))
    
    # 4. 关键人物关系
    relationships = project.memory.get_active_relationships()
    if relationships:
        rel_lines = [f"- {r.char_a_name} ↔ {r.char_b_name}: {r.relation}" for r in relationships]
        sections.append("## 人物关系\n" + "\n".join(rel_lines))
    
    # 5. 全局状态
    state = project.memory.get_series_state()
    if state and state.main_plot_summary:
        sections.append(f"## 全局剧情走向\n{state.main_plot_summary}")
    
    return "\n\n".join(sections)
```

---

## 1.5 快照与回滚

- 每集处理完成后，复制 `memory.db` 为 `snapshots/after_ep{N:02d}.db`
- 回滚操作：用快照文件覆盖 `memory.db`，并重建 Qdrant collection
- Qdrant 回滚策略：记录每集新增的 point IDs，回滚时批量删除

---

## 1.6 数据量预估

| 指标 | 预估值 | 说明 |
|------|--------|------|
| 角色数/部 | 10-30 | 主角+配角+龙套 |
| 事件数/集 | 3-8 | 关键剧情事件 |
| 关系数/部 | 20-60 | 角色间关系 |
| 伏笔数/部 | 5-20 | 开放线索 |
| SQLite 大小/部 | < 5 MB | 60集全量数据 |
| Qdrant 点数/部 | < 1000 | 角色+事件+摘要 |
| 快照目录大小 | < 300 MB | 60个快照 |
