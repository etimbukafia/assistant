"""
Token usage tracking for LLM operations.
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Load pricing data once at module import
_PRICING_FILE = Path(__file__).parent / "model_pricing.json"
_PRICING: dict = {}

try:
    with open(_PRICING_FILE, 'r') as f:
        _PRICING = json.load(f)
except FileNotFoundError:
    logger.warning(f"Model pricing file not found: {_PRICING_FILE}")
except json.JSONDecodeError as e:
    logger.error(f"Invalid model pricing JSON: {e}")


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost in USD for token usage.

    Args:
        model: Model name (e.g., 'gemini-3-flash-preview')
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD
    """
    pricing = _PRICING.get(model)
    if not pricing:
        # Try partial match for model variants
        for key in _PRICING:
            if key in model or model in key:
                pricing = _PRICING[key]
                break

    if not pricing:
        logger.warning(f"No pricing found for model: {model}")
        return 0.0

    input_cost = (input_tokens / 1_000_000) * pricing.get('input_per_million', 0)
    output_cost = (output_tokens / 1_000_000) * pricing.get('output_per_million', 0)

    return input_cost + output_cost


def get_model_pricing(model: str) -> Optional[dict[str, Any]]:
    """
    Return pricing metadata for a model if present.

    Uses the same exact-or-partial matching strategy as calculate_cost().
    """
    pricing = _PRICING.get(model)
    if pricing:
        return pricing

    for key in _PRICING:
        if key in model or model in key:
            return _PRICING[key]
    return None


def infer_provider_from_model(model: str) -> str:
    """
    Infer the provider/backend family for a model name.

    Prefers explicit pricing metadata and falls back to conservative
    name-based detection for older rows.
    """
    pricing = get_model_pricing(model) or {}
    provider = str(pricing.get("provider") or "").strip().lower()
    if provider:
        return provider

    normalized = (model or "").strip().lower()
    if normalized.startswith("claude"):
        return "anthropic"
    if normalized.startswith("gemini"):
        return "gemini"
    if normalized.startswith("gemma"):
        return "huggingface"
    if normalized.startswith("qwen/") or normalized.startswith("meta-llama/"):
        return "huggingface"
    return "unknown"


def is_billable_model(model: str) -> bool:
    """
    Whether this model should consume credits.

    Policy:
    - models with positive configured pricing are billable
    - zero-cost models are free
    - Gemma remains free
    - unknown models default to non-billable until explicitly priced
    """
    pricing = get_model_pricing(model)
    if not pricing:
        return False

    input_price = float(pricing.get("input_per_million", 0) or 0)
    output_price = float(pricing.get("output_per_million", 0) or 0)
    return input_price > 0 or output_price > 0


def record_token_usage(
    db: Session,
    user_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    operation: str,
    flush_credits: bool = True,
) -> None:
    """
    Record token usage to the database.

    Also updates credits_used on UserSettings for billable hosted models.

    Args:
        db: Database session
        user_id: User ID
        model: Model name used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        operation: Operation type (e.g., 'email_processing', 'chat')
    """
    if input_tokens == 0 and output_tokens == 0:
        return

    from app.data.models import TokenUsage
    from app.services.credits import add_credit_usage

    cost = calculate_cost(model, input_tokens, output_tokens)

    usage = TokenUsage(
        user_id=user_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        operation=operation
    )
    db.add(usage)

    # Update credit usage for billable models. Gemma remains free via zero pricing.
    if cost > 0 and is_billable_model(model):
        add_credit_usage(db, user_id, cost, flush=flush_credits)

    # Don't commit here - let caller handle transaction


def get_user_usage_summary(db: Session, user_id: str) -> dict:
    """
    Get total token usage summary for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Dict with total_input_tokens, total_output_tokens, total_cost_usd
    """
    from sqlalchemy import func
    from app.data.models import TokenUsage

    result = db.query(
        func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('total_input'),
        func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('total_output'),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0).label('total_cost')
    ).filter(TokenUsage.user_id == user_id).first()

    return {
        'total_input_tokens': int(result.total_input),
        'total_output_tokens': int(result.total_output),
        'total_cost_usd': float(result.total_cost)
    }


def get_usage_breakdown(
    db: Session,
    *,
    days: int = 30,
    user_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    operation: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Return grouped token-usage reporting for admin auditing.

    Grouping is per model + operation. Provider is inferred from pricing
    metadata or model naming so existing rows remain reportable without a
    schema migration.
    """
    from sqlalchemy import func
    from app.data.models import TokenUsage

    normalized_provider = (provider or "").strip().lower() or None
    normalized_model = (model or "").strip() or None
    normalized_operation = (operation or "").strip().lower() or None
    safe_days = max(1, int(days or 30))
    safe_limit = max(1, min(int(limit or 50), 200))
    since = datetime.now(timezone.utc) - timedelta(days=safe_days)

    query = db.query(
        TokenUsage.model.label("model"),
        TokenUsage.operation.label("operation"),
        func.count(TokenUsage.id).label("request_count"),
        func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(TokenUsage.cost_usd), 0.0).label("cost_usd"),
    ).filter(TokenUsage.created_at >= since.replace(tzinfo=None))

    if user_id:
        query = query.filter(TokenUsage.user_id == user_id)
    if normalized_model:
        query = query.filter(TokenUsage.model == normalized_model)
    if normalized_operation:
        query = query.filter(func.lower(TokenUsage.operation) == normalized_operation)

    rows = query.group_by(TokenUsage.model, TokenUsage.operation).all()

    breakdown: list[dict[str, Any]] = []
    provider_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "provider": "unknown",
            "request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
        }
    )

    total_input_tokens = 0
    total_output_tokens = 0
    total_cost_usd = 0.0
    total_requests = 0

    for row in rows:
        row_provider = infer_provider_from_model(row.model)
        if normalized_provider and row_provider != normalized_provider:
            continue

        input_tokens = int(row.input_tokens or 0)
        output_tokens = int(row.output_tokens or 0)
        request_count = int(row.request_count or 0)
        total_tokens = input_tokens + output_tokens
        cost_usd = float(row.cost_usd or 0.0)
        billable = is_billable_model(row.model)

        item = {
            "provider": row_provider,
            "model": str(row.model or "unknown"),
            "operation": str(row.operation or "unknown"),
            "request_count": request_count,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "billable": billable,
        }
        breakdown.append(item)

        provider_summary = provider_totals[row_provider]
        provider_summary["provider"] = row_provider
        provider_summary["request_count"] += request_count
        provider_summary["input_tokens"] += input_tokens
        provider_summary["output_tokens"] += output_tokens
        provider_summary["total_tokens"] += total_tokens
        provider_summary["cost_usd"] += cost_usd

        total_requests += request_count
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_cost_usd += cost_usd

    breakdown.sort(
        key=lambda item: (
            item["cost_usd"],
            item["total_tokens"],
            item["request_count"],
            item["model"],
            item["operation"],
        ),
        reverse=True,
    )
    breakdown = breakdown[:safe_limit]

    providers = sorted(
        provider_totals.values(),
        key=lambda item: (item["cost_usd"], item["total_tokens"], item["request_count"], item["provider"]),
        reverse=True,
    )

    return {
        "days": safe_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "user_id": user_id,
            "provider": normalized_provider,
            "model": normalized_model,
            "operation": normalized_operation,
            "limit": safe_limit,
        },
        "total_requests": total_requests,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost_usd": float(total_cost_usd),
        "providers": providers,
        "breakdown": breakdown,
    }
