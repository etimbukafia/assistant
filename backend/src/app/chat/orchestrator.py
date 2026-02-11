"""
Chat Orchestrator

Main orchestration layer for AI Chat.
Routes messages through LLM, executes tools, manages state.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
import uuid
import json
import logging

from sqlalchemy.orm import Session

from app.data.models import ChatSession, ChatMessage, ChatPendingAction
from .context import ChatContextManager, ConversationState
from .tools import ChatToolRegistry, ToolResult, ToolType
from app.security.prompt_sanitizer import detect_injection_attempt, detect_injection_patterns
from app.security.security_logger import log_injection_attempt

logger = logging.getLogger(__name__)

# Prompts directory (backend/prompts/)
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(f"Prompt file not found: {prompt_path}")
        return ""


class ChatOrchestrator:
    """
    Orchestrates chat conversations.
    
    Responsibilities:
    - Build prompts with context
    - Route to LLM
    - Execute tool calls
    - Create pending actions for approval-gated tools
    - Persist state after each turn
    """
    
    def __init__(self, db: Session, user_id: str, assistant_name: str = "Donna"):
        self.db = db
        self.user_id = user_id
        self.assistant_name = assistant_name
        self.context_manager = ChatContextManager(db, user_id)
        self.tool_registry = ChatToolRegistry(db, user_id)
        self._command_prompt_template: Optional[str] = None
        self._reflection_prompt_template: Optional[str] = None

    @property
    def command_system_prompt(self) -> str:
        """Lazy-load and format command mode system prompt."""
        if self._command_prompt_template is None:
            self._command_prompt_template = _load_prompt("chat_system")
        return self._command_prompt_template.format(assistant_name=self.assistant_name)

    @property
    def reflection_system_prompt(self) -> str:
        """Lazy-load reflection mode system prompt."""
        if self._reflection_prompt_template is None:
            self._reflection_prompt_template = _load_prompt("chat_reflection")
        return self._reflection_prompt_template

    
    async def process_message(
        self,
        session: ChatSession,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process a user message and generate a response.

        Returns:
            Dict with 'response', 'pending_actions', 'state_updates'
        """
        try:
            return await self._process_message_internal(session, user_message)
        except Exception as e:
            logger.error(f"Unexpected error in process_message: {e}", exc_info=True)
            return {
                "response": "I apologize, but I encountered an unexpected error. Please try again.",
                "pending_actions": [],
                "state": {}
            }

    async def _process_message_internal(
        self,
        session: ChatSession,
        user_message: str
    ) -> Dict[str, Any]:
        """Internal message processing with full error context."""
        # Security: Check for injection patterns in user message
        injection_patterns = detect_injection_patterns(user_message)
        if injection_patterns:
            log_injection_attempt(
                user_id=self.user_id,
                source="user_message",
                pattern_matched=", ".join(injection_patterns),
                content_preview=user_message[:100]
            )
            # Note: We log but don't block - the system prompt instructs the LLM
            # to not follow instructions from users. Blocking could affect legitimate
            # users who happen to use certain phrases.

        # Load current state
        state = self.context_manager.get_session_state(session)
        
        # Get conversation history
        history = self.context_manager.get_recent_messages(session.id)
        
        # Build context
        context = self.context_manager.build_prompt_context(
            session=session,
            state=state,
            context_type="drafting" if session.session_type == "command" else "task_review"
        )
        
        # Build system prompt based on session type
        if session.session_type == "reflection":
            base_prompt = self.reflection_system_prompt
            # Append context at the end of the prompt
            system_prompt = f"{base_prompt}\n\n## Current Context\n{context}"
            tools = []  # No tools in reflection mode
        else:
            base_prompt = self.command_system_prompt
            tool_names = ", ".join(self.tool_registry._tools.keys())
            # Append context and tool info to the prompt
            system_prompt = f"{base_prompt}\n\n## Current Context\n{context}\n\nAvailable tools: {tool_names}"
            tools = self.tool_registry.get_tool_definitions()
        
        # Build messages for LLM
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Call LLM
        try:
            response = await self._call_llm(messages, tools)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "response": "I apologize, but I encountered an error processing your request. Please try again.",
                "pending_actions": [],
                "error": str(e)
            }
        
        # Process response
        assistant_message = response.get("content", "")
        tool_calls = response.get("tool_calls", [])
        pending_actions = []
        
        # Execute any tool calls
        if tool_calls:
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name")
                args_str = tool_call.get("function", {}).get("arguments", "{}")
                try:
                    tool_args = json.loads(args_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse tool arguments: {e}, raw: {args_str[:100]}")
                    tool_args = {}

                result = self.tool_registry.execute_tool(tool_name, tool_args)
                tool_results.append(result)
                
                # Apply state updates
                if result.state_updates:
                    for key, value in result.state_updates.items():
                        setattr(state, key, value)
                
                # Collect pending actions
                if result.pending_action:
                    pending_actions.append(result.pending_action)
            
            # If we have tool results, get a follow-up response
            if tool_results and not assistant_message:
                assistant_message = self._format_tool_results(tool_results)
        
        # If still no response, provide a default
        if not assistant_message:
            assistant_message = "I've processed your request."
        
        # Save state
        self.context_manager.save_session_state(session, state)
        
        return {
            "response": assistant_message,
            "pending_actions": pending_actions,
            "state": state.to_dict()
        }
    
    async def _call_llm(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call the LLM with messages and optional tools.

        Uses LLMOrchestrator with structured JSON prompting for tool calls.
        """
        from core.llm.orchestrator import LLMOrchestrator
        from core.llm.config import LLMConfig
        from core.llm.token_tracking import record_token_usage

        orchestrator = LLMOrchestrator(config=LLMConfig.for_chat())

        # Build prompt from messages
        prompt_parts = []
        system_content = ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                prompt_parts.append(f"User: {msg['content']}")
            elif msg["role"] == "assistant":
                prompt_parts.append(f"Assistant: {msg['content']}")

        prompt = "\n\n".join(prompt_parts)

        # Add tool descriptions with JSON format instruction
        if tools:
            tool_desc = self._build_tool_prompt(tools)
            prompt = tool_desc + "\n\n" + prompt

        # Call LLM
        result = orchestrator.generate(
            prompt=prompt,
            system_prompt=system_content
        )

        # Record token usage
        usage = orchestrator.get_token_usage()
        if usage['input_tokens'] > 0 or usage['output_tokens'] > 0:
            record_token_usage(
                db=self.db,
                user_id=self.user_id,
                model=usage['model'],
                input_tokens=usage['input_tokens'],
                output_tokens=usage['output_tokens'],
                operation="chat"
            )
        orchestrator.reset_token_usage()

        # Parse response for tool calls
        content = result.get("text", result.get("content", ""))
        tool_calls = self._extract_tool_calls_from_response(result, content)

        return {
            "content": content if not tool_calls else "",
            "tool_calls": tool_calls
        }
    
    def _build_tool_prompt(self, tools: List[Dict[str, Any]]) -> str:
        """Build the tool description prompt with JSON schema."""
        lines = [
            "You have access to the following tools. To use a tool, include a JSON block in your response:",
            "",
            "```json",
            '{"tool_call": {"name": "tool_name", "arguments": {"arg1": "value1"}}}',
            "```",
            "",
            "Available tools:"
        ]
        
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])
            
            lines.append(f"\n**{name}**: {desc}")
            if params:
                lines.append("  Arguments:")
                for param_name, param_def in params.items():
                    req_marker = " (required)" if param_name in required else ""
                    param_type = param_def.get("type", "string")
                    param_desc = param_def.get("description", "")
                    lines.append(f"    - {param_name}: {param_type}{req_marker} - {param_desc}")
        
        lines.append("\n\nIf you don't need to use a tool, respond normally with text only.")
        return "\n".join(lines)
    
    def _extract_tool_calls_from_response(
        self,
        result: Dict[str, Any],
        content: str
    ) -> List[Dict[str, Any]]:
        """Extract tool calls from LLM response."""
        tool_calls = []
        
        # Method 1: Check if result dict contains tool_call directly
        if isinstance(result.get("tool_call"), dict):
            tc = result["tool_call"]
            tool_calls.append({
                "function": {
                    "name": tc.get("name"),
                    "arguments": json.dumps(tc.get("arguments", {}))
                }
            })
            return tool_calls
        
        # Method 2: Extract JSON blocks from content
        import re
        
        # Look for ```json ... ``` blocks
        json_blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        for block in json_blocks:
            try:
                parsed = json.loads(block)
                if "tool_call" in parsed:
                    tc = parsed["tool_call"]
                    tool_calls.append({
                        "function": {
                            "name": tc.get("name"),
                            "arguments": json.dumps(tc.get("arguments", {}))
                        }
                    })
            except json.JSONDecodeError:
                continue
        
        # Method 3: Look for inline JSON {"tool_call": ...}
        if not tool_calls:
            try:
                # Find JSON-like pattern for tool_call
                pattern = r'\{"tool_call"\s*:\s*\{[^}]+\}\s*\}'
                matches = re.findall(pattern, content)
                for match in matches:
                    parsed = json.loads(match)
                    if "tool_call" in parsed:
                        tc = parsed["tool_call"]
                        tool_calls.append({
                            "function": {
                                "name": tc.get("name"),
                                "arguments": json.dumps(tc.get("arguments", {}))
                            }
                        })
            except (json.JSONDecodeError, re.error):
                pass
        
        return tool_calls
    
    def _format_tool_results(self, results: List[ToolResult]) -> str:
        """Format tool results into a human-readable response."""
        parts = []
        
        for result in results:
            if not result.success:
                parts.append(f"I encountered an issue: {result.error}")
            elif result.data:
                # Format based on data type
                if "emails" in result.data:
                    count = result.data.get("count", 0)
                    if count == 0:
                        parts.append("I didn't find any matching emails.")
                    else:
                        parts.append(f"I found {count} email(s):")
                        for email in result.data["emails"][:3]:
                            parts.append(f"- \"{email['subject']}\" from {email['sender']}")
                
                elif "tasks" in result.data:
                    count = result.data.get("count", 0)
                    if count == 0:
                        parts.append("I didn't find any matching tasks.")
                    else:
                        parts.append(f"I found {count} task(s):")
                        for task in result.data["tasks"][:3]:
                            parts.append(f"- {task['title']} ({task['status']})")
                
                elif "events" in result.data:
                    count = result.data.get("count", 0)
                    if count == 0:
                        parts.append("No upcoming events found.")
                    else:
                        parts.append(f"You have {count} upcoming event(s):")
                        for event in result.data["events"][:3]:
                            parts.append(f"- {event['title']} at {event['start_time']}")
                
                elif "message" in result.data:
                    parts.append(result.data["message"])
        
        return "\n".join(parts) if parts else "Done."
    
    def create_pending_action(
        self,
        session_id: str,
        message_id: int,
        action_type: str,
        action_data: Dict[str, Any]
    ) -> ChatPendingAction:
        """Create a pending action for user approval."""
        action = ChatPendingAction(
            id=str(uuid.uuid4()),
            session_id=session_id,
            message_id=message_id,
            action_type=action_type,
            action_data=action_data,
            status="pending",
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action
