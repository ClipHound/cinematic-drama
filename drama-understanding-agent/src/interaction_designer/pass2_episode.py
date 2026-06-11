from __future__ import annotations

import json
from typing import Any

from interaction_designer.component_library import COMPONENT_LIBRARY
from interaction_designer.json_utils import parse_json_object
from interaction_designer.pass1_global import JsonLLM


SYSTEM_PROMPT = """你是短剧互动导演。
你根据剧情理解候选点和组件库，设计最终前端互动方案。
只输出 JSON，不要输出 markdown 或解释。
"""


def run_episode_pass(llm: JsonLLM, episode_context: dict[str, Any]) -> dict[str, Any]:
    response = llm.complete_json(SYSTEM_PROMPT, build_episode_prompt(episode_context))
    result = parse_json_object(response)
    result.setdefault("interaction_points", [])
    result.setdefault("episode_end_interaction", {})
    return result


def build_episode_prompt(episode_context: dict[str, Any]) -> str:
    return f"""请为本集设计最终互动方案。

你必须自主判断，而不是机械映射:
1. 从 candidate_interactions 和 plot_events 中选择真正值得互动的点。
2. 为每个点选择最适合的 component。
3. 可以合并、删减或微调时间窗口，但不能编造不存在的剧情。
4. 严格遵守本集密度约束；除非候选明显不足，不要低于互动点数量目标下限。
5. 时间必须是毫秒，start_ms < end_ms，持续 5-20 秒。
6. 悲伤/压抑场景不要用 shatter_strike 或 celebrate_confetti。
7. 甜蜜场景不要用 anger_release。
8. 集尾 prediction 的 reveal_episode_id 应指向后续集。
9. 不要盲目相信 candidate_interactions 的 emotion_type。它只是 VLM 初步标注，可能有偏差。
   你必须根据 reason、anchor_line、visual_cue 独立判断观众真实心理反应。
   特别注意: "funny" 不一定真的好笑；"对峙"不一定适合站队；"反差"不等于喜剧反差。

{COMPONENT_LIBRARY}

本集密度约束:
{episode_context.get("density_instruction", "")}

{_recent_themes_hint(episode_context)}

注意: 以下组件必须在 config 中提供特定字段:
- prediction_card: config.options = [{{"text": "选项文本", "is_correct": true/false}}]，至少 2 个选项。
- clue_judge_card: config.clue_text = "需要判断的线索描述"。
- team_cheer: config.sides = [{{"label": "阵营名", "character": "代表角色"}}]，至少 2 个阵营。

输出 JSON:
{{
  "interaction_points": [
    {{
      "id": "ip_ep_001_0001",
      "start_ms": 0,
      "end_ms": 9000,
      "component": "从组件库选择",
      "emotion": "观众情绪",
      "intensity": 0.0,
      "priority": 0.0,
      "confidence": 0.0,
      "title": "审核可读标题",
      "key_line": "代表性台词",
      "key_visual": "关键画面",
      "highlight_reason": "为什么适合互动",
      "score_type": "resonance|guard|insight|cocreate",
      "config": {{}}
    }}
  ],
  "episode_end_interaction": {{
    "predictions": [],
    "character_voices": [],
    "clue_summary_enabled": false
  }},
  "design_notes": "2-3句说明设计思路"
}}

本集上下文:
{json.dumps(episode_context, ensure_ascii=False)}
"""


def _recent_themes_hint(episode_context: dict[str, Any]) -> str:
    recent = episode_context.get("recent_themes") or []
    if not recent:
        return ""
    return (
        f"前两集已使用的组件集合: {json.dumps(recent, ensure_ascii=False)}\n"
        "请尽量避免与前两集完全相同的组件组合，保持互动体验的新鲜感。"
    )
