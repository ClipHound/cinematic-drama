# Drama Backend API

Start from this directory:

```powershell
$env:PYTHONPATH="src"
python -m drama_agent.api.server
```

The frontend Vite proxy already points `/api` to `http://127.0.0.1:8787`.

Useful environment variables:

- `DRAMA_API_PROJECTS_ROOT`: defaults to `projects`
- `DRAMA_API_OUTPUTS_ROOT`: defaults to `outputs`
- `DRAMA_API_VIDEO_ROOT`: defaults to `content/videos`
- `DRAMA_API_MAX_VIDEO_CHUNK_BYTES`: defaults to `2097152`

Video files are resolved in this order:

- `$DRAMA_API_VIDEO_ROOT/<drama-id>/`
- `$DRAMA_API_VIDEO_ROOT/<project-id>/`
- `<project>/episodes/`
- `<project>/videos/`
- `<project>/`

Supported video names include `ep_001.mp4`, `ep001.mp4`, `ep01.mp4`, `episode_1.mp4`, and `1.mp4`.

Main endpoints:

- `GET /api/dramas`
- `GET /api/dramas/:id`
- `GET /api/dramas/:id/episodes`
- `GET /api/dramas/:id/episodes/:number`
- `GET /api/dramas/:id/episodes/:number/interactions`
- `GET/HEAD /api/videos/:id/:number`
- `POST /api/ai/search`
- `POST /api/interactions`
- `GET /api/users/me/profile`
- `POST /api/pipelines/understand`
- `POST /api/pipelines/interactions`
- `POST /api/pipelines/recreate`
- `GET /api/jobs`
- `GET /api/jobs/:id`

Bandwidth behavior:

- Video responses support `Range`.
- Open-ended requests are capped by `DRAMA_API_MAX_VIDEO_CHUNK_BYTES`.
- Responses include `Accept-Ranges`, `Content-Range`, `Content-Length`, `ETag`, and long-lived cache headers for media.
- JSON responses are gzip-compressed when the client sends `Accept-Encoding: gzip`.
