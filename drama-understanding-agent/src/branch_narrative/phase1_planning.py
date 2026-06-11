from __future__ import annotations

import json
from typing import Any, Protocol

from branch_narrative.config import BranchNarrativeConfig
from interaction_designer.json_utils import parse_json_object


class JsonLLM(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        ...


SYSTEM_PROMPT = """你是一位短剧分支叙事编剧。
你只输出 JSON，不要输出 markdown 或解释。
"""


def run_planning(llm: JsonLLM, context: dict[str, Any], config: BranchNarrativeConfig) -> dict[str, Any]:
    response = llm.complete_json(SYSTEM_PROMPT, build_planning_prompt(context, config))
    plan = parse_json_object(response)
    return normalize_plan(plan)


def build_planning_prompt(context: dict[str, Any], config: BranchNarrativeConfig) -> str:
    return f"""请为已完结短剧设计分支剧情 DAG。

规格:
- 路线标签数: {config.route_count}
- 结局数: {config.route_count}
- 用户选择深度: {config.target_choice_depth}
- 内容节点总数不超过: {config.max_nodes}
- 每个选择点提供 {config.min_choices}-{config.max_choices} 个选项

要求:
1. 分支不是自由聊天，是预生成静态剧情包。
2. 使用 DAG 汇合，不能指数爆炸。
3. 三条路线要体现不同价值观，不要只是好/中/坏。
4. 开场必须承接正片最后一集。
5. 角色行为必须符合正片性格。

输出 JSON:
{{
  "route_tags": [
    {{"id": "justice", "name": "光明线", "theme": "...", "emotion_arc": "..."}}
  ],
  "endings_outline": [
    {{"ending_id": "ending_justice", "route_tag": "justice", "title": "...", "summary": "..."}}
  ],
  "dag_skeleton": {{
    "layers": [
      {{"layer": 0, "nodes": ["n_opening"]}},
      {{"layer": 1, "nodes": ["n_l1_a", "n_l1_b"]}},
      {{"layer": 2, "nodes": ["n_l2_justice", "n_l2_shadow", "n_l2_hermit"]}},
      {{"layer": 3, "nodes": ["n_l3_justice", "n_l3_shadow", "n_l3_hermit"]}},
      {{"layer": 4, "nodes": ["n_l4_justice", "n_l4_shadow", "n_l4_hermit"]}}
    ],
    "edges": [
      {{"from": "n_opening", "choices": [{{"to": "n_l1_a"}}, {{"to": "n_l1_b"}}]}}
    ]
  }},
  "opening_narrative": "..."
}}

全剧上下文:
{json.dumps(context, ensure_ascii=False)}
"""


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_plan()
    route_tags = plan.get("route_tags") or fallback["route_tags"]
    endings = plan.get("endings_outline") or fallback["endings_outline"]
    skeleton = plan.get("dag_skeleton") or fallback["dag_skeleton"]
    opening = plan.get("opening_narrative") or fallback["opening_narrative"]
    normalized_skeleton = _normalize_skeleton(skeleton)
    normalized_skeleton = _ensure_terminal_edges(normalized_skeleton, endings[:3])
    return {
        "route_tags": route_tags[:3],
        "endings_outline": endings[:3],
        "dag_skeleton": normalized_skeleton,
        "opening_narrative": opening,
    }


def _normalize_skeleton(skeleton: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_plan()["dag_skeleton"]
    layers = skeleton.get("layers") or fallback["layers"]
    edges = skeleton.get("edges") or fallback["edges"]
    return {"layers": layers[:5], "edges": edges}


def _ensure_terminal_edges(skeleton: dict[str, Any], endings: list[dict[str, Any]]) -> dict[str, Any]:
    if not endings:
        return skeleton
    edges = list(skeleton.get("edges") or [])
    edge_sources = {str(edge.get("from")) for edge in edges}
    layers = skeleton.get("layers") or []
    last_layer = max(layers, key=lambda item: int(item.get("layer") or 0), default={})
    ending_ids = [str(item.get("ending_id")) for item in endings if item.get("ending_id")]
    for index, node_id in enumerate(last_layer.get("nodes", [])):
        node_id = str(node_id)
        if node_id in edge_sources:
            continue
        targets = _terminal_targets(node_id, ending_ids, index)
        edges.append({"from": node_id, "choices": [{"to": target} for target in targets]})
    return {"layers": layers, "edges": edges}


def _terminal_targets(node_id: str, ending_ids: list[str], index: int) -> list[str]:
    if not ending_ids:
        return []
    for ending_id in ending_ids:
        if any(token and token in ending_id for token in node_id.split("_")):
            second = ending_ids[(ending_ids.index(ending_id) + 1) % len(ending_ids)]
            return [ending_id, second] if second != ending_id else [ending_id]
    first = ending_ids[index % len(ending_ids)]
    second = ending_ids[(index + 1) % len(ending_ids)]
    return [first, second] if second != first else [first]


def _fallback_plan() -> dict[str, Any]:
    route_tags = [
        {"id": "justice", "name": "光明正道", "theme": "公开真相与守护家国", "emotion_arc": "压抑到昂扬"},
        {"id": "shadow", "name": "暗影复仇", "theme": "隐忍布局与代价清算", "emotion_arc": "冷峻到释然"},
        {"id": "hermit", "name": "隐士归心", "theme": "放下权位与守护所爱", "emotion_arc": "紧绷到宁静"},
    ]
    layers = [
        {"layer": 0, "nodes": ["n_opening"]},
        {"layer": 1, "nodes": ["n_l1_a", "n_l1_b"]},
        {"layer": 2, "nodes": ["n_l2_justice", "n_l2_shadow", "n_l2_hermit"]},
        {"layer": 3, "nodes": ["n_l3_justice", "n_l3_shadow", "n_l3_hermit"]},
        {"layer": 4, "nodes": ["n_l4_justice", "n_l4_shadow", "n_l4_hermit"]},
    ]
    edges = [
        {"from": "n_opening", "choices": [{"to": "n_l1_a"}, {"to": "n_l1_b"}]},
        {"from": "n_l1_a", "choices": [{"to": "n_l2_justice"}, {"to": "n_l2_shadow"}]},
        {"from": "n_l1_b", "choices": [{"to": "n_l2_shadow"}, {"to": "n_l2_hermit"}]},
        {"from": "n_l2_justice", "choices": [{"to": "n_l3_justice"}, {"to": "n_l3_shadow"}]},
        {"from": "n_l2_shadow", "choices": [{"to": "n_l3_shadow"}, {"to": "n_l3_hermit"}]},
        {"from": "n_l2_hermit", "choices": [{"to": "n_l3_hermit"}, {"to": "n_l3_justice"}]},
        {"from": "n_l3_justice", "choices": [{"to": "n_l4_justice"}, {"to": "n_l4_shadow"}]},
        {"from": "n_l3_shadow", "choices": [{"to": "n_l4_shadow"}, {"to": "n_l4_hermit"}]},
        {"from": "n_l3_hermit", "choices": [{"to": "n_l4_hermit"}, {"to": "n_l4_justice"}]},
        {"from": "n_l4_justice", "choices": [{"to": "ending_justice"}, {"to": "ending_shadow"}]},
        {"from": "n_l4_shadow", "choices": [{"to": "ending_shadow"}, {"to": "ending_hermit"}]},
        {"from": "n_l4_hermit", "choices": [{"to": "ending_hermit"}, {"to": "ending_justice"}]},
    ]
    endings = [
        {"ending_id": "ending_justice", "route_tag": "justice", "title": "光明正道", "summary": "公开真相"},
        {"ending_id": "ending_shadow", "route_tag": "shadow", "title": "暗影复仇", "summary": "暗中清算"},
        {"ending_id": "ending_hermit", "route_tag": "hermit", "title": "归隐守心", "summary": "放下权位"},
    ]
    return {
        "route_tags": route_tags,
        "endings_outline": endings,
        "dag_skeleton": {"layers": layers, "edges": edges},
        "opening_narrative": "正片落幕后，未尽的风暴仍在暗处翻涌。",
    }
