"""CORS policy of the API.

Regression for docs/IMPROVEMENTS.md "CORS allows any origin with credentials":
``api/main.py`` used ``allow_origins=["http://localhost:8501", "*"]`` with
``allow_credentials=True``, so Starlette echoed back any requesting origin and
any website could make credentialed calls to the API from a visitor's browser.
"""
from src.config import DEFAULT_CORS_ALLOW_ORIGINS, parse_cors_origins

DASHBOARD = "http://localhost:8501"
EVIL = "https://evil.example.com"


def _preflight(client, origin):
    return client.options(
        "/products",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_preflight_from_unlisted_origin_gets_no_allow_origin(client):
    response = _preflight(client, EVIL)
    assert "access-control-allow-origin" not in response.headers


def test_simple_request_from_unlisted_origin_gets_no_allow_origin(client):
    response = client.get("/", headers={"Origin": EVIL})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_from_dashboard_origin_is_allowed(client):
    response = _preflight(client, DASHBOARD)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == DASHBOARD
    assert response.headers["access-control-allow-credentials"] == "true"


def test_default_origins_are_the_dashboard_only():
    assert parse_cors_origins(None) == [DASHBOARD]
    assert DEFAULT_CORS_ALLOW_ORIGINS == DASHBOARD


def test_parse_splits_trims_and_drops_blanks():
    raw = " http://localhost:8501 , https://dash.kinzoils.com,,"
    assert parse_cors_origins(raw) == ["http://localhost:8501", "https://dash.kinzoils.com"]


def test_parse_drops_wildcard():
    assert parse_cors_origins("*") == []
    assert parse_cors_origins("http://localhost:8501,*") == ["http://localhost:8501"]


def test_parse_empty_string_means_no_cross_origin_access():
    assert parse_cors_origins("") == []
