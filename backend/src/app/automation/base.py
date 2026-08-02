from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.automation.catalog import AutomationDefinition, AutomationStatus, get_automation_definition
from app.data.models import AutomationRun, AutomationUserSetting, GmailAccount, UserSettings


class BaseAutomationService:
    def __init__(self, db: Session, user_id: str, settings: UserSettings):
        self.db = db
        self.user_id = user_id
        self.settings = settings

    def _definition(self, automation_id: str) -> AutomationDefinition:
        return get_automation_definition(automation_id)

    def _get_or_create_setting(self, automation_id: str) -> AutomationUserSetting:
        setting = (
            self.db.query(AutomationUserSetting)
            .filter(
                AutomationUserSetting.user_id == self.user_id,
                AutomationUserSetting.automation_id == automation_id,
            )
            .first()
        )
        if setting:
            return setting

        definition = self._definition(automation_id)
        setting = AutomationUserSetting(
            user_id=self.user_id,
            automation_id=automation_id,
            configured=False,
            enabled=False,
            safety_mode=definition["safety_mode"],
            execution_mode=definition["execution_mode"],
        )
        self.db.add(setting)
        self.db.flush()
        return setting

    def _connector_state(self, connector_id: str) -> bool:
        if connector_id == "gmail":
            return bool(
                self.db.query(GmailAccount)
                .filter(GmailAccount.user_id == self.user_id)
                .first()
            )
        if connector_id == "calendar":
            return bool(self.settings.calendar_ids)
        return False

    def _status_for(self, automation_id: str, setting: AutomationUserSetting) -> AutomationStatus:
        definition = self._definition(automation_id)
        required_connected = all(
            self._connector_state(connector["id"])
            for connector in definition["required_connectors"]
        )
        if not required_connected:
            return "needs_connection"
        if setting.enabled:
            return "drafts_only" if setting.safety_mode == "draft_only" else "running"
        return "off" if setting.configured else "ready"

    def _build_connector_payload(self, automation_id: str) -> Dict[str, list[dict[str, Any]]]:
        definition = self._definition(automation_id)

        def serialize(connector: dict[str, Any]) -> dict[str, Any]:
            return {
                "id": connector["id"],
                "label": connector["label"],
                "required": connector["required"],
                "description": connector["description"],
                "connected": self._connector_state(connector["id"]),
            }

        return {
            "required": [serialize(item) for item in definition["required_connectors"]],
            "optional": [serialize(item) for item in definition["optional_connectors"]],
        }

    def _record_run(
        self,
        *,
        automation_id: str,
        status: str,
        trigger: str,
        summary: str,
        run_metadata: Optional[Dict[str, Any]] = None,
    ) -> AutomationRun:
        now = datetime.now(timezone.utc)
        run = AutomationRun(
            user_id=self.user_id,
            automation_id=automation_id,
            status=status,
            trigger=trigger,
            summary=summary,
            run_metadata=run_metadata or {},
            started_at=now,
            finished_at=now,
        )
        self.db.add(run)
        self.db.flush()
        return run

    def _recent_runs(self, automation_id: str, *, limit: int = 5) -> list[AutomationRun]:
        return (
            self.db.query(AutomationRun)
            .filter(
                AutomationRun.user_id == self.user_id,
                AutomationRun.automation_id == automation_id,
            )
            .order_by(AutomationRun.started_at.desc(), AutomationRun.id.desc())
            .limit(limit)
            .all()
        )
