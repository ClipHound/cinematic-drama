from __future__ import annotations

import json
from typing import Any

from branch_narrative.dag_types import BranchEnding, BranchNode, Choice
from branch_narrative.phase1_planning import JsonLLM
from interaction_designer.json_utils import parse_json_object


SYSTEM_PROMPT = """你是短剧分支剧情编剧。
你只输出 JSON，不要输出 markdown 或解释。
"""


def generate_nodes(llm: JsonLLM, context: dict[str, Any], plan: dict[str, Any]) -> dict[str, BranchNode]:
    edges = _edge_map(plan)
    layers = _layer_map(plan)
    nodes: dict[str, BranchNode] = {}
    for node_id in _node_order(plan):
        successors = edges.get(node_id, [])
        response = llm.complete_json(SYSTEM_PROMPT, build_node_prompt(context, plan, node_id, successors, nodes))
        data = parse_json_object(response)
        nodes[node_id] = _node_from_data(node_id, layers.get(node_id, 0), successors, data, plan)
    return nodes


def generate_endings(llm: JsonLLM, context: dict[str, Any], plan: dict[str, Any]) -> dict[str, BranchEnding]:
    endings: dict[str, BranchEnding] = {}
    for outline in plan.get("endings_outline", []):
        ending_id = str(outline.get("ending_id") or f"ending_{outline.get('route_tag', 'route')}")
        response = llm.complete_json(SYSTEM_PROMPT, build_ending_prompt(context, plan, outline))
        endings[ending_id] = _ending_from_data(ending_id, parse_json_object(response), outline)
    return endings


def build_node_prompt(
    context: dict[str, Any],
    plan: dict[str, Any],
    node_id: str,
    successors: list[str],
    existing_nodes: dict[str, BranchNode],
) -> str:
    return f"""请生成分支剧情节点内容。

本节点: {node_id}
后继节点: {successors}
路线规划: {json.dumps(plan.get("route_tags", []), ensure_ascii=False)}
已有前序节点摘要: {json.dumps(_predecessor_summaries(existing_nodes), ensure_ascii=False)}

输出 JSON:
{{
  "route_tag": "justice|shadow|hermit|opening",
  "narrative": {{
    "title": "...",
    "paragraphs": ["2-4段叙事，每段80-180字"],
    "scene_description": "...",
    "characters_present": ["..."],
    "mood": "..."
  }},
  "choices": [
    {{"option_text": "≤15字", "option_subtext": "≤25字", "leads_to": "{successors[0] if successors else ''}"}}
  ],
  "audio_hint": {{"bgm_mood": "...", "sfx_suggestion": "..."}}
}}

约束:
- choices 必须一一导向后继节点，不能创造新 node_id。
- 如果本节点是汇合节点，叙事不能假设用户来自某条固定路径。
- 角色言行要符合正片。

全剧上下文:
{json.dumps(context, ensure_ascii=False)}
"""


def build_ending_prompt(context: dict[str, Any], plan: dict[str, Any], outline: dict[str, Any]) -> str:
    return f"""请根据结局概要生成分支剧情结局。

结局概要:
{json.dumps(outline, ensure_ascii=False)}

输出 JSON:
{{
  "ending_title": "...",
  "ending_subtitle": "...",
  "narrative": {{"paragraphs": ["..."], "scene_description": "...", "mood": "..."}},
  "epilogue": "...",
  "character_fates": {{"角色名": "命运"}}
}}

全剧上下文:
{json.dumps(context, ensure_ascii=False)}
"""


def _node_from_data(
    node_id: str,
    layer: int,
    successors: list[str],
    data: dict[str, Any],
    plan: dict[str, Any],
) -> BranchNode:
    narrative = data.get("narrative") or _fallback_narrative(node_id, plan)
    choices_data = data.get("choices") or []
    choices = []
    for index, target in enumerate(successors, start=1):
        source = choices_data[index - 1] if index - 1 < len(choices_data) else {}
        choices.append(
            Choice(
                choice_id=source.get("choice_id") or f"c_{node_id}_{index}",
                option_text=source.get("option_text") or f"走向{index}",
                option_subtext=source.get("option_subtext") or "选择不同的命运方向",
                leads_to=target,
            )
        )
    return BranchNode(
        node_id=node_id,
        layer=layer,
        route_tag=str(data.get("route_tag") or _infer_route(node_id)),
        narrative=narrative,
        choices=choices,
        audio_hint=data.get("audio_hint") or {"bgm_mood": "tense_anticipation", "sfx_suggestion": ""},
    )


def _ending_from_data(ending_id: str, data: dict[str, Any], outline: dict[str, Any]) -> BranchEnding:
    narrative = data.get("narrative") or {
        "paragraphs": [outline.get("summary") or "尘埃落定，众人走向各自命运。"],
        "scene_description": "示例王朝都城，风云平息后的清晨",
        "mood": "resolved",
    }
    return BranchEnding(
        ending_id=ending_id,
        ending_title=data.get("ending_title") or outline.get("title") or ending_id,
        ending_subtitle=data.get("ending_subtitle") or "一条由选择塑造的命运线",
        narrative=narrative,
        visual={},
        epilogue=data.get("epilogue") or "多年后，这段选择仍被人们传颂。",
        character_fates=dict(data.get("character_fates") or {}),
    )


def _edge_map(plan: dict[str, Any]) -> dict[str, list[str]]:
    edges: dict[str, list[str]] = {}
    for item in plan.get("dag_skeleton", {}).get("edges", []):
        edges[str(item.get("from"))] = [str(choice.get("to")) for choice in item.get("choices", []) if choice.get("to")]
    return edges


def _layer_map(plan: dict[str, Any]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for layer in plan.get("dag_skeleton", {}).get("layers", []):
        for node_id in layer.get("nodes", []):
            mapping[str(node_id)] = int(layer.get("layer") or 0)
    return mapping


def _node_order(plan: dict[str, Any]) -> list[str]:
    return [node for layer in plan.get("dag_skeleton", {}).get("layers", []) for node in layer.get("nodes", [])]


def _predecessor_summaries(nodes: dict[str, BranchNode]) -> list[dict[str, str]]:
    return [{"node_id": node.node_id, "title": node.narrative.get("title", "")} for node in nodes.values()]


def _fallback_narrative(node_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    opening = plan.get("opening_narrative") if node_id == "n_opening" else ""
    return {
        "title": "命运的岔路",
        "paragraphs": [opening or "局势再次变化，角色A必须在新的风暴中做出选择。"],
        "scene_description": "示例王朝都城，夜色将尽",
        "characters_present": ["角色A"],
        "mood": "tense",
    }


def _infer_route(node_id: str) -> str:
    for route in ("justice", "shadow", "hermit"):
        if route in node_id:
            return route
    return "opening"
