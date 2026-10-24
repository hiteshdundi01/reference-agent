"""Fixtures for the agent's tests: the agent's client reaches the real backend in
the test's own process, and each test keeps its checkpoints in a file of its own."""

import pytest
from fastapi.testclient import TestClient

from agent import connection
from backend.main import app

STUB_MODEL = "stub:model"


@pytest.fixture(autouse=True)
def backend_in_process(monkeypatch):
    with TestClient(app, base_url="http://testserver/api") as client:
        monkeypatch.setattr(connection, "backend", client)
        yield client


@pytest.fixture(autouse=True)
def checkpoint_file(tmp_path, monkeypatch):
    path = tmp_path / "checkpoints.db"
    monkeypatch.setenv("CHECKPOINT_DB", str(path))
    return path


@pytest.fixture(autouse=True)
def model_name(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", STUB_MODEL)
    return STUB_MODEL
