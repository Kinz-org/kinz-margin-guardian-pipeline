# Contributing to kinz-margin-guardian-pipeline

## Development setup

```bash
git clone https://github.com/Kinz-org/kinz-margin-guardian-pipeline.git
cd kinz-margin-guardian-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy pytest pydantic SQLAlchemy
pip install -e .
# API test deps (optional but recommended)
pip install fastapi httpx PyJWT slowapi
```

## Running tests

```bash
pytest tests/ -v          # expect ~89 tests
ruff check src/ tests/     # expect clean
make check                 # test + ruff in its own .venv
```

`make check` builds `.venv` from `requirements.txt`, which does not include the
API test deps (`fastapi`, `PyJWT`, `slowapi`). In that venv `tests/test_api.py`
and `tests/test_api_without_astk.py` are skipped, so it runs fewer tests than CI.
Install the API deps into `.venv` (`.venv/bin/pip install fastapi httpx PyJWT slowapi`)
before `make check` to match CI.

## Full stack via Docker

```bash
make up    # Airflow :8080, API :8000, Dashboard :8501
make down
make seed  # seed KINZ products
```

## CI

CI runs on push + pull_request to main:
- Test job (Python 3.11 + 3.12): pytest + coverage + Codecov upload
- Docker build smoke test

## Pull request workflow

1. Create a branch from `main`.
2. Make your changes. Keep diffs small (≤400 lines).
3. Run `make check` locally (with the API deps installed, see above).
4. Open a PR with a clear description.
5. Squash-merge when CI is green.
