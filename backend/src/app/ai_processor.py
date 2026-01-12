import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.llm import LLMOrchestrator, LLMConfig

logger = logging.getLogger(__name__)


class AIProcessor:
    MAX_BODY_LENGTH = 3000
    MAX_SCHEDULING_BODY = 1500
    
    # Placeholder patterns for detection
    PLACEHOLDER_PATTERNS = ["[", "]", "{", "}", "INSERT", "TIME HERE", "NAME HERE", "YOUR", "THEIR"]

    def __init__(
        self,
        prompts_dir: str = "prompts",
        llm_config: Optional[LLMConfig] = None,
    ):
        self.prompts_dir = Path(prompts_dir)
        self._prompts_cache = {}
        self._orchestrator = LLMOrchestrator(config=llm_config)

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
    "type": "availability_request|time_request|reschedule_request|none",
    "confidence": 0.0-1.0
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
                'scheduling_intent_confidence': scheduling.get('confidence', 0.0)
            }
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return self._empty_process_result()

    def _empty_process_result(self) -> Dict[str, Any]:
        """Return empty result structure for process_message"""
        return {
            'summary': '',
            'needs_reply': None,
            'extracted_tasks': [],
            'extracted_dates': [],
            'extracted_people': [],
            'extracted_decisions': [],
            'scheduling_intent': False,
            'scheduling_intent_type': 'none',
            'scheduling_intent_confidence': 0.0
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
        prompt = prompt_template.format(text=text)

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

    def _fetch_availability_context(self, db: Any, user_id: str) -> str:
        """
        Fetch calendar availability and format as context string.
        
        Args:
            db: Database session
            user_id: ID of the user to fetch availability for
        """
        if not db or not user_id:
            logger.warning("_fetch_availability_context called without db or user_id")
            return ""

        try:
            from datetime import datetime, timezone, timedelta
            from .calendar_service import CalendarService
            from .models import UserSettings
            import asyncio

            # Secure query: Filter by user_id
            settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                return ""

            calendar_service = CalendarService(db)

            # Get availability for next 2 weeks
            start = datetime.now(timezone.utc)
            end = start + timedelta(days=14)

            # Safe async execution
            try:
                # Check for existing loop
                loop = asyncio.get_running_loop()
                # If we are here, we are in a loop.
                # Use nest_asyncio if available to allow re-entrant event loop
                try:
                    import nest_asyncio
                    nest_asyncio.apply()
                except ImportError:
                    pass 
                
                slots = loop.run_until_complete(
                    calendar_service.suggest_time_slots(
                        start_date=start,
                        end_date=end,
                        duration_minutes=settings.default_meeting_duration or 30,
                        count=5,
                        working_hours_start=settings.working_hours_start,
                        working_hours_end=settings.working_hours_end,
                        buffer_minutes=settings.buffer_minutes
                    )
                )
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                slots = asyncio.run(
                    calendar_service.suggest_time_slots(
                        start_date=start,
                        end_date=end,
                        duration_minutes=settings.default_meeting_duration or 30,
                        count=5,
                        working_hours_start=settings.working_hours_start,
                        working_hours_end=settings.working_hours_end,
                        buffer_minutes=settings.buffer_minutes
                    )
                )

            if not slots:
                return ""

            # Format slots as readable text
            tz_display = settings.default_timezone or "UTC"
            slot_texts = []
            for slot in slots[:5]:
                start_dt = slot.start_time
                slot_texts.append(start_dt.strftime("%A at %-I:%M%p").replace("AM", "am").replace("PM", "pm"))

            return f"\n- **Your available times ({tz_display}):** {', '.join(slot_texts)}"

        except Exception as e:
            logger.error(f"Error fetching availability: {e}")
            return ""

    def generate_draft_reply(
        self,
        message_data: Dict[str, Any],
        context: str = "",
        db=None,  # Optional: SQLAlchemy session for memory context
        user_id: str = None, # Required for RLS / Context
        scheduling_intent: bool = False  # From message.scheduling_intent
    ) -> str:
        """
        Generate a draft reply with:
        - Principal Memory context (tone, preferences, contact info)
        - Scheduling awareness when relevant
        """
        subject = message_data.get('subject', '')
        body = message_data.get('body', '')
        sender = message_data.get('sender', '')

        context_section = ""

        # 1. Inject Principal Memory context if db is available
        if db:
            if user_id:
                try:
                    from .context_builder import ContextBuilder
                    # Use provided user_id, NOT hardcoded "default"
                    builder = ContextBuilder(db, user_id=user_id)
                    memory_context = builder.build_context(
                        context_type="drafting",
                        sender_email=sender
                    )
                    if memory_context:
                        context_section += f"\n- **User preferences:** {memory_context}"
                except Exception as e:
                    logger.warning(f"Failed to load memory context: {e}")
            else:
                logger.warning("DB provided to generate_draft_reply but no user_id - skipping context")

        # 2. Add any additional context passed directly
        if context:
            context_section += f"\n- **Additional context:** {context}"

        # 3. Add availability context if scheduling intent detected
        if scheduling_intent:
            if db and user_id:
                availability_context = self._fetch_availability_context(db, user_id)
                if availability_context:
                    context_section += availability_context
                    context_section += "\n- **Note:** If they're asking for your availability, offer specific times from the list above."
            else:
                logger.warning("Scheduling intent detected but cannot fetch availability (missing db or user_id)")

        prompt_template = self._load_prompt('draft_reply')
        prompt = prompt_template.format(
            sender=sender,
            subject=subject,
            body=body,
            context_section=context_section
        )

        try:
            result = self._orchestrator.generate(prompt)
            draft = result.get('draft', '')

            if not draft or result.get('_error'):
                return ""

            # Safety check using standardized logic
            if self._has_placeholders(draft):
                logger.warning("Draft contained placeholder text, regenerating...")
                retry_prompt = prompt + "\n\nIMPORTANT: Your previous response contained placeholder text like [Insert Time]. This is NOT allowed. Generate a real response without ANY bracketed placeholders."
                result = self._orchestrator.generate(retry_prompt)
                draft = result.get('draft', '')

                if self._has_placeholders(draft):
                    return "Thank you for your email. I'll review this and get back to you shortly."

            return draft
        except Exception as e:
            logger.error(f"Error generating draft reply: {e}")
            return ""

    def extract_tasks_enhanced(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured tasks with enhanced context from a message.
        Uses the extract_tasks_enhanced.md prompt.

        Args:
            message_data: Dictionary with 'sender', 'subject', 'body', 'custom_instructions'

        Returns:
            Dictionary with 'tasks' array containing detailed task information
        """
        sender = message_data.get('sender', '')
        subject = message_data.get('subject', '')
        body = message_data.get('body', '')
        custom_instructions = message_data.get('custom_instructions', '')

        prompt_template = self._load_prompt('extract_tasks_enhanced')
        prompt = prompt_template.format(
            sender=sender,
            subject=subject,
            body=body,
            custom_instructions=custom_instructions or "None"
        )

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse extract_tasks_enhanced response")
                return {"tasks": []}

            return result
        except Exception as e:
            logger.error(f"Error extracting enhanced tasks: {e}")
            return {"tasks": []}

    def evaluate_reminder_context(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate if a reminder should be sent based on current context.
        Uses the evaluate_reminder_context.md prompt.

        Args:
            context_data: Dictionary with task and message details

        Returns:
            Dictionary with 'should_remind', 'reason', 'reschedule_for', 'suggested_message'
        """
        prompt_template = self._load_prompt('evaluate_reminder_context')
        prompt = prompt_template.format(
            task_title=context_data.get('task_title', ''),
            task_created_at=context_data.get('task_created_at', ''),
            reminder_context=json.dumps(context_data.get('reminder_context', {})),
            last_reminded_at=context_data.get('last_reminded_at', 'Never'),
            reminder_count=context_data.get('reminder_count', 0),
            message_subject=context_data.get('message_subject', ''),
            message_sender=context_data.get('message_sender', ''),
            current_time=context_data.get('current_time', '')
        )

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse evaluate_reminder_context response")
                return self._empty_reminder_result("Parse error")

            return result
        except Exception as e:
            logger.error(f"Error evaluating reminder context: {e}")
            return self._empty_reminder_result(str(e))

    def _empty_reminder_result(self, reason: str) -> Dict[str, Any]:
        """Return empty result for evaluate_reminder_context"""
        return {
            "should_remind": False,
            "reason": f"Evaluation error: {reason}",
            "reschedule_for": None,
            "suggested_message": None
        }

    def generate_meeting_followups(self, meeting_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate follow-up items for a completed meeting.

        Args:
            meeting_context: Dictionary with:
                - title: Meeting title
                - meeting_date: When the meeting occurred
                - attendees: List of attendee info
                - agenda: Meeting description/agenda
                - related_emails: Summary of related emails
                - open_tasks: Open tasks involving attendees
                - prep_warnings: Any unresolved prep warnings

        Returns:
            Dictionary with 'follow_ups' array and 'reasoning'
        """
        prompt_template = self._load_prompt('generate_meeting_followups')
        prompt = prompt_template.format(
            title=meeting_context.get('title', 'Untitled Meeting'),
            meeting_date=meeting_context.get('meeting_date', 'Unknown'),
            attendees=meeting_context.get('attendees', 'No attendees'),
            agenda=meeting_context.get('agenda', 'No agenda provided'),
            related_emails=meeting_context.get('related_emails', 'None'),
            open_tasks=meeting_context.get('open_tasks', 'None'),
            prep_warnings=meeting_context.get('prep_warnings', 'None')
        )

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse generate_meeting_followups response")
                return {"follow_ups": [], "reasoning": "Failed to generate follow-ups"}

            return result
        except Exception as e:
            logger.error(f"Error generating meeting follow-ups: {e}")
            return {"follow_ups": [], "reasoning": f"Error: {str(e)}"}

    def generate_follow_up_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a contextual follow-up message for an unresolved task.

        Args:
            context: Dictionary with:
                - sender: Original email sender
                - subject: Original email subject
                - snippet: Relevant snippet from original email
                - task_title: Title of the task
                - task_type: Type of task (waiting_for, implied_followup)
                - days_since: Days since task was created
                - reminder_count: Number of previous follow-ups sent
                - additional_context: Optional extra context

        Returns:
            Dictionary with 'follow_up', 'subject_line', 'tone'
        """
        prompt_template = self._load_prompt('generate_follow_up')
        prompt = prompt_template.format(
            sender=context.get('sender', 'Unknown'),
            subject=context.get('subject', 'No subject'),
            snippet=context.get('snippet', 'No content available'),
            task_title=context.get('task_title', 'Untitled task'),
            task_type=context.get('task_type', 'follow-up'),
            days_since=context.get('days_since', 0),
            reminder_count=context.get('reminder_count', 0),
            context=context.get('additional_context', 'None')
        )

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse generate_follow_up response")
                return self._fallback_follow_up(context)

            return result
        except Exception as e:
            logger.error(f"Error generating follow-up message: {e}")
            return self._fallback_follow_up(context)

    def _fallback_follow_up(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback template when AI generation fails."""
        task_title = context.get('task_title', 'this matter')
        return {
            "follow_up": (
                f"I wanted to follow up on my previous email regarding: {task_title}\n\n"
                "Just checking if you've had a chance to look at this. "
                "Let me know if you need any additional information.\n\n"
                "Thanks!"
            ),
            "subject_line": f"Following up: {context.get('subject', task_title)}",
            "tone": "professional"
        }

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
        prompts = [prompt_template.format(text=text) for text in texts]

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
            current_date=datetime.now(timezone.utc).strftime('%Y-%m-%d (%A)'),
            sender=message_data.get('sender', ''),
            subject=message_data.get('subject', ''),
            body=message_data.get('body', '')[:3000]  # Limit body size
        )

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
            "summary": message_data.get('subject', 'New conversation'),
            "tasks": [],
            "decisions": [],
            "last_action": "New message received",
            "last_action_by": message_data.get('sender', ''),
            "needs_reply": True,
            "needs_reply_reason": "Unable to analyze - defaulting to needs reply",
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
                current_date=current_date,
                sender=msg.get('sender', ''),
                subject=msg.get('subject', ''),
                body=msg.get('body', '')[:self.MAX_BODY_LENGTH]
            )
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
            body=message_data.get('body', '')[:self.MAX_BODY_LENGTH]  # Limit body size
        )

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
            "summary_update": None,
            "task_updates": [],
            "new_tasks": [],
            "new_decisions": [],
            "last_action": "New message received",
            "last_action_by": message_data.get('sender', ''),
            "needs_reply": True,
            "needs_reply_reason": "Unable to analyze - defaulting to needs reply",
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
                body=message_data.get('body', '')[:self.MAX_BODY_LENGTH]
            )
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

    def detect_scheduling_intent(
        self,
        message_body: str,
        message_subject: str = ""
    ) -> Dict[str, Any]:
        """
        Detect if a message contains scheduling intent and classify the type.

        Args:
            message_body: The message body text
            message_subject: The message subject

        Returns:
            Dict with has_intent, intent_type, confidence, and extracted details
        """
        prompt_template = self._load_prompt('scheduling_detect_intent')
        prompt = prompt_template.format(
            message_subject=message_subject,
            message_body=message_body[:self.MAX_SCHEDULING_BODY]
        )

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse detect_scheduling_intent response")
                return self._fallback_scheduling_intent()

            # Ensure required fields exist
            result.setdefault("intent_type", "none")
            result.setdefault("action_required", "")
            result.setdefault("meeting_with", "")
            result.setdefault("mentioned_times", [])

            return result
        except Exception as e:
            logger.error(f"Error detecting scheduling intent: {e}")
            return self._fallback_scheduling_intent()

    def _fallback_scheduling_intent(self) -> Dict[str, Any]:
        """Fallback when scheduling intent detection fails."""
        return {
            "has_intent": False,
            "intent_type": "none",
            "confidence": 0.0,
            "reason": "Error detecting intent",
            "action_required": "",
            "meeting_with": "",
            "mentioned_times": [],
            "detected_phrases": []
        }

    def extract_scheduling_details(
        self,
        message_body: str,
        message_subject: str = "",
        sender_email: str = ""
    ) -> Dict[str, Any]:
        """
        Extract scheduling details from a message.

        Args:
            message_body: The message body
            message_subject: The message subject
            sender_email: The sender's email address

        Returns:
            Dict with participants, time_constraints, meeting_type, duration_minutes, timezone
        """
        prompt_template = self._load_prompt('scheduling_extract_details')
        prompt = prompt_template.format(
            message_subject=message_subject,
            sender_email=sender_email,
            message_body=message_body[:self.MAX_BODY_LENGTH]
        )

        try:
            result = self._orchestrator.generate(prompt)

            if result.get("_error"):
                logger.warning("Failed to parse extract_scheduling_details response")
                return self._fallback_scheduling_details(sender_email)

            # Ensure sender is in participants
            if sender_email and sender_email not in result.get("participants", []):
                result["participants"] = [sender_email] + result.get("participants", [])

            return result
        except Exception as e:
            logger.error(f"Error extracting scheduling details: {e}")
            return self._fallback_scheduling_details(sender_email)

    def _fallback_scheduling_details(self, sender_email: str = "") -> Dict[str, Any]:
        """Fallback when scheduling details extraction fails."""
        return {
            "participants": [sender_email] if sender_email else [],
            "time_constraints": {},
            "meeting_type": "other",
            "duration_minutes": 30,
            "timezone": None,
            "source_snippet": ""
        }

    def generate_scheduling_reply(
        self,
        intent_type: str,
        context_details: str,
        sentence_limit: str = "1-2 sentences max",
        tone_guidance: str = "Professional and friendly",
        additional_requirements: str = "",
        example: str = ""
    ) -> str:
        """
        Generate a context-appropriate scheduling reply based on intent type.

        Args:
            intent_type: Type of scheduling intent detected
            context_details: Formatted context string with all necessary details
            sentence_limit: How long the reply should be
            tone_guidance: Tone instructions
            additional_requirements: Any additional requirements
            example: Example reply to guide the LLM

        Returns:
            Draft reply text
        """
        # Build intent-specific instructions
        intent_instructions = {
            "meeting_confirmation": "Generate a brief reply acknowledging a meeting confirmation.",
            "meeting_reminder": "Generate a brief reply acknowledging a meeting reminder.",
            "time_request": "Generate a brief reply providing meeting times.",
            "reschedule_request": "Generate a brief reply offering alternative times for rescheduling.",
            "availability_request": "Generate a brief, professional scheduling reply."
        }

        intent_specific = intent_instructions.get(
            intent_type,
            "Generate a brief, professional scheduling reply."
        )

        prompt_template = self._load_prompt('scheduling_draft_reply')
        prompt = prompt_template.format(
            intent_specific_instructions=intent_specific,
            context_details=context_details,
            sentence_limit=sentence_limit,
            tone_guidance=tone_guidance,
            additional_requirements=additional_requirements,
            example=example
        )

        try:
            result = self._orchestrator.generate(prompt)

            # For non-JSON mode, result is typically {"text": "..."}
            if isinstance(result, dict):
                reply = result.get("text", "").strip().strip('"').strip("'")
            else:
                reply = str(result).strip().strip('"').strip("'")

            # Safety check: reject if it contains obvious placeholders
            if self._has_placeholders(reply):
                logger.warning(f"AI generated placeholder text, using fallback: {reply}")
                return "I'll check my calendar and get back to you shortly."

            return reply
        except Exception as e:
            logger.error(f"Error generating draft reply: {e}")
            return "I'll check my calendar and get back to you with available times."

    def generate_event_description(
        self,
        message_body: str,
        meeting_type: str,
        participants: List[str]
    ) -> str:
        """
        Generate a calendar event description from email context.

        Args:
            message_body: Original message body
            meeting_type: Type of meeting
            participants: List of participant emails

        Returns:
            Event description text
        """
        prompt_template = self._load_prompt('scheduling_event_description')
        prompt = prompt_template.format(
            meeting_type=meeting_type,
            participants=', '.join(participants),
            message_body=message_body[:self.MAX_SCHEDULING_BODY]
        )

        try:
            result = self._orchestrator.generate(prompt)

            # For non-JSON mode, result is typically {"text": "..."}
            if isinstance(result, dict):
                return result.get("text", "").strip()
            else:
                return str(result).strip()
        except Exception as e:
            logger.error(f"Error generating event description: {e}")
            return f"{meeting_type.title()} with {', '.join(participants)}"

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
