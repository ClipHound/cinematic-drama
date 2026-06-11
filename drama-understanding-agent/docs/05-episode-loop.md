# 05 - 逐集理解循环设计

> Episode Loop 是 Agent 的主运行循环。它协调模型调用、Action Plan 执行、记忆更新，驱动整部剧的理解过程。

---

## 5.1 运行模式

```
CLI 入口
    │
    ▼
初始化 Project
    │
    ▼
┌─── Episode Loop ──────────────────────────────────────────┐
│                                                           │
│   for episode in episodes (按序):                          │
│       1. 构建上下文 (从记忆中提取)                          │
│       2. 组装 Prompt                                       │
│       3. 调用模型 (视频 + prompt → Action Plan)            │
│       4. 解析 Action Plan                                  │
│       5. 执行 Actions → 生成 State Patches                 │
│       6. 提交 Patches → 更新记忆                           │
│       7. 创建快照                                          │
│       8. 输出进度报告                                      │
│                                                           │
└───────────────────────────────────────────────────────────┘
    │
    ▼
生成最终报告
```

---

## 5.2 核心类

```python
@dataclass
class ProjectConfig:
    """项目配置"""
    project_id: str
    drama_title: str
    video_dir: Path              # 视频文件目录
    video_pattern: str           # 文件名模式, e.g. "ep{num:02d}.mp4"
    total_episodes: int
    output_dir: Path             # 项目输出目录
    
    # 模型配置
    model_endpoint: str
    model_token: str
    model_name: str
    
    # Qdrant 配置
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    
    # Embedding 配置
    embed_endpoint: str = "http://localhost:11434"
    embed_model: str = "qwen3-embedding:0.6b"
    
    # 运行配置
    start_episode: int = 1       # 从第几集开始（支持断点续跑）
    mode: str = "full_auto"      # full_auto / hitl_light / hitl_strict


@dataclass  
class EpisodeContext:
    """单集处理上下文"""
    episode_num: int
    video_path: Path
    asr_text: str                # ASR 结果文本
    known_characters: list[dict] # 已知角色摘要列表
    open_threads: list[dict]     # 未解决伏笔列表
    previous_summary: str        # 上集摘要
    series_state: dict           # 全局剧情状态
```

---

## 5.3 主循环实现

```python
class EpisodeLoop:
    """逐集理解主循环"""
    
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.project = Project(config)  # 管理项目目录和存储
        self.memory = MemoryStore(self.project.db_path)
        self.vectors = VectorStore(config)
        self.model = DoubaoClient(config.model_endpoint, config.model_token, config.model_name)
        self.engine = ActionPlanEngine(self.memory, self.vectors)
        self.committer = PatchCommitter(self.memory, self.vectors)
    
    def run(self) -> ProjectResult:
        """运行完整的逐集理解循环"""
        
        # 初始化项目（如果是新项目）
        self.project.initialize()
        
        # 确定起始集（支持断点续跑）
        start = self._determine_start_episode()
        
        results = []
        for ep_num in range(start, self.config.total_episodes + 1):
            print(f"\n{'='*60}")
            print(f"  Episode {ep_num} / {self.config.total_episodes}")
            print(f"{'='*60}\n")
            
            result = self._process_episode(ep_num)
            results.append(result)
            
            if result.has_critical_error:
                print(f"  ⚠ Critical error at ep{ep_num}, stopping.")
                break
        
        # 生成最终报告
        report = self._generate_final_report(results)
        return report
    
    def _process_episode(self, ep_num: int) -> ExecutionResult:
        """处理单集"""
        
        # 1. 构建上下文
        ctx = self._build_context(ep_num)
        
        # 2. 组装 prompt
        prompt = self._assemble_prompt(ctx)
        
        # 3. 调用模型
        print(f"  Calling model... (video: {ctx.video_path.name})")
        raw_response = self.model.understand_episode(
            video_path=ctx.video_path,
            episode_prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )
        
        # 4. 解析 Action Plan
        plan = parse_action_plan(raw_response)
        if "_error" in plan:
            return ExecutionResult(episode_num=ep_num, has_critical_error=True, ...)
        
        print(f"  Actions: {len(plan.get('actions', []))}")
        
        # 5. 执行 Actions
        patches = self.engine.execute(plan, ctx)
        
        # 6. 提交 Patches
        commit_result = self.committer.commit_episode_patches(patches)
        
        # 7. 写入集摘要
        self.memory.save_episode_summary(
            episode_num=ep_num,
            summary=plan.get("episode_summary", ""),
            mood=plan.get("mood", ""),
            cliffhanger=plan.get("cliffhanger", ""),
        )
        
        # 8. 创建快照
        self.project.create_snapshot(ep_num)
        
        # 9. 输出进度
        self._print_progress(ep_num, commit_result)
        
        return commit_result
    
    def _build_context(self, ep_num: int) -> EpisodeContext:
        """从记忆中提取当前集需要的上下文"""
        
        # 视频路径
        video_path = self._get_video_path(ep_num)
        
        # ASR (如果有预处理好的)
        asr_text = self._load_asr(ep_num)
        
        # 已知角色（按重要度排序，取 top 20）
        characters = self.memory.get_active_characters(limit=20)
        
        # 未解决伏笔
        threads = self.memory.get_open_threads()
        
        # 上集摘要
        prev_summary = self.memory.get_episode_summary(ep_num - 1)
        
        # 全局状态
        series_state = self.memory.get_series_state()
        
        return EpisodeContext(
            episode_num=ep_num,
            video_path=video_path,
            asr_text=asr_text,
            known_characters=characters,
            open_threads=threads,
            previous_summary=prev_summary,
            series_state=series_state,
        )
    
    def _determine_start_episode(self) -> int:
        """确定从哪集开始（支持断点续跑）"""
        if self.config.start_episode > 1:
            return self.config.start_episode
        
        # 检查已有进度
        current = self.memory.get_series_state().get("current_episode", 0)
        if current > 0:
            print(f"  Resuming from episode {current + 1} (found existing progress)")
            return current + 1
        
        return 1
```

---

## 5.4 上下文压缩策略

当角色数超过 20 个时，Prompt 中的角色摘要需要压缩:

```python
def compress_character_context(characters: list[dict], limit: int = 20) -> list[dict]:
    """
    压缩策略:
    1. 按 last_seen 降序（最近出现的优先）
    2. 按 importance 加权（主角 > 配角 > 路人）
    3. 超出 limit 的角色只保留 name + 一句话描述
    4. 与当前集相关的角色（由上集 cliffhanger 提到的）强制保留
    """
```

---

## 5.5 ASR 预处理

ASR 作为辅助输入，在主循环之前预处理:

```python
def preprocess_asr(video_path: Path, output_path: Path) -> str:
    """
    ASR 预处理流程:
    1. 检查是否已有 ASR 结果缓存
    2. 如果没有: 调用 faster-whisper 生成
    3. 格式化为时间戳+文本格式:
       [00:05] 今天全场消费都由本公子买单
       [00:12] 公子A出手真阔绰
       ...
    4. 限制长度: 超过 2000 字符时截取关键段落
    """
```

---

## 5.6 错误恢复

```python
class EpisodeLoop:
    
    def _handle_episode_failure(self, ep_num: int, error: Exception):
        """
        单集失败处理:
        1. 记录错误到 operation_logs
        2. 不阻塞后续集的处理
        3. 在最终报告中标记
        4. 如果是 API 配额耗尽: 暂停整个循环
        5. 如果连续 3 集失败: 停止并报告
        """
    
    def resume_from(self, episode_num: int):
        """
        从指定集恢复:
        1. 恢复到 ep{num-1} 的快照
        2. 从该集重新开始
        """
```

---

## 5.7 最终产出

循环结束后生成:

```
projects/{project_id}/
├── output/
│   ├── report.md              # 人类可读的剧情分析报告
│   ├── report.json            # 机器可读的完整数据
│   ├── characters.json        # 角色档案导出
│   ├── relationships.json     # 关系图导出
│   ├── plot_events.json       # 事件时间线
│   ├── plot_threads.json      # 伏笔追踪
│   └── uncertainties.json     # 不确定标记汇总
```

---

## 5.8 CLI 入口

```python
# 创建新项目并运行
drama-agent run \
    --title "示例剧A" \
    --video-dir ./videos/fuyao/ \
    --pattern "第{num}集.mp4" \
    --episodes 60

# 从断点续跑
drama-agent run \
    --project ./projects/fuyao/ \
    --resume

# 从某集重新开始
drama-agent run \
    --project ./projects/fuyao/ \
    --from-episode 15

# 查看项目状态
drama-agent status --project ./projects/fuyao/

# 导出报告
drama-agent export --project ./projects/fuyao/ --format markdown
```

---

## 5.9 性能预期

| 指标 | 预期值 | 说明 |
|------|--------|------|
| 单集模型调用耗时 | 50-80s | 基于实验数据 |
| 单集 Action 执行耗时 | 2-5s | 主要是 DB 写入和 ffmpeg |
| 单集总耗时 | ~60-90s | 含网络延迟 |
| 60 集总耗时 | ~60-90 分钟 | 无并行，顺序处理 |
| 内存占用 | < 500MB | SQLite + Qdrant 本地 |
| 磁盘占用 (不含视频) | < 200MB / 项目 | DB + 向量 + 快照 + 资产 |
