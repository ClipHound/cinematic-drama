from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from drama_agent.memory.schemas import CommitResult, StatePatch, utc_now
from drama_agent.memory.store import MemoryStore
from drama_agent.memory.vectors import VectorStore


class PatchCommitter:
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        memory: MemoryStore,
        vectors: VectorStore | None = None,
        *,
        patch_log_dir: Path | None = None,
    ):
        self.memory = memory
        self.vectors = vectors
        self.patch_log_dir = patch_log_dir

    def commit_episode_patches(self, patches: list[StatePatch]) -> CommitResult:
        if not patches:
            return CommitResult(episode_num=0)
        episode_num = patches[0].episode_num
        result = CommitResult(episode_num=episode_num, patches_total=len(patches))

        deduped: OrderedDict[tuple[str, str], StatePatch] = OrderedDict()
        for patch in patches:
            deduped[(patch.table, patch.record_id)] = patch

        prepared: list[tuple[StatePatch, str]] = []
        for patch in deduped.values():
            status = "committed"
            if patch.confidence < self.CONFIDENCE_THRESHOLD or patch.conflicts:
                status = "committed_flagged"
            prepared.append((patch, status))

        try:
            with self.memory.connect() as conn:
                for patch, status in prepared:
                    self.memory.apply_patch_with_conn(conn, patch)
                    self.memory.record_patch_with_conn(conn, patch, status)
        except Exception as exc:
            result.errors.append(str(exc))
            self._write_patch_log(episode_num, patches)
            return result

        result.patches_committed = len(prepared)
        result.patches_flagged = sum(1 for _, status in prepared if status == "committed_flagged")
        result.errors.extend(self._sync_vectors([patch for patch, _ in prepared]))

        self._write_patch_log(episode_num, patches)
        return result

    def _apply_patch(self, patch: StatePatch) -> None:
        if patch.operation == "insert":
            self.memory.apply_insert(patch.table, patch.field_changes)
        elif patch.operation == "update":
            self.memory.apply_update(patch.table, patch.record_id, patch.field_changes)
        elif patch.operation == "delete":
            self.memory.apply_delete(patch.table, patch.record_id)

    def _sync_vectors(self, patches: list[StatePatch]) -> list[str]:
        errors: list[str] = []
        if self.vectors is None:
            return errors
        for patch in patches:
            if patch.table != "characters":
                continue
            try:
                if patch.operation == "delete":
                    self.vectors.delete_point("characters", patch.record_id)
                    continue
                character = self.memory.get_character(patch.record_id)
                if character:
                    self.vectors.sync_character(character)
            except Exception as exc:
                errors.append(f"vector sync failed for {patch.record_id}: {exc}")
        return errors

    def _write_patch_log(self, episode_num: int, patches: list[StatePatch]) -> None:
        if not self.patch_log_dir:
            return
        self.patch_log_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "episode_num": episode_num,
            "processed_at": utc_now(),
            "patches": [patch.model_dump() for patch in patches],
        }
        path = self.patch_log_dir / f"ep{episode_num:02d}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
