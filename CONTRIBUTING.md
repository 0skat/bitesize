# Contributing

Thanks for your interest in BiteSIze!

## Setup

1. Fork and clone the repo.
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your local credentials (never commit `.env`).

## Running tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov
```

Add or update tests when changing behavior. CI runs the suite plus coverage, `pip-audit`, and gitleaks.

## Pull requests

- Keep changes focused and include tests for behavior changes.
- Do not commit secrets: `.env`, `data/`, `token.json`, or `credentials.json`.
- Run the full test suite before opening a PR.

## Security

See [SECURITY.md](SECURITY.md) for the threat model and how to report vulnerabilities.
