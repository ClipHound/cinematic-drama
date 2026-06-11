from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.catalog.models import Drama, Episode
from apps.interactions.models import InteractionManifest, InteractionPoint
from apps.search.models import SearchDocument


MANIFEST_RE = re.compile(r"^ep_(\d+)\.interactions\.json$")
VIDEO_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v")


class Command(BaseCommand):
    help = "Import existing offline agent artifacts into the Django online database."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--root", default=str(settings.LEGACY_AGENT_ROOT))
        parser.add_argument("--slug", default="")
        parser.add_argument("--project-id", default="")
        parser.add_argument("--publish", action="store_true", default=True)

    def handle(self, *args, **options) -> None:
        root = Path(options["root"]).resolve()
        project_id = str(options["project_id"])
        slug = str(options["slug"])
        project_dir = root / "projects" / project_id
        project_json = project_dir / "project.json"
        if not project_json.exists():
            raise CommandError(f"project.json not found: {project_json}")
        metadata = read_json(project_json)
        report = read_optional(project_dir / "output" / "report.json")
        interactions_dir = find_interactions_dir(root / "outputs", slug, project_id)
        manifests = manifest_map(interactions_dir)
        videos_dir = root / "content" / "videos" / slug

        drama, _ = Drama.objects.update_or_create(
            slug=slug,
            defaults={
                "title": str(metadata.get("drama_title") or report.get("drama_title") or slug),
                "subtitle": subtitle(report),
                "description": description(report),
                "status": Drama.Status.PUBLISHED if options["publish"] else Drama.Status.READY,
                "genre_tags": genres(report),
                "score_label": "暂无评分",
                "source": "legacy_import",
                "published_at": timezone.now() if options["publish"] else None,
            },
        )

        episode_numbers = set(range(1, int(metadata.get("total_episodes") or 0) + 1))
        episode_numbers.update(manifests)
        imported_points = 0
        for number in sorted(num for num in episode_numbers if num > 0):
            manifest_json = read_optional(manifests.get(number))
            summary = episode_summary(report, number)
            video_path = find_video(videos_dir, number)
            episode, _ = Episode.objects.update_or_create(
                drama=drama,
                episode_number=number,
                defaults={
                    "title": f"第 {number} 集",
                    "description": summary,
                    "duration_ms": int(manifest_json.get("duration_ms") or manifest_json.get("video_duration_ms") or duration_from_report(report, number) or 0),
                    "source_video_path": str(video_path) if video_path else "",
                    "video_status": Episode.VideoStatus.READY if video_path else Episode.VideoStatus.FAILED,
                    "manifest_status": Episode.ManifestStatus.READY if manifest_json else Episode.ManifestStatus.MISSING,
                    "is_published": bool(options["publish"] and video_path),
                },
            )
            if manifest_json:
                manifest, _ = InteractionManifest.objects.update_or_create(
                    episode=episode,
                    defaults={
                        "version": str(manifest_json.get("manifest_version") or "1.0.0"),
                        "schema_version": str(manifest_json.get("schema_version") or "1.0.0"),
                        "duration_ms": int(manifest_json.get("duration_ms") or episode.duration_ms),
                        "raw_json": manifest_json,
                        "source_path": str(manifests[number]),
                        "generated_by": "legacy_import",
                        "status": InteractionManifest.Status.READY,
                    },
                )
                manifest.points.all().delete()
                for order, point in enumerate(manifest_json.get("interaction_points") or [], start=1):
                    InteractionPoint.objects.create(
                        manifest=manifest,
                        point_key=str(point.get("id") or f"ip_{order:03d}"),
                        component=str(point.get("component") or "unknown"),
                        title=str(point.get("title") or ""),
                        emotion=str(point.get("emotion") or ""),
                        start_ms=int(point.get("start_ms") or 0),
                        end_ms=int(point.get("end_ms") or 0),
                        priority=float(point.get("priority") or 0),
                        highlight_reason=str(point.get("highlight_reason") or ""),
                        config=point.get("config") if isinstance(point.get("config"), dict) else {},
                        sort_order=order,
                    )
                    imported_points += 1
            SearchDocument.objects.update_or_create(
                object_type=SearchDocument.ObjectType.EPISODE,
                object_id=str(episode.id),
                defaults={"title": f"{drama.title} 第 {number} 集", "body": summary, "tags": drama.genre_tags, "embedding_status": "pending"},
            )

        drama.heat_label = f"{drama.episodes.count()} 集"
        drama.save(update_fields=["heat_label", "updated_at"])
        SearchDocument.objects.update_or_create(
            object_type=SearchDocument.ObjectType.DRAMA,
            object_id=str(drama.id),
            defaults={"title": drama.title, "body": f"{drama.subtitle}\n{drama.description}", "tags": drama.genre_tags, "embedding_status": "pending"},
        )
        self.stdout.write(self.style.SUCCESS(f"Imported {drama.slug}: {drama.episodes.count()} episodes, {imported_points} points"))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_optional(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def find_interactions_dir(outputs_root: Path, slug: str, project_id: str) -> Path | None:
    candidates = [
        outputs_root / "component-fix-verify" / slug,
        outputs_root / project_id / slug,
        outputs_root / project_id,
    ]
    candidates.extend(path.parent for path in outputs_root.glob(f"**/{slug}/ep_*.interactions.json"))
    best = None
    best_count = 0
    for candidate in candidates:
        if not candidate.exists():
            continue
        count = len(list(candidate.glob("ep_*.interactions.json")))
        if count > best_count:
            best = candidate
            best_count = count
    return best


def manifest_map(path: Path | None) -> dict[int, Path]:
    if path is None:
        return {}
    result = {}
    for item in path.glob("ep_*.interactions.json"):
        match = MANIFEST_RE.match(item.name)
        if match:
            result[int(match.group(1))] = item
    return result


def find_video(videos_dir: Path, number: int) -> Path | None:
    stems = [f"ep_{number:03d}", f"ep{number:03d}", f"ep{number:02d}", f"episode_{number}", str(number)]
    for stem in stems:
        for extension in VIDEO_EXTENSIONS:
            path = videos_dir / f"{stem}{extension}"
            if path.exists():
                return path.resolve()
    return None


def description(report: dict[str, Any]) -> str:
    for item in report.get("episode_summaries", []):
        summary = str(item.get("summary") or "").strip()
        if summary:
            return summary[:240]
    for item in report.get("results", []):
        summary = str(item.get("summary") or "").strip()
        if summary:
            return summary[:240]
    return ""


def subtitle(report: dict[str, Any]) -> str:
    return description(report)[:36] or "互动短剧"


def episode_summary(report: dict[str, Any], number: int) -> str:
    for key in ("episode_summaries", "results"):
        for item in report.get(key, []):
            if int(item.get("episode_num") or 0) == number:
                return str(item.get("summary") or "")
    return ""


def duration_from_report(report: dict[str, Any], number: int) -> int:
    for item in report.get("results", []):
        if int(item.get("episode_num") or 0) != number:
            continue
        ends = [int(point.get("end_ms") or 0) for point in item.get("candidate_interactions") or [] if isinstance(point, dict)]
        return max(ends) + 12000 if ends else 0
    return 0


def genres(report: dict[str, Any]) -> list[str]:
    text = json.dumps(report, ensure_ascii=False)
    values = []
    for label, words in [
        ("古装", ("皇帝", "公主", "朝臣", "蛮夷", "侯")),
        ("权谋", ("朝堂", "国体", "权贵")),
        ("爽剧", ("打脸", "反转", "爽", "高手")),
        ("互动", ("interaction", "candidate_interactions", "互动")),
    ]:
        if any(word in text for word in words):
            values.append(label)
    return values or ["互动短剧"]
