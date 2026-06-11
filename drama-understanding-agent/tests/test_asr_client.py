from drama_agent.asr.client import format_asr_for_prompt, normalize_asr_response


def test_normalize_asr_response_and_format_prompt() -> None:
    result = normalize_asr_response(
        {
            "text": "你敢",
            "language": "Chinese",
            "time_stamps": [{"text": "你敢", "start_time": 47.23, "end_time": 48.9}],
            "emotion_segments": [{"emotion": "angry", "start_ms": 47000, "end_ms": 49000, "score": 0.87}],
        }
    )

    prompt = format_asr_for_prompt(result.model_dump())

    assert result.segments[0]["start_ms"] == 47230
    assert "[00:47.230-00:48.900] 你敢" in prompt
    assert "[emotion:angry@0.87]" in prompt


def test_format_prompt_uses_sentence_level_segments() -> None:
    result = normalize_asr_response(
        {
            "segments": [
                {"text": "你", "start_ms": 1000, "end_ms": 1100},
                {"text": "敢", "start_ms": 1100, "end_ms": 1200},
                {"text": "吗", "start_ms": 1200, "end_ms": 1300},
                {"text": "我", "start_ms": 2200, "end_ms": 2300},
                {"text": "敢", "start_ms": 2300, "end_ms": 2400},
            ],
            "vad_segments": [
                {"type": "speech", "start_ms": 900, "end_ms": 1400},
                {"type": "speech", "start_ms": 2100, "end_ms": 2500},
            ],
        }
    )

    prompt = format_asr_for_prompt(result.model_dump())

    assert len(result.segments) == 5
    assert result.sentences == [
        {"text": "你敢吗", "start_ms": 1000, "end_ms": 1300},
        {"text": "我敢", "start_ms": 2200, "end_ms": 2400},
    ]
    assert "[00:01.000-00:01.300] 你敢吗" in prompt
    assert "[00:02.200-00:02.400] 我敢" in prompt
    assert "[00:01.000-00:01.100] 你" not in prompt
