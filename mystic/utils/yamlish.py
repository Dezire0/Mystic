"""A tiny YAML subset loader sufficient for Mystic v0.1 config files."""

from __future__ import annotations

from pathlib import Path


def load_yaml_file(path: str | Path) -> dict:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    cleaned = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cleaned.append(raw.rstrip("\n"))

    value, index = _parse_block(cleaned, 0, 0)
    if index != len(cleaned):
        raise ValueError(f"Unexpected trailing config content near line {index + 1}")
    if not isinstance(value, dict):
        raise ValueError("Top-level YAML content must be a mapping")
    return value


def _parse_block(lines: list[str], index: int, indent: int):
    if index >= len(lines):
        return {}, index

    current_indent = _indent_of(lines[index])
    if current_indent < indent:
        return {}, index
    if current_indent > indent:
        raise ValueError(f"Invalid indentation near line {index + 1}")

    if lines[index].lstrip().startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: list[str], index: int, indent: int):
    result: dict[str, object] = {}
    while index < len(lines):
        line = lines[index]
        current_indent = _indent_of(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"Unexpected nested indentation near line {index + 1}")
        stripped = line.strip()
        if stripped.startswith("- "):
            break
        key, _, tail = stripped.partition(":")
        if not _:
            raise ValueError(f"Expected mapping entry near line {index + 1}")
        value_text = tail.strip()
        index += 1
        if value_text:
            result[key] = _parse_scalar(value_text)
            continue
        if index >= len(lines) or _indent_of(lines[index]) <= current_indent:
            result[key] = {}
            continue
        nested, index = _parse_block(lines, index, current_indent + 2)
        result[key] = nested
    return result, index


def _parse_list(lines: list[str], index: int, indent: int):
    result: list[object] = []
    while index < len(lines):
        line = lines[index]
        current_indent = _indent_of(line)
        if current_indent < indent:
            break
        if current_indent != indent:
            raise ValueError(f"Unexpected list indentation near line {index + 1}")
        stripped = line.strip()
        if not stripped.startswith("- "):
            break
        value_text = stripped[2:].strip()
        if not value_text:
            raise ValueError(f"Empty list value near line {index + 1}")
        result.append(_parse_scalar(value_text))
        index += 1
    return result, index


def _parse_scalar(value: str):
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value.strip("'\"")


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))

