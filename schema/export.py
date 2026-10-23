"""Export and validate an external report while retaining the primary report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import warnings

from jsonschema.validators import validator_for
from jsonschema.exceptions import SchemaError

from .adapter import AdapterWarning, to_external
from .validate import FORMAT_CHECKER, SCHEMA_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--schema", type=Path, help="external JSON Schema; omitted means identity export")
    parser.add_argument("--out", type=Path, help="default: report.external.json beside the primary report")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        external = json.loads(args.schema.read_text(encoding="utf-8")) if args.schema else None
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", AdapterWarning)
            exported = to_external(report, external)
        target_schema = external or json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        validator_class = validator_for(target_schema)
        validator_class.check_schema(target_schema)
        errors = sorted(validator_class(target_schema, format_checker=FORMAT_CHECKER).iter_errors(exported), key=lambda error: str(list(error.path)))
        output = args.out or args.report.with_name(args.report.stem + ".external.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        notes = [str(item.message) for item in captured]
        if notes:
            output.with_suffix(".notes.json").write_text(json.dumps({"adapter_notes": notes}, indent=2) + "\n", encoding="utf-8")
            for note in notes:
                print("NOTE: " + note)
        if errors:
            for error in errors:
                print(f"{output}: $.{'.'.join(str(part) for part in error.path)}: {error.message}")
            return 1
        output.write_text(json.dumps(exported, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{output}: valid ({'external contract' if external else 'identity; primary contract'})")
        return 0
    except (OSError, ValueError, KeyError, SchemaError) as exc:
        print(f"Cannot export: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
