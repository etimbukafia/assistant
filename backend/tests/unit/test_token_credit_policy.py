from unittest.mock import MagicMock, patch

from datetime import datetime, timezone

from core.llm.token_tracking import (
    calculate_cost,
    get_usage_breakdown,
    infer_provider_from_model,
    is_billable_model,
    record_token_usage,
)


def test_is_billable_model_true_for_claude_and_gemini():
    assert is_billable_model("claude-sonnet-4-20250514") is True
    assert is_billable_model("gemini-2.5-flash-lite") is True


def test_is_billable_model_false_for_gemma_and_unknown():
    assert is_billable_model("gemma-3-4b-it") is False
    assert is_billable_model("some-unknown-model") is False


def test_calculate_cost_positive_for_claude():
    cost = calculate_cost("claude-sonnet-4-20250514", input_tokens=1000, output_tokens=500)
    assert cost > 0


def test_infer_provider_from_model_uses_pricing_metadata_and_prefixes():
    assert infer_provider_from_model("claude-sonnet-4-20250514") == "anthropic"
    assert infer_provider_from_model("gemini-2.5-flash-lite") == "gemini"
    assert infer_provider_from_model("gemma-3-4b-it") == "huggingface"
    assert infer_provider_from_model("unknown-model") == "unknown"


def test_record_token_usage_charges_credits_for_billable_model():
    db = MagicMock()
    token_usage_model = MagicMock()
    with patch("app.services.credits.add_credit_usage") as add_credit_usage:
        with patch("app.data.models.TokenUsage", token_usage_model):
            record_token_usage(
                db=db,
                user_id="user-1",
                model="claude-sonnet-4-20250514",
                input_tokens=1000,
                output_tokens=500,
                operation="chat",
            )

    assert db.add.called
    add_credit_usage.assert_called_once()


def test_record_token_usage_does_not_charge_credits_for_gemma():
    db = MagicMock()
    token_usage_model = MagicMock()
    with patch("app.services.credits.add_credit_usage") as add_credit_usage:
        with patch("app.data.models.TokenUsage", token_usage_model):
            record_token_usage(
                db=db,
                user_id="user-1",
                model="gemma-3-4b-it",
                input_tokens=1000,
                output_tokens=500,
                operation="email_processing",
            )

    assert db.add.called
    add_credit_usage.assert_not_called()


def test_get_usage_breakdown_groups_by_provider_and_model(db_session):
    from app.data.models import TokenUsage

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add_all(
        [
            TokenUsage(
                user_id="user-1",
                model="claude-sonnet-4-20250514",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.00105,
                operation="chat",
                created_at=now,
            ),
            TokenUsage(
                user_id="user-1",
                model="gemini-2.5-flash-lite",
                input_tokens=80,
                output_tokens=20,
                cost_usd=0.000016,
                operation="drafting",
                created_at=now,
            ),
            TokenUsage(
                user_id="user-1",
                model="gemma-3-4b-it",
                input_tokens=40,
                output_tokens=20,
                cost_usd=0.0,
                operation="email_processing",
                created_at=now,
            ),
        ]
    )
    db_session.commit()

    report = get_usage_breakdown(db_session, days=30, user_id="user-1")

    providers = {item["provider"]: item for item in report["providers"]}
    assert providers["anthropic"]["request_count"] == 1
    assert providers["gemini"]["request_count"] == 1
    assert providers["huggingface"]["request_count"] == 1

    breakdown = {(item["provider"], item["model"]): item for item in report["breakdown"]}
    assert breakdown[("anthropic", "claude-sonnet-4-20250514")]["billable"] is True
    assert breakdown[("huggingface", "gemma-3-4b-it")]["billable"] is False
