import json
from pathlib import Path

from branch_narrative.agent import BranchNarrativeAgent


class FakeBranchLLM:
    def __init__(self):
        self.calls = 0

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return json.dumps({})
        if "结局概要" in user_prompt:
            return json.dumps(
                {
                    "ending_title": "光明结局",
                    "ending_subtitle": "尘埃落定",
                    "narrative": {
                        "paragraphs": ["角色A完成最后的选择，示例王朝重归安宁。"],
                        "scene_description": "皇城清晨",
                        "mood": "resolved",
                    },
                    "epilogue": "三个月后，示例王朝国境安定。",
                    "character_fates": {"角色A": "守护示例王朝"},
                }
            )
        return json.dumps(
            {
                "route_tag": "justice",
                "narrative": {
                    "title": "命运再起",
                    "paragraphs": ["正片落幕后，新的选择摆在角色A面前。"],
                    "scene_description": "镇北侯府",
                    "characters_present": ["角色A"],
                    "mood": "tense",
                },
                "choices": [
                    {"option_text": "公开真相", "option_subtext": "正面迎战"},
                    {"option_text": "暗中布局", "option_subtext": "等待时机"},
                ],
                "audio_hint": {"bgm_mood": "tense", "sfx_suggestion": "wind"},
            }
        )


def test_branch_narrative_agent_writes_package(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "output").mkdir(parents=True)
    report = {
        "project_id": "demo",
        "drama_title": "Demo",
        "episodes_processed": 1,
        "characters": [{"name": "角色A", "description": "隐忍"}],
        "relationships": [],
        "plot_threads": [{"thread_id": "t1", "status": "open", "description": "未尽风波"}],
        "episode_summaries": [{"episode_num": 1, "summary": "角色A获胜"}],
        "plot_events": [],
        "results": [{"episode_num": 1, "candidate_interactions": []}],
    }
    (project / "output" / "report.json").write_text(json.dumps(report), encoding="utf-8")

    result = BranchNarrativeAgent(FakeBranchLLM()).run(
        project_dir=project,
        output_dir=tmp_path / "outputs",
        drama_id="demo",
    )

    package = json.loads(result.package_path.read_text(encoding="utf-8"))
    assert package["entry_node"] == "n_opening"
    assert len(package["endings"]) == 3
    assert package["metadata"]["total_nodes"] <= 25
    assert package["nodes"]["n_opening"]["choices"]
    assert result.warnings == []
