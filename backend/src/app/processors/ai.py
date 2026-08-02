import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.llm import LLMOrchestrator, LLMConfig
from core.llm.token_tracking import record_token_usage

logger = logging.getLogger(__name__)


def _strip_quoted_replies(body: str) -> str:
    """Strip quoted reply blocks from email body to reduce redundant content."""
    # Remove "On <date>, <person> wrote:" blocks and everything after
    pattern = r'\n\s*On .{10,80} wrote:\s*\n'
    match = re.search(pattern, body)
    if match:
        body = body[:match.start()].rstrip()

    # Remove lines starting with ">" (quoted text)
    lines = body.split('\n')
    cleaned = []
    consecutive_quotes = 0
    for line in lines:
        if line.strip().startswith('>'):
            consecutive_quotes += 1
            if consecutive_quotes <= 2:
                # Keep first couple of quoted lines for context
                cleaned.append(line)
        else:
            consecutive_quotes = 0
            cleaned.append(line)

    return '\n'.join(cleaned).strip()


def _prepare_body(body: str, max_length: int) -> str:
    """Strip quoted replies and apply smart truncation (head + tail) if needed."""
    body = _strip_quoted_replies(body)

    if len(body) <= max_length:
        return body

    # Smart truncation: keep head and tail where action items often live
    head_size = int(max_length * 0.7)
    tail_size = max_length - head_size - 30  # 30 chars for marker
    truncated = body[:head_size] + "\n\n[... content truncated ...]\n\n" + body[-tail_size:]

    logger.info(f"Email body truncated from {len(body)} to {max_length} chars")
    return truncated


class AIProcessor:
    MAX_BODY_LENGTH = 12000
    MAX_SCHEDULING_BODY = 4000
    
    # Placeholder patterns for detection
    PLACEHOLDER_PATTERNS = ["[", "]", "{", "}", "INSERT", "TIME HERE", "NAME HERE", "YOUR", "THEIR"]

    def __init__(
        self,
        prompts_dir: str = "prompts",
        llm_config: Optional[LLMConfig] = None,
        assistant_name: str = "Teeks",
    ):
        self.prompts_dir = Path(prompts_dir)
        self._prompts_cache = {}
        self._orchestrator = LLMOrchestrator(config=llm_config or LLMConfig.for_email())
        self.assistant_name = assistant_name

    def record_and_reset_tokens(self, db, user_id: str, operation: str) -> None:
        """Record accumulated token usage to database and reset counters."""
        usage = self._orchestrator.get_token_usage()
        if usage['input_tokens'] > 0 or usage['output_tokens'] > 0:
            record_token_usage(
                db=db,
                user_id=user_id,
                model=usage['model'],
                input_tokens=usage['input_tokens'],
                output_tokens=usage['output_tokens'],
                operation=operation
            )
        self._orchestrator.reset_token_usage()

    def _has_placeholders(self, text: str) -> bool:
        """Check if text contains template placeholders."""
        text_upper = text.upper()
        return any(p in text_upper for p in self.PLACEHOLDER_PATTERNS)

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

    # Extraction prompts to compose into process_message
    EXTRACTION_PROMPTS = [
        'extract_tasks',
        'extract_dates',
        'extract_people',
        'extract_decisions',
        'detect_scheduling_intent'
    ]

    # JSON schema for process_message output
    JSON_SCHEMA = '''{
  "summary": "...",
  "needs_reply": true/false,
  "tasks": [],
  "dates": [],
  "people": [],
  "decisions": [],
  "scheduling_intent": {
    "detected": true/false,
    "type": "availability_request|time_request|meeting_confirmation|meeting_reminder|reschedule_request|none",
    "confidence": 0.0-1.0,
    "summary": "One sentence e.g. Sarah asked when you are free for the Q4 review (null if not detected)",
    "meeting_title": "Clean meeting title e.g. Q4 Review (null if not specified)",
    "meeting_date": "ISO date e.g. 2024-12-20 or null if not specified"
  }
}'''

    def _build_extraction_instructions(self) -> str:
        """Compose extraction instructions from individual prompts."""
        instructions = ["**Extractions:**"]
        for prompt_name in self.EXTRACTION_PROMPTS:
            try:
                instruction = self._load_prompt(prompt_name)
                instructions.append(instruction)
            except FileNotFoundError:
                logger.warning(f"Extraction prompt not found: {prompt_name}")
        return "\n\n".join(instructions)

    def process_message(
        self,
        message_data: Dict[str, Any],
        db=None,
        thread_id: str = None,
        message_id: int = None
    ) -> Dict[str, Any]:
        """
        Process a single message with AI features.

        NOTE: For thread-aware processing, use ThreadStateService instead.
        This method processes messages in isolation without thread context.

        Args:
            message_data: Dict with 'subject', 'body', 'sender'
            db: Unused (kept for backwards compatibility)
            thread_id: Unused (kept for backwards compatibility)
            message_id: Unused (kept for backwards compatibility)

        Returns:
            Dict with summary, needs_reply, extracted_tasks, etc.
        """
        subject = message_data.get('subject', '')
        body = message_data.get('body', '')
        sender = message_data.get('sender', '')

        # Build composed prompt with extraction instructions
        extraction_instructions = self._build_extraction_instructions()

        prompt_template = self._load_prompt('process_message')
        prompt = prompt_template.format(
            sender=sender,
            subject=subject,
            body=body,
            extraction_instructions=extraction_instructions,
            json_schema=self.JSON_SCHEMA
        )

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning(f"Failed to parse process_message response")
                return self._empty_process_result()

            # Extract scheduling intent
            scheduling = result.get('scheduling_intent', {})

            return {
                'summary': result.get('summary', ''),
                'needs_reply': result.get('needs_reply', False),
                'extracted_tasks': result.get('tasks', []),
                'extracted_dates': result.get('dates', []),
                'extracted_people': result.get('people', []),
                'extracted_decisions': result.get('decisions', []),
                'scheduling_intent': scheduling.get('detected', False),
                'scheduling_intent_type': scheduling.get('type', 'none'),
                'scheduling_intent_confidence': scheduling.get('confidence', 0.0),
                'scheduling_intent_summary': scheduling.get('summary'),
                'scheduling_intent_meeting_title': scheduling.get('meeting_title'),
                'scheduling_intent_meeting_date': scheduling.get('meeting_date'),
            }
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return self._empty_process_result()

    def _empty_process_result(self) -> Dict[str, Any]:
        """Return fallback result structure when process_message fails"""
        return {
            '_fallback': True,
            'summary': '',
            'needs_reply': None,
            'extracted_tasks': [],
            'extracted_dates': [],
            'extracted_people': [],
            'extracted_decisions': [],
            'scheduling_intent': False,
            'scheduling_intent_type': 'none',
            'scheduling_intent_confidence': 0.0,
            'scheduling_intent_summary': None,
            'scheduling_intent_meeting_title': None,
            'scheduling_intent_meeting_date': None,
        }

    def summarize(self, text: str, db=None, thread_id: str = None) -> str:
        """
        Summarize text.

        NOTE: For thread summaries, use ThreadStateService.get_thread_summary()
        which returns the cached thread summary from state-based processing.

        Args:
            text: Text to summarize
            db: Unused (kept for backwards compatibility)
            thread_id: Unused (kept for backwards compatibility)

        Returns:
            Summary string
        """
        prompt_template = self._load_prompt('summarize')
        prompt = prompt_template.format(assistant_name=self.assistant_name, text=text)

        try:
            result = self._orchestrator.generate(prompt)
            return result.get('summary', '')
        except Exception as e:
            logger.error(f"Error summarizing: {e}")
            return ""

    def classify_needs_reply(self, subject: str, body: str, sender: str) -> bool:
        """Classify if message needs a reply"""
        prompt_template = self._load_prompt('classify_needs_reply')
        prompt = prompt_template.format(sender=sender, subject=subject, body=body)

        try:
            result = self._orchestrator.generate(prompt)
            return result.get('needs_reply', False)
        except Exception as e:
            logger.error(f"Error classifying: {e}")
            return False

    def extract_info(self, text: str, info_type: str) -> list:
        """Extract specific information (tasks, dates, people, decisions)"""
        prompt_template = self._load_prompt(f'extract_{info_type}')
        prompt = prompt_template.format(text=text)

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning(f"Failed to parse extract_{info_type} response")
                return []

            # Handle both list and dict responses
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and info_type in result:
                return result[info_type]
            return []
        except Exception as e:
            logger.error(f"Error extracting {info_type}: {e}")
            return []




    def process_messages_batch(
        self,
        messages: List[Dict[str, Any]],
        db=None,
    ) -> List[Dict[str, Any]]:
        """
        Process multiple messages in a single batch operation.

        NOTE: For thread-aware processing, use ThreadStateService instead.
        This method processes messages in isolation without thread context.
        """
        if not messages:
            return []

        prompt_template = self._load_prompt('process_message')
        prompts = []
        for msg in messages:
            subject = msg.get('subject', '')
            body = msg.get('body', '')
            sender = msg.get('sender', '')

            prompt = prompt_template.format(sender=sender, subject=subject, body=body)
            prompts.append(prompt)

        try:
            raw_results = self._orchestrator.generate_batch(prompts)
        except Exception as e:
            logger.error(f"Batch process_messages failed: {e}")
            return [self._empty_process_result() for _ in messages]

        return [
            self._empty_process_result() if result.get("_error") else {
                'summary': result.get('summary', ''),
                'needs_reply': result.get('needs_reply', False),
                'extracted_tasks': result.get('tasks', []),
                'extracted_dates': result.get('dates', []),
                'extracted_people': result.get('people', []),
                'extracted_decisions': result.get('decisions', [])
            }
            for result in raw_results
        ]

    def extract_tasks_batch(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract tasks from multiple messages in a single batch operation."""
        if not messages:
            return []

        prompt_template = self._load_prompt('extract_tasks_enhanced')
        prompts = [
            prompt_template.format(
                assistant_name=self.assistant_name,
                sender=msg.get('sender', ''),
                subject=msg.get('subject', ''),
                body=msg.get('body', ''),
                custom_instructions=msg.get('custom_instructions', '') or "None"
            )
            for msg in messages
        ]

        try:
            raw_results = self._orchestrator.generate_batch(prompts)
        except Exception as e:
            logger.error(f"Batch extract_tasks failed: {e}")
            return [{"tasks": []} for _ in messages]

        return [
            {"tasks": []} if result.get("_error") else result
            for result in raw_results
        ]

    def summarize_batch(self, texts: List[str]) -> List[str]:
        """Summarize multiple texts in a single batch operation."""
        if not texts:
            return []

        prompt_template = self._load_prompt('summarize')
        prompts = [prompt_template.format(assistant_name=self.assistant_name, text=text) for text in texts]

        try:
            results = self._orchestrator.generate_batch(prompts)
            return [r.get('summary', '') for r in results]
        except Exception as e:
            logger.error(f"Batch summarize failed: {e}")
            return ["" for _ in texts]

    # =========================================================================
    # Thread State Methods (State-Based Thread Processing)
    # =========================================================================

    def init_thread_state(
        self,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initialize thread state from the first message in a thread.

        Args:
            message_data: Dict with 'subject', 'body', 'sender'

        Returns:
            Dict with summary, tasks, decisions, last_action, needs_reply
        """
        prompt_template = self._load_prompt('init_thread_state')
        prompt = prompt_template.format(
            assistant_name=self.assistant_name,
            current_date=datetime.now(timezone.utc).strftime('%Y-%m-%d (%A)'),
            sender=message_data.get('sender', ''),
            subject=message_data.get('subject', ''),
            body=_prepare_body(message_data.get('body', ''), self.MAX_BODY_LENGTH)
        )
        custom_instructions = (message_data.get('custom_instructions') or "").strip()
        if custom_instructions:
            prompt += f"\n\n**CUSTOM TASK DETECTION INSTRUCTIONS (user-defined):**\n{custom_instructions}"

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse init_thread_state response")
                return self._fallback_init_thread_state(message_data)

            return result
        except Exception as e:
            logger.error(f"Error initializing thread state: {e}")
            return self._fallback_init_thread_state(message_data)

    def _fallback_init_thread_state(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback when thread state initialization fails."""
        return {
            "_fallback": True,
            "summary": message_data.get('subject', 'New conversation'),
            "tasks": [],
            "decisions": [],
            "last_action": "New message received",
            "last_action_by": message_data.get('sender', ''),
            "needs_reply": None,  # Unknown - don't assume either way
            "needs_reply_reason": "Unable to analyze",
            "scheduling_intent": False,
            "scheduling_intent_type": "none",
            "scheduling_intent_confidence": 0.0
        }

    def init_thread_state_batch(
        self,
        messages_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Initialize thread state for multiple messages in a single LLM batch call.
        
        Uses the Gemini batch API to process multiple new threads simultaneously,
        reducing API calls from N to 1.
        
        Args:
            messages_data: List of dicts, each with 'subject', 'body', 'sender'
            
        Returns:
            List of result dicts in same order as input, each with:
            summary, tasks, decisions, last_action, needs_reply, scheduling_intent
        """
        if not messages_data:
            return []
        
        # Build prompts for each message
        prompt_template = self._load_prompt('init_thread_state')
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d (%A)')
        prompts = []
        for msg in messages_data:
            prompt = prompt_template.format(
                assistant_name=self.assistant_name,
                current_date=current_date,
                sender=msg.get('sender', ''),
                subject=msg.get('subject', ''),
                body=_prepare_body(msg.get('body', ''), self.MAX_BODY_LENGTH)
            )
            custom_instructions = (msg.get('custom_instructions') or "").strip()
            if custom_instructions:
                prompt += f"\n\n**CUSTOM TASK DETECTION INSTRUCTIONS (user-defined):**\n{custom_instructions}"
            prompts.append(prompt)
        
        try:
            # Single batch API call for all messages
            results = self._orchestrator.generate_batch(prompts)
            
            # Process results, using fallbacks for failures
            processed = []
            for i, result in enumerate(results):
                if result.get("_error"):
                    logger.warning(f"Failed to parse init_thread_state batch item {i}")
                    processed.append(self._fallback_init_thread_state(messages_data[i]))
                else:
                    processed.append(result)
            
            logger.info(f"Batch init_thread_state: processed {len(processed)} messages in 1 API call")
            return processed
            
        except Exception as e:
            logger.error(f"Batch init_thread_state failed: {e}")
            # Fall back to individual processing
            return [self._fallback_init_thread_state(msg) for msg in messages_data]

    def update_thread_state(
        self,
        thread_state: Dict[str, Any],
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update thread state based on a new message.

        This is the core of state-based thread processing:
        - Takes current thread state + new message
        - Returns state delta (what changed)
        - No full thread transcript analysis

        Args:
            thread_state: Current thread state with summary, open_tasks, decisions, etc.
            message_data: New message with subject, body, sender

        Returns:
            Dict with state updates: summary_update, task_updates, new_tasks,
            new_decisions, last_action, needs_reply
        """
        # Format current state for prompt
        open_tasks_str = "None"
        if thread_state.get('open_tasks'):
            tasks = thread_state['open_tasks']
            if isinstance(tasks, list) and tasks:
                open_tasks_str = "\n".join([
                    f"- [{t.get('status', 'open')}] {t.get('title', 'Untitled')}"
                    for t in tasks
                ])

        decisions_str = "None"
        if thread_state.get('decisions'):
            decisions = thread_state['decisions']
            if isinstance(decisions, list) and decisions:
                decisions_str = "\n".join([
                    f"- {d.get('decision', '')}"
                    for d in decisions
                ])

        participants_str = "Unknown"
        if thread_state.get('participants'):
            participants = thread_state['participants']
            if isinstance(participants, list) and participants:
                participants_str = ", ".join([
                    p.get('email', p.get('name', 'Unknown'))
                    for p in participants
                ])

        prompt_template = self._load_prompt('update_thread_state')
        prompt = prompt_template.format(
            current_date=datetime.now(timezone.utc).strftime('%Y-%m-%d (%A)'),
            thread_summary=thread_state.get('summary', 'No summary yet'),
            participants=participants_str,
            open_tasks=open_tasks_str,
            decisions=decisions_str,
            last_action=thread_state.get('last_action', 'None'),
            message_count=thread_state.get('message_count', 0),
            sender=message_data.get('sender', ''),
            subject=message_data.get('subject', ''),
            body=_prepare_body(message_data.get('body', ''), self.MAX_BODY_LENGTH)
        )
        custom_instructions = (message_data.get('custom_instructions') or "").strip()
        if custom_instructions:
            prompt += f"\n\n**CUSTOM TASK DETECTION INSTRUCTIONS (user-defined):**\n{custom_instructions}"

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse update_thread_state response")
                return self._fallback_update_thread_state(message_data)

            return result
        except Exception as e:
            logger.error(f"Error updating thread state: {e}")
            return self._fallback_update_thread_state(message_data)

    def _fallback_update_thread_state(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback when thread state update fails."""
        return {
            "_fallback": True,
            "summary_update": None,
            "task_updates": [],
            "new_tasks": [],
            "new_decisions": [],
            "last_action": "New message received",
            "last_action_by": message_data.get('sender', ''),
            "needs_reply": None,  # Unknown - don't assume either way
            "needs_reply_reason": "Unable to analyze",
            "scheduling_intent": False,
            "scheduling_intent_type": "none",
            "scheduling_intent_confidence": 0.0
        }

    def update_thread_state_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Update thread state for multiple messages from DIFFERENT threads in a single batch.
        
        Each item contains both the current thread state and the new message.
        Since they're from different threads, they have no state dependencies.
        
        Args:
            items: List of dicts, each with 'thread_state' and 'message_data'
            
        Returns:
            List of result dicts in same order as input
        """
        if not items:
            return []
        
        # Build prompts for each item
        prompt_template = self._load_prompt('update_thread_state')
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d (%A)')
        prompts = []
        
        for item in items:
            thread_state = item['thread_state']
            message_data = item['message_data']
            
            # Format thread state strings
            open_tasks_str = "None"
            if thread_state.get('open_tasks'):
                tasks = thread_state['open_tasks']
                if isinstance(tasks, list) and tasks:
                    open_tasks_str = "\n".join([
                        f"- [{t.get('status', 'open')}] {t.get('title', 'Untitled')}"
                        for t in tasks
                    ])
            
            decisions_str = "None"
            if thread_state.get('decisions'):
                decisions = thread_state['decisions']
                if isinstance(decisions, list) and decisions:
                    decisions_str = "\n".join([
                        f"- {d.get('decision', '')}"
                        for d in decisions
                    ])
            
            participants_str = "Unknown"
            if thread_state.get('participants'):
                participants = thread_state['participants']
                if isinstance(participants, list) and participants:
                    participants_str = ", ".join([
                        p.get('email', p.get('name', 'Unknown'))
                        for p in participants
                    ])
            
            prompt = prompt_template.format(
                current_date=current_date,
                thread_summary=thread_state.get('summary', 'No summary yet'),
                participants=participants_str,
                open_tasks=open_tasks_str,
                decisions=decisions_str,
                last_action=thread_state.get('last_action', 'None'),
                message_count=thread_state.get('message_count', 0),
                sender=message_data.get('sender', ''),
                subject=message_data.get('subject', ''),
                body=_prepare_body(message_data.get('body', ''), self.MAX_BODY_LENGTH)
            )
            custom_instructions = (message_data.get('custom_instructions') or "").strip()
            if custom_instructions:
                prompt += f"\n\n**CUSTOM TASK DETECTION INSTRUCTIONS (user-defined):**\n{custom_instructions}"
            prompts.append(prompt)

        try:
            # Single batch API call
            results = self._orchestrator.generate_batch(prompts)
            
            # Process results with fallbacks
            processed = []
            for i, result in enumerate(results):
                if result.get("_error"):
                    logger.warning(f"Failed to parse update_thread_state batch item {i}")
                    processed.append(self._fallback_update_thread_state(items[i]['message_data']))
                else:
                    processed.append(result)
            
            logger.info(f"Batch update_thread_state: processed {len(processed)} messages in 1 API call")
            return processed
            
        except Exception as e:
            logger.error(f"Batch update_thread_state failed: {e}")
            return [self._fallback_update_thread_state(item['message_data']) for item in items]


    # =========================================================================
    # Scheduling Methods
    # =========================================================================


    # =========================================================================
    # Lifecycle
    # =========================================================================

    def cleanup(self) -> None:
        """
        Instance cleanup - no-op since LLM providers are shared at class level.

        Use AIProcessor.cleanup_all() for actual cleanup on application shutdown.
        """
        pass

    @staticmethod
    def cleanup_all() -> None:
        """
        Release all shared LLM resources.

        Call this on application shutdown to properly clean up providers.
        """
        from core.llm import LLMOrchestrator
        LLMOrchestrator.cleanup_all()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
