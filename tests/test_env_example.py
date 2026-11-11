"""Every environment variable ``src/config.py`` reads must be listed in ``.env.example``.

Regression test: ``DEFAULT_ALERT_THRESHOLD_PCT``, ``B2B_DISCOUNT_FACTOR`` and
``PRICE_RETENTION_DAYS`` (the pipeline's main business knobs) were read by
``src/config.py`` but missing from ``.env.example``, so nobody setting up a
``.env`` from the template knew they could be changed.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _config_env_names() -> set[str]:
    src = (REPO_ROOT / "src" / "config.py").read_text()
    return set(re.findall(r"os\.getenv\(\s*[\"']([A-Z0-9_]+)[\"']", src))


def _env_example_names() -> set[str]:
    text = (REPO_ROOT / ".env.example").read_text()
    return set(re.findall(r"^([A-Z0-9_]+)=", text, flags=re.MULTILINE))


def test_config_reads_some_env_vars():
    # Guards the regex: if config.py stopped using os.getenv literally, the
    # comparison below would pass vacuously.
    assert {"DATABASE_URL", "PRICE_RETENTION_DAYS"} <= _config_env_names()


def test_every_config_env_var_is_in_env_example():
    missing = _config_env_names() - _env_example_names()
    assert not missing, f".env.example is missing: {sorted(missing)}"
