"""Integration coverage for provider-switched chat/drafting endpoints and usage reporting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient


pytestmark = pytest.mark.integration


class _FakeTelemetryWriter:
    def enqueue_chat_metric(self, **kwargs):
        return None

    def enqueue_token_usage(self, **kwargs):
        return None


class _FakeContextAssembler:
    def __init__(self, *args, **kwargs):
        pass

    def build_layers_with_trace(self, **kwargs):
        layers = SimpleNamespace(
            instruction="Use the conversation only.",
            task="",
            profile="",
            structured="",
        )
        return layers, {}

    def log_context_trace(self, trace, user_message):
        return None


class _FakeRouteLLM:
    instances: list["_FakeRouteLLM"] = []

    def __init__(self, config):
        self.config = config
        self._token_usage = {
            "model": self._active_model,
            "input_tokens": 18,
            "output_tokens": 9,
        }
        self.__class__.instances.append(self)

    @property
    def _active_model(self) -> str:
        if self.config.provider == "anthropic":
            return self.config.anthropic_model
        if self.config.provider == "gemini":
            return self.config.gemini_model
        return self.config.hf_model_id

    async def agenerate_text(self, prompt: str, system_prompt: str | None = None) -> str:
        return f"chat response via {self.config.provider}:{self._active_model}"

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        return f"draft response via {self.config.provider}:{self._active_model}"

    def supports_tools(self) -> bool:
        return False

    def get_token_usage(self):
        return dict(self._token_usage)

    def reset_token_usage(self):
        self._token_usage = {
            "model": self._active_model,
            "input_tokens": 0,
            "output_tokens": 0,
        }


@pytest.fixture
def authenticated_user():
    from app.security.auth import AuthenticatedUser

    return AuthenticatedUser(
        user_id="user-ai-routes",
        email="admin@example.com",
        email_verified=True,
        provider="google",
        app_metadata={"provider": "google"},
        user_metadata={"full_name": "Admin User"},
    )


@pytest.fixture
def active_user_settings(db_session, authenticated_user):
    from app.data.models import UserSettings

    settings = UserSettings(
        user_id=authenticated_user.user_id,
        user_email=authenticated_user.email,
        subscription_tier="trial",
        subscription_status="trialing",
        assistant_name="Teeks",
        credits_limit=5.0,
        credits_used=0.0,
        credits_period_start=datetime.now(timezone.utc),
    )
    settings.trial_ends_at = datetime.now(timezone.utc) + timedelta(days=14)
    db_session.add(settings)
    db_session.commit()
    return settings


@pytest.fixture
def app_client(db_session, authenticated_user, active_user_settings):
    from app.infra.database import get_db
    from app.security.auth import (
        get_current_user,
        get_db_for_user,
        get_user_settings,
        require_admin_user,
    )
    from main import app

    def override_get_db():
        yield db_session

    def override_get_db_for_user():
        return db_session

    def override_get_current_user():
        return authenticated_user

    def override_get_user_settings():
        return active_user_settings

    def override_require_admin_user():
        return authenticated_user

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_db_for_user] = override_get_db_for_user
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_user_settings] = override_get_user_settings
    app.dependency_overrides[require_admin_user] = override_require_admin_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("gemini", "gemini-2.5-flash-lite"),
        ("anthropic", "claude-sonnet-4-20250514"),
    ],
)
def test_chat_endpoint_respects_provider_switch(app_client, monkeypatch, provider, model):
    import app.chat.orchestrator as chat_orchestrator
    import core.llm.orchestrator as llm_orchestrator

    _FakeRouteLLM.instances.clear()
    chat_orchestrator._chat_llm = None

    monkeypatch.setenv("LLM_CHAT_PROVIDER", provider)
    monkeypatch.setenv("LLM_CHAT_MODEL", model)
    monkeypatch.setattr(chat_orchestrator, "ContextAssembler", _FakeContextAssembler)
    monkeypatch.setattr(chat_orchestrator, "get_telemetry_writer", lambda: _FakeTelemetryWriter())
    monkeypatch.setattr(llm_orchestrator, "LLMOrchestrator", _FakeRouteLLM)

    session_response = app_client.post("/v1/chat/sessions", json={"session_type": "reflection"})
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    response = app_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "Summarize my priorities for today."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "complete"
    assert f"{provider}:{model}" in payload["response"]
    assert _FakeRouteLLM.instances[-1].config.provider == provider


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        ("gemini", "gemini-2.5-flash-lite"),
        ("anthropic", "claude-sonnet-4-20250514"),
    ],
)
def test_email_draft_endpoint_respects_provider_switch(app_client, monkeypatch, provider, model):
    import app.superpowers.email_drafting as email_drafting

    _FakeRouteLLM.instances.clear()
    email_drafting._draft_llm = None

    monkeypatch.setenv("LLM_DRAFT_PROVIDER", provider)
    monkeypatch.setenv("LLM_DRAFT_MODEL", model)
    monkeypatch.setattr(email_drafting, "LLMOrchestrator", _FakeRouteLLM)

    response = app_client.post(
        "/v1/action-tools/email-draft",
        json={
            "subject": "Project update",
            "intent": "send a concise progress update",
            "recipient": "ceo@example.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert f"{provider}:{model}" in payload["body"]
    assert _FakeRouteLLM.instances[-1].config.provider == provider


def test_admin_token_usage_report_groups_by_provider_and_model(app_client, db_session):
    from app.data.models import TokenUsage

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add_all(
        [
            TokenUsage(
                user_id="user-ai-routes",
                model="gemini-2.5-flash-lite",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0003,
                operation="chat",
                created_at=now,
            ),
            TokenUsage(
                user_id="user-ai-routes",
                model="claude-sonnet-4-20250514",
                input_tokens=2000,
                output_tokens=750,
                cost_usd=0.01725,
                operation="drafting",
                created_at=now,
            ),
            TokenUsage(
                user_id="user-ai-routes",
                model="gemma-3-4b-it",
                input_tokens=300,
                output_tokens=200,
                cost_usd=0.0,
                operation="email_processing",
                created_at=now,
            ),
        ]
    )
    db_session.commit()

    response = app_client.get("/v1/billing/admin/token-usage?days=30")
    assert response.status_code == 200
    payload = response.json()

    providers = {item["provider"]: item for item in payload["providers"]}
    assert {"anthropic", "gemini", "huggingface"} <= set(providers.keys())
    assert providers["anthropic"]["cost_usd"] == pytest.approx(0.01725)
    assert providers["huggingface"]["cost_usd"] == pytest.approx(0.0)

    breakdown = {(item["provider"], item["model"]): item for item in payload["breakdown"]}
    assert breakdown[("anthropic", "claude-sonnet-4-20250514")]["billable"] is True
    assert breakdown[("huggingface", "gemma-3-4b-it")]["billable"] is False

    filtered = app_client.get("/v1/billing/admin/token-usage?days=30&provider=anthropic")
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert len(filtered_payload["providers"]) == 1
    assert filtered_payload["providers"][0]["provider"] == "anthropic"
    assert filtered_payload["breakdown"][0]["model"] == "claude-sonnet-4-20250514"
