"""
Assistant Orchestrator - The brain of the autonomous assistant

This orchestrator makes ALL decisions and routes work to specialized modules.
"""
import json
import logging
import uuid
from typing import Dict, Any, List
from pathlib import Path

import google.genai as genai
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infra.config import get_settings
from app.data.models import Message, Task, UserSettings, AgentActivityLog
from .modules import (
    BaseModule,
    FollowUpModule,
    CommunicationModule,
    SchedulingModule,
)

logger = logging.getLogger(__name__)


class AssistantOrchestrator:
    """
    The orchestrator brain that makes all autonomous decisions

    This class:
    - Receives events (message_received, task_created, reminder_due)
    - Analyzes context using AI
    - Decides what actions to take
    - Routes work to appropriate modules
    - Logs all decisions for transparency
    """

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash-lite",
        prompts_dir: str = "prompts",
        assistant_name: str = "Teeks"
    ):
        """Initialize the orchestrator"""
        self.model_name = model_name
        self.prompts_dir = Path(prompts_dir)
        self.assistant_name = assistant_name
        self.orchestrator_id = str(uuid.uuid4())[:8]  # Short ID for this instance

        # Initialize AI client
        self.client = genai.Client(api_key=get_settings().GOOGLE_API_KEY)

        # Initialize modules
        self.modules: Dict[str, BaseModule] = {
            "FollowUpModule": FollowUpModule(),
            "CommunicationModule": CommunicationModule(),
            "SchedulingModule": SchedulingModule(),
        }

        # Prompts cache
        self._prompts_cache = {}

        logger.info(f"AssistantOrchestrator initialized (ID: {self.orchestrator_id})")

    def _load_prompt(self, prompt_name: str) -> str:
        """Load a prompt from the prompts directory"""
        if prompt_name in self._prompts_cache:
            return self._prompts_cache[prompt_name]

        prompt_path = self.prompts_dir / f"{prompt_name}.md"
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
                self._prompts_cache[prompt_name] = prompt
                return prompt
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    def get_available_modules(self) -> Dict[str, Dict[str, str]]:
        """Get capabilities of all available modules"""
        return {
            module_name: module.get_capabilities()
            for module_name, module in self.modules.items()
        }

    def load_context(
        self,
        event_type: str,
        event_payload: Dict[str, Any],
        db: Session,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Load relevant context for decision-making

        Args:
            event_type: Type of event (message_received, task_created, etc.)
            event_payload: Event data
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            Context dictionary with all relevant information
        """
        context = {
            "event_type": event_type,
            "event_payload": event_payload,
        }

        # Load user settings (filtered by user_id)
        user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not user_settings:
            logger.warning(f"No UserSettings found for user_id={user_id}")
            # Use minimal defaults - settings should be created by auth flow
            context["settings"] = {
                "auto_approve_tasks": False,
                "enable_auto_reply": False,
                "enable_auto_follow_up": False,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "task_detection_instructions": "None",
            }
        else:
            context["settings"] = {
                "auto_approve_tasks": user_settings.auto_approve_tasks,
                "enable_auto_reply": False,  # Will be added to settings later
                "enable_auto_follow_up": False,  # Will be added to settings later
                "quiet_hours_start": (user_settings.reminder_preferences or {}).get("quiet_hours_start", "22:00"),
                "quiet_hours_end": (user_settings.reminder_preferences or {}).get("quiet_hours_end", "08:00"),
                "task_detection_instructions": user_settings.task_detection_instructions or "None",
            }

        # Load related message if message_id in payload
        if "message_id" in event_payload:
            message = db.query(Message).filter(
                Message.id == event_payload["message_id"]
            ).first()
            if message:
                context["message"] = {
                    "id": message.id,
                    "subject": message.subject,
                    "sender": message.sender,
                    "body": (message.decrypted_body or "")[:500],  # First 500 chars
                    "needs_reply": message.needs_reply,
                }

        # Load related task if task_id in payload
        if "task_id" in event_payload:
            task = db.query(Task).filter(
                Task.id == event_payload["task_id"]
            ).first()
            if task:
                context["task"] = {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "task_type": task.task_type,
                    "priority": task.priority,
                    "status": task.status,
                }

        # Load recent agent activity (last 10 actions)
        recent_activity = db.query(AgentActivityLog).order_by(
            AgentActivityLog.created_at.desc()
        ).limit(10).all()

        context["recent_activity"] = [
            {
                "action_type": log.action_type,
                "confidence": log.confidence,
                "user_visible_message": log.user_visible_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in recent_activity
        ]

        return context

    def make_decision(
        self,
        event_type: str,
        event_payload: Dict[str, Any],
        correlation_id: str,
        db
    ) -> Dict[str, Any]:
        """
        Make a decision about what actions to take

        Args:
            event_type: Type of event
            event_payload: Event data
            correlation_id: Correlation ID for tracking
            db: Database session

        Returns:
            Decision dictionary with actions to take
        """
        # Load context
        context = self.load_context(event_type, event_payload, db, user_id)

        # Get available modules
        available_modules = self.get_available_modules()

        # Load orchestration decision prompt
        prompt_template = self._load_prompt("orchestration_decision")

        # Format prompt with context
        prompt = prompt_template.format(
            assistant_name=self.assistant_name,
            event_type=event_type,
            event_payload=json.dumps(event_payload, indent=2),
            correlation_id=correlation_id,
            context=json.dumps(context.get("message") or context.get("task") or {}, indent=2),
            auto_approve_tasks=context["settings"]["auto_approve_tasks"],
            enable_auto_reply=context["settings"]["enable_auto_reply"],
            enable_auto_follow_up=context["settings"]["enable_auto_follow_up"],
            quiet_hours_start=context["settings"]["quiet_hours_start"],
            quiet_hours_end=context["settings"]["quiet_hours_end"],
            task_detection_instructions=context["settings"]["task_detection_instructions"],
            available_modules=json.dumps(available_modules, indent=2),
            recent_activity=json.dumps(context["recent_activity"], indent=2),
        )

        try:
            # Call AI to make decision
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            result_text = response.text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            decision = json.loads(result_text)

            logger.info(
                f"Decision made: should_act={decision.get('should_act')}, "
                f"confidence={decision.get('confidence')}, "
                f"action_type={decision.get('action_type')}"
            )

            return decision

        except Exception as e:
            logger.error(f"Error making decision: {e}", exc_info=True)
            return {
                "should_act": False,
                "confidence": 0.0,
                "action_type": None,
                "reason": f"Error in decision-making: {str(e)}",
                "actions": [],
                "user_visible_message": None,
                "requires_user_approval": True,
            }

    def execute_actions(
        self,
        decision: Dict[str, Any],
        correlation_id: str,
        db: Session,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Execute the actions specified in a decision

        Args:
            decision: Decision dictionary from make_decision()
            correlation_id: Correlation ID for tracking
            db: Database session with RLS context
            user_id: Current user's ID

        Returns:
            List of execution results
        """
        if not decision.get("should_act"):
            logger.info(f"No action needed: {decision.get('reason')}")
            return []

        actions = decision.get("actions", [])
        results = []

        # Sort actions by order
        actions.sort(key=lambda x: x.get("order", 0))

        previous_result = None

        for action in actions:
            module_name = action.get("module")
            method = action.get("method")
            params = action.get("params", {})

            # Replace {{RESULT_FROM_PREVIOUS}} with actual result
            if previous_result is not None:
                params = self._replace_placeholders(params, previous_result)

            # Get module
            module = self.modules.get(module_name)
            if not module:
                logger.error(f"[{correlation_id}] Module not found: {module_name}")
                results.append({
                    "success": False,
                    "error": f"Module '{module_name}' not found",
                    "module": module_name,
                    "method": method,
                    "correlation_id": correlation_id,
                })
                continue

            # Execute action
            try:
                logger.info(
                    f"[{correlation_id}] Executing {module_name}.{method}() with params: {params}"
                )
                # Inject db and user_id into params for module methods
                params["db"] = db
                params["user_id"] = user_id
                result = module.execute(method, **params)
                results.append({
                    **result,
                    "module": module_name,
                    "method": method,
                    "correlation_id": correlation_id,
                })

                # Store result for next action
                if result.get("success"):
                    previous_result = result.get("data")

            except Exception as e:
                logger.error(
                    f"[{correlation_id}] Error executing {module_name}.{method}(): {e}",
                    exc_info=True
                )
                results.append({
                    "success": False,
                    "error": str(e),
                    "module": module_name,
                    "method": method,
                    "correlation_id": correlation_id,
                })

        return results

    def _replace_placeholders(self, params: Dict[str, Any], previous_result: Any) -> Dict[str, Any]:
        """Replace {{RESULT_FROM_PREVIOUS}} placeholders with actual values"""
        updated_params = {}
        for key, value in params.items():
            if isinstance(value, str) and "{{RESULT_FROM_PREVIOUS}}" in value:
                updated_params[key] = str(previous_result)
            else:
                updated_params[key] = value
        return updated_params

    def log_activity(
        self,
        decision: Dict[str, Any],
        execution_results: List[Dict[str, Any]],
        event_type: str,
        event_payload: Dict[str, Any],
        correlation_id: str,
        db
    ):
        """
        Log the orchestrator's activity to the database

        Args:
            decision: Decision that was made
            execution_results: Results of action execution
            event_type: Original event type
            event_payload: Original event payload
            correlation_id: Correlation ID
            db: Database session
        """
        try:
            activity_log = AgentActivityLog(
                orchestrator_id=self.orchestrator_id,
                module_name="AssistantOrchestrator",
                action_type=decision.get("action_type"),
                action_description=decision.get("reason"),
                confidence=decision.get("confidence"),
                user_visible_message=decision.get("user_visible_message"),
                related_message_id=event_payload.get("message_id"),
                related_task_id=event_payload.get("task_id"),
                decision_context={
                    "event_type": event_type,
                    "event_payload": event_payload,
                    "correlation_id": correlation_id,
                    "should_act": decision.get("should_act"),
                    "requires_user_approval": decision.get("requires_user_approval"),
                },
                action_result={
                    "execution_results": execution_results,
                    "success": bool(execution_results) and all(r.get("success", False) for r in execution_results),
                },
            )

            db.add(activity_log)
            db.commit()

            logger.info(f"Activity logged (ID: {activity_log.id})")

        except Exception as e:
            logger.error(f"Error logging activity: {e}", exc_info=True)
            db.rollback()

    def process_event(
        self,
        event_type: str,
        event_payload: Dict[str, Any],
        correlation_id: str,
        db: Session,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Main entry point - process an event and take autonomous action

        Args:
            event_type: Type of event (message_received, task_created, etc.)
            event_payload: Event data
            correlation_id: Correlation ID for tracking
            db: Database session with RLS context set
            user_id: User ID for RLS context

        Returns:
            Summary of what actions were taken
        """
        try:
            logger.info(f"Processing event: {event_type} (correlation_id: {correlation_id}, user_id: {user_id})")

            # Make decision
            decision = self.make_decision(event_type, event_payload, correlation_id, db)

            # Execute actions if decision says to act
            execution_results = []
            if decision.get("should_act") and not decision.get("requires_user_approval"):
                execution_results = self.execute_actions(decision, correlation_id, db, user_id)

            # Log activity
            self.log_activity(decision, execution_results, event_type, event_payload, correlation_id, db)

            return {
                "decision": decision,
                "execution_results": execution_results,
                "logged": True,
            }

        except Exception as e:
            logger.error(f"Error processing event: {e}", exc_info=True)
            db.rollback()
            return {
                "decision": {"should_act": False, "error": str(e)},
                "execution_results": [],
                "logged": False,
            }
