import json
import google.genai as genai
from typing import Dict, Any
from pathlib import Path

from .config import settings


def get_thread_messages(db, thread_id: str, exclude_message_id: int = None) -> list:
    """
    Fetch all messages in a thread, ordered chronologically.

    Args:
        db: SQLAlchemy session
        thread_id: Gmail thread ID
        exclude_message_id: Optional message ID to exclude (e.g., current message)

    Returns:
        List of Message objects ordered by received_at
    """
    from .models import Message

    query = db.query(Message).filter(Message.thread_id == thread_id)
    if exclude_message_id:
        query = query.filter(Message.id != exclude_message_id)
    return query.order_by(Message.received_at.asc()).all()


def build_thread_context(messages: list, current_message_id: int = None) -> str:
    """
    Build a formatted string of thread history for AI context.

    Args:
        messages: List of Message objects
        current_message_id: ID of the current message being processed

    Returns:
        Formatted thread context string
    """
    if not messages:
        return ""

    thread_parts = []
    for msg in messages:
        if current_message_id and msg.id == current_message_id:
            continue  # Skip current message if specified

        received_str = msg.received_at.strftime("%Y-%m-%d %H:%M") if msg.received_at else "Unknown"
        thread_parts.append(
            f"[{received_str}] From: {msg.sender}\n"
            f"Subject: {msg.subject}\n\n"
            f"{msg.decrypted_body}"
        )

    if not thread_parts:
        return ""

    return "\n\n---\n\n".join(thread_parts)


class AIProcessor:
    def __init__(self, model_name: str = "gemini-3-flash-preview", prompts_dir: str = "prompts"):
        self.model = model_name
        self.prompts_dir = Path(prompts_dir)
        self._prompts_cache = {}
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)

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

    def process_message(
        self,
        message_data: Dict[str, Any],
        db=None,
        thread_id: str = None,
        message_id: int = None
    ) -> Dict[str, Any]:
        """
        Process a message with all AI features.

        Args:
            message_data: Dict with 'subject', 'body', 'sender'
            db: Optional SQLAlchemy session for thread context
            thread_id: Optional Gmail thread ID to fetch conversation history
            message_id: Optional current message ID to exclude from thread context

        Returns:
            Dict with summary, needs_reply, extracted_tasks, etc.
        """
        subject = message_data.get('subject', '')
        body = message_data.get('body', '')
        sender = message_data.get('sender', '')

        # Build thread context if db and thread_id are provided
        thread_context = ""
        if db and thread_id:
            thread_messages = get_thread_messages(db, thread_id, exclude_message_id=message_id)
            if thread_messages:
                thread_context = build_thread_context(thread_messages, current_message_id=message_id)

        # Use thread-aware prompt if we have thread context
        if thread_context:
            prompt_template = self._load_prompt('process_message_thread')
            prompt = prompt_template.format(
                sender=sender,
                subject=subject,
                body=body,
                thread_context=thread_context
            )
        else:
            prompt_template = self._load_prompt('process_message')
            prompt = prompt_template.format(sender=sender, subject=subject, body=body)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result_text = response.text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            return {
                'summary': result.get('summary', ''),
                'needs_reply': result.get('needs_reply', False),
                'extracted_tasks': result.get('tasks', []),
                'extracted_dates': result.get('dates', []),
                'extracted_people': result.get('people', []),
                'extracted_decisions': result.get('decisions', [])
            }
        except Exception as e:
            print(f"Error processing message: {e}")
            return {
                'summary': 'Error processing message',
                'needs_reply': None,
                'extracted_tasks': [],
                'extracted_dates': [],
                'extracted_people': [],
                'extracted_decisions': []
            }

    def summarize(self, text: str, db=None, thread_id: str = None) -> str:
        """
        Summarize text or an entire email thread.

        Args:
            text: Text to summarize (used if no thread_id provided)
            db: Optional SQLAlchemy session for thread context
            thread_id: Optional Gmail thread ID to summarize entire thread

        Returns:
            Summary string
        """
        # If thread_id provided, fetch and summarize the entire thread
        if db and thread_id:
            thread_messages = get_thread_messages(db, thread_id)
            if thread_messages:
                thread_context = build_thread_context(thread_messages)
                if thread_context:
                    text = thread_context

        prompt_template = self._load_prompt('summarize')
        prompt = prompt_template.format(text=text)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"Error summarizing: {e}")
            return "Error generating summary"

    def classify_needs_reply(self, subject: str, body: str, sender: str) -> bool:
        """Classify if message needs a reply"""
        prompt_template = self._load_prompt('classify_needs_reply')
        prompt = prompt_template.format(sender=sender, subject=subject, body=body)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            return response.text.strip().lower() == "true"
        except Exception as e:
            print(f"Error classifying: {e}")
            return False

    def extract_info(self, text: str, info_type: str) -> list:
        """Extract specific information (tasks, dates, people, decisions)"""
        prompt_template = self._load_prompt(f'extract_{info_type}')
        prompt = prompt_template.format(text=text)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result_text = response.text.strip()

            # Extract JSON array from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            return json.loads(result_text)
        except Exception as e:
            print(f"Error extracting {info_type}: {e}")
            return []

    # Scheduling keywords for quick detection (no LLM call)
    SCHEDULING_KEYWORDS = [
        "meeting", "schedule", "calendar", "available", "availability",
        "slot", "book", "appointment", "call", "sync", "catch up",
        "free time", "when are you", "let's meet", "set up a time",
        "tomorrow", "next week", "this week", "reschedule"
    ]

    def _has_scheduling_intent(self, subject: str, body: str) -> bool:
        """Quick keyword check for scheduling intent (no LLM call)"""
        text = f"{subject} {body}".lower()
        return any(keyword in text for keyword in self.SCHEDULING_KEYWORDS)

    def _fetch_availability_context(self) -> str:
        """Fetch calendar availability and format as context string"""
        try:
            from datetime import datetime, timezone, timedelta
            from .database import SessionLocal
            from .calendar_service import CalendarService
            from .models import UserSettings

            db = SessionLocal()
            try:
                settings = db.query(UserSettings).first()
                if not settings:
                    return ""

                calendar_service = CalendarService(db)

                # Get availability for next 2 weeks
                start = datetime.now(timezone.utc)
                end = start + timedelta(days=14)

                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
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
                finally:
                    loop.close()

                if not slots:
                    return ""

                # Format slots as readable text
                tz_display = settings.default_timezone or "UTC"
                slot_texts = []
                for slot in slots[:5]:
                    start_dt = slot.start_time
                    slot_texts.append(start_dt.strftime("%A at %-I:%M%p").replace("AM", "am").replace("PM", "pm"))

                return f"\n- **Your available times ({tz_display}):** {', '.join(slot_texts)}"

            finally:
                db.close()

        except Exception as e:
            print(f"Error fetching availability: {e}")
            return ""

    def generate_draft_reply(
        self,
        message_data: Dict[str, Any],
        context: str = "",
        db=None  # Optional: SQLAlchemy session for memory context
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
            try:
                from .context_builder import ContextBuilder
                builder = ContextBuilder(db, user_id="default")
                memory_context = builder.build_context(
                    context_type="drafting",
                    sender_email=sender
                )
                if memory_context:
                    context_section += f"\n- **User preferences:** {memory_context}"
            except Exception as e:
                print(f"Warning: Failed to load memory context: {e}")

        # 2. Add any additional context passed directly
        if context:
            context_section += f"\n- **Additional context:** {context}"

        # 3. Check for scheduling intent (fast keyword check, no LLM)
        if self._has_scheduling_intent(subject, body):
            availability_context = self._fetch_availability_context()
            if availability_context:
                context_section += availability_context
                context_section += "\n- **Note:** If they're asking for your availability, offer specific times from the list above."

        prompt_template = self._load_prompt('draft_reply')
        prompt = prompt_template.format(
            sender=sender,
            subject=subject,
            body=body,
            context_section=context_section
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            draft = response.text.strip()

            # Safety check: reject if it contains obvious placeholders
            placeholder_patterns = ["[Insert", "[Time]", "[Date]", "[Name]", "[Your", "[Their"]
            if any(p.lower() in draft.lower() for p in placeholder_patterns):
                print(f"Warning: Draft contained placeholder text, regenerating...")
                # Try once more with stronger instruction
                retry_prompt = prompt + "\n\nIMPORTANT: Your previous response contained placeholder text like [Insert Time]. This is NOT allowed. Generate a real response without ANY bracketed placeholders."
                retry_response = self.client.models.generate_content(
                    model=self.model,
                    contents=retry_prompt
                )
                draft = retry_response.text.strip()

                # If still has placeholders, return a safe fallback
                if any(p.lower() in draft.lower() for p in placeholder_patterns):
                    return "Thank you for your email. I'll review this and get back to you shortly."

            return draft
        except Exception as e:
            print(f"Error generating draft reply: {e}")
            return "Error generating draft reply"

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
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result_text = response.text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)
            return result

        except Exception as e:
            print(f"Error extracting enhanced tasks: {e}")
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
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result_text = response.text.strip()

            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)
            return result

        except Exception as e:
            print(f"Error evaluating reminder context: {e}")
            return {
                "should_remind": False,
                "reason": f"Evaluation error: {str(e)}",
                "reschedule_for": None,
                "suggested_message": None
            }
