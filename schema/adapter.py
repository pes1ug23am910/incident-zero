"""Project the primary report contract into a supplied external contract."""

from __future__ import annotations

import copy
from pathlib import Path
import warnings

MAPPING_PATH = Path(__file__).with_name("MAPPING.md")
_MISSING = object()


class AdapterWarning(UserWarning):
    """An external field has no measured internal value."""


def field_mapping(path: Path = MAPPING_PATH) -> dict[str, str]:
    """Read the reviewable ours-to-theirs Markdown table, keyed by theirs."""
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Ours", "---", "*"}:
            continue
        if cells[0] and cells[1]:
            result[cells[1]] = cells[0]
    return result


def _get_path(value, path):
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def to_external(report: dict, external_schema: dict | None = None) -> dict:
    """Identity until a schema arrives; otherwise drop unmapped external fields.

    Required unavailable values become null (if permitted) or not_available for
    strings. Unsupported required numeric/structured fields remain explicit
    nulls, so validation fails visibly instead of inventing measurements.
    """
    if not external_schema:
        return copy.deepcopy(report)
    mapping = field_mapping()
    notes = []

    def dereference(schema):
        seen = set()
        while "$ref" in schema:
            ref = schema["$ref"]
            if not ref.startswith("#/") or ref in seen:
                raise ValueError("adapter supports non-recursive local schema references only")
            seen.add(ref)
            node = external_schema
            for part in ref[2:].split("/"):
                node = node[part.replace("~1", "/").replace("~0", "~")]
            schema = {**node, **{key: value for key, value in schema.items() if key != "$ref"}}
        return schema

    def missing_value(schema, path):
        types = schema.get("type", [])
        types = [types] if isinstance(types, str) else types
        notes.append(f"{path}: required external field has no internal value; exported an explicit unavailable value.")
        if "null" in types or not types:
            return None
        return "not_available" if "string" in types else None

    def project(value, schema, path=""):
        schema = dereference(schema)
        properties = schema.get("properties")
        if isinstance(properties, dict):
            output = {}
            required = set(schema.get("required", []))
            for key, child_schema in properties.items():
                child_path = f"{path}.{key}" if path else key
                child_value = _get_path(report, mapping[child_path]) if child_path in mapping else (
                    value.get(key, _MISSING) if isinstance(value, dict) else _MISSING
                )
                child_schema = dereference(child_schema)
                if child_value is _MISSING:
                    if key in required:
                        output[key] = missing_value(child_schema, child_path)
                else:
                    output[key] = project(child_value, child_schema, child_path)
            return output
        if isinstance(value, list) and isinstance(schema.get("items"), dict):
            return [project(item, schema["items"], path + "[]") for item in value]
        return copy.deepcopy(value)

    result = project(report, external_schema)
    if not isinstance(result, dict):
        raise ValueError("external report schema must describe an object")
    if notes:
        note_schema = external_schema.get("properties", {}).get("adapter_notes")
        if note_schema:
            result["adapter_notes"] = notes if note_schema.get("type") == "array" else " ".join(notes)
        for note in notes:
            warnings.warn(note, AdapterWarning, stacklevel=2)
    return result
