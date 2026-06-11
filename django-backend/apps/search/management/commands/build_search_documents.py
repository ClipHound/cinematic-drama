from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.catalog.models import Drama, Episode
from apps.catalog.metadata import imported_poster_name
from apps.media_assets.thumbnails import ensure_episode_thumbnail
from apps.search.document_builder import (
    BuiltSearchDocument,
    DeliveryDramaArtifacts,
    DeliverySource,
    build_drama_document_from_artifacts,
    build_episode_document_from_artifacts,
    infer_genre_tags,
)
from apps.search.models import SearchDocument


class Command(BaseCommand):
    help = "Build rich SearchDocument rows from full-delivery drama understanding artifacts."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--source",
            default=os.getenv("AI_RAG_DELIVERY_SOURCE") or str(settings.LEGACY_AGENT_ROOT / "outputs" / "full-delivery" / "full-delivery-all.zip"),
            help="Path to full-delivery-all.zip or an extracted full-delivery directory.",
        )
        parser.add_argument("--drama-slug", help="Only process one drama slug from the delivery source.")
        parser.add_argument("--all", action="store_true", help="Process every drama in the delivery source.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of dramas to process.")
        parser.add_argument("--no-create-catalog", dest="create_catalog", action="store_false", help="Skip dramas/episodes missing from catalog.")
        parser.add_argument("--no-publish", dest="publish", action="store_false", help="Do not mark newly created catalog rows as published.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing database rows.")
        parser.set_defaults(create_catalog=True, publish=True)

    def handle(self, *args, **options) -> None:
        source_path = Path(options["source"])
        if not source_path.exists():
            raise CommandError(f"Delivery source not found: {source_path}")

        source = DeliverySource(source_path)
        slugs = [str(options["drama_slug"])] if options.get("drama_slug") else source.list_slugs()
        if not options.get("drama_slug") and not options["all"]:
            raise CommandError("Pass --all to process every drama or --drama-slug <slug> for one drama.")
        if options["limit"]:
            slugs = slugs[: options["limit"]]
        if not slugs:
            raise CommandError(f"No delivery dramas found in {source_path}")

        total_documents = 0
        changed_documents = 0
        skipped_episodes = 0
        for slug in slugs:
            artifacts = source.load(slug)
            drama = self._get_or_create_drama(artifacts, options)
            if drama is None:
                self.stderr.write(f"Skipped {slug}: drama is missing from catalog")
                continue

            genre_tags = list(drama.genre_tags or []) or infer_genre_tags(artifacts)
            drama_doc = build_drama_document_from_artifacts(artifacts, genre_tags)
            total_documents += 1
            changed_documents += self._upsert_document(SearchDocument.ObjectType.DRAMA, str(drama.id), drama_doc, options)

            episode_numbers = sorted({*artifacts.episode_summaries.keys(), *artifacts.understandings.keys(), *artifacts.interactions.keys()})
            for number in episode_numbers:
                episode = self._get_or_create_episode(drama, artifacts, number, options)
                if episode is None:
                    skipped_episodes += 1
                    continue
                built = build_episode_document_from_artifacts(artifacts, number, episode_title=episode.title, genre_tags=genre_tags)
                total_documents += 1
                changed_documents += self._upsert_document(SearchDocument.ObjectType.EPISODE, str(episode.id), built, options)

            self.stdout.write(f"{slug}: {len(episode_numbers)} episodes indexed")

        self.stdout.write(
            self.style.SUCCESS(
                f"Search document build complete: {changed_documents}/{total_documents} changed, {skipped_episodes} episodes skipped"
            )
        )

    def _get_or_create_drama(self, artifacts: DeliveryDramaArtifacts, options: dict[str, Any]) -> Drama | None:
        drama = Drama.objects.filter(slug=artifacts.slug).first()
        if drama is None and not options["create_catalog"]:
            return None
        if options["dry_run"]:
            return drama or Drama(slug=artifacts.slug, title=artifacts.drama_title, genre_tags=infer_genre_tags(artifacts))

        genre_tags = list(drama.genre_tags or []) if drama else infer_genre_tags(artifacts)
        description = _first_episode_summary(artifacts)[:500]
        subtitle = _first_episode_mood(artifacts)[:120] or description[:60]
        defaults = {
            "title": artifacts.drama_title,
            "subtitle": subtitle,
            "description": description,
            "genre_tags": genre_tags,
            "heat_label": f"{artifacts.total_episodes} 集" if artifacts.total_episodes else "0 集",
            "source": "full_delivery",
        }
        poster_name = imported_poster_name(
            settings.MEDIA_ROOT,
            artifacts.slug,
            artifacts.drama_title,
            settings.BASE_DIR / "data",
        )
        if poster_name:
            defaults["poster"] = poster_name
        if options["publish"]:
            defaults.update({"status": Drama.Status.PUBLISHED, "published_at": (drama.published_at if drama else None) or timezone.now()})
        elif drama is None:
            defaults.update({"status": Drama.Status.READY})
        drama, _ = Drama.objects.update_or_create(slug=artifacts.slug, defaults=defaults)
        return drama

    def _get_or_create_episode(self, drama: Drama, artifacts: DeliveryDramaArtifacts, number: int, options: dict[str, Any]) -> Episode | None:
        episode = Episode.objects.filter(drama=drama, episode_number=number).first()
        if episode is None and not options["create_catalog"]:
            return None
        summary = artifacts.episode_summaries.get(number) or artifacts.understandings.get(number) or {}
        duration_ms = int((artifacts.interactions.get(number) or {}).get("duration_ms") or (artifacts.interactions.get(number) or {}).get("video_duration_ms") or 0)
        if options["dry_run"]:
            return episode or Episode(drama=drama, episode_number=number, title=f"第 {number} 集", description=str(summary.get("summary") or summary.get("episode_summary") or ""))

        defaults: dict[str, Any] = {
            "title": episode.title if episode and episode.title else f"第 {number} 集",
            "description": str(summary.get("summary") or summary.get("episode_summary") or ""),
            "manifest_status": Episode.ManifestStatus.READY if number in artifacts.interactions else Episode.ManifestStatus.MISSING,
            "is_published": bool(options["publish"]) if episode is None else episode.is_published or bool(options["publish"]),
        }
        if duration_ms:
            defaults["duration_ms"] = duration_ms
        if episode is None and options["publish"]:
            defaults["video_status"] = Episode.VideoStatus.READY
        episode, _ = Episode.objects.update_or_create(drama=drama, episode_number=number, defaults=defaults)
        if episode.video_file or episode.source_video_path:
            ensure_episode_thumbnail(episode)
        return episode

    def _upsert_document(self, object_type: str, object_id: str, built: BuiltSearchDocument, options: dict[str, Any]) -> int:
        current = SearchDocument.objects.filter(object_type=object_type, object_id=object_id).first()
        changed = current is None or current.title != built.title or current.body != built.body or list(current.tags or []) != built.tags
        if not changed:
            return 0
        if options["dry_run"]:
            self.stdout.write(f"Would update {object_type}:{object_id} ({built.title})")
            return 1
        SearchDocument.objects.update_or_create(
            object_type=object_type,
            object_id=object_id,
            defaults={
                "title": built.title,
                "body": built.body,
                "tags": built.tags,
                "embedding_status": "pending",
                "embedding_vector": [],
            },
        )
        return 1


def _first_episode_summary(artifacts: DeliveryDramaArtifacts) -> str:
    for summary in sorted(artifacts.episode_summaries.values(), key=lambda item: int(item.get("episode_num") or 0)):
        text = str(summary.get("summary") or summary.get("episode_summary") or "").strip()
        if text:
            return text
    return ""


def _first_episode_mood(artifacts: DeliveryDramaArtifacts) -> str:
    for summary in sorted(artifacts.episode_summaries.values(), key=lambda item: int(item.get("episode_num") or 0)):
        text = str(summary.get("mood") or "").strip()
        if text:
            return text
    return ""
