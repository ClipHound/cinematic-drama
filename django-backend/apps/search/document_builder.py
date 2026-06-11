from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EPISODE_FILE_RE = re.compile(r"^ep_(\d+)\.(understanding|interactions)\.json$")
DRAMA_BODY_CHAR_LIMIT = 12000
EPISODE_BODY_CHAR_LIMIT = 5200


@dataclass(frozen=True)
class BuiltSearchDocument:
    title: str
    body: str
    tags: list[str]


@dataclass(frozen=True)
class DeliveryDramaArtifacts:
    slug: str
    drama_title: str
    total_episodes: int
    episode_summaries: dict[int, dict[str, Any]]
    understandings: dict[int, dict[str, Any]]
    interactions: dict[int, dict[str, Any]]
    characters: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    plot_events: list[dict[str, Any]]
    plot_threads: list[dict[str, Any]]
    branch_narrative: dict[str, Any]


class DeliverySource:
    """Read full-delivery artifacts from either an extracted directory or a zip."""

    def __init__(self, source: str | Path):
        self.source = Path(source)

    def list_slugs(self) -> list[str]:
        if self._is_zip():
            with zipfile.ZipFile(self.source) as archive:
                slugs = {
                    name.split("/", 1)[0]
                    for name in archive.namelist()
                    if name.endswith("/episode_summaries.json") and "/" in name
                }
            return sorted(slugs)

        root = self.source
        if (root / "episode_summaries.json").exists():
            return [root.name]
        return sorted(child.name for child in root.iterdir() if child.is_dir() and (child / "episode_summaries.json").exists())

    def load(self, slug: str) -> DeliveryDramaArtifacts:
        if self._is_zip():
            return self._load_zip(slug)
        return self._load_dir(slug)

    def _is_zip(self) -> bool:
        return self.source.is_file() and self.source.suffix.lower() == ".zip"

    def _load_zip(self, slug: str) -> DeliveryDramaArtifacts:
        if not self.source.exists():
            raise FileNotFoundError(self.source)
        prefix = f"{slug}/"
        understandings: dict[int, dict[str, Any]] = {}
        interactions: dict[int, dict[str, Any]] = {}
        with zipfile.ZipFile(self.source) as archive:
            names = set(archive.namelist())
            if f"{prefix}episode_summaries.json" not in names:
                raise FileNotFoundError(f"{prefix}episode_summaries.json")

            episode_payload = self._read_json_from_zip(archive, f"{prefix}episode_summaries.json")
            characters_payload = self._read_json_from_zip(archive, f"{prefix}characters_index.json", default={})
            report_payload = self._read_json_from_zip(archive, f"{prefix}understanding_report.json", default={})
            branch_payload = self._read_json_from_zip(archive, f"{prefix}branch_narrative.json", default={})

            for name in names:
                if not name.startswith(prefix):
                    continue
                match = EPISODE_FILE_RE.match(name.removeprefix(prefix))
                if not match:
                    continue
                number = int(match.group(1))
                payload = self._read_json_from_zip(archive, name)
                if match.group(2) == "understanding":
                    understandings[number] = payload
                else:
                    interactions[number] = payload

        return _artifacts_from_payloads(slug, episode_payload, characters_payload, report_payload, branch_payload, understandings, interactions)

    def _load_dir(self, slug: str) -> DeliveryDramaArtifacts:
        root = self.source if (self.source / "episode_summaries.json").exists() else self.source / slug
        if not root.exists():
            raise FileNotFoundError(root)

        episode_payload = _read_json(root / "episode_summaries.json")
        characters_payload = _read_json(root / "characters_index.json", default={})
        report_payload = _read_json(root / "understanding_report.json", default={})
        branch_payload = _read_json(root / "branch_narrative.json", default={})
        understandings: dict[int, dict[str, Any]] = {}
        interactions: dict[int, dict[str, Any]] = {}

        for path in root.glob("ep_*.json"):
            match = EPISODE_FILE_RE.match(path.name)
            if not match:
                continue
            number = int(match.group(1))
            if match.group(2) == "understanding":
                understandings[number] = _read_json(path)
            else:
                interactions[number] = _read_json(path)

        return _artifacts_from_payloads(slug, episode_payload, characters_payload, report_payload, branch_payload, understandings, interactions)

    @staticmethod
    def _read_json_from_zip(archive: zipfile.ZipFile, name: str, *, default: Any | None = None) -> Any:
        try:
            with archive.open(name) as handle:
                return json.loads(handle.read().decode("utf-8"))
        except KeyError:
            if default is not None:
                return default
            raise


def build_drama_search_document(
    *,
    drama_title: str,
    subtitle: str = "",
    description: str = "",
    genre_tags: Sequence[str] = (),
    summaries: Sequence[Mapping[str, Any]] = (),
    characters: Sequence[Mapping[str, Any]] = (),
    relationships: Sequence[Mapping[str, Any]] = (),
    plot_threads: Sequence[Mapping[str, Any]] = (),
    branch_narrative: Mapping[str, Any] | None = None,
    interactions_by_episode: Mapping[int, Mapping[str, Any]] | None = None,
) -> BuiltSearchDocument:
    char_names = _character_name_map(characters)
    lines: list[str] = [
        _section("剧名", drama_title),
        _section("类型标签", _join_values(genre_tags)),
        _section("一句话简介", subtitle),
        _section("剧情总览", description or _first_summary_text(summaries)),
    ]

    character_lines = []
    for character in _sort_characters(characters)[:28]:
        name = _clean(character.get("name"))
        if not name:
            continue
        aliases = _join_values(character.get("aliases") or [])
        description_text = _clean(character.get("description"))
        detail = "；".join(part for part in [f"别名：{aliases}" if aliases else "", description_text] if part)
        character_lines.append(f"{name}：{detail}" if detail else name)
    lines.append(_section("主要角色", "；".join(character_lines)))

    relationship_lines = []
    for relationship in relationships[:18]:
        left = _character_ref(relationship.get("character_a"), char_names)
        right = _character_ref(relationship.get("character_b"), char_names)
        relation = _clean(relationship.get("relation"))
        if left and right and relation:
            relationship_lines.append(f"{left}与{right}：{relation}")
    lines.append(_section("角色关系", "；".join(relationship_lines)))

    thread_lines = []
    for thread in plot_threads[:12]:
        title = _clean(thread.get("title"))
        text = _clean(thread.get("description"))
        status = _clean(thread.get("status"))
        if title or text:
            thread_lines.append(f"{title}（{status}）：{text}" if title and status else f"{title}：{text}" if title else text)
    lines.append(_section("剧情线索", "；".join(thread_lines)))

    episode_lines = []
    for summary in sorted(summaries, key=lambda item: int(item.get("episode_num") or 0)):
        number = int(summary.get("episode_num") or 0)
        if not number:
            continue
        text = _limit_chars(_summary_text(summary), 180)
        mood = _clean(summary.get("mood"))
        cliffhanger = _limit_chars(_clean(summary.get("cliffhanger")), 90)
        episode_lines.append(f"第{number}集：{text}" + (f"；情绪：{mood}" if mood else "") + (f"；悬念：{cliffhanger}" if cliffhanger else ""))
    lines.append(_section("分集概要", "\n".join(episode_lines)))

    interaction_lines = []
    for number, manifest in sorted((interactions_by_episode or {}).items()):
        for point in (manifest.get("interaction_points") or [])[:4]:
            title = _clean(point.get("title"))
            key_line = _clean(point.get("key_line"))
            component = _clean(point.get("component"))
            if title or key_line:
                interaction_lines.append(f"第{number}集 {title}（{component}）：{key_line}")
        if len(interaction_lines) >= 32:
            break
    lines.append(_section("互动点", "；".join(interaction_lines)))

    route_lines = []
    for route in (branch_narrative or {}).get("route_tags") or []:
        if not isinstance(route, Mapping):
            continue
        name = _clean(route.get("name"))
        theme = _clean(route.get("theme"))
        emotion_arc = _limit_chars(_clean(route.get("emotion_arc")), 120)
        route_lines.append("：".join(part for part in [name, theme, emotion_arc] if part))
    lines.append(_section("分支叙事", "；".join(route_lines)))

    tags = _unique_strings(
        [
            *genre_tags,
            drama_title,
            *_names_from_characters(characters),
            *(_clean(thread.get("title")) for thread in plot_threads),
            *(_clean(route.get("name")) for route in (branch_narrative or {}).get("route_tags") or [] if isinstance(route, Mapping)),
        ],
        limit=90,
    )
    return BuiltSearchDocument(title=drama_title, body=_limit_chars(_join_sections(lines), DRAMA_BODY_CHAR_LIMIT), tags=tags)


def build_episode_search_document(
    *,
    drama_title: str,
    episode_number: int,
    episode_title: str = "",
    summary: Mapping[str, Any] | str | None = None,
    understanding: Mapping[str, Any] | None = None,
    interactions: Mapping[str, Any] | None = None,
    characters: Sequence[Mapping[str, Any]] = (),
    relationships: Sequence[Mapping[str, Any]] = (),
    plot_events: Sequence[Mapping[str, Any]] = (),
    plot_threads: Sequence[Mapping[str, Any]] = (),
    genre_tags: Sequence[str] = (),
) -> BuiltSearchDocument:
    summary_data = _normalise_summary(summary, understanding)
    understanding = understanding or {}
    interactions = interactions or {}
    char_names = _character_name_map(characters)
    mentioned_names = _mentioned_character_names(understanding, summary_data, characters, plot_events, episode_number)

    lines = [
        _section("剧名", drama_title),
        _section("集数", f"第{episode_number}集 {episode_title}".strip()),
        _section("本集摘要", _summary_text(summary_data) or _summary_text(understanding)),
        _section("情绪基调", _clean(summary_data.get("mood") or understanding.get("mood"))),
        _section("悬念钩子", _clean(summary_data.get("cliffhanger") or understanding.get("cliffhanger"))),
        _section("出场角色", _episode_character_lines(mentioned_names, characters)),
    ]

    event_lines = []
    for event in _episode_plot_events(plot_events, episode_number):
        time_label = _time_range(event)
        event_type = _clean(event.get("event_type"))
        description = _clean(event.get("description"))
        names = _join_values(_character_ref(value, char_names) for value in event.get("characters") or [])
        prefix = " ".join(part for part in [time_label, event_type] if part)
        suffix = f"（角色：{names}）" if names else ""
        if description:
            event_lines.append(f"{prefix}：{description}{suffix}" if prefix else f"{description}{suffix}")
    key_events = [_clean(value) for value in summary_data.get("key_events") or [] if _clean(value)]
    lines.append(_section("关键事件", "；".join([*key_events, *event_lines[:10]])))

    active_threads = []
    active_thread_titles = []
    for thread in plot_threads:
        opened_at = _to_int(thread.get("opened_at"))
        resolved_at = _to_int(thread.get("resolved_at"))
        if opened_at and opened_at > episode_number:
            continue
        if resolved_at and resolved_at < episode_number:
            continue
        title = _clean(thread.get("title"))
        description = _clean(thread.get("description"))
        if title or description:
            if title:
                active_thread_titles.append(title)
            active_threads.append(f"{title}：{description}" if title else description)
        if len(active_threads) >= 8:
            break
    lines.append(_section("相关线索", "；".join(active_threads)))

    interaction_lines = []
    for point in (interactions.get("interaction_points") or [])[:12]:
        if not isinstance(point, Mapping):
            continue
        title = _clean(point.get("title"))
        component = _clean(point.get("component") or point.get("sub_type"))
        emotion = _clean(point.get("emotion"))
        key_line = _clean(point.get("key_line"))
        reason = _clean(point.get("highlight_reason"))
        label = "/".join(part for part in [component, emotion] if part)
        interaction_lines.append("；".join(part for part in [f"{title}（{label}）" if label else title, f"台词：{key_line}" if key_line else "", reason] if part))
    for point in (understanding.get("candidate_interactions") or [])[:8]:
        if not isinstance(point, Mapping):
            continue
        anchor = _clean(point.get("anchor_line"))
        emotion = _clean(point.get("emotion_type"))
        reason = _clean(point.get("reason"))
        interaction_lines.append("；".join(part for part in [f"候选互动（{emotion}）" if emotion else "候选互动", f"台词：{anchor}" if anchor else "", reason] if part))
    lines.append(_section("互动看点", "；".join(_unique_strings(interaction_lines, limit=18))))

    tags = _unique_strings(
        [
            *genre_tags,
            drama_title,
            f"第{episode_number}集",
            *mentioned_names,
            *_emotion_tokens(_clean(summary_data.get("mood") or understanding.get("mood"))),
            *(_clean(point.get("component") or point.get("sub_type") or point.get("title")) for point in interactions.get("interaction_points") or [] if isinstance(point, Mapping)),
            *active_thread_titles,
        ],
        limit=80,
    )
    title = f"{drama_title} 第 {episode_number} 集"
    return BuiltSearchDocument(title=title, body=_limit_chars(_join_sections(lines), EPISODE_BODY_CHAR_LIMIT), tags=tags)


def build_drama_document_from_artifacts(artifacts: DeliveryDramaArtifacts, genre_tags: Sequence[str] = ()) -> BuiltSearchDocument:
    summaries = list(artifacts.episode_summaries.values())
    return build_drama_search_document(
        drama_title=artifacts.drama_title,
        subtitle=_drama_subtitle(artifacts),
        description=_drama_description(artifacts),
        genre_tags=genre_tags,
        summaries=summaries,
        characters=artifacts.characters,
        relationships=artifacts.relationships,
        plot_threads=artifacts.plot_threads,
        branch_narrative=artifacts.branch_narrative,
        interactions_by_episode=artifacts.interactions,
    )


def build_episode_document_from_artifacts(
    artifacts: DeliveryDramaArtifacts,
    episode_number: int,
    *,
    episode_title: str = "",
    genre_tags: Sequence[str] = (),
) -> BuiltSearchDocument:
    return build_episode_search_document(
        drama_title=artifacts.drama_title,
        episode_number=episode_number,
        episode_title=episode_title,
        summary=artifacts.episode_summaries.get(episode_number),
        understanding=artifacts.understandings.get(episode_number),
        interactions=artifacts.interactions.get(episode_number),
        characters=artifacts.characters,
        relationships=artifacts.relationships,
        plot_events=artifacts.plot_events,
        plot_threads=artifacts.plot_threads,
        genre_tags=genre_tags,
    )


def infer_genre_tags(artifacts: DeliveryDramaArtifacts) -> list[str]:
    text = json.dumps(
        {
            "title": artifacts.drama_title,
            "summaries": list(artifacts.episode_summaries.values())[:5],
            "threads": artifacts.plot_threads,
        },
        ensure_ascii=False,
    )
    rules = [
        ("古装", ("皇帝", "公主", "朝堂", "侯府", "王朝")),
        ("仙侠", ("修仙", "仙", "灵根", "宗门")),
        ("权谋", ("朝堂", "权贵", "谋逆", "皇权")),
        ("爽剧", ("打脸", "逆袭", "复仇", "碾压", "反转")),
        ("悬疑", ("悬疑", "真相", "凶手", "案件")),
        ("盗墓", ("古墓", "盗墓", "墓穴", "寻宝")),
        ("现实", ("工人", "打工", "返乡", "家庭", "工厂")),
        ("情感", ("离婚", "闪婚", "婚姻", "未婚夫")),
        ("年代", ("厂", "改革", "年代", "总厂")),
        ("互动", ("interaction_points", "互动", "预测", "投票")),
    ]
    tags = [label for label, keywords in rules if any(keyword in text for keyword in keywords)]
    return tags or ["互动短剧"]


def _artifacts_from_payloads(
    slug: str,
    episode_payload: Mapping[str, Any],
    characters_payload: Mapping[str, Any],
    report_payload: Mapping[str, Any],
    branch_payload: Mapping[str, Any],
    understandings: dict[int, dict[str, Any]],
    interactions: dict[int, dict[str, Any]],
) -> DeliveryDramaArtifacts:
    summary_items = episode_payload.get("episodes") or episode_payload.get("episode_summaries") or report_payload.get("episode_summaries") or []
    episode_summaries = {_to_int(item.get("episode_num")): dict(item) for item in summary_items if isinstance(item, Mapping) and _to_int(item.get("episode_num"))}
    for item in report_payload.get("results") or []:
        if not isinstance(item, Mapping):
            continue
        number = _to_int(item.get("episode_num"))
        if number and number not in episode_summaries:
            episode_summaries[number] = dict(item)

    characters = list(report_payload.get("characters") or characters_payload.get("characters") or [])
    title = _clean(episode_payload.get("drama_title") or report_payload.get("drama_title") or slug)
    total = _to_int(episode_payload.get("total_episodes") or len(episode_summaries) or max([*episode_summaries.keys(), *understandings.keys(), *interactions.keys(), 0]))
    return DeliveryDramaArtifacts(
        slug=slug,
        drama_title=title,
        total_episodes=total,
        episode_summaries=episode_summaries,
        understandings=understandings,
        interactions=interactions,
        characters=[dict(item) for item in characters if isinstance(item, Mapping)],
        relationships=[dict(item) for item in report_payload.get("relationships") or [] if isinstance(item, Mapping)],
        plot_events=[dict(item) for item in report_payload.get("plot_events") or [] if isinstance(item, Mapping)],
        plot_threads=[dict(item) for item in report_payload.get("plot_threads") or [] if isinstance(item, Mapping)],
        branch_narrative=dict(branch_payload) if isinstance(branch_payload, Mapping) else {},
    )


def _read_json(path: Path, *, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _drama_description(artifacts: DeliveryDramaArtifacts) -> str:
    if artifacts.plot_threads:
        main_threads = [thread for thread in artifacts.plot_threads if thread.get("thread_type") == "mainplot"]
        thread = (main_threads or artifacts.plot_threads)[0]
        if _clean(thread.get("description")):
            return _clean(thread.get("description"))
    return _first_summary_text(artifacts.episode_summaries.values())


def _drama_subtitle(artifacts: DeliveryDramaArtifacts) -> str:
    first = next(iter(sorted(artifacts.episode_summaries.values(), key=lambda item: int(item.get("episode_num") or 0))), {})
    return _limit_chars(_clean(first.get("mood")), 72)


def _normalise_summary(summary: Mapping[str, Any] | str | None, understanding: Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(summary, str):
        summary_data: dict[str, Any] = {"summary": summary}
    elif isinstance(summary, Mapping):
        summary_data = dict(summary)
    else:
        summary_data = {}
    if "summary" not in summary_data and "episode_summary" in summary_data:
        summary_data["summary"] = summary_data.get("episode_summary")
    for key in ("episode_summary", "mood", "cliffhanger", "characters_mentioned"):
        if not summary_data.get(key) and understanding and understanding.get(key):
            summary_data[key] = understanding.get(key)
    return summary_data


def _summary_text(item: Mapping[str, Any] | None) -> str:
    if not item:
        return ""
    return _clean(item.get("summary") or item.get("episode_summary"))


def _first_summary_text(summaries: Iterable[Mapping[str, Any]]) -> str:
    for summary in sorted(summaries, key=lambda item: int(item.get("episode_num") or 0)):
        text = _summary_text(summary)
        if text:
            return text
    return ""


def _sort_characters(characters: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        characters,
        key=lambda item: (
            0 if _clean(item.get("status")) == "active" else 1,
            _to_int(item.get("first_seen")) or 9999,
            _clean(item.get("name")),
        ),
    )


def _names_from_characters(characters: Sequence[Mapping[str, Any]]) -> list[str]:
    return [_clean(item.get("name")) for item in _sort_characters(characters) if _clean(item.get("name"))]


def _character_name_map(characters: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in characters:
        name = _clean(item.get("name"))
        if not name:
            continue
        for key in [item.get("id"), name, *(item.get("aliases") or [])]:
            text = _clean(key)
            if text:
                result[text] = name
    return result


def _character_ref(value: Any, name_map: Mapping[str, str]) -> str:
    text = _clean(value)
    return name_map.get(text, text)


def _mentioned_character_names(
    understanding: Mapping[str, Any],
    summary_data: Mapping[str, Any],
    characters: Sequence[Mapping[str, Any]],
    plot_events: Sequence[Mapping[str, Any]],
    episode_number: int,
) -> list[str]:
    name_map = _character_name_map(characters)
    names = [_character_ref(value, name_map) for value in understanding.get("characters_mentioned") or summary_data.get("characters_mentioned") or []]
    for event in _episode_plot_events(plot_events, episode_number):
        names.extend(_character_ref(value, name_map) for value in event.get("characters") or [])
    return _unique_strings(names, limit=18)


def _episode_character_lines(names: Sequence[str], characters: Sequence[Mapping[str, Any]]) -> str:
    by_name = {_clean(item.get("name")): item for item in characters if _clean(item.get("name"))}
    lines = []
    for name in names[:12]:
        description = _limit_chars(_clean(by_name.get(name, {}).get("description")), 120)
        lines.append(f"{name}：{description}" if description else name)
    return "；".join(lines)


def _episode_plot_events(plot_events: Sequence[Mapping[str, Any]], episode_number: int) -> list[Mapping[str, Any]]:
    events = [event for event in plot_events if _to_int(event.get("episode_num")) == episode_number]
    return sorted(events, key=lambda item: (_clean(item.get("start_time")), -float(item.get("importance") or 0)))


def _time_range(item: Mapping[str, Any]) -> str:
    start = _clean(item.get("start_time"))
    end = _clean(item.get("end_time"))
    if start and end:
        return f"{start}-{end}"
    return start or end


def _emotion_tokens(text: str) -> list[str]:
    if not text:
        return []
    tokens = re.split(r"[，,、；;\s]+", text)
    return [token for token in tokens if 1 < len(token) <= 12][:10]


def _section(label: str, value: Any) -> str:
    text = _clean(value)
    return f"【{label}】{text}" if text else ""


def _join_sections(lines: Iterable[str]) -> str:
    return "\n".join(line for line in lines if line)


def _join_values(values: Iterable[Any]) -> str:
    return "、".join(_unique_strings([_clean(value) for value in values]))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _unique_strings(values: Iterable[Any], *, limit: int | None = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean(value)
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
        if limit and len(result) >= limit:
            break
    return result


def _limit_chars(text: str, limit: int) -> str:
    text = _clean(text)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."
