from __future__ import annotations

from drama_agent.engine.episode_types import EpisodeContext


SYSTEM_PROMPT = """You are a professional short-drama analysis agent.
You watch episodes sequentially and maintain structured story memory.

Your task:
1. Watch the current episode video.
2. Use existing character and plot memory as context.
3. Output a JSON Action Plan telling the system what to update.
4. Also identify candidate_interactions: precise moments where viewers may want to interact.

Return only valid JSON. Do not include markdown or extra commentary.
"""


def build_episode_prompt(ctx: EpisodeContext, drama_title: str, total_episodes: int) -> str:
    characters = "\n".join(
        f"- {c.get('name', '')}: {c.get('description', '')[:160]}" for c in ctx.known_characters
    ) or "(none)"
    threads = "\n".join(
        f"- {t.get('title', '')}: {t.get('description', '')[:140]}" for t in ctx.open_threads
    ) or "(none)"
    previous = ctx.previous_summary or "(none)"
    asr_text = ctx.asr_text or "(none)"

    return f"""## Current State

Episode: {ctx.episode_num} / {total_episodes}
Drama title: {drama_title}

## Known Characters
{characters}

## Open Plot Threads
{threads}

## Previous Episode Summary
{previous}

## Current Episode ASR
{asr_text}

## Required Output

Return this JSON object:

{{
  "episode_summary": "150-300 Chinese characters",
  "mood": "episode mood",
  "cliffhanger": "ending hook if any",
  "candidate_interactions": [
    {{
      "start_ms": 47000,
      "end_ms": 55000,
      "anchor_line": "representative dialogue if any",
      "emotion_type": "anger|sweet|funny|sad|shocking|satisfying|tense|curious|guard|absurd|indignant|bittersweet|anticipation",
      "intensity": 0.9,
      "reason": "why viewers will have a strong emotional reaction here",
      "visual_cue": "the strongest visual element at this moment",
      "is_cliffhanger": false
    }}
  ],
  "actions": [
    {{
      "action": "upsert_character",
      "name": "character name",
      "match_existing": null,
      "match_confidence": 0.95,
      "description": "complete character description",
      "aliases": [],
      "emotion": "emotion in this episode",
      "goal": "goal in this episode",
      "identity_change": "",
      "appearance": ""
    }},
    {{
      "action": "update_relationship",
      "character_a": "A",
      "character_b": "B",
      "relation": "relationship description",
      "direction": "a_to_b | b_to_a | bidirectional",
      "is_new": true
    }},
    {{
      "action": "append_plot_event",
      "start_time": "MM:SS",
      "end_time": "MM:SS",
      "event_type": "setup|conflict|climax|resolution|reveal|twist",
      "description": "event description",
      "characters": [],
      "importance": 0.8
    }},
    {{
      "action": "update_plot_thread",
      "title": "thread title",
      "description": "thread detail",
      "thread_type": "foreshadow|mystery|subplot|mainplot",
      "status": "open|resolved",
      "resolution": "",
      "characters": []
    }},
    {{
      "action": "capture_frame",
      "timestamp": "MM:SS",
      "purpose": "character_anchor|evidence|key_scene",
      "target": "character name or evidence description",
      "description": "what this frame shows"
    }},
    {{
      "action": "update_series_state",
      "field": "main_plot_summary|genre|setting|tone",
      "value": "new value"
    }},
    {{
      "action": "mark_uncertain",
      "category": "identity|contradiction|timeline",
      "description": "uncertainty",
      "related_characters": []
    }}
  ]
}}

Only include actions that are needed.
Use stable character names and set match_existing when an observed character is the same as a known character.
Use ASR timestamps when available. candidate_interactions must use millisecond start_ms/end_ms,
prefer 3-6 strong points per episode, and avoid weak filler moments.

emotion_type guidance:
- funny: viewers will clearly laugh. If the scene is only absurd/ridiculous but not comedic, use absurd.
- anger: general anger. If the anger is moral outrage about injustice, bullying, abuse, or invasion, use indignant.
- bittersweet: sadness and sweetness coexist.
- anticipation: viewers are eager to see an expected payoff, not merely curious.
"""
