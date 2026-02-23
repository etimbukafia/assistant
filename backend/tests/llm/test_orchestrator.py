"""
Test script for LLM Orchestrator.
Compares Qwen (local) vs Gemini (API) outputs.

Uses true batching: groups all emails per test type into single API call.
- 5 emails × 7 tests = 7 API calls (not 35)

Usage:
    python -m tests.llm.test_orchestrator [--provider huggingface|gemini|both]
"""

import argparse
import json
import time
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import LLMOrchestrator, LLMConfig
from core.llm.schemas import (
    SummaryOutput,
    ClassifyReplyOutput,
    TasksOutput,
    DatesOutput,
    PeopleOutput,
    DecisionsOutput,
    DraftOutput,
)
from tests.llm.test_emails import get_all_emails


# =============================================================================
# Prompt builders - return prompt string for an email
# =============================================================================

def build_summarize_prompt(email: dict) -> str:
    return f"""Summarize the following email in 2-3 sentences. Focus on the main point and any action required.

From: {email['sender']}
Subject: {email['subject']}

{email['body']}

Respond with JSON containing a "summary" field."""


def build_classify_prompt(email: dict) -> str:
    return f"""Analyze this email and determine if it requires a reply from the recipient.

From: {email['sender']}
Subject: {email['subject']}

{email['body']}

Set needs_reply to true if: a question is asked, a response is requested, action is needed, or it's a direct message expecting acknowledgment.
Set needs_reply to false if: it's a newsletter, automated notification, FYI only, or no response expected.

Respond with JSON containing a "needs_reply" boolean field."""


def build_extract_tasks_prompt(email: dict) -> str:
    return f"""What actions or tasks is the recipient being asked to do in this email?

From: {email['sender']}
Subject: {email['subject']}

{email['body']}

Extract each action item. Examples of tasks: schedule a meeting, review a document, send information, make a decision, confirm attendance.

Respond with JSON: {{"tasks": ["first task", "second task"]}} or {{"tasks": []}} if none."""


def build_extract_dates_prompt(email: dict) -> str:
    return f"""What dates or times are written in this email? Only extract dates that appear in the text.

From: {email['sender']}
Subject: {email['subject']}

{email['body']}

Copy the exact date/time phrases from the email. Do NOT generate or invent dates.

Respond with JSON: {{"dates": ["date from email"]}} or {{"dates": []}} if none mentioned."""


def build_extract_people_prompt(email: dict) -> str:
    return f"""Read this email and extract the names of all people mentioned.

From: {email['sender']}
Subject: {email['subject']}

{email['body']}

Include the sender and anyone else referenced by name. If no names are found, return an empty array.

Respond with JSON containing a "people" array field."""


def build_extract_decisions_prompt(email: dict) -> str:
    return f"""Read this email and extract any decisions, conclusions, or determinations that were made.

From: {email['sender']}
Subject: {email['subject']}

{email['body']}

List specific decisions or conclusions stated in the email. If no decisions are mentioned, return an empty array.

Respond with JSON containing a "decisions" array field."""


def build_draft_reply_prompt(email: dict) -> str:
    return f"""Write a professional reply to this email. Be concise and address the main points.

From: {email['sender']}
Subject: {email['subject']}

{email['body']}

Write only the reply body - no greeting line, no signature, no subject line. Use a professional but friendly tone.

Respond with JSON containing a "draft" field with your reply text."""


# Test definitions: (name, prompt_builder, schema)
TEST_DEFINITIONS = [
    ("summarize", build_summarize_prompt, SummaryOutput),
    ("classify_needs_reply", build_classify_prompt, ClassifyReplyOutput),
    ("extract_tasks", build_extract_tasks_prompt, TasksOutput),
    ("extract_dates", build_extract_dates_prompt, DatesOutput),
    ("extract_people", build_extract_people_prompt, PeopleOutput),
    ("extract_decisions", build_extract_decisions_prompt, DecisionsOutput),
    ("draft_reply", build_draft_reply_prompt, DraftOutput),
]


def run_tests_for_provider(provider: str, emails: list, use_outlines: bool = True) -> dict:
    """
    Run all tests for a specific provider using true batching.
    Groups all emails per test type into single API call.
    """
    print(f"\n{'='*60}")
    print(f"TESTING PROVIDER: {provider.upper()}")
    if provider == "huggingface":
        print(f"Mode: {'Outlines (constrained)' if use_outlines else 'Legacy (JSON repair)'}")
    print(f"{'='*60}")

    config = LLMConfig(provider=provider, use_outlines=use_outlines)

    # Initialize results structure
    results = {
        "provider": provider,
        "emails": {}
    }
    for email in emails:
        results["emails"][email["id"]] = {
            "subject": email["subject"],
            "sender": email["sender"],
            "tests": {}
        }

    with LLMOrchestrator(config=config) as orchestrator:
        # Run each test type as a batch across all emails
        for test_name, prompt_builder, schema in TEST_DEFINITIONS:
            print(f"\n--- Running {test_name} (batch of {len(emails)}) ---", flush=True)

            # Build prompts for all emails
            prompts = [prompt_builder(email) for email in emails]

            start = time.time()
            try:
                # Single batch call for all emails with schema
                batch_results = orchestrator.generate_batch(prompts, schema=schema)
                elapsed = time.time() - start
                print(f"  Completed in {elapsed:.2f}s ({elapsed/len(emails):.2f}s per email)")

                # Map results back to emails
                for i, email in enumerate(emails):
                    email_id = email["id"]
                    results["emails"][email_id]["tests"][test_name] = {
                        "task": test_name,
                        "result": batch_results[i] if i < len(batch_results) else {"_error": True},
                        "time_seconds": round(elapsed / len(emails), 2)  # Average time per email
                    }

            except Exception as e:
                elapsed = time.time() - start
                print(f"  ERROR: {e}")
                # Mark all as failed
                for email in emails:
                    results["emails"][email["id"]]["tests"][test_name] = {
                        "task": test_name,
                        "error": str(e),
                        "time_seconds": round(elapsed, 2)
                    }

    return results


def print_comparison(hf_results: dict, gemini_results: dict):
    """Print side-by-side comparison of results."""
    print("\n" + "="*80)
    print("COMPARISON: HuggingFace (Qwen) vs Gemini")
    print("="*80)

    for email_id in hf_results["emails"]:
        hf_email = hf_results["emails"][email_id]
        gemini_email = gemini_results["emails"].get(email_id, {})

        print(f"\n{'─'*80}")
        print(f"EMAIL: {email_id}")
        print(f"Subject: {hf_email['subject']}")
        print(f"{'─'*80}")

        for test_name in hf_email["tests"]:
            hf_test = hf_email["tests"][test_name]
            gemini_test = gemini_email.get("tests", {}).get(test_name, {})

            print(f"\n[{test_name.upper()}]")
            print(f"  HuggingFace ({hf_test.get('time_seconds', '?')}s):")
            hf_result = hf_test.get("result", hf_test.get("error", "N/A"))
            print(f"    {json.dumps(hf_result, indent=4, ensure_ascii=False)[:500]}")

            print(f"  Gemini ({gemini_test.get('time_seconds', '?')}s):")
            gemini_result = gemini_test.get("result", gemini_test.get("error", "N/A"))
            print(f"    {json.dumps(gemini_result, indent=4, ensure_ascii=False)[:500]}")


def print_single_results(results: dict):
    """Print results for a single provider."""
    print("\n" + "="*80)
    print(f"RESULTS: {results['provider'].upper()}")
    print("="*80)

    for email_id, email_data in results["emails"].items():
        print(f"\n{'─'*80}")
        print(f"EMAIL: {email_id}")
        print(f"Subject: {email_data['subject']}")
        print(f"{'─'*80}")

        for test_name, test_data in email_data["tests"].items():
            print(f"\n[{test_name.upper()}] ({test_data.get('time_seconds', '?')}s)")
            result = test_data.get("result", test_data.get("error", "N/A"))
            print(json.dumps(result, indent=2, ensure_ascii=False))


def save_results(results: dict, filename: str):
    """Save results to JSON file."""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / filename
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Test LLM Orchestrator")
    parser.add_argument(
        "--provider",
        choices=["huggingface", "gemini", "both"],
        default="both",
        help="Which provider to test"
    )
    parser.add_argument(
        "--no-outlines",
        action="store_true",
        help="Disable Outlines (use legacy JSON repair for HuggingFace)"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results to JSON files"
    )
    args = parser.parse_args()

    use_outlines = not args.no_outlines
    print(f"Outlines: {'enabled' if use_outlines else 'disabled (legacy mode)'}")

    emails = get_all_emails()
    print(f"Testing with {len(emails)} emails")

    hf_results = None
    gemini_results = None

    if args.provider in ("huggingface", "both"):
        hf_results = run_tests_for_provider("huggingface", emails, use_outlines=use_outlines)
        if args.save:
            suffix = "_outlines" if use_outlines else "_legacy"
            save_results(hf_results, f"results_huggingface{suffix}.json")

    if args.provider in ("gemini", "both"):
        gemini_results = run_tests_for_provider("gemini", emails, use_outlines=use_outlines)
        if args.save:
            save_results(gemini_results, "results_gemini.json")

    # Print results
    if args.provider == "both" and hf_results and gemini_results:
        print_comparison(hf_results, gemini_results)
    elif hf_results:
        print_single_results(hf_results)
    elif gemini_results:
        print_single_results(gemini_results)

    print("\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
