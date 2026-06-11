# Contributing to Cinematic Drama Interactive System

Thank you for your interest in contributing! This document will guide you through setting up your development environment and our contribution workflow.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Security](#security)
- [Development Environment Setup](#development-environment-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Pre-Commit Hooks](#pre-commit-hooks)
- [Pull Request Process](#pull-request-process)
- [Style Guides](#style-guides)

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

**Never commit secrets to the repository.** If you discover a security vulnerability, please follow the instructions in [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Development Environment Setup

### Prerequisites

- **Python 3.11+** for the Django backend and offline agent
- **Node.js 22+** for the React frontend
- **FFmpeg** for video processing
- **Ollama** (optional) for local embedding generation
- **Qdrant** (optional) for vector search in the offline pipeline

### 1. Clone and Configure

```bash
git clone https://github.com/ClipHound/cinematic-drama.git
cd cinematic-drama

# Copy environment templates — NEVER commit the resulting .env files
cp django-backend/.env.example django-backend/.env
cp drama-understanding-agent/.env.example drama-understanding-agent/.env
cp cinematic-drama-app-frontend-source/.env.example cinematic-drama-app-frontend-source/.env
```

### 2. Configure Environment Files

Edit each `.env` file with your own API keys and configuration:

**`django-backend/.env`**:
```
DJANGO_SECRET_KEY=<generate a random key>
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

# AI API (e.g., SiliconFlow — see below for alternatives)
AI_CHAT_API_KEY=<your-api-key>
AI_CHAT_MODEL=deepseek-ai/DeepSeek-V4-Flash
AI_EMBEDDING_API_KEY=<your-api-key>
AI_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
```

**`drama-understanding-agent/.env`**:
```
DRAMA_AGENT_MODEL_TOKEN=<your-ark-api-key>
DRAMA_AGENT_MODEL_NAME=<your-doubao-endpoint-id>
```

### 3. Install Dependencies

```bash
# Backend
cd django-backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
python manage.py migrate
python manage.py runserver

# Frontend
cd cinematic-drama-app-frontend-source
npm install
npm run dev
```

### 4. Third-Party API Providers

This project uses OpenAI-compatible APIs. You can use any compatible provider:

| Provider | Chat API | Embedding API | VLM |
|----------|---------|---------------|-----|
| [SiliconFlow](https://siliconflow.cn) | ✅ | ✅ | ❌ |
| [Volcengine Ark](https://www.volcengine.com/product/ark) | ✅ | ✅ | ✅ (Doubao) |
| [OpenAI](https://platform.openai.com) | ✅ | ✅ | ✅ (GPT-4V) |
| [Groq](https://groq.com) | ✅ | ❌ | ❌ |
| Local (Ollama) | Optional | ✅ | ❌ |

## Project Structure

```
.
├── cinematic-drama-app-frontend-source/  # React + Vite + Capacitor
│   ├── src/
│   │   ├── data/          # API clients, types, device-id
│   │   ├── pages/         # Route page components
│   │   └── interaction/   # 12 interactive component types
│   └── public/assets/     # Lottie animations, static assets
├── django-backend/                     # Django REST API backend
│   ├── apps/
│   │   ├── accounts/      # Device-based user identity
│   │   ├── catalog/       # Drama & episode metadata
│   │   ├── interactions/  # Interaction manifests & events
│   │   ├── comments/      # Episode comments
│   │   ├── analytics/     # Favorites, watch progress
│   │   ├── pipeline/      # Offline pipeline management
│   │   ├── search/        # AI-powered RAG search
│   │   └── media_assets/  # Video & poster management
│   └── config/            # Django settings, URLs, WSGI/ASGI
├── drama-understanding-agent/          # Offline AI pipeline
│   ├── src/               # Core agent logic
│   └── tests/             # Pipeline tests
└── sdd/                               # Software Design Documents
```

## Development Workflow

1. **Fork** the repository and create your branch from `main`.
2. **Install pre-commit hooks** (see below).
3. **Make changes** following our style guides.
4. **Write/update tests** for any new or changed functionality.
5. **Run the test suite** to ensure nothing is broken.
6. **Commit** your changes (pre-commit hooks will scan for secrets automatically).
7. **Push** to your fork and open a Pull Request.

## Pre-Commit Hooks

We use **gitleaks** to prevent secrets from being committed. Install it once:

```bash
# Install gitleaks
# macOS:   brew install gitleaks
# Linux:   see https://github.com/gitleaks/gitleaks#installing
# Windows: choco install gitleaks  or  scoop install gitleaks

# Then install the pre-commit hook
pip install pre-commit && pre-commit install
```

The hook scans `git diff --staged` before every commit. If it finds a potential secret, the commit is blocked.

You can also run a full history scan anytime:
```bash
gitleaks detect --source . --verbose
```

## Pull Request Process

1. Ensure your PR description clearly describes the problem and solution.
2. Include references to any related issues (e.g., `Fixes #123`).
3. Make sure all tests pass and the code lints cleanly.
4. If your change adds new environment variables, update `.env.example` accordingly.
5. A maintainer will review your PR. Address any feedback before it can be merged.

## Style Guides

### Python (Backend & Agent)
- Follow [PEP 8](https://peps.python.org/pep-0008/).
- Use type hints where practical.
- Run `ruff check` and `ruff format` before committing.

### TypeScript / React (Frontend)
- Use the existing project conventions (functional components, React Router v7 patterns).
- Run `npm run build` to type-check before committing (`tsc -b`).

### Commit Messages
- Use the present tense ("Add feature" not "Added feature").
- Reference issues where applicable.
- Keep the first line under 72 characters.

---

If you have questions, please open a [Discussion](https://github.com/ClipHound/cinematic-drama/discussions). Happy contributing!
