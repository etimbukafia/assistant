"""
Token usage tracking for LLM operations.
"""
import json
import logging
from pathlib import Path
from typing import Optional

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

    Also updates credits_used on UserSettings for Gemini models (not Gemma).

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
    from app.services.credits import is_gemini_model, add_credit_usage

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

    # Update credit usage for Gemini models (not Gemma)
    if cost > 0 and is_gemini_model(model):
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
