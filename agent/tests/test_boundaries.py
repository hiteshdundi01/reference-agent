"""What each part of the agent may import (docs/CODE_STANDARDS.md, rule 15), and
the one module that sends requests."""

import ast
from pathlib import Path

AGENT = Path(__file__).parent.parent
# Each module of the agent, and the agent's modules it may import.
ALLOWED = {
    "connection": set(),
    "api": {"connection"},
    "models": set(),
    "checkpoints": set(),
    "tools": {"api", "connection"},
    "harness": {"api", "checkpoints", "connection", "models", "tools"},
    "entrypoint": {"api", "connection", "harness", "models"},
}


def tree_of(module: str) -> ast.Module:
    return ast.parse((AGENT / f"{module}.py").read_text(encoding="utf-8"))


def agent_imports(module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree_of(module)):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if node.module == "agent":
            names |= {alias.name for alias in node.names}
        elif node.module.startswith("agent."):
            names.add(node.module.removeprefix("agent."))
    return names


def test_every_module_is_listed():
    assert {path.stem for path in AGENT.glob("*.py")} - {"__init__"} == set(ALLOWED)


def test_each_module_imports_only_what_it_may():
    for module, allowed in ALLOWED.items():
        assert agent_imports(module) <= allowed, module


def test_nothing_imports_the_app():
    for module in ALLOWED:
        assert "entrypoint" not in agent_imports(module), module


def test_only_the_connection_makes_an_http_client():
    for module in ALLOWED.keys() - {"connection"}:
        source = (AGENT / f"{module}.py").read_text(encoding="utf-8")
        assert "httpx.Client(" not in source, module


def test_the_agent_never_imports_the_backend():
    for module in ALLOWED:
        for node in ast.walk(tree_of(module)):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("backend"), module
