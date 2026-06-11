# Full Pipeline 5-Episode V2 Improvement Test Report

Date: 2026-06-10

Source plan: `docs/10-iteration-v2-improvements.md`

## Summary

V2 improvements have been implemented and validated.

Status: pass with notes.

## Implemented Changes

### 1. ASR sentence-level merge

Added sentence-level ASR compaction while preserving raw character-level `segments`.

Files:

- `src/drama_agent/asr/sentence_merger.py`
- `src/drama_agent/asr/client.py`
- `src/interaction_designer/context_builder.py`

Result:

| Episode | Raw segments | Sentences | Prompt lines | Prompt chars |
| --- | ---: | ---: | ---: | ---: |
| Ep1 | 572 | 31 | 31 | 1321 |
| Ep2 | 229 | 12 | 12 | 541 |
| Ep3 | 301 | 13 | 13 | 636 |
| Ep4 | 313 | 21 | 21 | 832 |
| Ep5 | 167 | 19 | 19 | 640 |

Previous Ep1 prompt was about 500+ ASR lines. V2 reduces it to 31 lines.

### 2. ASR batch pre-run

`EpisodeLoop.run()` now runs ASR for all missing episodes before the VLM loop.

Observed execution:

```text
ASR ep01: start
ASR ep01: done
ASR ep02: start
ASR ep02: done
ASR ep03: start
ASR ep03: done
ASR ep04: start
ASR ep04: done
ASR ep05: start
ASR ep05: done
Processed 5 episode(s).
```

Timing:

| Run | Phase 1 time |
| --- | ---: |
| Before V2 | 638.5s |
| After V2 | 516.7s |

Improvement: about 19% faster in this run.

### 3. Pass 1 blueprint persistence

The global rhythm blueprint is now saved and can be reused with `--blueprint`.

Output:

```text
outputs/v3-rerun/example-drama-a/rhythm_blueprint.json
```

Validated:

- Blueprint file exists.
- `--blueprint` rerun completed.
- Rerun skipped Pass 1 and reused the saved blueprint.

### 4. Configurable interaction density and short-episode downsampling

Added `DesignConfig` and CLI `--config`.

Defaults:

- `max_points_per_minute = 1.5`
- `min_points_per_episode = 2`
- `max_points_per_episode = 8`
- `max_coverage_ratio = 0.35`
- `min_gap_ms = 10000`

Result on V2 rerun:

| Episode | Duration ms | Points | Coverage | Warnings | Issues |
| --- | ---: | ---: | ---: | ---: | --- |
| Ep1 | 308991 | 5 | 15.5% | 0 | none |
| Ep2 | 75477 | 2 | 26.5% | 0 | none |
| Ep3 | 183252 | 4 | 15.3% | 0 | none |
| Ep4 | 183808 | 3 | 17.4% | 0 | none |
| Ep5 | 108608 | 2 | 23.0% | 0 | none |

Ep2 and Ep5 are now downsampled to 2 points and remain below 35% coverage.

### 5. Video duration fallback

Duration inference now uses:

1. `ffprobe`
2. ASR `vad_end_ms` / `vad_segments`
3. Manifest interaction max end time fallback

This gives Pass 2 and safety rules a more reliable duration for density control.

### 6. Duration/density injected into Pass 2

Each episode context now includes:

- `duration_ms`
- `density_instruction`
- compact sentence-level ASR

Pass 2 prompt now instructs the LLM to follow the target interaction count range, not just a fixed `3-8` rule.

## Commands Run

```powershell
& '<project-root>/.venv\Scripts\python.exe' -m pytest -q
```

Result:

```text
35 passed
```

```powershell
& '<project-root>/.venv\Scripts\python.exe' -m drama_agent.cli run `
  --title '示例剧A' `
  --video-dir '<project-root>/样例剧(测试使用)' `
  --pattern '第{num}集.mp4' `
  --episodes 5 `
  --project-id test-5eps-v3
```

Result:

```text
Processed 5 episode(s).
Report: projects\test-5eps-v3\output\report.md
```

```powershell
& '<project-root>/.venv\Scripts\python.exe' -m drama_agent.cli design-interactions `
  --project '<project-root>/drama-understanding-agent\projects\test-5eps-v3' `
  --output-dir '<project-root>/drama-understanding-agent\outputs\v3-rerun' `
  --drama-id example-drama-a `
  --video-dir '<project-root>/样例剧(测试使用)' `
  --pattern '第{num}集.mp4' `
  --blueprint '<project-root>/drama-understanding-agent\outputs\v3-default\example-drama-a\rhythm_blueprint.json'
```

Result:

```text
Ep01: 5 interaction(s)
Ep02: 2 interaction(s)
Ep03: 4 interaction(s)
Ep04: 3 interaction(s)
Ep05: 2 interaction(s)
```

## Generated Artifacts

Project:

```text
projects/test-5eps-v3/
```

Interaction outputs:

```text
outputs/v3-rerun/example-drama-a/
```

Important files:

```text
projects/test-5eps-v3/asr/ep01.json
projects/test-5eps-v3/output/report.json
outputs/v3-rerun/example-drama-a/rhythm_blueprint.json
outputs/v3-rerun/example-drama-a/ep_001.interactions.json
outputs/v3-rerun/example-drama-a/ep_002.interactions.json
outputs/v3-rerun/example-drama-a/ep_003.interactions.json
outputs/v3-rerun/example-drama-a/ep_004.interactions.json
outputs/v3-rerun/example-drama-a/ep_005.interactions.json
```

## Notes

- `emotion_segments` still remains empty because ASR service has `ENABLE_EMOTION2VEC=0`; this is service configuration, not agent code.
- The first `v3-default` design run produced Ep2 with only 1 point because the prompt only stated an upper limit. The prompt was then changed to include an explicit target range, and `v3-rerun` produced Ep2 with 2 points.
- `interaction_generator/` was not modified, per the V2 instruction.

## Conclusion

V2 implementation is complete.

The main measurable improvements are:

- ASR prompt noise reduced from hundreds of character-level lines to sentence-level context.
- Full 5-episode Phase 1 runtime improved from 638.5s to 516.7s.
- Pass 1 global rhythm blueprint is now auditable and reusable.
- Short episodes are automatically downsampled to lower interaction density.
- Final manifests have no warnings, no interval issues, and coverage below 35%.
