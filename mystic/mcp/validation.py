from __future__ import annotations

from typing import Any


def validate_json_schema(instance: Any, schema: dict[str, Any], *, path: str = "$") -> list[str]:
    errors: list[str] = []
    schema_type = schema.get("type")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']}")

    if schema_type is not None and not _matches_type(instance, schema_type):
        return [f"{path} must be of type {schema_type}"]

    if schema_type == "object":
        errors.extend(_validate_object(instance, schema, path=path))
    elif schema_type == "array":
        errors.extend(_validate_array(instance, schema, path=path))
    elif schema_type == "string":
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < int(min_length):
            errors.append(f"{path} must be at least {min_length} characters long")
    elif schema_type == "integer":
        errors.extend(_validate_number(instance, schema, path=path))
    elif schema_type == "number":
        errors.extend(_validate_number(instance, schema, path=path))

    return errors


def _validate_object(instance: dict[str, Any], schema: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    additional = schema.get("additionalProperties", True)

    for key in required:
        if key not in instance:
            errors.append(f"{path}.{key} is required")

    for key, value in instance.items():
        key_path = f"{path}.{key}"
        if key in properties:
            errors.extend(validate_json_schema(value, properties[key], path=key_path))
            continue
        if additional is False:
            errors.append(f"{key_path} is not allowed")
        elif isinstance(additional, dict):
            errors.extend(validate_json_schema(value, additional, path=key_path))

    return errors


def _validate_array(instance: list[Any], schema: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    min_items = schema.get("minItems")
    max_items = schema.get("maxItems")
    item_schema = schema.get("items")

    if min_items is not None and len(instance) < int(min_items):
        errors.append(f"{path} must contain at least {min_items} item(s)")
    if max_items is not None and len(instance) > int(max_items):
        errors.append(f"{path} must contain at most {max_items} item(s)")

    if isinstance(item_schema, dict):
        for index, value in enumerate(instance):
            errors.extend(validate_json_schema(value, item_schema, path=f"{path}[{index}]"))

    return errors


def _validate_number(instance: int | float, schema: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    if minimum is not None and instance < minimum:
        errors.append(f"{path} must be >= {minimum}")
    if maximum is not None and instance > maximum:
        errors.append(f"{path} must be <= {maximum}")
    return errors


def _matches_type(instance: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(instance, dict)
    if schema_type == "array":
        return isinstance(instance, list)
    if schema_type == "string":
        return isinstance(instance, str)
    if schema_type == "boolean":
        return isinstance(instance, bool)
    if schema_type == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if schema_type == "number":
        return (isinstance(instance, int) and not isinstance(instance, bool)) or isinstance(instance, float)
    return True
