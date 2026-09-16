import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator

SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "schemas"


def load_schema(schema_name: str) -> Dict[str, Any]:
    schema_path = SCHEMAS_DIR / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file {schema_name} not found at {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_data_against_schema(data: Dict[str, Any], schema_name: str) -> Tuple[bool, List[str]]:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema)
    errors = [err.message for err in validator.iter_errors(data)]
    return len(errors) == 0, errors


def validate_resource_manifest(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    return validate_data_against_schema(data, "resource.schema.json")


def validate_graph_edge(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    return validate_data_against_schema(data, "graph.schema.json")


def validate_stack_manifest(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    return validate_data_against_schema(data, "stack.schema.json")
