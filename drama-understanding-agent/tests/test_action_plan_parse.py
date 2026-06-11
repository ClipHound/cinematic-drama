from drama_agent.engine.action_plan import parse_action_plan


def test_parse_action_plan_plain_json() -> None:
    plan = parse_action_plan('{"episode_summary":"s","actions":[]}')

    assert plan["episode_summary"] == "s"
    assert plan["actions"] == []


def test_parse_action_plan_markdown_fence() -> None:
    plan = parse_action_plan(
        """
        ```json
        {"episode_summary":"s","mood":"m","actions":[]}
        ```
        """
    )

    assert plan["mood"] == "m"


def test_parse_action_plan_returns_error_for_invalid() -> None:
    plan = parse_action_plan("no json here")

    assert plan["_error"] == "parse_failed"
