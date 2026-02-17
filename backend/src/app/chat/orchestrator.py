"""
Chat Orchestrator

Main orchestration layer for AI Chat.
Routes messages through LLM, executes tools, manages state.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
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

# Module-level cached LLM orchestrator (avoids re-init per request)
_chat_llm = None


def _get_chat_llm():
    """Get or create a cached LLM orchestrator for chat."""
    global _chat_llm
    if _chat_llm is None:
        from core.llm.orchestrator import LLMOrchestrator
        from core.llm.config import LLMConfig
        _chat_llm = LLMOrchestrator(config=LLMConfig.for_chat())
    return _chat_llm

# Prompts directory (backend/prompts/)
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"

# Prompt template cache (loaded once per process)
_prompt_cache: Dict[str, str] = {}


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory (cached)."""
    if name not in _prompt_cache:
        prompt_path = PROMPTS_DIR / f"{name}.md"
        try:
            _prompt_cache[name] = prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {prompt_path}")
            _prompt_cache[name] = ""
    return _prompt_cache[name]


# =========================================================================
# Mode Configuration
# =========================================================================

@dataclass
class ModeConfig:
    """Resolved configuration for a chat mode. No branching needed downstream."""
    system_prompt: str
    context_type: str
    tools: List[Dict[str, Any]] = field(default_factory=list)
    use_tools: bool = False


def resolve_mode(
    session_type: str,
    assistant_name: str,
    user_name: Optional[str],
    context: str,
    tool_registry: ChatToolRegistry,
) -> ModeConfig:
    """
    Resolve all mode-specific config upfront.

    Returns a ModeConfig that the orchestrator can use without
    checking session_type again.
    """
    # Identity preamble — tells the LLM its name and who it's talking to
    identity = f"Your name is {assistant_name}."
    if user_name:
        identity += f" You are speaking with {user_name}."

    if session_type == "reflection":
        base_prompt = _load_prompt("chat_reflection")
        return ModeConfig(
            system_prompt=f"{identity}\n\n{base_prompt}\n\n## Current Context\n{context}",
            context_type="task_review",
            tools=[],
            use_tools=False,
        )

    # Action / command mode
    base_prompt = _load_prompt("chat_system").format(assistant_name=assistant_name)
    tool_names = ", ".join(tool_registry._tools.keys())
    tools = tool_registry.get_tool_definitions()
    return ModeConfig(
        system_prompt=f"{identity}\n\n{base_prompt}\n\n## Current Context\n{context}\n\nAvailable tools: {tool_names}",
        context_type="drafting",
        tools=tools,
        use_tools=True,
    )


# =========================================================================
# Orchestrator
# =========================================================================

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

    def __init__(
        self,
        db: Session,
        user_id: str,
        assistant_name: str = "Teeks",
        user_name: Optional[str] = None,
    ):
        self.db = db
        self.user_id = user_id
        self.assistant_name = assistant_name
        self.user_name = user_name
        self.context_manager = ChatContextManager(db, user_id)
        self.tool_registry = ChatToolRegistry(db, user_id)

    async def process_message(
        self,
        session: ChatSession,
        user_message: str,
        mention_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message and generate a response.

        Returns:
            Dict with 'response', 'pending_actions', 'state_updates'
        """
        try:
            return await self._process_message_internal(session, user_message, mention_context=mention_context or {})
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
        user_message: str,
        mention_context: Optional[Dict[str, Any]] = None,
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

        # Load current state
        state = self.context_manager.get_session_state(session)

        # Get conversation history
        history = self.context_manager.get_recent_messages(session.id)

        # Resolve mode config upfront — no more session_type branching below
        context = self.context_manager.build_prompt_context(
            session=session,
            state=state,
            context_type="drafting" if session.session_type == "command" else "task_review"
        )
        mode = resolve_mode(
            session_type=session.session_type,
            assistant_name=self.assistant_name,
            user_name=self.user_name,
            context=context,
            tool_registry=self.tool_registry,
        )

        # Build messages for LLM
        messages = [{"role": "system", "content": mode.system_prompt}]
        if mention_context:
            # Structured mention context is serialized as JSON to avoid prompt-shape injection.
            safe_context = json.dumps(mention_context, ensure_ascii=True, separators=(",", ":"))
            messages.append({
                "role": "system",
                "content": f"Resolved mention context JSON: {safe_context}",
            })
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        # Call LLM
        try:
            response = await self._call_llm(messages, mode.tools)
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

        # Execute tool calls (only possible in action mode)
        if tool_calls and mode.use_tools:
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

                if result.state_updates:
                    for key, value in result.state_updates.items():
                        setattr(state, key, value)

                if result.pending_action:
                    pending_actions.append(result.pending_action)

            if tool_results and not assistant_message:
                assistant_message = self._format_tool_results(tool_results)

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

        Uses async text generation (no JSON parsing) for natural language
        chat responses. Tool calls are extracted from the raw text.
        """
        from core.llm.token_tracking import record_token_usage

        orchestrator = _get_chat_llm()

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

        # Async text generation — no JSON parsing, no event loop blocking
        raw_text = await orchestrator.agenerate_text(
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

        # Extract tool calls from raw text
        tool_calls = self._extract_tool_calls_from_response({}, raw_text)

        # If tool calls found, strip the JSON blocks from content
        content = raw_text
        if tool_calls:
            import re as _re
            content = _re.sub(r'```json\s*.*?\s*```', '', content, flags=_re.DOTALL).strip()
            content = _re.sub(r'\{"tool_call"\s*:\s*\{[^}]+\}\s*\}', '', content).strip()

        return {
            "content": content,
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
