from __future__ import annotations

from branch_narrative.config import BranchNarrativeConfig
from branch_narrative.dag_types import BranchEnding, BranchNode


def validate_package(
    *,
    entry_node: str,
    nodes: dict[str, BranchNode],
    endings: dict[str, BranchEnding],
    config: BranchNarrativeConfig,
) -> list[str]:
    warnings: list[str] = []
    if entry_node not in nodes:
        warnings.append(f"G1: entry node missing: {entry_node}")
    if len(nodes) + len(endings) > config.max_nodes:
        warnings.append(f"G2: node count exceeds max {config.max_nodes}")
    _validate_dead_ends(nodes, endings, warnings)
    _validate_reachability(entry_node, nodes, endings, warnings)
    _validate_merge_nodes(nodes, warnings)
    return warnings


def _validate_dead_ends(
    nodes: dict[str, BranchNode],
    endings: dict[str, BranchEnding],
    warnings: list[str],
) -> None:
    valid_targets = set(nodes) | set(endings)
    for node in nodes.values():
        if not node.choices:
            warnings.append(f"G3: node has no choices: {node.node_id}")
        for choice in node.choices:
            if choice.leads_to not in valid_targets:
                warnings.append(f"G4: {node.node_id}/{choice.choice_id} leads to missing {choice.leads_to}")


def _validate_reachability(
    entry_node: str,
    nodes: dict[str, BranchNode],
    endings: dict[str, BranchEnding],
    warnings: list[str],
) -> None:
    visited: set[str] = set()
    stack = [entry_node]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        if current in nodes:
            stack.extend(choice.leads_to for choice in nodes[current].choices)
    for node_id in nodes:
        if node_id not in visited:
            warnings.append(f"G5: unreachable node {node_id}")
    for ending_id in endings:
        if ending_id not in visited:
            warnings.append(f"G6: unreachable ending {ending_id}")


def _validate_merge_nodes(nodes: dict[str, BranchNode], warnings: list[str]) -> None:
    indegree = {node_id: 0 for node_id in nodes}
    for node in nodes.values():
        for choice in node.choices:
            if choice.leads_to in indegree:
                indegree[choice.leads_to] += 1
    if not any(value >= 2 for value in indegree.values()):
        warnings.append("G7: no merge node detected in DAG")
