from __future__ import annotations

import gzip
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from drama_agent.api.activity import ActivityStore, normalize_device_id
from drama_agent.api.content import ContentRepository, guess_media_type, safe_id
from drama_agent.api.jobs import JobManager, run_interaction_design, run_recreation, run_understanding


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_MAX_VIDEO_CHUNK = 2 * 1024 * 1024
MAX_BODY_BYTES = 2 * 1024 * 1024
VIDEO_ROUTE = re.compile(r"^/api/videos/([^/]+)/(\d+)$")
DRAMA_ROUTE = re.compile(r"^/api/dramas/([^/]+)$")
EPISODES_ROUTE = re.compile(r"^/api/dramas/([^/]+)/episodes$")
EPISODE_ROUTE = re.compile(r"^/api/dramas/([^/]+)/episodes/(\d+)$")
INTERACTIONS_ROUTE = re.compile(r"^/api/dramas/([^/]+)/episodes/(\d+)/interactions$")
JOB_ROUTE = re.compile(r"^/api/jobs/([A-Za-z0-9]+)$")


class DramaApiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler)
        self.repository = ContentRepository.from_env(Path.cwd())
        self.jobs = JobManager()
        activity_path = Path(os.getenv("DRAMA_API_ACTIVITY_STORE", "runtime/activity-events.json")).resolve()
        self.activity = ActivityStore(activity_path)
        self.max_video_chunk = int(os.getenv("DRAMA_API_MAX_VIDEO_CHUNK_BYTES", str(DEFAULT_MAX_VIDEO_CHUNK)))


class Handler(BaseHTTPRequestHandler):
    server: DramaApiServer

    def do_HEAD(self) -> None:
        self._dispatch(head_only=True)

    def do_GET(self) -> None:
        self._dispatch(head_only=False)

    def do_POST(self) -> None:
        try:
            self._dispatch_post()
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("DRAMA_API_ACCESS_LOG", "0") == "1":
            super().log_message(format, *args)

    def _dispatch(self, *, head_only: bool) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/health":
                self._send_json({"status": "ok"}, head_only=head_only)
                return
            if path == "/api/dramas":
                self._send_json({"dramas": self.server.repository.list_dramas()}, head_only=head_only)
                return
            if path == "/api/jobs":
                jobs = [job.to_dict() for job in self.server.jobs.list()]
                self._send_json({"jobs": jobs}, head_only=head_only)
                return
            if path == "/api/users/me/profile":
                device_id = normalize_device_id(self.headers.get("X-Device-Id"))
                self._send_json(self.server.activity.profile(device_id), head_only=head_only)
                return
            if match := JOB_ROUTE.match(path):
                job = self.server.jobs.get(match.group(1))
                if job is None:
                    self._send_error(HTTPStatus.NOT_FOUND, "job not found")
                    return
                self._send_json(job.to_dict(), head_only=head_only)
                return
            if match := DRAMA_ROUTE.match(path):
                record = self.server.repository.get_record(match.group(1))
                self._send_json(self.server.repository.to_drama_item(record), head_only=head_only)
                return
            if match := EPISODES_ROUTE.match(path):
                record = self.server.repository.get_record(match.group(1))
                episodes = [self.server.repository.to_episode_item(record, episode) for episode in record.episodes]
                self._send_json({"episodes": episodes}, head_only=head_only)
                return
            if match := EPISODE_ROUTE.match(path):
                record, episode = self.server.repository.get_episode(match.group(1), int(match.group(2)))
                self._send_json(self.server.repository.to_episode_item(record, episode), head_only=head_only)
                return
            if match := INTERACTIONS_ROUTE.match(path):
                manifest = self.server.repository.load_manifest(match.group(1), int(match.group(2)))
                self._send_json(manifest, cache="public, max-age=60", head_only=head_only)
                return
            if match := VIDEO_ROUTE.match(path):
                self._send_video(match.group(1), int(match.group(2)), head_only=head_only)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "route not found")
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "content not found")
        except FileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _dispatch_post(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/ai/search":
            payload = self._read_json_body()
            query = str(payload.get("query") or "")
            limit = int(payload.get("limit") or 8)
            results = self.server.repository.search(query, limit=limit)
            self._send_json(
                {
                    "status": "ok",
                    "message": f"Found {len(results)} matching item(s).",
                    "results": results,
                }
            )
            return
        if path == "/api/interactions":
            payload = self._read_json_body()
            events = payload.get("events")
            if not isinstance(events, list):
                events = [payload]
            result = self.server.activity.add_events(self.headers.get("X-Device-Id") or "", events)
            self._send_json({"status": "ok", **result})
            return
        if path == "/api/pipelines/understand":
            self._start_job("understand", run_understanding)
            return
        if path == "/api/pipelines/interactions":
            self._start_job("interactions", run_interaction_design)
            return
        if path == "/api/pipelines/recreate":
            self._start_job("recreate", run_recreation)
            return
        self._send_error(HTTPStatus.NOT_FOUND, "route not found")

    def _start_job(self, kind: str, target: Any) -> None:
        payload = self._read_json_body()
        job = self.server.jobs.start(kind, payload, target)
        self._send_json(job.to_dict(), status=HTTPStatus.ACCEPTED)

    def _send_video(self, drama_id: str, number: int, *, head_only: bool) -> None:
        safe_id(drama_id)
        path = self.server.repository.find_video(drama_id, number)
        if path is None:
            self._send_error(
                HTTPStatus.NOT_FOUND,
                "video file not found; set DRAMA_API_VIDEO_ROOT or place files under project episodes/",
            )
            return
        file_size = path.stat().st_size
        start, end, partial = self._range(file_size)
        length = end - start + 1
        etag = f'W/"{path.stat().st_mtime_ns:x}-{file_size:x}"'
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": guess_media_type(path),
            "Content-Length": str(length),
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
            "X-Content-Bandwidth-Policy": f"max-chunk={self.server.max_video_chunk}",
        }
        if partial:
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status = HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        if head_only:
            return
        with path.open("rb") as stream:
            stream.seek(start)
            remaining = length
            while remaining > 0:
                chunk = stream.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _range(self, file_size: int) -> tuple[int, int, bool]:
        header = self.headers.get("Range", "")
        max_chunk = max(1, self.server.max_video_chunk)
        if not header:
            return 0, min(file_size - 1, max_chunk - 1), file_size > max_chunk
        if not header.startswith("bytes="):
            raise ValueError("unsupported range unit")
        value = header.removeprefix("bytes=").split(",", 1)[0].strip()
        if value.startswith("-"):
            suffix = int(value[1:] or 0)
            start = max(file_size - suffix, 0)
            end = file_size - 1
        else:
            start_text, _, end_text = value.partition("-")
            start = int(start_text)
            requested_end = int(end_text) if end_text else file_size - 1
            end = min(requested_end, file_size - 1)
        if start < 0 or start >= file_size or end < start:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            raise ValueError("range not satisfiable")
        end = min(end, start + max_chunk - 1)
        return start, end, True

    def _send_json(
        self,
        payload: dict[str, Any],
        *,
        status: HTTPStatus = HTTPStatus.OK,
        cache: str = "no-store",
        head_only: bool = False,
    ) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        accept_encoding = self.headers.get("Accept-Encoding", "")
        use_gzip = len(raw) > 1024 and "gzip" in accept_encoding.lower()
        body = gzip.compress(raw) if use_gzip else raw
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(body)))
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        if status == HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE:
            return
        self._send_json({"status": "error", "message": message}, status=status)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = DramaApiServer((host, port), Handler)
    print(f"drama-api listening on http://{host}:{port}")
    print(f"projects={server.repository.projects_root}")
    print(f"outputs={server.repository.outputs_root}")
    print(f"video_root={server.repository.video_root}")
    server.serve_forever()


def main() -> None:
    host = os.getenv("DRAMA_API_HOST", DEFAULT_HOST)
    port = int(os.getenv("DRAMA_API_PORT", str(DEFAULT_PORT)))
    serve(host, port)


if __name__ == "__main__":
    main()
