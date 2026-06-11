<!-- PROJECT-META
name: Cinematic Drama Interactive System
type: fullstack-application
language: Python, TypeScript, JavaScript
framework: Django, Django REST Framework, React, Vite, Capacitor
ai-features: VLM video understanding, LLM plot analysis, embedding retrieval, Qdrant vector memory, multi-agent interaction design
domain: interactive-entertainment, short-drama, video-understanding
license: Apache-2.0
repository: https://github.com/ClipHound/cinematic-drama
END-META -->

# Cinematic Drama Interactive System

> An AI-assisted platform that analyzes short-drama episodes offline, generates timeline-aware interaction manifests, and renders those interactions in a cross-platform viewer.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-0C4B33)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-19-149ECA)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6)](https://www.typescriptlang.org/)
[![Node](https://img.shields.io/badge/Node.js-22%2B-339933)](https://nodejs.org/)

Built by **ClipHound**, the open-source identity of the team **给狗剪毛**.

## What It Does

- **Offline video understanding:** an OpenAI-compatible vision-language client, ASR integration, structured episode memory, and multi-stage agents extract plot and visual signals.
- **Interaction design:** the pipeline selects precise timeline windows and emits validated JSON manifests for 12 component types.
- **Interactive playback:** the React viewer loads manifests, triggers overlays against video time, provides animation and haptic feedback, and batches interaction events to the API.
- **Content platform:** Django serves dramas, episodes, video files, manifests, device-based profiles, favorites, comments, analytics, and pipeline jobs.
- **Content retrieval:** Django provides indexed keyword search; the retained offline agent also includes embedding-based cosine retrieval and Qdrant vector memory.
- **Cross-platform delivery:** the same React application runs on the web and can be packaged for Android or iOS through Capacitor.

## Architecture

```text
Episode video
    |
    v
Offline AI pipeline
  VLM + ASR -> structured memory -> global/episode interaction design
    |
    v
Validated interaction manifest (JSON)
    |
    +-----------------------> Django content/search APIs
    |                                |
    v                                v
React timeline player <------ drama, episode, profile and event data
    |
    v
Local animation/haptics -> batched interaction events -> analytics
```

The offline pipeline and online application are deliberately separated: expensive media analysis happens before publication, while playback only reads prepared manifests and records user activity.

## Interaction Components

The manifest schema currently allows these 12 components:

`celebrate_confetti`, `anger_release`, `tear_resonance`, `laugh_burst`, `shatter_strike`, `sugar_storm`, `guardian_shield`, `team_cheer`, `prediction_card`, `clue_judge_card`, `episode_end_prediction`, and `emotion_buffer`.

Selection rules reject emotionally inappropriate combinations and validate required component configuration before a manifest is written.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript 5.9, React Router 7, Tailwind CSS 4, Vite 8 |
| Mobile packaging | Capacitor 8 for Android and iOS |
| Online API | Python 3.11+, Django 5, Django REST Framework |
| Background jobs | Celery 5 with Redis |
| AI pipeline | Python, OpenAI-compatible VLM/LLM APIs, multi-agent stages, ASR endpoint integration |
| Retrieval and memory | SQLite structured memory, Qdrant, OpenAI-compatible embeddings, cosine similarity |
| Application database | SQLite for local development; PostgreSQL supported for production |

## Project Structure

```text
cinematic-drama-app-frontend-source/  React/Vite viewer and Capacitor shell
  src/pages/                          Seven routed application pages
  src/interaction/                    Timeline runtime and component renderers
django-backend/                       Django REST API with eight domain apps
  apps/catalog/                       Drama and episode metadata
  apps/interactions/                  Manifests, points, events and aggregates
  apps/search/                        Online search index and API
  apps/pipeline/                      Offline-processing job records
drama-understanding-agent/            Offline understanding and design pipeline
  src/drama_agent/                    VLM, ASR, memory, API and orchestration
  src/interaction_designer/           Two-pass interaction planning and validation
  src/interaction_generator/          Highlight-to-manifest generation
  src/branch_narrative/                Branch narrative planning pipeline
sdd/                                  Chinese software design documents
docs/zh/                              Chinese plans, audits and release notes
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 22+
- Redis only when running Celery workers
- Optional external VLM, embedding, ASR, Ollama, and Qdrant services for the offline AI features

### Backend

```bash
cd django-backend
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
cp .env.example .env
python manage.py migrate
python manage.py runserver 127.0.0.1:8787
```

The default local database is SQLite. Configure `DATABASE_URL` to use PostgreSQL.

### Frontend

```bash
cd cinematic-drama-app-frontend-source
cp .env.example .env
npm ci
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8787` during local development.

### Offline Agent

```bash
cd drama-understanding-agent
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env
drama-agent --help
```

Configure provider credentials only in local `.env` files. Never commit API keys.

## Validation

```bash
# Django checks and tests
cd django-backend
python manage.py check
python manage.py test

# Offline agent tests
cd ../drama-understanding-agent
pytest

# Frontend type-check and production build
cd ../cinematic-drama-app-frontend-source
npm run build
```

## Documentation

- [Django backend](django-backend/README.md)
- [Offline AI pipeline](drama-understanding-agent/README.md)
- [Frontend and mobile packaging](cinematic-drama-app-frontend-source/README.md)
- [Software design documents](sdd/README.md)
- [Chinese project documents](docs/zh/)

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
