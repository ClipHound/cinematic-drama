from __future__ import annotations

import json
import mimetypes
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from drama_agent.memory.embeddings import EmbeddingClient


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_MANIFEST_RE = re.compile(r"^ep_(\d+)\.interactions\.json$")
_VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v")


def safe_id(value: str) -> str:
    if not _SAFE_ID.match(value):
        raise ValueError(f"invalid id: {value!r}")
    return value


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(slots=True)
class EpisodeRecord:
    number: int
    duration_ms: int = 0
    manifest_path: Path | None = None

    @property
    def id(self) -> str:
        return f"ep_{self.number:03d}"

    @property
    def duration_label(self) -> str:
        if self.duration_ms <= 0:
            return "--:--"
        seconds = round(self.duration_ms / 1000)
        minutes, second = divmod(seconds, 60)
        return f"{minutes:02d}:{second:02d}"


@dataclass(slots=True)
class DramaRecord:
    public_id: str
    project_id: str
    title: str
    description: str
    project_dir: Path
    interactions_dir: Path | None
    episodes: list[EpisodeRecord]


class ContentRepository:
    def __init__(
        self,
        *,
        projects_root: Path,
        outputs_root: Path,
        video_root: Path,
        public_base_url: str = "",
    ) -> None:
        self.projects_root = projects_root
        self.outputs_root = outputs_root
        self.video_root = video_root
        self.public_base_url = public_base_url.rstrip("/")
        self._embedder = EmbeddingClient(
            endpoint=os.getenv("DRAMA_API_EMBED_ENDPOINT", "http://localhost:11434"),
            model=os.getenv("DRAMA_API_EMBED_MODEL", "qwen3-embedding:0.6b"),
        )

    @classmethod
    def from_env(cls, cwd: Path | None = None) -> "ContentRepository":
        base = cwd or Path.cwd()
        projects_root = _env_path("DRAMA_API_PROJECTS_ROOT", base / "projects")
        outputs_root = _env_path("DRAMA_API_OUTPUTS_ROOT", base / "outputs")
        video_root = _env_path("DRAMA_API_VIDEO_ROOT", base / "content" / "videos")
        return cls(
            projects_root=projects_root,
            outputs_root=outputs_root,
            video_root=video_root,
            public_base_url=os.getenv("DRAMA_API_PUBLIC_BASE_URL", ""),
        )

    def list_dramas(self) -> list[dict[str, Any]]:
        return [self.to_drama_item(record) for record in self._records()]

    def get_record(self, drama_id: str) -> DramaRecord:
        safe_id(drama_id)
        for record in self._records():
            aliases = {record.public_id, record.project_id}
            if drama_id in aliases:
                return record
        raise KeyError(drama_id)

    def to_drama_item(self, record: DramaRecord) -> dict[str, Any]:
        report = _read_optional(record.project_dir / "output" / "report.json")
        return {
            "id": record.public_id,
            "title": record.title,
            "subtitle": _subtitle(report, record.description),
            "poster": self._url(f"/api/videos/{record.public_id}/1"),
            "cover": self._url(f"/api/videos/{record.public_id}/1"),
            "genre": _genres(report),
            "heat": f"{len(record.episodes)} 集",
            "score": "暂无评分",
            "description": record.description,
            "episodes": [self.to_episode_item(record, episode) for episode in record.episodes],
        }

    def to_episode_item(self, record: DramaRecord, episode: EpisodeRecord) -> dict[str, Any]:
        number = episode.number
        return {
            "id": episode.id,
            "episodeNumber": number,
            "title": f"第 {number} 集",
            "durationLabel": episode.duration_label,
            "videoUrl": self._url(f"/api/videos/{record.public_id}/{number}"),
            "interactionUrl": self._url(
                f"/api/dramas/{record.public_id}/episodes/{number}/interactions"
            ),
        }

    def get_episode(self, drama_id: str, number: int) -> tuple[DramaRecord, EpisodeRecord]:
        record = self.get_record(drama_id)
        for episode in record.episodes:
            if episode.number == number:
                return record, episode
        raise KeyError(f"{drama_id}:{number}")

    def load_manifest(self, drama_id: str, number: int) -> dict[str, Any]:
        record, episode = self.get_episode(drama_id, number)
        if episode.manifest_path is None or not episode.manifest_path.exists():
            raise FileNotFoundError(f"manifest missing for {record.public_id} episode {number}")
        manifest = read_json(episode.manifest_path)
        manifest["drama_id"] = record.public_id
        manifest["episode_id"] = episode.id
        manifest["video_url"] = self._url(f"/api/videos/{record.public_id}/{number}")
        manifest["source_video_url"] = manifest["video_url"]
        manifest.setdefault("duration_ms", episode.duration_ms)
        manifest.setdefault("video_duration_ms", episode.duration_ms)
        hints = dict(manifest.get("client_hints") or {})
        hints.setdefault("asset_base_url", "/assets/")
        hints.setdefault("ws_enabled", False)
        hints.setdefault("tick_ms", 100)
        manifest["client_hints"] = hints
        return manifest

    def find_video(self, drama_id: str, number: int) -> Path | None:
        record = self.get_record(drama_id)
        names = _video_candidates(number)
        roots = [
            self.video_root / record.public_id,
            self.video_root / record.project_id,
            record.project_dir / "episodes",
            record.project_dir / "videos",
            record.project_dir,
        ]
        for root in roots:
            for name in names:
                path = root / name
                if path.is_file():
                    return path
        return None

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if not needle:
            return []
        docs = self._search_documents()
        query_vector = self._embedder.embed(query)
        ranked: list[tuple[float, dict[str, Any]]] = []
        query_terms = set(_tokens(query))
        for doc in docs:
            text = str(doc.pop("_text"))
            vector = self._embedder.embed(text)
            semantic_score = _cosine(query_vector, vector)
            lexical_score = _lexical_score(needle, query_terms, text.lower())
            score = (semantic_score * 0.7) + (lexical_score * 0.3)
            if lexical_score > 0 or score > 0.18:
                ranked.append((score, doc))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in ranked[:limit]]

    def _search_documents(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for record in self._records():
            drama_item = self.to_drama_item(record)
            results.append(
                {
                    "type": "drama",
                    "dramaId": record.public_id,
                    "title": record.title,
                    "subtitle": drama_item["subtitle"],
                    "poster": drama_item["poster"],
                    "snippet": record.description[:160],
                    "_text": f"{record.title}\n{drama_item['subtitle']}\n{record.description}\n{' '.join(drama_item['genre'])}",
                }
            )
            report_path = record.project_dir / "output" / "report.json"
            if report_path.exists():
                report = read_json(report_path)
                for item in report.get("episode_summaries", []):
                    summary = str(item.get("summary") or "")
                    episode_num = int(item.get("episode_num") or 0)
                    if not summary or episode_num <= 0:
                        continue
                    results.append(
                        {
                            "type": "episode",
                            "dramaId": record.public_id,
                            "episodeNumber": episode_num,
                            "title": f"{record.title} 第 {episode_num} 集",
                            "snippet": summary[:160],
                            "poster": drama_item["poster"],
                            "_text": f"{record.title} 第 {episode_num} 集\n{summary}",
                        }
                    )
        return results

    def _records(self) -> list[DramaRecord]:
        records: list[DramaRecord] = []
        if not self.projects_root.exists():
            return records
        for project_json in sorted(self.projects_root.glob("*/project.json")):
            project_dir = project_json.parent
            try:
                metadata = read_json(project_json)
            except Exception:
                continue
            project_id = str(metadata.get("project_id") or project_dir.name)
            report = _read_optional(project_dir / "output" / "report.json")
            interactions_dir = self._find_interactions_dir(project_id)
            public_id = self._public_id(project_id, interactions_dir)
            episodes = self._episodes(metadata, report, interactions_dir)
            if not episodes:
                continue
            records.append(
                DramaRecord(
                    public_id=public_id,
                    project_id=project_id,
                    title=str(metadata.get("drama_title") or report.get("drama_title") or project_id),
                    description=_description(report),
                    project_dir=project_dir,
                    interactions_dir=interactions_dir,
                    episodes=episodes,
                )
            )
        return sorted(records, key=lambda item: (-len(item.episodes), item.public_id))

    def _episodes(
        self,
        metadata: dict[str, Any],
        report: dict[str, Any],
        interactions_dir: Path | None,
    ) -> list[EpisodeRecord]:
        nums = {int(value) for value in range(1, int(metadata.get("total_episodes") or 0) + 1)}
        nums.update(int(item.get("episode_num") or 0) for item in report.get("results", []))
        nums.update(int(item.get("episode_num") or 0) for item in report.get("episode_summaries", []))
        manifests = _manifest_map(interactions_dir)
        nums.update(manifests)
        episodes: list[EpisodeRecord] = []
        for num in sorted(num for num in nums if num > 0):
            manifest = _read_optional(manifests.get(num)) if num in manifests else {}
            duration_ms = int(
                manifest.get("duration_ms")
                or manifest.get("video_duration_ms")
                or _duration_from_report(report, num)
                or 0
            )
            episodes.append(EpisodeRecord(num, duration_ms, manifests.get(num)))
        return episodes

    def _find_interactions_dir(self, project_id: str) -> Path | None:
        candidates = [
            self.outputs_root / project_id,
            self.outputs_root / project_id / _slug(project_id),
        ]
        candidates.extend(path.parent for path in self.outputs_root.glob(f"**/{project_id}/ep_*.interactions.json"))
        candidates.extend(path.parent for path in self.outputs_root.glob("**/ep_*.interactions.json"))
        best: Path | None = None
        best_count = 0
        for path in candidates:
            if not path.exists():
                continue
            count = len(list(path.glob("ep_*.interactions.json")))
            if count > best_count and _looks_related(project_id, path):
                best = path
                best_count = count
        return best

    def _public_id(self, project_id: str, interactions_dir: Path | None) -> str:
        if interactions_dir:
            first = next(iter(sorted(interactions_dir.glob("ep_*.interactions.json"))), None)
            if first:
                try:
                    drama_id = str(read_json(first).get("drama_id") or "")
                    if drama_id and _SAFE_ID.match(drama_id):
                        return drama_id
                except Exception:
                    pass
        if project_id.endswith("-20eps-final"):
            return project_id.removesuffix("-20eps-final")
        return _slug(project_id)

    def _url(self, path: str) -> str:
        return f"{self.public_base_url}{path}" if self.public_base_url else path


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


def _read_optional(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def _manifest_map(path: Path | None) -> dict[int, Path]:
    if path is None or not path.exists():
        return {}
    result: dict[int, Path] = {}
    for item in path.glob("ep_*.interactions.json"):
        match = _MANIFEST_RE.match(item.name)
        if match:
            result[int(match.group(1))] = item
    return result


def _description(report: dict[str, Any]) -> str:
    for item in report.get("episode_summaries", []):
        summary = str(item.get("summary") or "").strip()
        if summary:
            return summary[:240]
    for item in report.get("results", []):
        summary = str(item.get("summary") or "").strip()
        if summary:
            return summary[:240]
    return "Interactive drama generated from the backend understanding pipeline."


def _subtitle(report: dict[str, Any], description: str) -> str:
    summary = description.strip()
    if summary and summary != "Interactive drama generated from the backend understanding pipeline.":
        return summary[:36]
    title = str(report.get("drama_title") or "").strip()
    return f"{title} 互动短剧" if title else "互动短剧"


def _genres(report: dict[str, Any]) -> list[str]:
    text = json.dumps(report, ensure_ascii=False)
    candidates = [
        ("古装", ("皇帝", "公主", "朝臣", "蛮夷", "侯")),
        ("权谋", ("皇帝", "朝堂", "国体", "权贵")),
        ("爽剧", ("打脸", "反转", "爽", "高手")),
        ("互动", ("interaction", "candidate_interactions", "互动")),
    ]
    genres = [label for label, words in candidates if any(word in text for word in words)]
    return genres[:4] or ["互动短剧"]


def _tokens(text: str) -> list[str]:
    compact = "".join(text.lower().split())
    if not compact:
        return []
    chars = list(compact)
    bigrams = [compact[index : index + 2] for index in range(max(len(compact) - 1, 0))]
    return chars + bigrams


def _lexical_score(needle: str, query_terms: set[str], haystack: str) -> float:
    if not query_terms:
        return 0.0
    exact = 1.0 if needle and needle in haystack else 0.0
    hay_terms = set(_tokens(haystack))
    overlap = len(query_terms & hay_terms) / max(len(query_terms), 1)
    return min(1.0, exact + overlap)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = sum(value * value for value in left[:size]) ** 0.5
    right_norm = sum(value * value for value in right[:size]) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _duration_from_report(report: dict[str, Any], episode_num: int) -> int:
    for result in report.get("results", []):
        if int(result.get("episode_num") or 0) != episode_num:
            continue
        points = result.get("candidate_interactions") or []
        ends = [int(point.get("end_ms") or 0) for point in points if isinstance(point, dict)]
        return (max(ends) + 12000) if ends else 0
    return 0


def _video_candidates(number: int) -> list[str]:
    stems = [
        f"ep_{number:03d}",
        f"ep{number:03d}",
        f"ep{number:02d}",
        f"episode_{number:03d}",
        f"episode_{number}",
        str(number),
    ]
    return [f"{stem}{extension}" for stem in stems for extension in _VIDEO_EXTENSIONS]


def _slug(value: str) -> str:
    return "-".join(part for part in re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).split("-") if part) or "drama"


def _looks_related(project_id: str, path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    slug = _slug(project_id)
    if project_id.lower() in parts or slug in parts:
        return True
    return False


def guess_media_type(path: Path) -> str:
    guessed = mimetypes.guess_type(path.name)[0]
    return guessed or "application/octet-stream"
