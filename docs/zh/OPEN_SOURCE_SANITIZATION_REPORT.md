# Open Source Sanitization Report

**Generated**: 2026-06-11
**Release Version**: 0.1.0
**License**: Apache 2.0

## Purpose

This report documents all sanitization actions performed on the codebase before open-source release. It serves as both a transparency record and a checklist for future releases.

---

## Security Sanitization

### API Keys & Secrets — VERIFIED CLEAN

| File | Original Content | Action Taken |
|------|-----------------|--------------|
| `django-backend/.env` (disk only) | SiliconFlow API Key `sk-pyqzaz...` | **NOT included in release** — `.env` is gitignored and was never tracked |
| `drama-understanding-agent/.env` (disk only) | Volcengine Ark Token `ark-973d...` | **NOT included in release** — `.env` is gitignored and was never tracked |
| `django-backend/.env.example` L2 | `DJANGO_SECRET_KEY=django-insecure-local-dev-key` | Changed to `DJANGO_SECRET_KEY=change-me-to-a-random-secret-key` |
| `django-backend/.env.example` L4 | `DJANGO_ALLOWED_HOSTS=...,116.204.134.65` | Removed production IP `116.204.134.65` |
| `django-backend/.env.example` L11-12 | Local Windows paths `./...` | Changed to relative paths and placeholder |
| `cinematic-drama-app-frontend-source/.env.production` | `http://116.204.134.65` | **Renamed to `.env.production.example`** with placeholder value |
| `AUDIT-REPORT.md` L194 | Partial token `ark-973d982f-...` | Replaced with `<REDACTED>` |
| `drama-understanding-agent/.env.example` | ✅ Already clean (empty values / placeholders) | No changes needed |
| `cinematic-drama-app-frontend-source/.env.example` | ✅ Already clean (empty value) | No changes needed |

### Git History

- **Status**: CLEAN — `git log --all -- "**/.env"` returns no results
- `.env` files were never committed to the repository
- No git history rewrite required

---

## Infrastructure & Path Sanitization

| Original | Sanitized |
|----------|-----------|
| Server IP `116.204.134.65` | Removed from all committed files |
| `./` absolute paths | Replaced with relative paths / placeholders |
| `<project-root>/` paths | Removed |

---

## Files Added for Open Source Release

| File | Purpose |
|------|---------|
| `LICENSE` | Apache License 2.0 |
| `SECURITY.md` | Vulnerability disclosure policy + key rotation guide |
| `CONTRIBUTING.md` | Dev environment setup, workflow, style guides |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.0 |
| `.pre-commit-config.yaml` | Gitleaks + ruff + general hygiene hooks |
| `.github/workflows/secret-scan.yml` | CI pipeline: full-history scan on push/PR/schedule |
| `.cursorignore` | Prevent AI assistants from reading `.env` files |
| `.claudeignore` | Prevent Claude Code from reading `.env` files |

## Files Modified for Open Source Release

| File | Change |
|------|--------|
| `.gitignore` | Enhanced with `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `credentials.json`, `service-account.json`, `.env.production` ignore, `!.env.production.example` exception |
| `cinematic-drama-app-frontend-source/package.json` | Removed `"private": true` |
| `django-backend/.env.example` | Sanitized keys, paths, and hostnames |
| `cinematic-drama-app-frontend-source/.env.production` | Renamed to `.env.production.example`, IP replaced with placeholder |
| `AUDIT-REPORT.md` | Token prefix redacted; drama names replaced with generic placeholders |
| `AI-RAG-实施计划.md` | All specific drama names/searches replaced with generic placeholders |
| All `*.md` / `*.ps1` / `*.py` / `*.tsx` files | Local Windows paths replaced; all drama names/character names/slugs replaced with generic placeholders |
| `src/pages/*.tsx` (3 files) | Hardcoded `'furao-dadi'` fallback values replaced with empty string |
| `django-backend/apps/catalog/.../import_legacy_content.py` | Hardcoded `--slug` / `--project-id` defaults removed |
| `drama-understanding-agent/src/drama_agent/api/content.py` | Hardcoded `furao-dadi` project-id check removed |
| `drama-understanding-agent/tests/test_vectors.py` | Character names replaced with generic placeholders |
| `drama-understanding-agent/tests/test_thread_dedup.py` | Plot descriptions replaced with generic descriptions |

## Files REMOVED (Copyrighted Drama Content)

| File | Reason |
|------|--------|
| `INTERACTION-POINT-REPORT.md` | 328 lines: detailed analysis of 10 specific dramas, 592 interaction points |
| `drama-understanding-agent/ANALYSIS-ep01-understanding-to-design.md` | Detailed copyrighted episode transcript analysis |
| `drama-understanding-agent/ANALYSIS-component-selection-errors.md` | Detailed scene-by-scene analysis of specific drama content |

## Files NOT Included (Intentionally Excluded)

| File/Pattern | Reason |
|-------------|--------|
| All `.env` files (with real keys) | Security — contains API keys |
| `*.log`, `tmp-*.log` | Runtime artifacts — not source code |
| `*.sqlite`, `*.sqlite3`, `*.db` | Local databases — may contain user data |
| `django-backend/media/`, `django-backend/staticfiles/` | Uploaded/generated content |
| `drama-understanding-agent/projects/`, `outputs/`, `runtime/`, `frames_ep*/` | Large generated artifacts |
| `drama-understanding-agent/content/videos/` | Copyrighted video content |
| `cinematic-drama-app-frontend-source/android/` | Generated build artifacts |
| `node_modules/`, `.venv/`, `venv/` | Dependencies (install via npm/pip) |
| `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` | Python bytecode/cache |
| `.claude/` | Claude Code internal data |
| `_pdf_extracted.txt`, `_pdf_pages/` | Extracted PDF content |
| `*.zip` files | Binary archives |
| `我自己的杂项/` | Personal files |
| `AI全栈挑战赛*.pdf`, `AI全栈挑战赛*.docx` | Binary competition files |

---

## Pre-Release Verification Checklist

- [x] Gitleaks full-history scan — clean
- [x] No `.env` files with real keys in the release
- [x] `.env.example` templates use placeholders only
- [x] No hardcoded server IPs in committed files
- [x] No absolute local paths (for example, developer workstation paths)
- [x] `LICENSE` file added (Apache 2.0)
- [x] `SECURITY.md` added with disclosure policy
- [x] `CONTRIBUTING.md` added with setup instructions
- [x] `CODE_OF_CONDUCT.md` added
- [x] `.pre-commit-config.yaml` configured
- [x] `.github/workflows/secret-scan.yml` CI pipeline configured
- [x] `.cursorignore` and `.claudeignore` created
- [x] `package.json` no longer marked `"private": true`
- [x] `.gitignore` enhanced with additional security patterns

## Known Limitations

1. **Doubao/Seed VLM dependency**: The offline agent relies on ByteDance's proprietary Doubao vision model. Open-source users will need their own Volcengine Ark account or swap in an alternative VLM provider (e.g., OpenAI GPT-4V, Claude Vision).

2. **Content metadata**: The catalog and interaction data reference 10 specific short dramas. Users should replace these with their own content.

3. **Interaction assets**: The 12 interaction component animations in `public/assets/` are custom-designed. Confirm you have the rights to distribute them under Apache 2.0.

4. **FunASR deployment**: ASR requires a separately deployed FunASR server at `localhost:10000`. Documentation for this setup is in the SDD.

5. **Qdrant dependency**: The offline agent uses Qdrant for vector storage. This is optional for the core Django backend.

---

## Post-Release Actions for Maintainers

After pushing to a public repository:

1. **Rotate all API keys** that were ever used during development:
   - SiliconFlow: `sk-pyqzaz...` → DELETE and regenerate
   - Volcengine Ark: `ark-973d...` → DELETE and regenerate

2. **Enable GitHub Secret Scanning** in repository settings.

3. **Set up branch protection** on `main`:
   - Require pull request reviews
   - Require status checks (secret scan must pass)
   - Do not allow force pushes

4. **Register with GitHub Security Advisories** for vulnerability reporting.

5. **Monitor** for automated secret detection alerts from GitHub / GitGuardian in the first 24 hours after going public.
