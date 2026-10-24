# Security Policy

## Reporting a vulnerability

Do not publish API keys, access tokens, private research data, or exploit details in a public issue. Until a private reporting channel is configured by the repository owner, contact the maintainer through a trusted private channel.

## Secret handling

- Never commit `.env`, `.streamlit/secrets.toml`, API keys, tokens, or production database files.
- Rotate any credential that has been exposed; deleting it in a later commit does not remove it from Git history.
- Keep LLM/OpenScholar credentials on the backend service, not in Streamlit frontend settings.
- Use synthetic or non-sensitive queries for initial deployment tests.
- Review provider data-retention policies before sending research or personal data to third-party services.

## Deployment hardening

Before exposing a deployment publicly, assess authentication/authorization, rate limiting, request limits, logging of user queries, backup/restore, and dependency update procedures. The current MVP does not claim to provide a complete production security boundary.
