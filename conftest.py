"""Fixtures for the backend's and the agent's tests. No test reaches a service
outside the machine, reads .env or calls a real model."""

import json
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import agent_service, auth
from backend.database import engine, seed
from backend.dependencies import API_KEY_HEADER
from backend.main import app
from backend.tests.credentials import TEST_KEY, TEST_PASSWORD, TEST_SECRET

SETTINGS = (
    "AGENT_URL",
    "APP_API",
    "AGENT_MODEL",
    "CHECKPOINT_DB",
    "ANTHROPIC_WORKSPACE_ID",
)


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    """The tests' own key, password and secret, and none of the shell's service
    settings."""
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AGENT_KEY", TEST_KEY)
    monkeypatch.setenv("USER_PASSWORD", TEST_PASSWORD)
    monkeypatch.setenv("AUTH_SECRET", TEST_SECRET)


@pytest.fixture(scope="session")
def seeded(tmp_path_factory):
    """A database seeded once for the whole session."""
    path = tmp_path_factory.mktemp("seeded") / "app.db"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("APP_DB", str(path))
        monkeypatch.setenv("USER_PASSWORD", TEST_PASSWORD)
        seed(engine())
    return path


@pytest.fixture(autouse=True)
def database(seeded, tmp_path, monkeypatch):
    """Every test's own copy of the seeded database, which is quicker than
    seeding each time."""
    path = tmp_path / "app.db"
    shutil.copyfile(seeded, path)
    monkeypatch.setenv("APP_DB", str(path))
    return path


@pytest.fixture
def agent_answers(monkeypatch):
    """Answer the backend's calls to the agent with a handler of the test's own."""

    def answer_with(handler):
        transport = httpx.MockTransport(handler)
        monkeypatch.setattr(agent_service, "client", httpx.Client(transport=transport))

    return answer_with


@pytest.fixture(autouse=True)
def agent_calls(agent_answers):
    """Stand in for the agent, taking every piece of work and keeping each payload."""
    calls: list[dict] = []

    def accept(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=agent_service.ACCEPTED)

    agent_answers(accept)
    return calls


@pytest.fixture
def agent():
    """The backend as the agent calls it, with its key."""
    with TestClient(app, headers={API_KEY_HEADER: TEST_KEY}) as caller:
        yield caller


@pytest.fixture
def anonymous():
    """The backend as a browser calls it before anyone signs in."""
    with TestClient(app) as caller:
        yield caller


def signed_in_as(email: str) -> TestClient:
    return TestClient(app, headers={"Authorization": f"Bearer {auth.token_for(email)}"})


@pytest.fixture
def rep():
    """The backend as Riley Chen, a rep, calls it."""
    with signed_in_as("riley.chen@acme.example") as caller:
        yield caller


@pytest.fixture
def supervisor():
    """The backend as Morgan Diaz, a supervisor, calls it."""
    with signed_in_as("morgan.diaz@acme.example") as caller:
        yield caller
