from drama_agent.engine.reporting import render_markdown_report


def test_report_markdown_includes_narrative_sections_and_names() -> None:
    payload = {
        "project_id": "demo",
        "drama_title": "Demo",
        "episodes_processed": 1,
        "results": [
            {
                "episode_num": 1,
                "summary": "Su Yu appears.",
                "actions_total": 2,
                "actions_succeeded": 2,
                "actions_failed": 0,
                "patches_committed": 3,
                "errors": [],
            }
        ],
        "episode_summaries": [
            {"episode_num": 1, "summary": "Su Yu appears.", "mood": "tense", "cliffhanger": "hook"}
        ],
        "characters": [
            {
                "id": "char-suyu",
                "name": "Su Yu",
                "aliases": ["Su Gongzi"],
                "description": "Hidden master",
                "first_seen": 1,
                "last_seen": 1,
                "status": "active",
                "confidence": 0.95,
            },
            {
                "id": "char-emperor",
                "name": "Emperor",
                "aliases": [],
                "description": "Ruler",
                "first_seen": 1,
                "last_seen": 1,
                "status": "active",
                "confidence": 0.9,
            },
        ],
        "relationships": [
            {
                "character_a": "char-emperor",
                "character_b": "char-suyu",
                "relation": "distrusts him",
            }
        ],
        "plot_threads": [
            {
                "title": "Hidden identity",
                "description": "Su Yu is more than he appears.",
                "thread_type": "mystery",
                "status": "open",
                "opened_at": 1,
                "characters": ["char-suyu"],
            }
        ],
        "plot_events": [
            {
                "episode_num": 1,
                "start_time": "00:10",
                "event_type": "reveal",
                "description": "Su Yu shows power.",
                "characters": ["char-suyu"],
            }
        ],
    }

    report = render_markdown_report(payload)

    assert "## Episode Summaries" in report
    assert "## Characters" in report
    assert "## Relationships" in report
    assert "## Plot Threads" in report
    assert "## Timeline" in report
    assert "**Emperor** ↔ **Su Yu**" in report
    assert "Characters: Su Yu" in report
