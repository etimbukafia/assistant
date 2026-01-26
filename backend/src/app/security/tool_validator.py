"""
Tool Argument Validator

Validates and sanitizes tool arguments before execution.
Prevents malicious or malformed arguments from being processed.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class ValidationResult:
    """Result of tool argument validation."""
    valid: bool
    errors: List[str]
    sanitized_args: Dict[str, Any]


# Maximum lengths for string fields to prevent abuse
MAX_STRING_LENGTHS = {
    "query": 500,
    "title": 200,
    "description": 2000,
    "key": 100,
    "value": 1000,
    "reason": 500,
    "tone": 50,
    "default": 1000
}

# Allowed enum values for validation
ALLOWED_ENUMS = {
    "status": ["pending", "in_progress", "done", "dismissed"],
    "priority": ["low", "medium", "high", "urgent"],
    "tone": ["professional", "friendly", "formal", "casual", "empathetic"],
    "context_type": ["drafting", "scheduling", "task_review"]
}


def validate_tool_args(
    tool_name: str,
    args: Dict[str, Any],
    schema: Dict[str, Any]
) -> ValidationResult:
    """
    Validate tool arguments against their schema.

    Args:
        tool_name: Name of the tool being called
        args: Arguments provided by the LLM
        schema: JSON schema for the tool's parameters

    Returns:
        ValidationResult with validation status and sanitized args
    """
    errors = []
    sanitized = {}

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Check required fields
    for field in required:
        if field not in args or args[field] is None:
            errors.append(f"Missing required field: {field}")

    # Validate and sanitize each provided argument
    for field, value in args.items():
        if field not in properties:
            # Unknown field - skip it (don't pass to tool)
            continue

        field_schema = properties[field]
        field_type = field_schema.get("type", "string")

        # Type validation and sanitization
        if field_type == "string":
            valid, sanitized_value, error = _validate_string(
                field, value, field_schema
            )
            if not valid:
                errors.append(error)
            else:
                sanitized[field] = sanitized_value

        elif field_type == "integer":
            valid, sanitized_value, error = _validate_integer(
                field, value, field_schema
            )
            if not valid:
                errors.append(error)
            else:
                sanitized[field] = sanitized_value

        elif field_type == "boolean":
            valid, sanitized_value, error = _validate_boolean(field, value)
            if not valid:
                errors.append(error)
            else:
                sanitized[field] = sanitized_value

        elif field_type == "array":
            valid, sanitized_value, error = _validate_array(
                field, value, field_schema
            )
            if not valid:
                errors.append(error)
            else:
                sanitized[field] = sanitized_value

        else:
            # Unknown type - pass through but sanitize if string-like
            sanitized[field] = _sanitize_value(value)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        sanitized_args=sanitized
    )


def _validate_string(
    field: str,
    value: Any,
    schema: Dict[str, Any]
) -> Tuple[bool, str, Optional[str]]:
    """Validate and sanitize a string field."""
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return False, "", f"Field {field} must be a string"

    # Apply max length
    max_len = MAX_STRING_LENGTHS.get(field, MAX_STRING_LENGTHS["default"])
    if len(value) > max_len:
        value = value[:max_len]

    # Check enum constraints
    if "enum" in schema:
        allowed = schema["enum"]
        # Also check our additional enum constraints
        if field in ALLOWED_ENUMS:
            allowed = ALLOWED_ENUMS[field]

        if value not in allowed:
            return False, "", f"Field {field} must be one of: {allowed}"

    # Sanitize: strip control characters
    sanitized = _strip_control_chars(value)

    return True, sanitized, None


def _validate_integer(
    field: str,
    value: Any,
    schema: Dict[str, Any]
) -> Tuple[bool, int, Optional[str]]:
    """Validate an integer field."""
    if isinstance(value, bool):
        return False, 0, f"Field {field} must be an integer, not boolean"

    if not isinstance(value, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            return False, 0, f"Field {field} must be an integer"

    # Check bounds
    minimum = schema.get("minimum")
    maximum = schema.get("maximum")

    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum

    # Default max for IDs and limits
    if field.endswith("_id") and value > 2147483647:  # Max int32
        return False, 0, f"Field {field} exceeds maximum value"
    if field == "limit" and value > 100:
        value = 100

    return True, value, None


def _validate_boolean(
    field: str,
    value: Any
) -> Tuple[bool, bool, Optional[str]]:
    """Validate a boolean field."""
    if isinstance(value, bool):
        return True, value, None

    if isinstance(value, str):
        if value.lower() in ("true", "1", "yes"):
            return True, True, None
        if value.lower() in ("false", "0", "no"):
            return True, False, None

    return False, False, f"Field {field} must be a boolean"


def _validate_array(
    field: str,
    value: Any,
    schema: Dict[str, Any]
) -> Tuple[bool, List, Optional[str]]:
    """Validate an array field."""
    if not isinstance(value, list):
        return False, [], f"Field {field} must be an array"

    # Limit array size
    max_items = schema.get("maxItems", 20)
    if len(value) > max_items:
        value = value[:max_items]

    # Sanitize array items
    items_schema = schema.get("items", {})
    items_type = items_schema.get("type", "string")

    sanitized = []
    for item in value:
        if items_type == "string":
            if isinstance(item, str):
                sanitized.append(_strip_control_chars(item[:500]))
        else:
            sanitized.append(_sanitize_value(item))

    return True, sanitized, None


def _strip_control_chars(text: str) -> str:
    """Remove control characters from text."""
    return "".join(char for char in text if char >= " " or char in "\n\r\t")


def _sanitize_value(value: Any) -> Any:
    """Generic sanitization for unknown types."""
    if isinstance(value, str):
        return _strip_control_chars(value[:1000])
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value[:20]]
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in list(value.items())[:20]}
    return None


def sanitize_tool_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Quick sanitization without schema validation.
    Use when you just need to clean values.
    """
    return {k: _sanitize_value(v) for k, v in args.items()}
