from django.core.management.base import BaseCommand

from apps.catalog.models import Episode
from apps.media_assets.thumbnails import ensure_episode_thumbnail


class Command(BaseCommand):
    help = "Generate and persist low-resolution first-frame thumbnails for episodes."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--drama-slug")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options) -> None:
        episodes = Episode.objects.select_related("drama").order_by("drama__slug", "episode_number")
        if options.get("drama_slug"):
            episodes = episodes.filter(drama__slug=options["drama_slug"])

        generated = skipped = failed = 0
        for episode in episodes:
            if options["force"] and episode.thumbnail:
                episode.thumbnail.delete(save=False)
                episode.thumbnail = ""
            if episode.thumbnail and not options["force"]:
                skipped += 1
                continue
            if ensure_episode_thumbnail(episode):
                generated += 1
            else:
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(f"Episode thumbnails: {generated} generated, {skipped} skipped, {failed} failed")
        )
