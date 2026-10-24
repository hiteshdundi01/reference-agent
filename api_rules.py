"""The rules every operation of our API follows, checked against its OpenAPI
schema: an operation id and a one-line description, and for the operations the
agent's tools call (tagged "agent") no optional inputs, including inside the
models a request body holds."""

from typing import Any

AGENT_TAG = "agent"


def references(node: Any) -> list[str]:
    """The names of the models a part of the schema refers to."""
    if isinstance(node, dict):
        found = [node["$ref"].split("/")[-1]] if "$ref" in node else []
        return found + [name for value in node.values() for name in references(value)]
    if isinstance(node, list):
        return [name for value in node for name in references(value)]
    return []


def optional_fields(models: dict[str, Any], name: str, seen: set[str]) -> list[str]:
    """The optional fields of a model and of every model inside it."""
    if name in seen:
        return []
    seen.add(name)
    properties = models[name].get("properties", {})
    optional = set(properties) - set(models[name].get("required", []))
    found = [f"{name}.{field} is optional" for field in sorted(optional)]
    for inner in dict.fromkeys(
        references(properties) + references(models[name].get("oneOf", []))
    ):
        found += optional_fields(models, inner, seen)
    return found


def inputs_breaks(
    name: str, operation: dict[str, Any], models: dict[str, Any]
) -> list[str]:
    """Where an agent operation takes an optional input."""
    breaks = [
        f"{name}: {parameter['name']} is optional"
        for parameter in operation.get("parameters", [])
        if not parameter["required"]
    ]
    if "requestBody" in operation:
        body = operation["requestBody"]
        if not body.get("required"):
            breaks.append(f"{name}: the body is optional")
        seen: set[str] = set()
        for model in dict.fromkeys(references(body)):
            breaks += [
                f"{name}: {field}" for field in optional_fields(models, model, seen)
            ]
    return breaks


def rule_breaks(schema: dict[str, Any]) -> list[str]:
    """Every place the API breaks the rules, or nothing when it keeps them."""
    models = schema.get("components", {}).get("schemas", {})
    breaks = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            name = f"{method.upper()} {path}"
            description = operation.get("description", "")
            if not operation.get("operationId"):
                breaks.append(f"{name} has no operation id")
            if not description or "\n" in description:
                breaks.append(f"{name} needs a one-line description")
            if AGENT_TAG in operation.get("tags", []):
                breaks += inputs_breaks(name, operation, models)
    return breaks
