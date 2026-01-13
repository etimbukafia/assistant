"""
Document Processor: AI-powered attachment analysis using Gemini Files API.

Extracts summaries, tasks, key points, and deadlines from email attachments.
Integrates seamlessly with the email sync pipeline.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.llm.providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)

# Load prompt template
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analyze_attachment.md"


class DocumentProcessor:
    """
    Process email attachments using Gemini's file understanding capabilities.
    
    Usage:
        processor = DocumentProcessor()
        insights = processor.process_attachment(file_bytes, "application/pdf", "report.pdf")
    """

    def __init__(self):
        self.gemini = GeminiProvider()
        self._prompt_template: Optional[str] = None

    @property
    def prompt_template(self) -> str:
        """Lazy-load prompt template."""
        if self._prompt_template is None:
            try:
                self._prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning(f"Prompt not found at {PROMPT_PATH}, using default")
                self._prompt_template = "Analyze this document and extract: summary, tasks, key_points, deadlines, people. Return JSON."
        return self._prompt_template

    def is_supported(self, mime_type: str) -> bool:
        """Check if file type is supported for processing."""
        return self.gemini.is_supported_file_type(mime_type)

    def process_attachment(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Analyze an attachment and extract structured insights.

        Args:
            file_bytes: Raw file content
            mime_type: MIME type of the file
            filename: Original filename

        Returns:
            Dict with keys: summary, document_type, key_points, tasks, deadlines, people
            On error: {"_error": True, "_raw": "error message"}
        """
        if not self.is_supported(mime_type):
            logger.warning(f"Unsupported file type: {mime_type} for {filename}")
            return {
                "_error": True,
                "_raw": f"Unsupported file type: {mime_type}"
            }

        # Build prompt with file metadata
        prompt = self.prompt_template.format(
            filename=filename,
            mime_type=mime_type
        )

        logger.info(f"Processing attachment: {filename} ({mime_type}, {len(file_bytes)} bytes)")

        result = self.gemini.generate_with_file_bytes(
            file_bytes=file_bytes,
            mime_type=mime_type,
            filename=filename,
            prompt=prompt
        )

        if result.get("_error"):
            logger.error(f"Failed to process attachment {filename}: {result.get('_raw')}")
            return result

        # Normalize response structure
        return self._normalize_result(result)

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure all expected fields are present with defaults."""
        return {
            "summary": result.get("summary", ""),
            "document_type": result.get("document_type", "other"),
            "key_points": result.get("key_points", []),
            "tasks": result.get("tasks", []),
            "deadlines": result.get("deadlines", []),
            "people": result.get("people", []),
        }

    def process_multiple(
        self,
        attachments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process multiple attachments and merge insights.

        Args:
            attachments: List of dicts with keys: bytes, mime_type, filename

        Returns:
            Merged insights dict with combined tasks, people, etc.
        """
        merged = {
            "summaries": [],
            "document_types": [],
            "key_points": [],
            "tasks": [],
            "deadlines": [],
            "people": [],
            "processed_count": 0,
            "error_count": 0,
        }

        for att in attachments:
            result = self.process_attachment(
                file_bytes=att["bytes"],
                mime_type=att["mime_type"],
                filename=att["filename"]
            )

            if result.get("_error"):
                merged["error_count"] += 1
                continue

            merged["processed_count"] += 1
            merged["summaries"].append({
                "filename": att["filename"],
                "summary": result["summary"],
                "document_type": result["document_type"]
            })
            merged["document_types"].append(result["document_type"])
            merged["key_points"].extend(result["key_points"])
            merged["tasks"].extend(result["tasks"])
            merged["deadlines"].extend(result["deadlines"])
            merged["people"].extend(result["people"])

        # Deduplicate lists
        merged["key_points"] = list(set(merged["key_points"]))
        merged["tasks"] = list(set(merged["tasks"]))
        merged["deadlines"] = list(set(merged["deadlines"]))
        merged["people"] = list(set(merged["people"]))

        return merged


# Singleton instance for easy import
document_processor = DocumentProcessor()
