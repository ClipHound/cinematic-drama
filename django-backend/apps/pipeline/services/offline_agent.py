from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings

from apps.catalog.models import Drama, Episode


class OfflineAgentAdapter:
    """Adapter boundary for calling the retained offline understanding pipeline.

    The online API should enqueue PipelineJob records and let Celery call this
    adapter. It intentionally does not run from request handlers.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.LEGACY_AGENT_ROOT).resolve()

    def build_workspace_payload(self, drama: Drama, episodes: list[Episode] | None = None) -> dict[str, Any]:
        selected = episodes or list(drama.episodes.order_by("episode_number"))
        return {
            "legacyRoot": str(self.root),
            "drama": {"id": drama.id, "slug": drama.slug, "title": drama.title},
            "episodes": [
                {
                    "id": episode.id,
                    "episodeNumber": episode.episode_number,
                    "videoPath": episode.video_file.path if episode.video_file else episode.source_video_path,
                }
                for episode in selected
            ],
        }

    def run_ingest(self, drama: Drama) -> dict[str, Any]:
        # Celery task hook: wire EpisodeLoop / InteractionDesignAgent here.
        return {
            "status": "queued_for_worker",
            "payload": self.build_workspace_payload(drama),
        }
