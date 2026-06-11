# Drama Understanding Agent

Offline Python pipeline that converts episode videos into structured memories and validated interaction manifests. It combines an OpenAI-compatible vision-language client, optional ASR, SQLite-backed narrative memory, embedding retrieval, Qdrant vector storage, two-pass interaction design, and branch-narrative generation.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env
drama-agent --help
```

Provider endpoints and credentials are configured through `.env`; generated projects are isolated below `DRAMA_AGENT_PROJECTS_ROOT`. Run `pytest` for the agent test suite. See [API.md](API.md) and [docs/](docs/) for deeper implementation notes.
