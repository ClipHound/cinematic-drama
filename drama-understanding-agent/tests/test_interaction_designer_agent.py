import json
from pathlib import Path

from interaction_designer.agent import InteractionDesignAgent
from interaction_designer.config import DesignConfig
from interaction_designer.safety_rules import normalize_design_output


class FakeDesignLLM:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return json.dumps(
                {
                    "drama_profile": {"genre": "爽剧", "core_emotion": "反转", "audience_expectation": "爽感"},
                    "rhythm_blueprint": [
                        {
                            "episode_num": 1,
                            "positioning": "反转集",
                            "interaction_density": "medium",
                            "primary_emotion": "curious",
                            "emphasis": "身份悬念",
                            "end_interaction_type": "prediction",
                        }
                    ],
                    "global_strategy": {"component_distribution": "预测优先", "escalation_plan": "逐步增强"},
                }
            )
        return json.dumps(
            {
                "interaction_points": [
                    {
                        "start_ms": 1000,
                        "end_ms": 9000,
                        "component": "prediction_card",
                        "emotion": "curious",
                        "intensity": 0.8,
                        "priority": 0.9,
                        "confidence": 0.88,
                        "title": "剧情预测",
                        "key_line": "他到底是谁",
                        "key_visual": "角色A抬头",
                        "highlight_reason": "身份悬念强",
                        "score_type": "insight",
                        "config": {"question": "他会暴露身份吗？", "options": []},
                    }
                ],
                "episode_end_interaction": {"predictions": [], "character_voices": [], "clue_summary_enabled": True},
                "design_notes": "选择预测卡而非规则映射。",
            }
        )


class RepeatedThemeLLM:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return json.dumps(
                {
                    "rhythm_blueprint": [
                        {"episode_num": 1},
                        {"episode_num": 2},
                        {"episode_num": 3},
                    ]
                }
            )
        return json.dumps(
            {
                "interaction_points": [
                    {
                        "start_ms": 1000,
                        "end_ms": 7000,
                        "component": "prediction_card",
                        "emotion": "curious",
                        "priority": 0.8,
                        "score_type": "drama",
                        "highlight_reason": "same theme",
                        "config": {},
                    }
                ],
                "episode_end_interaction": {},
            }
        )


def test_interaction_design_agent_uses_llm_design_output(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "output").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"project_id": "demo", "drama_title": "Demo", "total_episodes": 1}),
        encoding="utf-8",
    )
    report = {
        "project_id": "demo",
        "drama_title": "Demo",
        "results": [
            {
                "episode_num": 1,
                "summary": "Su Yu appears.",
                "candidate_interactions": [
                    {
                        "start_ms": 1000,
                        "end_ms": 9000,
                        "anchor_line": "他到底是谁",
                        "emotion_type": "curious",
                        "intensity": 0.8,
                        "reason": "身份悬念",
                        "visual_cue": "角色A抬头",
                    }
                ],
            }
        ],
        "episode_summaries": [{"episode_num": 1, "summary": "Su Yu appears.", "mood": "悬念"}],
        "plot_events": [
            {"episode_num": 1, "start_time": "00:01", "end_time": "00:09", "event_type": "reveal"}
        ],
        "characters": [],
        "plot_threads": [],
        "relationships": [],
    }
    (project / "output" / "report.json").write_text(json.dumps(report), encoding="utf-8")

    results = InteractionDesignAgent(FakeDesignLLM()).run(project_dir=project, output_dir=tmp_path / "outputs")

    manifest = json.loads(results[0].manifest_path.read_text(encoding="utf-8"))
    first = manifest["interaction_points"][0]
    assert first["component"] == "prediction_card"
    assert first["signal_source"] == "interaction_design_agent"
    assert manifest["model_info"]["version"] == "interaction-design-agent-v1"
    blueprint = json.loads((tmp_path / "outputs" / "demo" / "rhythm_blueprint.json").read_text(encoding="utf-8"))
    assert blueprint["rhythm_blueprint"][0]["episode_num"] == 1


def test_safety_rules_shift_boundary_point_to_valid_duration() -> None:
    design = {
        "interaction_points": [
            {
                "id": "ip_ep_001_0001",
                "start_ms": 119000,
                "end_ms": 121000,
                "component": "guardian_shield",
                "emotion": "guard",
                "highlight_reason": "片尾守护",
                "config": {},
            }
        ]
    }

    normalized, warnings = normalize_design_output(design, episode_id="ep_001", duration_ms=120000)

    point = normalized["interaction_points"][0]
    assert point["start_ms"] == 115000
    assert point["end_ms"] == 120000
    assert point["end_ms"] - point["start_ms"] == 5000
    assert warnings == []
    assert any("shifted" in note for note in normalized["repair_notes"])


def test_safety_rules_trim_short_episode_by_density() -> None:
    design = {
        "interaction_points": [
            _point("a", 0, 6000, 0.4),
            _point("b", 16000, 22000, 0.9),
            _point("c", 32000, 38000, 0.8),
            _point("d", 48000, 54000, 0.7),
        ]
    }

    normalized, warnings = normalize_design_output(
        design,
        episode_id="ep_001",
        duration_ms=75000,
        config=DesignConfig(max_points_per_minute=1.5),
    )

    points = normalized["interaction_points"]
    assert [point["id"] for point in points] == ["b", "c"]
    assert warnings == []
    assert any("density config" in note for note in normalized["repair_notes"])


def test_safety_rules_fill_score_type_and_required_config() -> None:
    design = {
        "interaction_points": [
            {
                "id": "ip_ep_001_0001",
                "start_ms": 1000,
                "end_ms": 8000,
                "component": "prediction_card",
                "emotion": "curious",
                "score_type": "emotional",
                "highlight_reason": "身份悬念",
                "config": {},
            }
        ]
    }

    normalized, warnings = normalize_design_output(design, episode_id="ep_001", duration_ms=60000)

    point = normalized["interaction_points"][0]
    assert point["score_type"] == "insight"
    assert len(point["config"]["options"]) == 2
    assert warnings == []
    assert any("G14" in note for note in normalized["repair_notes"])
    assert any("G15" in note for note in normalized["repair_notes"])


def test_interaction_design_agent_warns_on_three_identical_component_sets(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "output").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"project_id": "demo", "drama_title": "Demo", "total_episodes": 3}),
        encoding="utf-8",
    )
    report = {
        "project_id": "demo",
        "drama_title": "Demo",
        "results": [{"episode_num": i, "summary": "same", "candidate_interactions": []} for i in range(1, 4)],
        "episode_summaries": [{"episode_num": i, "summary": "same"} for i in range(1, 4)],
        "plot_events": [],
        "characters": [],
        "plot_threads": [],
        "relationships": [],
    }
    (project / "output" / "report.json").write_text(json.dumps(report), encoding="utf-8")

    results = InteractionDesignAgent(RepeatedThemeLLM()).run(project_dir=project, output_dir=tmp_path / "outputs")

    assert results[2].warnings
    assert results[2].warnings[0].startswith("G9:")


def _point(point_id: str, start_ms: int, end_ms: int, priority: float) -> dict:
    return {
        "id": point_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "component": "prediction_card",
        "emotion": "curious",
        "priority": priority,
        "highlight_reason": "test",
        "config": {},
    }
