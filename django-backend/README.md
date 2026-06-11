# Django Backend

The online Django REST API for Cinematic Drama. Eight domain apps manage device identities, the drama catalog, media, interaction manifests and events, comments, pipeline jobs, search documents, and analytics. It replaces the legacy `drama_agent.api.server` for user-facing APIs while retaining the offline agent as the media-analysis pipeline.

## Local Run

```powershell
cd django-backend
python -m pip install -e .
Copy-Item .env.example .env
python manage.py migrate
python manage.py import_legacy_content --slug example-drama-a --project-id example-drama-a-20eps-final
python manage.py runserver 127.0.0.1:8787
```

The frontend Vite proxy already points `/api` to `127.0.0.1:8787`.

Run `python manage.py check` and `python manage.py test` to validate the backend.

## Production Configuration

Use environment variables for production:

- `DATABASE_URL=postgres://user:password@host:5432/dbname`
- `DJANGO_SECRET_KEY=<long random secret>`
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=example.com,api.example.com`
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `CELERY_RESULT_BACKEND=redis://redis:6379/0`
- `LEGACY_AGENT_ROOT=<path to retained offline pipeline checkout>`

Local development defaults to SQLite so the project can run without PostgreSQL. Production should use PostgreSQL 16 as specified.

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
- `POST /api/admin/dramas/upload`
- `GET /api/admin/pipeline/jobs`

## Legacy Boundary

The retained `drama-understanding-agent` modules remain the offline Pipeline implementation. Online content serving, user behavior, comments, favorites, interaction events, and jobs are persisted in Django models.
