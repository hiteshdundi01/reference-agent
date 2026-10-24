"""The dashboard's build, served beside the API, and seeding from the command line."""

import runpy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import auth
from backend.dashboard import serve_dashboard


@pytest.fixture
def built(tmp_path):
    """An app serving a stand-in for the dashboard's build."""
    (tmp_path / "index.html").write_text("<title>Dashboard</title>")
    (tmp_path / "app.js").write_text("console.log('app')")
    app = FastAPI()
    serve_dashboard(app, tmp_path)
    with TestClient(app) as client:
        yield client


def test_the_builds_files_are_served(built):
    assert built.get("/app.js").text == "console.log('app')"


def test_the_dashboards_own_routes_load_its_page(built):
    assert "Dashboard" in built.get("/requests/REQ-1001").text


def test_an_unknown_api_path_stays_a_404(built):
    assert built.get("/api/nothing").status_code == 404


def test_with_no_build_the_app_is_the_api_alone(tmp_path):
    app = FastAPI()
    serve_dashboard(app, tmp_path / "dist")
    assert TestClient(app).get("/").status_code == 404


def test_seeding_from_the_command_line_rebuilds_the_database(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("APP_DB", str(tmp_path / "fresh.db"))
    runpy.run_module("backend.seed", run_name="__main__")
    assert "Seeded" in capsys.readouterr().out
    assert (tmp_path / "fresh.db").exists()


def test_signing_needs_the_secret(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET")
    with pytest.raises(RuntimeError, match="AUTH_SECRET is missing"):
        auth.token_for("riley.chen@acme.example")
