"""Batch validation CLI: check Scoreholder JSON files for structural issues.

Usage:
    python -m app.validate_json path/to/file.json [path/to/file2.json ...]
    python -m app.validate_json data-collection/2025/json/*.json
"""

import json
import sys
from pathlib import Path

from app.parser import parse_json, validate_upload_structure


def validate_file(path: Path) -> dict:
    """Validate a single JSON file. Returns a result dict."""
    result = {
        "path": str(path),
        "valid": True,
        "structure_errors": [],
        "parse_error": None,
        "event_name": None,
        "row_count": 0,
    }

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["structure_errors"].append(f"Invalid JSON: {e}")
        return result
    except FileNotFoundError:
        result["valid"] = False
        result["structure_errors"].append("File not found")
        return result

    errors = validate_upload_structure(data)
    if errors:
        result["valid"] = False
        result["structure_errors"] = errors
        return result

    try:
        event_info, rows = parse_json(data)
        result["event_name"] = event_info["name"]
        result["row_count"] = len(rows)
    except Exception as e:
        result["valid"] = False
        result["parse_error"] = str(e)

    return result


def main():
    paths = [Path(a) for a in sys.argv[1:]]

    if not paths:
        print("Usage: python -m app.validate_json path/to/file.json [...]")
        sys.exit(1)

    total = 0
    passed = 0
    failed = 0

    for path in paths:
        if path.is_dir():
            for child in sorted(path.glob("*.json")):
                result = validate_file(child)
                total += 1
                _print_result(result)
                if result["valid"]:
                    passed += 1
                else:
                    failed += 1
        else:
            result = validate_file(path)
            total += 1
            _print_result(result)
            if result["valid"]:
                passed += 1
            else:
                failed += 1

    print(f"\n{'=' * 40}")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
    sys.exit(0 if failed == 0 else 1)


def _print_result(result: dict):
    status = "PASS" if result["valid"] else "FAIL"
    name = result["event_name"] or "(unknown)"
    detail = f"  ({result['row_count']} rows)" if result["valid"] else ""
    print(f"[{status}] {result['path']} — {name}{detail}")
    for err in result["structure_errors"]:
        print(f"       STRUCTURE: {err}")
    if result["parse_error"]:
        print(f"       PARSE: {result['parse_error']}")


if __name__ == "__main__":
    main()
