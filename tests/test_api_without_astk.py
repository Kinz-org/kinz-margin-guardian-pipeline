"""The API must import and serve without the private ``astk`` toolkit.

Regression test: ``api/database.py`` used to hard-import ``astk.db.make_engine``
(and ``api/main.py`` ``astk.db.healthcheck``) with no fallback. In the
lightweight CI environment, where astk is not installed, that ImportError was
caught by the ``client`` fixture and every test in ``tests/test_api.py`` was
skipped as "fastapi not installed", so the API routes were never tested in CI.

Each check runs in a fresh interpreter with ``astk`` blocked in ``sys.modules``,
so it behaves the same whether or not astk happens to be installed locally.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("jwt")
pytest.importorskip("slowapi")

ROOT = Path(__file__).resolve().parent.parent

_PRELUDE = """
import sys
sys.modules["astk"] = None
sys.modules["astk.db"] = None
"""


def _run(code: str, database_url: str) -> dict:
    env = {"DATABASE_URL": database_url, "PATH": "", "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        [sys.executable, "-c", _PRELUDE + code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_api_app_imports_without_astk(tmp_path):
    out = _run(
        "import json\n"
        "from api.main import app\n"
        "from api.database import get_db, engine\n"
        "print(json.dumps({'title': app.title, 'url': str(engine.url)}))\n",
        f"sqlite:///{tmp_path / 'x.db'}",
    )
    assert out["title"] == "Kinz Margin Guardian API"
    assert out["url"].endswith("x.db")


def test_fallback_healthcheck_reports_reachable_and_unreachable(tmp_path):
    out = _run(
        "import json\n"
        "from api.database import engine, healthcheck, make_engine\n"
        "bad = make_engine('sqlite:////nonexistent-dir-for-test/sub/x.db')\n"
        "print(json.dumps({'ok': healthcheck(engine), 'bad': healthcheck(bad)}))\n",
        f"sqlite:///{tmp_path / 'y.db'}",
    )
    assert out == {"ok": True, "bad": False}


def test_fallback_make_engine_caches_and_shares_in_memory_sqlite(tmp_path):
    out = _run(
        "import json\n"
        "from sqlalchemy import text\n"
        "from sqlalchemy.pool import StaticPool\n"
        "from api.database import make_engine\n"
        "a = make_engine('sqlite://')\n"
        "b = make_engine('sqlite://')\n"
        "with a.begin() as c:\n"
        "    c.execute(text('CREATE TABLE t (x INTEGER)'))\n"
        "    c.execute(text('INSERT INTO t VALUES (7)'))\n"
        "with b.connect() as c:\n"
        "    v = c.execute(text('SELECT x FROM t')).scalar()\n"
        "print(json.dumps({'same': a is b, 'static': isinstance(a.pool, StaticPool),\n"
        "                  'value': v, 'pre_ping': a.pool._pre_ping}))\n",
        f"sqlite:///{tmp_path / 'z.db'}",
    )
    assert out == {"same": True, "static": True, "value": 7, "pre_ping": True}
