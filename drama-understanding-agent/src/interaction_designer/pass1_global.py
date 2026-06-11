from __future__ import annotations

import json
from typing import Any, Protocol

from interaction_designer.json_utils import parse_json_object


class JsonLLM(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        ...


SYSTEM_PROMPT = """你是一位短剧互动体验总导演。
你只输出 JSON，不要输出 markdown 或解释。
"""


def run_global_pass(llm: JsonLLM, global_context: dict[str, Any]) -> dict[str, Any]:
    response = llm.complete_json(SYSTEM_PROMPT, build_global_prompt(global_context))
    result = parse_json_object(response)
    if "rhythm_blueprint" not in result:
        result["rhythm_blueprint"] = []
    return result


def build_global_prompt(global_context: dict[str, Any]) -> str:
    return f"""请基于全剧结构化理解结果，制定全剧互动节奏蓝图。

设计目标:
1. 判断每集互动定位、密度、主情绪和设计重点。
2. 不要机械套规则，要考虑观众追短剧的爽点、悬念、情绪释放。
3. 互动节奏不能单调，连续集之间需要有变化。

输出 JSON:
{{
  "drama_profile": {{
    "genre": "...",
    "core_emotion": "...",
    "audience_expectation": "..."
  }},
  "rhythm_blueprint": [
    {{
      "episode_num": 1,
      "positioning": "铺垫集|过渡集|高燃集|情感集|反转集",
      "interaction_density": "low|medium|high",
      "primary_emotion": "...",
      "emphasis": "...",
      "end_interaction_type": "prediction|character_voice|clue_review|none"
    }}
  ],
  "global_strategy": {{
    "component_distribution": "...",
    "escalation_plan": "..."
  }}
}}

全剧上下文:
{json.dumps(global_context, ensure_ascii=False)}
"""
