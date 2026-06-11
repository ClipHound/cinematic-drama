from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.catalog.metadata import imported_poster_name


class CatalogMetadataTests(SimpleTestCase):
    def test_bundled_poster_is_matched_by_imported_title(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / "data" / "posters" / "天下第一纨绔.jpg"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"poster")

            name = imported_poster_name(root / "media", "furao-dadi", "天下第一纨绔", root / "data")

            self.assertEqual(name, "posters/furao-dadi.jpg")
            self.assertEqual((root / "media" / name).read_bytes(), b"poster")
