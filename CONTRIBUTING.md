# Contributing

## Development workflow

1. Create a branch for a focused change.
2. Use Python 3.11 where possible.
3. Install dependencies with `python -m pip install -r requirements.txt`.
4. Run `python -m pytest -q` before opening a pull request.
5. Document behavior changes and configuration changes in the README or `docs/`.
6. Never include secrets, personal data, production SQLite files, or generated cache folders.

## Research integrity

- Do not fabricate bibliographic metadata, DOIs, citations, or verification outcomes.
- Distinguish metadata resolution from verification of a paper's claims.
- Preserve explicit uncertainty and human-review requirements.
- Add tests for edge cases and missing bibliographic fields.

## Pull requests

Describe the problem, the change, tests executed, known limitations, and whether any external provider was contacted. Do not state that a live integration was tested unless it was actually tested.
