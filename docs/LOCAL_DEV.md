# Local development

Generic commands for running BiteSIze on your machine. Do not put personal emails, API keys, or paths here — use `.env` and gitignored local notes instead.

## Python CLI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit with your credentials
python main.py --all
```

## Settings dashboard

```bash
python dashboard.py
```

Open http://127.0.0.1:8765 — settings are stored in `data/bitesize.db` (gitignored).

## Tests

```bash
pip install -r requirements-dev.txt   # readability-lxml + pytest-cov + pip-audit
pytest tests/ -v --cov
```

## Wordflow (experimental)

See [wordflow/README.md](../wordflow/README.md).
