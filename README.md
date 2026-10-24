# Youth Ink Network (YIN) — Research Engine

**Arabic documentation:** [README_AR.md](README_AR.md) · [Android GitHub guide](docs/GITHUB_ANDROID_AR.md) · [Deployment guide](docs/DEPLOYMENT_AR.md)

**Version:** 0.4.0 (local development build)  
**Purpose:** literature discovery using OpenAlex, Crossref DOI metadata checks, persistent SQLite run history, conservative reference export, and optional LLM-assisted claim auditing.

> **Status:** development build. Automated tests cover core storage, API, and exporter behavior. The Streamlit interface and live external-provider integrations have not been end-to-end tested in this environment. APA output is a formatting aid and requires human review.

## What is included

- `app.py`: FastAPI endpoints for search, review, DOI metadata lookup, reference export, and run history.
- `engine.py`: OpenAlex literature discovery, abstract reconstruction, Crossref DOI lookup, and evidence-report generation.
- `storage.py`: SQLite persistence for search/review runs, retrieved metadata, and audit events.
- `reference_export.py`: APA-like text, BibTeX, and RIS exporters with missing-field handling.
- `verification_layer.py`: optional OpenAI-compatible LLM-as-a-judge claim audit. It reports `not_configured` rather than inventing a verification result when credentials are absent.
- `streamlit_app.py`: bilingual Arabic/English UI for search, saved runs, reports, and reference export.
- `openscholar_adapter.py`: optional bridge to a separately deployed OpenScholar-compatible service.
- `tests/`: pytest acceptance tests.

## Local setup

Python 3.10+ is recommended (tested here with Python 3.13). From this directory:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` if desired, then set environment variables in your shell or your preferred environment loader. The application does not automatically load `.env` files.

Start the API:

```bash
uvicorn app:app --reload
```

Start the UI in another terminal:

```bash
streamlit run streamlit_app.py
```

The UI defaults to `http://127.0.0.1:8000`. Override with `YIN_API_URL` if needed. API docs: `http://127.0.0.1:8000/docs`; health check: `http://127.0.0.1:8000/health`.

## Configuration

- `YIN_DB_PATH`: SQLite path; defaults to `yin.sqlite3` in the project directory.
- `YIN_API_URL`: FastAPI base URL used by Streamlit.
- `YIN_OPENSCHOLAR_BRIDGE_URL`: optional URL for a separately deployed OpenScholar wrapper. This project does not install or run the full OpenScholar model.
- `YIN_LLM_BASE_URL`, `YIN_LLM_API_KEY`, `YIN_LLM_MODEL`: all three are required to enable semantic auditing against an OpenAI-compatible `/chat/completions` endpoint. Never commit API keys.
- `YIN_LLM_TIMEOUT`: request timeout in seconds (default 60).

Semantic auditing is not available until an LLM endpoint and model are configured. The audit uses LLM-as-a-judge and is **not** a validated NLI classifier. Its classifications require human review. Abstract-only checks cannot establish support that may exist only in full text.

## API endpoints

- `GET /health`
- `POST /search` — searches and stores a run.
- `POST /review` — searches, writes a metadata-based evidence report, optionally requests synthesis, optionally audits the returned synthesis, optionally includes reference exports, and stores the run.
- `POST /verify-doi?doi=10.xxxx/example` — checks whether Crossref resolves a DOI record. A Crossref record is not validation of research claims.
- `POST /export/{bibtex|ris|apa7}` — body: `{"papers": [{...}]}`; returns a downloadable text file.
- `GET /runs?limit=50` — lists recent saved runs.
- `GET /runs/{run_id}` — returns parameters, retrieved papers, outputs, and event records.

Example review request:

```json
{
  "query": "administrative process reengineering and university performance",
  "limit": 10,
  "year_from": 2020,
  "year_to": 2026,
  "open_access_only": false,
  "include_synthesis": false,
  "run_semantic_audit": false,
  "export_references": true
}
```

## Reproducibility and data limits

SQLite stores the query, request parameters, timestamps, run status, provider-returned metadata, report/synthesis output, semantic audit result when requested, and run events. This improves traceability but does not guarantee exact reproducibility: external provider indexes can change, API responses can change, and stochastic model outputs may differ. The current build does not yet archive raw provider responses, exact provider query URLs, prompt/model hashes, or full-text snapshots. Do not describe it as a fully reproducible systematic-review platform.

## Export and bibliographic integrity

- Missing fields are omitted or labelled conservatively; no missing DOI is fabricated.
- BibTeX citation keys are made unique within each exported file.
- RIS uses a generic record type when no journal/source is supplied.
- APA 7 formatting is an approximation. Author-name parsing, non-English names, source types, capitalization, issue/page details, and special publication types may require manual correction.
- DOI syntax or Crossref metadata resolution alone does not prove the metadata matches the paper being cited.

## Run tests

```bash
python -m pytest -q
```

The tests use mocked provider results for API behavior and do not make live OpenAlex, Crossref, OpenScholar, or LLM calls. A successful test run is not an end-to-end deployment test.

## Known limitations

- Search coverage and ranking depend on OpenAlex indexing and query wording; this is not a complete systematic search across all scholarly databases.
- No automated full-text acquisition, duplicate screening, risk-of-bias assessment, or PRISMA workflow is implemented yet.
- Semantic audit is optional and unavailable until configured; LLM judgments can be wrong.
- Streamlit UI needs a local browser session and installed Streamlit dependencies; it has not been browser-tested in this environment.
- Human screening and source-level checking remain mandatory before academic citation.

## Deployment notes (API + Streamlit)

### FastAPI backend on Render

A `render.yaml` Blueprint is provided for the API. It uses the existing Dockerfile, `/health` health check, and a persistent disk mounted at `/var/data` for SQLite. **This configuration uses Render's paid `starter` service plan because a persistent disk is required for durable SQLite storage.** A free/ephemeral container filesystem can lose the database on restart or redeploy, so do not use it for persistent research history.

1. Push this repository to a private or public GitHub repository (never commit `.env`, keys, or database files).
2. In Render, create a new Blueprint and select the repository containing `render.yaml`.
3. Review the service plan and persistent-disk cost before applying it.
4. Add only the LLM/OpenScholar secrets you actually use. Leave optional integrations unconfigured if not needed.
5. After deployment, verify `https://<your-api-host>/health` and `https://<your-api-host>/docs`.
6. Confirm the returned health payload reports the expected SQLite path. Run a test search and then check `/runs`; restart/redeploy only after confirming the persistent disk is mounted.

### Streamlit Community Cloud frontend

The frontend can be deployed separately from the repository:

1. Connect the GitHub repository in Streamlit Community Cloud.
2. Set the app entry point to `streamlit_app.py`.
3. In the app's Secrets/settings, set `YIN_API_URL` to the deployed HTTPS API origin (without a trailing slash), for example `https://your-api-service.onrender.com`.
4. Do not put LLM API keys in the Streamlit frontend; keep provider secrets only in the backend service.
5. Test search, history retrieval, export downloads, and the disconnected-API error state.

### Container alternative for the frontend

`Dockerfile.streamlit` is included for platforms that support a separate Streamlit container. Set `YIN_API_URL` to the backend's HTTPS origin. The default `127.0.0.1` address is only correct when API and UI run on the same machine/network namespace.

### Deployment acceptance checklist

- [ ] `/health` returns HTTP 200.
- [ ] A test `/review` request returns a `run_id` and saves a record.
- [ ] `/runs` lists that record after an API restart.
- [ ] SQLite file resides on the persistent mount, not the container's ephemeral layer.
- [ ] Streamlit can reach the backend over HTTPS.
- [ ] No secrets, raw API keys, or database files are committed to Git.
- [ ] LLM audit and OpenScholar synthesis are tested only if their backend credentials/services are configured.

Cloud resources have not been created by this repository change. Actual deployment requires the user to connect the GitHub repository and approve any paid plan or disk.
