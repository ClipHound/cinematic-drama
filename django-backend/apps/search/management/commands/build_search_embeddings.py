from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from apps.search.models import SearchDocument
from apps.search.services import AiProviderError, build_embedding_for_document


class Command(BaseCommand):
    help = "Build embeddings for searchable drama documents."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--all", action="store_true", help="Rebuild all documents instead of pending/failed documents.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of documents to process.")
        parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between provider requests.")

    def handle(self, *args, **options) -> None:
        queryset = SearchDocument.objects.all().order_by("id")
        if not options["all"]:
            queryset = queryset.exclude(embedding_status="ready")
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        processed = 0
        failed = 0
        for document in queryset:
            try:
                build_embedding_for_document(document)
                processed += 1
                if options["sleep"] > 0:
                    time.sleep(options["sleep"])
            except AiProviderError as exc:
                failed += 1
                self.stderr.write(f"Embedding failed for {document.object_type}:{document.object_id}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Embedding build complete: {processed} ready, {failed} failed"))
