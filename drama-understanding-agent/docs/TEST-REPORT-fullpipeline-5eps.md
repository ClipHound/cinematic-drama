# Full Pipeline 5-Episode Test Report

Date: 2026-06-10

## Scope

Test target: `docs/TEST-INSTRUCTION-fullpipeline-5eps.md`

Project: `projects/test-5eps-v2`

Interaction output: `outputs/example-drama-a`

Videos: `<project-root>/样例剧(测试使用)/第1集.mp4` through `第5集.mp4`

## Environment

- ASR endpoint configured in `.env`: `DRAMA_AGENT_ASR_ENDPOINT=http://localhost:10000`
- ASR health check: healthy
- ASR service: `qwen3-asr-server`
- VLM provider: Doubao endpoint from `.env`
- Editable install: completed with `pip install -e .`
- Unit tests before pipeline: `33 passed`

## Commands Run

```powershell
& '<project-root>/.venv\Scripts\python.exe' -m drama_agent.cli run `
  --title '示例剧A' `
  --video-dir '<project-root>/样例剧(测试使用)' `
  --pattern '第{num}集.mp4' `
  --episodes 5 `
  --project-id test-5eps-v2
```

Result: processed 5 episodes.

Elapsed: 638.5 seconds.

```powershell
& '<project-root>/.venv\Scripts\python.exe' -m drama_agent.cli design-interactions `
  --project '<project-root>/drama-understanding-agent\projects\test-5eps-v2' `
  --output-dir '<project-root>/drama-understanding-agent\outputs' `
  --drama-id example-drama-a `
  --video-dir '<project-root>/样例剧(测试使用)' `
  --pattern '第{num}集.mp4'
```

Result: generated 5 interaction manifests.

Elapsed: 223.9 seconds.

## Phase 1 Result

Report generated:

- `projects/test-5eps-v2/output/report.json`
- `projects/test-5eps-v2/output/report.md`

Summary:

| Metric | Value |
| --- | ---: |
| Episodes processed | 5 |
| Characters | 15 |
| Relationships | 3 |
| Plot events | 16 |
| Plot threads | 2 |
| Total candidate_interactions | 25 |

ASR files:

| Episode | ASR available | Segments | VAD segments | Emotion segments |
| --- | --- | ---: | ---: | ---: |
| ep01 | true | 572 | 73 | 0 |
| ep02 | true | 229 | 22 | 0 |
| ep03 | true | 301 | 50 | 0 |
| ep04 | true | 313 | 46 | 0 |
| ep05 | true | 167 | 27 | 0 |

Note: `emotion_segments` is 0 because the ASR service currently has `ENABLE_EMOTION2VEC=0`.

ASR sample from ep01:

```json
{"text": "真", "start_ms": 12880, "end_ms": 12880}
{"text": "要", "start_ms": 12880, "end_ms": 12880}
{"text": "嫁", "start_ms": 12880, "end_ms": 13120}
{"text": "女", "start_ms": 13120, "end_ms": 13200}
{"text": "儿", "start_ms": 13200, "end_ms": 13360}
```

Candidate interaction counts:

| Episode | Count |
| --- | ---: |
| Ep1 | 5 |
| Ep2 | 5 |
| Ep3 | 5 |
| Ep4 | 6 |
| Ep5 | 4 |

## Phase 2 Result

Generated files:

- `outputs/example-drama-a/ep_001.interactions.json`
- `outputs/example-drama-a/ep_002.interactions.json`
- `outputs/example-drama-a/ep_003.interactions.json`
- `outputs/example-drama-a/ep_004.interactions.json`
- `outputs/example-drama-a/ep_005.interactions.json`

Manifest validation:

| Manifest | Points | Warnings | Repairs | Issues |
| --- | ---: | ---: | ---: | --- |
| ep_001.interactions.json | 5 | 0 | 0 | none |
| ep_002.interactions.json | 4 | 0 | 0 | none |
| ep_003.interactions.json | 5 | 0 | 1 | none |
| ep_004.interactions.json | 5 | 0 | 0 | none |
| ep_005.interactions.json | 4 | 0 | 0 | none |

Validation checks performed:

- Required root fields are present.
- Required interaction point fields are present.
- Component names are in the allowed frontend whitelist.
- `sub_type` equals `component`.
- `0 <= start_ms < end_ms <= duration_ms`.
- Interaction duration is within `[5000, 20000]` ms.
- No overlapping final interaction windows.
- No duplicate interaction point IDs.

Component distribution:

| Episode | Components |
| --- | --- |
| Ep1 | anger_release, laugh_burst, tear_resonance, anger_release, prediction_card |
| Ep2 | prediction_card, clue_judge_card, laugh_burst, guardian_shield |
| Ep3 | anger_release, team_cheer, clue_judge_card, tear_resonance, shatter_strike |
| Ep4 | emotion_buffer, team_cheer, anger_release, shatter_strike, laugh_burst |
| Ep5 | laugh_burst, tear_resonance, anger_release, shatter_strike |

## Quality Notes

The main path is the LLM-based interaction designer, not the old rule converter. All generated interaction points use `signal_source=interaction_design_agent`.

The pipeline produced usable frontend manifests with no final `design_warnings` and no structural validation issues.

`ep_003` has one `design_repairs` entry, but the final manifest is valid. This means safety post-processing corrected an intermediate LLM output and no unresolved issue remains.

`ep_004` design notes mention 6 interaction points while the final manifest contains 5. This is a text-only note mismatch from the LLM output; the actual manifest is valid and frontend-consumable.

## ASR Performance Finding

The 5-episode understanding run took longer than expected because the current episode loop runs serially:

`ASR(epN) -> VLM(epN) -> ASR(epN+1) -> VLM(epN+1)`

The ASR server has `GPU_OFFLOAD_SEC=60`. VLM calls took about 60-98 seconds after ASR output per episode, so the ASR model repeatedly unloaded while waiting for remote VLM. Docker logs show:

```text
ASR model idle 69s, offloading GPU->CPU
GPU->CPU offload failed, falling back to full unload
All models unloaded
Lazy-loading ASR model from /app/models/Qwen3-ASR-1.7B...
```

Recommended follow-up:

- Increase ASR `GPU_OFFLOAD_SEC` to `900` or `1800` for full-pipeline runs.
- Refactor the pipeline to batch ASR for all episodes first, then run VLM understanding, so the ASR model stays hot.

## Conclusion

The requested 5-episode full pipeline test is complete.

Status: pass with notes.

Blocking issues: none.

Follow-up optimization: avoid repeated ASR model unload/reload during mixed ASR + VLM serial execution.
