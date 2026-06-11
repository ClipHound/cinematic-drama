from interaction_designer.safety_rules import _check_exclusion_rules


def test_team_cheer_with_violence_keyword_becomes_anger_release() -> None:
    point = {
        "component": "team_cheer",
        "emotion": "support",
        "key_line": "蛮夷当众强抢民女",
        "highlight_reason": "对峙场景",
        "key_visual": "",
        "title": "",
        "config": {"sides": [{"label": "示例王朝"}, {"label": "蛮夷"}]},
        "score_type": "cocreate",
    }
    repairs: list[str] = []

    result = _check_exclusion_rules(point, {}, repairs)

    assert result["component"] == "anger_release"
    assert result["emotion"] == "angry"
    assert result["config"] == {}
    assert any("G16" in item for item in repairs)


def test_team_cheer_valid_moral_choice_is_kept() -> None:
    point = {
        "component": "team_cheer",
        "emotion": "support",
        "key_line": "主战派认为应该迎击，主和派认为应该议和",
        "highlight_reason": "两种合理立场的对抗",
        "key_visual": "",
        "title": "",
        "config": {"sides": [{"label": "主战"}, {"label": "主和"}]},
        "score_type": "cocreate",
    }
    repairs: list[str] = []

    result = _check_exclusion_rules(point, {}, repairs)

    assert result["component"] == "team_cheer"
    assert repairs == []


def test_laugh_burst_absurd_but_not_funny_becomes_buffer() -> None:
    point = {
        "component": "laugh_burst",
        "emotion": "funny",
        "key_line": "今天全场消费都由本公子买单",
        "highlight_reason": "纨绔人设建立，荒诞挥霍",
        "key_visual": "银票满地，女子哄抢",
        "title": "撒金",
        "config": {},
        "score_type": "resonance",
    }
    repairs: list[str] = []

    result = _check_exclusion_rules(point, {}, repairs)

    assert result["component"] == "emotion_buffer"
    assert result["emotion"] == "buffer"
    assert any("G17" in item for item in repairs)


def test_laugh_burst_genuine_comedy_is_kept() -> None:
    point = {
        "component": "laugh_burst",
        "emotion": "funny",
        "key_line": "他一本正经说了句完全搞笑的推理",
        "highlight_reason": "滑稽的推理让人笑喷",
        "key_visual": "",
        "title": "",
        "config": {},
        "score_type": "resonance",
    }
    repairs: list[str] = []

    result = _check_exclusion_rules(point, {}, repairs)

    assert result["component"] == "laugh_burst"
    assert repairs == []
