from __future__ import annotations

from pathlib import Path
from typing import Any

from branch_narrative.dag_types import BranchEnding, BranchNode
from branch_narrative.image_generator import ImageGenerator, ImageRequest


def attach_visuals(
    *,
    nodes: dict[str, BranchNode],
    endings: dict[str, BranchEnding],
    context: dict[str, Any],
    image_generator: ImageGenerator,
) -> None:
    assets = context.get("character_assets") or {}
    for node in nodes.values():
        node.visual = _visual_for_node(node.node_id, node.narrative, assets, image_generator)
    for ending in endings.values():
        ending.visual = _visual_for_node(ending.ending_id, ending.narrative, assets, image_generator)


def _visual_for_node(
    node_id: str,
    narrative: dict[str, Any],
    assets: dict[str, list[str]],
    image_generator: ImageGenerator,
) -> dict[str, Any]:
    characters = [str(item) for item in narrative.get("characters_present", [])]
    refs = _reference_images(characters, assets)
    style_tags = _style_tags(narrative.get("mood", ""))
    prompt = _prompt(narrative)
    result = image_generator.generate(
        ImageRequest(
            node_id=node_id,
            prompt=prompt,
            reference_images=[Path(item) for item in refs],
            style_tags=style_tags,
        )
    )
    return {
        "prompt": result.prompt_used or prompt,
        "reference_images": refs,
        "style_tags": style_tags,
        "image_url": result.image_url,
        "image_path": str(result.image_path) if result.image_path else None,
        "status": result.status,
    }


def _reference_images(characters: list[str], assets: dict[str, list[str]]) -> list[str]:
    refs: list[str] = []
    for character in characters:
        refs.extend(assets.get(character, [])[:1])
    return refs[:3]


def _style_tags(mood: str) -> list[str]:
    base = ["cinematic", "ancient_chinese", "drama_still"]
    if mood:
        base.append(str(mood))
    return base


def _prompt(narrative: dict[str, Any]) -> str:
    scene = narrative.get("scene_description") or "古装短剧分支剧情场景"
    title = narrative.get("title") or "命运选择"
    mood = narrative.get("mood") or "dramatic"
    return f"{scene}，{title}，{mood}情绪，电影感构图，细腻人物表情，古装东方美学"
