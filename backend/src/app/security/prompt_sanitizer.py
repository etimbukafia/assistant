"""
Prompt Injection Defense Utilities

Sanitizes user-controlled content before injection into LLM prompts.
Uses delimiter wrapping and pattern neutralization to prevent prompt injection attacks.
"""
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


# Patterns that may indicate prompt injection attempts
INJECTION_PATTERNS: List[Tuple[str, str]] = [
    # Role markers that could confuse the LLM
    (r"(?i)\bSYSTEM\s*:", "SYSTEM:"),
    (r"(?i)\bUSER\s*:", "USER:"),
    (r"(?i)\bASSISTANT\s*:", "ASSISTANT:"),
    (r"(?i)\bHUMAN\s*:", "HUMAN:"),
    (r"(?i)\bAI\s*:", "AI:"),

    # Instruction override attempts
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", "ignore instructions"),
    (r"(?i)disregard\s+(all\s+)?(previous|prior|above)\s+instructions?", "disregard instructions"),
    (r"(?i)forget\s+(all\s+)?(previous|prior|above)\s+instructions?", "forget instructions"),
    (r"(?i)new\s+instructions?\s*:", "new instructions:"),
    (r"(?i)override\s+instructions?", "override instructions"),

    # Delimiter injection
    (r"---+", "---"),  # Markdown horizontal rules
    (r"```", "```"),   # Code block markers
    (r"<\s*/?\s*system\s*>", "<system>"),  # XML system tags
    (r"<\s*/?\s*user\s*>", "<user>"),
    (r"<\s*/?\s*assistant\s*>", "<assistant>"),

    # Jailbreak attempts
    (r"(?i)you\s+are\s+now\s+(in\s+)?[a-z]+\s+mode", "mode switch attempt"),
    (r"(?i)pretend\s+(you\s+are|to\s+be)", "pretend attempt"),
    (r"(?i)act\s+as\s+(if\s+you\s+are|a)", "act as attempt"),
    (r"(?i)roleplay\s+as", "roleplay attempt"),
    (r"(?i)DAN\s+mode", "DAN mode"),
    (r"(?i)developer\s+mode", "developer mode"),
]


@dataclass
class SanitizationResult:
    """Result of sanitization with detection info."""
    sanitized_text: str
    patterns_detected: List[str]
    was_modified: bool


def detect_injection_patterns(text: str) -> List[str]:
    """
    Detect potential prompt injection patterns in text.

    Args:
        text: Text to analyze

    Returns:
        List of pattern names that were detected
    """
    if not text:
        return []

    detected = []
    for pattern, name in INJECTION_PATTERNS:
        if re.search(pattern, text):
            detected.append(name)

    return detected


def detect_injection_attempt(text: str) -> bool:
    """
    Check if text contains potential prompt injection.

    Args:
        text: Text to check

    Returns:
        True if potential injection detected
    """
    return len(detect_injection_patterns(text)) > 0


def sanitize_for_prompt(text: str) -> str:
    """
    Sanitize text for safe inclusion in LLM prompts.

    Neutralizes patterns that could be used for prompt injection
    while preserving the semantic content of the text.

    Args:
        text: Raw text to sanitize

    Returns:
        Sanitized text safe for prompt inclusion
    """
    if not text:
        return ""

    sanitized = text

    # Escape role markers by adding zero-width spaces
    # This breaks the pattern without changing visible content
    sanitized = re.sub(r"(?i)(SYSTEM|USER|ASSISTANT|HUMAN|AI)\s*:", r"\1" + "\u200B:", sanitized)

    # Escape markdown delimiters
    sanitized = sanitized.replace("---", "\\-\\-\\-")
    sanitized = sanitized.replace("```", "\\`\\`\\`")

    # Escape XML-like tags that could interfere with our delimiters
    sanitized = re.sub(r"<\s*(/?)\s*(data|system|user|assistant)\s*>",
                       r"[\1\2]", sanitized, flags=re.IGNORECASE)

    # Normalize excessive newlines (could be used to push content out of view)
    sanitized = re.sub(r"\n{4,}", "\n\n\n", sanitized)

    # Strip control characters except common whitespace
    sanitized = "".join(
        char for char in sanitized
        if char >= " " or char in "\n\r\t"
    )

    return sanitized


def wrap_user_content(content: str, tag: str = "data") -> str:
    """
    Wrap user-controlled content in delimiters for safe prompt inclusion.

    The LLM is instructed to treat content within these tags as data,
    not as instructions.

    Args:
        content: User content to wrap
        tag: Tag name to use (default: "data")

    Returns:
        Content wrapped in XML-style delimiters
    """
    sanitized = sanitize_for_prompt(content)
    return f"<{tag}>{sanitized}</{tag}>"


def sanitize_with_detection(text: str) -> SanitizationResult:
    """
    Sanitize text and return detection information.

    Useful when you need to log detected patterns.

    Args:
        text: Text to sanitize

    Returns:
        SanitizationResult with sanitized text and detection info
    """
    patterns = detect_injection_patterns(text)
    sanitized = sanitize_for_prompt(text)

    return SanitizationResult(
        sanitized_text=sanitized,
        patterns_detected=patterns,
        was_modified=sanitized != text
    )


def wrap_with_detection(
    content: str,
    tag: str = "data"
) -> Tuple[str, List[str]]:
    """
    Wrap content and return detected patterns for logging.

    Args:
        content: Content to wrap
        tag: Tag name to use

    Returns:
        Tuple of (wrapped content, list of detected patterns)
    """
    patterns = detect_injection_patterns(content)
    wrapped = wrap_user_content(content, tag)
    return wrapped, patterns


def sanitize_email_content(
    subject: Optional[str] = None,
    sender: Optional[str] = None,
    body: Optional[str] = None,
    max_body_length: int = 500
) -> dict:
    """
    Sanitize email fields for prompt context.

    Args:
        subject: Email subject line
        sender: Sender email/name
        body: Email body (will be truncated)
        max_body_length: Maximum body length to include

    Returns:
        Dict with sanitized fields and detection info
    """
    result = {
        "subject": "",
        "sender": "",
        "body_preview": "",
        "patterns_detected": []
    }

    if subject:
        subj_result = sanitize_with_detection(subject)
        result["subject"] = subj_result.sanitized_text
        result["patterns_detected"].extend(subj_result.patterns_detected)

    if sender:
        # Sender is typically an email address, less risk but still sanitize
        result["sender"] = sanitize_for_prompt(sender)

    if body:
        # Truncate first, then sanitize
        truncated = body[:max_body_length]
        body_result = sanitize_with_detection(truncated)
        result["body_preview"] = body_result.sanitized_text
        result["patterns_detected"].extend(body_result.patterns_detected)

    # Deduplicate patterns
    result["patterns_detected"] = list(set(result["patterns_detected"]))

    return result


def sanitize_task_content(
    title: Optional[str] = None,
    description: Optional[str] = None,
    max_description_length: int = 300
) -> dict:
    """
    Sanitize task fields for prompt context.

    Args:
        title: Task title
        description: Task description (will be truncated)
        max_description_length: Maximum description length

    Returns:
        Dict with sanitized fields and detection info
    """
    result = {
        "title": "",
        "description": "",
        "patterns_detected": []
    }

    if title:
        title_result = sanitize_with_detection(title)
        result["title"] = title_result.sanitized_text
        result["patterns_detected"].extend(title_result.patterns_detected)

    if description:
        truncated = description[:max_description_length]
        desc_result = sanitize_with_detection(truncated)
        result["description"] = desc_result.sanitized_text
        result["patterns_detected"].extend(desc_result.patterns_detected)

    result["patterns_detected"] = list(set(result["patterns_detected"]))

    return result
