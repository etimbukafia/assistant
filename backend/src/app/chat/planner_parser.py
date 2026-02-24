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


def _repair_plan_shape(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tolerate minor planner contract misses by synthesizing sub_requests from nodes.
    """
    if not isinstance(data, dict):
        return data

    nodes = data.get("nodes")
    sub_requests = data.get("sub_requests")
    if isinstance(nodes, list) and nodes and (not isinstance(sub_requests, list) or not sub_requests):
        synthesized: list[Dict[str, Any]] = []
        seen: set[str] = set()
        for idx, node in enumerate(nodes, start=1):
            if not isinstance(node, dict):
                continue
            srid = str(node.get("sub_request_id") or node.get("id") or f"sr_{idx}").strip()
            if not srid or srid in seen:
                continue
            seen.add(srid)
            # Backfill node sub_request_id if missing/blank
            if not (node.get("sub_request_id") or "").strip():
                node["sub_request_id"] = srid
            tool_name = str(node.get("tool") or "action").strip() or "action"
            args = node.get("args")
            text_hint = ""
            if isinstance(args, dict):
                text_hint = (
                    str(args.get("meeting_subject") or "")
                    or str(args.get("subject") or "")
                    or str(args.get("query") or "")
                ).strip()
            synthesized.append(
                {
                    "id": srid,
                    "intent": tool_name,
                    "text": text_hint or tool_name,
                    "blocking": False,
                    "metadata": {},
                }
            )
        if synthesized:
            data["sub_requests"] = synthesized
    # Repair sub_requests shape if LLM used "description" instead of "text"
    if isinstance(sub_requests, list):
        for item in sub_requests:
            if not isinstance(item, dict):
                continue
            if not item.get("text") and item.get("description"):
                item["text"] = str(item.get("description") or "").strip()
            if not item.get("intent"):
                item["intent"] = str(item.get("tool") or item.get("type") or "request").strip()
    return data


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

    data = _repair_plan_shape(data)

    try:
        return ExecutionPlan.model_validate(data)
    except ValidationError as exc:
        raise PlanParseError(f"Invalid execution plan: {exc}") from exc
