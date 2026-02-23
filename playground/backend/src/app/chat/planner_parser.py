"""
Parsing and validation helpers for structured execution plans.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Union

from pydantic import ValidationError

from .planner_models import ExecutionPlan


class PlanParseError(ValueError):
    """Raised when planner output cannot be parsed into a valid ExecutionPlan."""


_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def _strip_code_fence(raw: str) -> str:
    match = _CODE_FENCE_RE.match(raw or "")
    if match:
        return (match.group(1) or "").strip()
    return (raw or "").strip()


def _extract_first_json_object(raw: str) -> Dict[str, Any]:
    decoder = json.JSONDecoder()
    text = raw or ""
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[idx:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    raise PlanParseError("Could not find a valid JSON object in planner output")


def parse_execution_plan(payload: Union[str, Dict[str, Any], ExecutionPlan]) -> ExecutionPlan:
    """
    Parse planner output and validate against ExecutionPlan contract.
    """
    if isinstance(payload, ExecutionPlan):
        return payload

    data: Dict[str, Any]
    if isinstance(payload, dict):
        data = payload
    elif isinstance(payload, str):
        raw = _strip_code_fence(payload)
        if not raw:
            raise PlanParseError("Planner output is empty")
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise PlanParseError("Planner output must be a JSON object")
            data = parsed
        except json.JSONDecodeError:
            data = _extract_first_json_object(raw)
    else:
        raise PlanParseError(f"Unsupported planner payload type: {type(payload).__name__}")

    try:
        return ExecutionPlan.model_validate(data)
    except ValidationError as exc:
        raise PlanParseError(f"Invalid execution plan: {exc}") from exc
