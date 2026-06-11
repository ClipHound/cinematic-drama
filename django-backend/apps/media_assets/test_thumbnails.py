from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.catalog.models import Drama, Episode
from apps.media_assets.thumbnails import ensure_episode_thumbnail


class EpisodeThumbnailTests(TestCase):
    def setUp(self) -> None:
        self.drama = Drama.objects.create(
            slug="thumbnail-demo",
            title="缩略图测试",
            status=Drama.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.episode = Episode.objects.create(
            drama=self.drama,
            episode_number=1,
            title="第 1 集",
            video_status=Episode.VideoStatus.READY,
            is_published=True,
        )

    def test_generates_and_reuses_low_resolution_thumbnail(self) -> None:
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory) / "media"):
            video = Path(directory) / "episode.mp4"
            video.write_bytes(b"video")
            self.episode.source_video_path = str(video)

            def fake_run(command, **kwargs):
                Path(command[-1]).write_bytes(b"jpeg")

            with patch("apps.media_assets.thumbnails.shutil.which", return_value="ffmpeg"), patch(
                "apps.media_assets.thumbnails.subprocess.run", side_effect=fake_run
            ) as run:
                first = ensure_episode_thumbnail(self.episode)
                second = ensure_episode_thumbnail(self.episode)

            self.assertEqual(first, second)
            self.episode.refresh_from_db()
            self.assertEqual(self.episode.thumbnail.name, "thumbnails/thumbnail-demo/ep_001.jpg")
            self.assertEqual(first.read_bytes(), b"jpeg")
            self.assertEqual(run.call_count, 1)
            self.assertIn("scale=160:-2", run.call_args.args[0])
