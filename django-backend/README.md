# Django Backend

This is the new online backend for the interactive short-drama app. It replaces the legacy `drama_agent.api.server` HTTP server for user-facing APIs.

## Local Run

```powershell
cd django-backend
python -m pip install -e .
python manage.py migrate
python manage.py build_search_documents --source ../drama-understanding-agent/outputs/full-delivery --all
python manage.py runserver 127.0.0.1:8787
```

The frontend Vite proxy already points `/api` to `127.0.0.1:8787`.

## AI Search / RAG

`SearchDocument` is populated from the full-delivery understanding artifacts. The current local dataset has 10 dramas, 228 episodes, and 238 searchable documents.

Build or refresh rich search documents:

```powershell
cd django-backend
python manage.py build_search_documents --source ../drama-understanding-agent/outputs/full-delivery --all
```

Configure an OpenAI-compatible provider, then build embeddings:

```powershell
Copy-Item .env.example .env
# Fill AI_CHAT_API_KEY, AI_CHAT_MODEL, AI_EMBEDDING_API_KEY,
# and AI_EMBEDDING_MODEL in .env. Django loads this file automatically.

python manage.py build_search_embeddings --all --sleep 0.2
```

Without provider keys, `/api/ai/chat` and `/api/ai/search` still return playable recommendations through keyword fallback over the rich document bodies.

## Production Configuration

Use environment variables for production:

- `DATABASE_URL=postgres://user:password@host:5432/dbname`
- `DJANGO_SECRET_KEY=<long random secret>`
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=example.com,api.example.com`
- HTTP Android 包：`DJANGO_CORS_ALLOWED_ORIGINS=http://localhost`
- HTTPS Android 包：`DJANGO_CORS_ALLOWED_ORIGINS=https://localhost`
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://redis:6379/0`
- `LEGACY_AGENT_ROOT=<path to retained offline pipeline checkout>`
- `AI_CHAT_BASE_URL=<OpenAI-compatible chat base URL>`
- `AI_CHAT_API_KEY=<chat API key>`
- `AI_CHAT_MODEL=<chat model>`
- `AI_EMBEDDING_BASE_URL=<OpenAI-compatible embeddings base URL>`
- `AI_EMBEDDING_API_KEY=<embedding API key>`
- `AI_EMBEDDING_MODEL=<embedding model>`
- `AI_EMBEDDING_DIMENSIONS=<optional embedding dimensions, 0 for provider default>`
- `AI_HTTP_MAX_RETRIES=<provider retry count, default 2>`
- `AI_HTTP_RETRY_BASE_SECONDS=<provider retry base delay, default 0.8>`

Local development defaults to SQLite so the project can run without PostgreSQL. Production should use PostgreSQL 16 as specified.

See `../HTTPS-DEPLOYMENT.md` for Nginx, Let’s Encrypt and Android HTTPS migration instructions.

## Main APIs

- `GET /api/dramas`
- `GET /api/dramas/<slug>`
- `GET /api/dramas/<slug>/episodes`
- `GET /api/dramas/<slug>/episodes/<number>`
- `GET /api/dramas/<slug>/episodes/<number>/interactions`
- `GET /api/videos/<slug>/<number>`
- `POST /api/interactions`
- `GET /api/users/me/profile`
- `GET/PUT/DELETE /api/users/me/favorites`
- `GET/POST /api/comments`
- `GET /api/search?q=`
- `POST /api/ai/search`
- `POST /api/ai/chat`
- `POST /api/admin/dramas/upload`
- `GET /api/admin/pipeline/jobs`

## Legacy Boundary

The retained `drama-understanding-agent` modules remain the offline Pipeline implementation. Online content serving, user behavior, comments, favorites, interaction events, and jobs are persisted in Django models.
