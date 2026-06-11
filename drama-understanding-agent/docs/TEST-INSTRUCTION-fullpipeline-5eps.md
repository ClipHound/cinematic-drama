# 全流程测试指令: 5 集端到端 (理解 + 互动设计)

> 执行人: 代码助手
> 目标: 验证 drama-understanding-agent (含 ASR 接入 + candidate_interactions) + interaction-design-agent 全流程

---

## 0. 前置确认

在开始之前，确认以下条件:

- [ ] 当前工作目录: `<project-root>/drama-understanding-agent`
- [ ] Python 虚拟环境可用，已安装 `pip install -e .`
- [ ] ASR 服务已启动在 `http://localhost:10000` (如未启动，见 §0.1)
- [ ] VLM API 可达 (Doubao-Seed, 配置已在 .env 中)
- [ ] 视频文件存在: `<project-root>/样例剧(测试使用)/第1集.mp4` ~ `第5集.mp4`

### 0.1 ASR 服务启动 (如未运行)

```bash
# 在 ASR-SERVER 目录
cd E:/ASR-SERVER
docker compose up -d
# 或者直接 python 启动 (如果是本地环境)
# 等待模型加载完成后，验证:
curl http://localhost:10000/health
```

### 0.2 环境准备

```bash
cd <project-root>/drama-understanding-agent

# 在 .env 中追加 ASR 配置 (如果还没有)
echo 'DRAMA_AGENT_ASR_ENDPOINT=http://localhost:10000' >> .env

# 确认 .env 最终包含:
# DRAMA_AGENT_ASR_ENDPOINT=http://localhost:10000

# 安装/更新包
pip install -e .
```

---

## 1. 清理旧数据 (重新跑干净的 5 集)

旧的 test-5eps 没有 ASR 数据也没有 candidate_interactions，需要重建。

```bash
# 备份旧数据 (可选)
mv projects/test-5eps projects/test-5eps-backup-$(date +%Y%m%d)

# 或者如果不需要备份，直接删除
rm -rf projects/test-5eps
```

---

## 2. Phase 1: 全集理解 (含 ASR + candidate_interactions)

```bash
drama-agent run \
  --title "示例剧A" \
  --video-dir "<project-root>/样例剧(测试使用)" \
  --pattern "第{num}集.mp4" \
  --episodes 5 \
  --project-id test-5eps-v2
```

**预期行为:**
1. 每集先调用 ASR 服务 → 生成 `projects/test-5eps-v2/asr/ep01.json` ~ `ep05.json`
2. ASR 结果含 `segments` (带 start_ms/end_ms) + `emotion_segments` + `vad_segments`
3. ASR 文本以 `[MM:SS.mmm-MM:SS.mmm] 台词 [emotion:xxx@0.xx]` 格式注入 VLM Prompt
4. VLM 返回含 `candidate_interactions[]` 的 action_plan
5. 最终 `output/report.json` 中每集 results 有 candidate_interactions

**验证检查点 (每步完成后检查):**

```bash
# 检查 ASR 文件是否生成
ls projects/test-5eps-v2/asr/

# 检查 ASR 内容是否含时间戳
python -c "
import json
data = json.loads(open('projects/test-5eps-v2/asr/ep01.json', encoding='utf-8').read())
print('asr_available:', data.get('asr_available'))
print('segments count:', len(data.get('segments', [])))
print('emotion_segments count:', len(data.get('emotion_segments', [])))
print('vad_segments count:', len(data.get('vad_segments', [])))
if data.get('segments'):
    seg = data['segments'][0]
    print('First segment:', seg)
"

# 检查 action_plan 是否含 candidate_interactions
python -c "
import json
for i in range(1, 6):
    plan = json.loads(open(f'projects/test-5eps-v2/action_plans/ep{i:02d}.json', encoding='utf-8').read())
    ci = plan.get('candidate_interactions') or []
    print(f'Ep{i}: {len(ci)} candidate_interactions')
    if ci:
        print(f'  Sample: start_ms={ci[0].get(\"start_ms\")}, emotion={ci[0].get(\"emotion_type\")}')
"

# 检查 report.json 完整性
python -c "
import json
data = json.loads(open('projects/test-5eps-v2/output/report.json', encoding='utf-8').read())
print('Episodes:', data.get('episodes_processed'))
print('Characters:', len(data.get('characters', [])))
print('Events:', len(data.get('plot_events', [])))
total_ci = sum(len(r.get('candidate_interactions') or []) for r in data.get('results', []))
print('Total candidate_interactions:', total_ci)
"
```

---

## 3. Phase 2: 互动设计

```bash
drama-agent design-interactions \
  --project projects/test-5eps-v2 \
  --output-dir outputs \
  --drama-id example-drama-a \
  --video-dir "<project-root>/样例剧(测试使用)" \
  --pattern "第{num}集.mp4"
```

**预期行为:**
1. 读取 report.json + action_plans + asr/ → 构建全剧上下文
2. Pass 1: 单次 LLM 调用 → 输出 rhythm_blueprint (5集节奏蓝图)
3. Pass 2: 5次 LLM 调用 → 每集输出 interaction_points[]
4. safety_rules 后处理 → 修正时长/重叠/组件合法性
5. 输出 `outputs/example-drama-a/ep_001.interactions.json` ~ `ep_005.interactions.json`

**验证检查点:**

```bash
# 检查输出文件
ls outputs/example-drama-a/

# 检查 Manifest 内容
python -c "
import json
from pathlib import Path

output_dir = Path('outputs/example-drama-a')
for f in sorted(output_dir.glob('*.interactions.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    points = data.get('interaction_points', [])
    end_interaction = data.get('episode_end_interaction', {})
    warnings = data.get('design_warnings', [])
    repairs = data.get('design_repairs', [])
    print(f'{f.name}:')
    print(f'  interaction_points: {len(points)}')
    print(f'  episode_end_interaction: {list(end_interaction.keys())}')
    print(f'  warnings: {len(warnings)}')
    print(f'  repairs: {len(repairs)}')
    for p in points[:2]:
        print(f'    {p[\"id\"]}: [{p[\"start_ms\"]}-{p[\"end_ms\"]}] {p[\"component\"]} | {p.get(\"emotion\",\"\")} | {p.get(\"key_line\",\"\")[:20]}')
    print()
"
```

---

## 4. (可选) 一键全流程

如果以上分步没问题，可以用 full-pipeline 命令一键执行:

```bash
# 清理之前的输出
rm -rf projects/test-5eps-v3 outputs/example-drama-a-full

drama-agent full-pipeline \
  --title "示例剧A" \
  --video-dir "<project-root>/样例剧(测试使用)" \
  --pattern "第{num}集.mp4" \
  --episodes 5 \
  --project-id test-5eps-v3 \
  --interactions-output outputs \
  --video-base-url ""
```

---

## 5. 故障排查

### 5.1 ASR 不可用

如果 ASR 服务未启动或不可达:
- 系统应降级运行: `asr/ep{N}.json` 会写入 `{"asr_available": false, "error": "..."}`
- VLM Prompt 中 ASR 部分显示 `(ASR unavailable)`
- candidate_interactions 的 start_ms/end_ms 将由 VLM 从视频时间估算 (精度降为秒级)
- **这不应阻塞测试**，只是互动点时间精度降低

### 5.2 VLM 未返回 candidate_interactions

可能原因:
- 模型没遵循新 Prompt 格式 (旧 prompt 缓存?)
- 检查 action_plan JSON 是否有 candidate_interactions 键

排查:
```bash
# 看原始 action_plan
cat projects/test-5eps-v2/action_plans/ep01.json | python -m json.tool | head -30
```

如果没有，说明 prompts.py 的变更没生效。确认:
```bash
python -c "
import sys; sys.path.insert(0, 'src')
from drama_agent.model.prompts import build_episode_prompt
# 检查 prompt 中是否包含 candidate_interactions
from drama_agent.engine.episode_types import EpisodeContext
from pathlib import Path
ctx = EpisodeContext(episode_num=1, video_path=Path('.'))
prompt = build_episode_prompt(ctx, 'test', 5)
assert 'candidate_interactions' in prompt, 'PROMPT NOT UPDATED!'
print('✓ Prompt contains candidate_interactions requirement')
"
```

### 5.3 interaction_designer Pass 失败

```bash
# 检查 Pass 1 输出 (全剧蓝图)
# 如果 Pass 1 失败，blueprint 为空 {} → Pass 2 仍可运行但无节奏指导

# 检查具体报错
drama-agent design-interactions \
  --project projects/test-5eps-v2 \
  --output-dir outputs \
  --drama-id example-drama-a \
  --video-dir "<project-root>/样例剧(测试使用)" \
  --pattern "第{num}集.mp4" 2>&1 | tee design-output.log
```

### 5.4 video_pattern 不匹配

视频文件名是 `第1集.mp4` (不是 `第01集.mp4`)。pattern 应该是 `第{num}集.mp4`。
如果 typer 的 format 不支持，可能需要调整为 `第{num:d}集.mp4` 或修改代码。

验证:
```bash
python -c "
pattern = '第{num}集.mp4'
for i in range(1, 6):
    print(pattern.format(num=i))
"
# 期望输出: 第1集.mp4 第2集.mp4 ... 第5集.mp4
```

---

## 6. 产出物清单 (测试成功后应有)

```
projects/test-5eps-v2/
├── asr/
│   ├── ep01.json  (含 segments/emotion_segments/vad_segments)
│   ├── ep02.json
│   ├── ep03.json
│   ├── ep04.json
│   └── ep05.json
├── action_plans/
│   ├── ep01.json  (含 candidate_interactions[])
│   ├── ep02.json
│   ├── ep03.json
│   ├── ep04.json
│   └── ep05.json
├── output/
│   ├── report.json
│   └── report.md
└── memory.db

outputs/example-drama-a/
├── ep_001.interactions.json
├── ep_002.interactions.json
├── ep_003.interactions.json
├── ep_004.interactions.json
└── ep_005.interactions.json
```

---

## 7. 收集分析数据 (跑完后执行)

请将以下内容输出并反馈:

```bash
# 7.1 ASR 质量抽检 (第1集前3段)
python -c "
import json
data = json.loads(open('projects/test-5eps-v2/asr/ep01.json', encoding='utf-8').read())
for seg in data.get('segments', [])[:5]:
    print(seg)
print('---')
for emo in data.get('emotion_segments', [])[:3]:
    print(emo)
"

# 7.2 candidate_interactions 质量抽检
python -c "
import json
for i in range(1, 6):
    plan = json.loads(open(f'projects/test-5eps-v2/action_plans/ep{i:02d}.json', encoding='utf-8').read())
    ci = plan.get('candidate_interactions') or []
    print(f'\\n=== Ep{i} ({len(ci)} candidates) ===')
    for c in ci:
        print(f'  [{c.get(\"start_ms\")}-{c.get(\"end_ms\")}] {c.get(\"emotion_type\")} | {c.get(\"anchor_line\",\"\")[:30]} | reason: {c.get(\"reason\",\"\")[:40]}')
"

# 7.3 互动设计质量抽检
python -c "
import json
from pathlib import Path
for f in sorted(Path('outputs/example-drama-a').glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    print(f'\\n=== {f.name} ===')
    print(f'design_notes: {data.get(\"design_notes\", \"\")}')
    for p in data.get('interaction_points', []):
        print(f'  {p[\"id\"]}: [{p[\"start_ms\"]//1000}s-{p[\"end_ms\"]//1000}s] {p[\"component\"]:20s} | {p.get(\"emotion\",\"\")} | {p.get(\"key_line\",\"\")[:25]}')
    end = data.get('episode_end_interaction', {})
    if end.get('predictions'):
        print(f'  END: {len(end[\"predictions\"])} predictions')
    warnings = data.get('design_warnings', [])
    if warnings:
        print(f'  ⚠ {len(warnings)} warnings: {warnings[:2]}')
"

# 7.4 全局节奏蓝图检查 (如果保存了 Pass 1 输出)
# Pass 1 输出目前没有持久化，可以从 design_notes 推断
```

---

## 8. 已知限制 & 预期偏差

| 项目 | 预期情况 |
|------|---------|
| ASR 时间戳精度 | ForcedAligner 提供字级精度，预期 ±200ms |
| emotion_segments 覆盖率 | emotion2vec 对纯音乐/背景音不产出情绪，可能有空段 |
| candidate_interactions 数量 | 预期每集 3-6 个，如果 <2 说明 VLM 对新 Prompt 遵循度不够 |
| 互动点组件分配 | LLM 自主判断，可能偏保守（多用 emotion_buffer），迭代优化 |
| Pass 1 蓝图质量 | 首次运行，可能过于泛化，需要看实际输出调整 Prompt |

---

> **执行完毕后，请将 §7 的完整输出粘贴回来，我们一起分析问题并迭代。**
