# Improvements

The repo's improvement list, worked top-down by the `kinz-polish` loop. Each open
item says what is wrong, why it matters, and how to check the fix. Only things
found in the code are listed.

- [x] **API tests never ran in CI (all 23 skipped as "fastapi not installed").** (done 2026-10-12)
  `api/database.py` and `api/main.py` hard-imported `astk.db` (the private toolkit,
  not installed in CI). The `client` fixture in `tests/conftest.py` caught the
  resulting `ImportError` and skipped every test in `tests/test_api.py` with a
  message blaming fastapi, which CI does install. Fixed: `api/database.py` now falls
  back to SQLAlchemy-only `make_engine`/`healthcheck` (same behaviour: cached per
  URL, `pool_pre_ping`, SQLite-safe; `SELECT 1` probe that never raises) and
  `api/main.py` takes `healthcheck` from there. The fixture now skips only when
  fastapi/httpx/PyJWT/slowapi are really missing. Check: `pytest -rs` shows 0
  skips in `tests/test_api.py`; `tests/test_api_without_astk.py` imports the app
  with astk blocked.

- [ ] **`POST /auth/token` ignores `JWT_EXPIRE_MINUTES`.**
  `api/main.py`'s `login()` passes `expires_delta=timedelta(minutes=60)` to
  `create_access_token`, so the token lifetime is always 60 minutes. The setting
  is defined in `src/config.py`, documented in `.env.example`, and used as the
  default in `api/auth.py`, but the only caller overrides it. Changing it in
  `.env` has no effect. Fix: drop the explicit `expires_delta` (or pass
  `JWT_EXPIRE_MINUTES`). Check: a test that sets a different expiry and decodes
  the `exp` claim of a token from `/auth/token`.

- [ ] **CORS allows any origin with credentials.**
  `api/main.py` configures `CORSMiddleware(allow_origins=["http://localhost:8501", "*"],
  allow_credentials=True)`. With `"*"` present the localhost entry is meaningless,
  and Starlette echoes back any requesting origin when credentials are allowed, so
  any website can make credentialed calls to the API from a visitor's browser.
  Fix: read allowed origins from config (defaulting to the dashboard URL) and drop
  `"*"`. Check: a TestClient preflight from an unlisted origin gets no
  `access-control-allow-origin` header.

- [ ] **Three margin/retention settings are undocumented in `.env.example`.**
  `src/config.py` reads `DEFAULT_ALERT_THRESHOLD_PCT` (40.0), `B2B_DISCOUNT_FACTOR`
  (0.85) and `PRICE_RETENTION_DAYS` (90) from the environment in both the astk and
  the fallback branch, but `.env.example` stops at the JWT, Slack, API and Airflow
  variables. These are the main business knobs of the pipeline. Check: every
  `os.getenv` name in `src/config.py` appears in `.env.example` (a small test can
  enforce it).

- [ ] **No `.github/dependabot.yml`.**
  `.github/` holds only `ISSUE_TEMPLATE/` and `workflows/ci.yml`, so dependency
  updates are never surfaced. The requirements files use `>=` with no pins, so a
  breaking release lands silently on the next install. Check: the file exists and
  covers `pip` (the four `requirements*.txt`) and `github-actions`.
