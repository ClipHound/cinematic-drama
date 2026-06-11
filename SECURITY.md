# Security Policy

## Supported Versions

Only the latest release on the `main` branch receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

**Please do NOT open a public GitHub Issue to report a security vulnerability.**

Instead, use GitHub's built-in [Security Advisory](https://github.com/ClipHound/cinematic-drama/security/advisories/new) feature.

We will acknowledge your report within **48 hours** and aim to provide a resolution timeline within **5 business days**.

### What to include in your report

- Affected component(s) and version(s)
- Step-by-step reproduction instructions
- Potential impact of the vulnerability
- Any suggested mitigations (optional)

### Disclosure Policy

We follow a **coordinated disclosure** process:

1. You report the vulnerability privately.
2. We validate, develop, and release a fix.
3. We publish a security advisory after the fix is released.
4. You receive public credit in the advisory (unless you prefer to remain anonymous).

## If You Accidentally Committed a Secret

1. **Immediately revoke the key/token** on the provider's dashboard (e.g., SiliconFlow, Volcengine Ark, GitHub, etc.).
2. **Contact the maintainers** so we can clean git history and force-push a sanitized version.
3. **Rotate all related credentials** — assume the leaked key was scraped by automated bots within minutes.

## Security Best Practices for Contributors

- Never commit `.env` files, `.pem` keys, `.crt` certificates, or any file containing credentials.
- Use `.env.example` as a template — copy it to `.env` and fill in your own keys.
- Run `pre-commit install` to activate the gitleaks secret-scanning hook.
- If you are unsure whether a file contains secrets, ask a maintainer before committing.
- Review `git diff --staged` before every commit.

## Scope

| In Scope | Out of Scope |
|----------|-------------|
| Django backend API endpoints | Social engineering attacks |
| React frontend application | Physical security |
| Offline understanding agent pipeline | DDoS / volumetric attacks |
| RAG search system | Third-party API provider vulnerabilities |
| Authentication / device-id handling | Outdated browser exploits |

## Recognition

We appreciate the security community's help in keeping this project safe. Contributors who report valid vulnerabilities will be acknowledged in our release notes and security advisories.
