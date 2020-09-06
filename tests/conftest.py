"""``pytest`` configuration."""

import pytest

from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def app(monkeypatch) -> TestClient:
    """Make sure we use monkeypatch env."""
    monkeypatch.setenv("DISABLE_CACHE", "YESPLEASE")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "jqt")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "rde")
    from rezoning_api.main import app

    return TestClient(app)
