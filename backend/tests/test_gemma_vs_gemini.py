"""
LLM Model Comparison Test: Gemma vs Gemini for Email Processing

This script tests the proficiency of Gemma family models vs Gemini family models
when processing emails. It evaluates:
- Summarization quality
- Needs reply classification accuracy
- Task extraction completeness
- Date extraction accuracy
- People extraction
- Decision extraction
- Scheduling intent detection

Usage:
    python tests/test_gemma_vs_gemini.py
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, field

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.llm import LLMConfig, LLMOrchestrator
from app.processors.ai import AIProcessor


# =============================================================================
# Test Email Definitions
# =============================================================================

@dataclass
class TestEmail:
    """A test email with expected extraction results for validation."""
    name: str
    subject: str
    sender: str
    body: str
    description: str
    # Expected extractions (for validation)
    expected_needs_reply: bool
    expected_tasks: List[str] = field(default_factory=list)
    expected_dates: List[str] = field(default_factory=list)
    expected_people: List[str] = field(default_factory=list)
    expected_decisions: List[str] = field(default_factory=list)
    expected_scheduling_intent: bool = False
    expected_scheduling_type: str = "none"


# Test Email 1: Complex Business Email with Tasks, Dates, People, and Decisions
TEST_EMAIL_1 = TestEmail(
    name="Complex Business Planning",
    description="""
    Tests: Tasks, Dates, People, Decisions, Needs Reply
    This email covers multiple extraction types in a realistic business context.
    """,
    subject="Q1 2026 Product Launch - Action Items from Today's Meeting",
    sender="Sarah Chen <sarah.chen@company.com>",
    body="""Hi team,

Thanks for joining today's product launch planning meeting. Here's a summary of what we discussed and the action items we agreed on.

**Key Decisions Made:**
1. We've decided to move forward with the January 28th launch date for the mobile app v2.0
2. The marketing budget has been approved at $75,000 for the Q1 campaign
3. We're partnering with TechReview.com for the exclusive first look

**Action Items:**
- @John: Please finalize the press release draft by Friday, January 24th at 5pm
- @Maria: Can you coordinate with the dev team to ensure all beta bugs are resolved by Tuesday?
- @David: Schedule the all-hands meeting for next Monday at 2pm to discuss launch readiness
- Everyone: Please review the attached launch checklist and add any missing items by EOD tomorrow

**Upcoming Deadlines:**
- Beta testing completion: January 25th
- Final QA sign-off: January 27th
- Public launch: January 28th, 9am PST

Dr. Martinez from Legal mentioned he needs to review our Terms of Service updates before launch. I've already sent him the documents but please follow up if you don't hear back by Wednesday.

Let me know if I missed anything from our discussion.

Best,
Sarah""",
    expected_needs_reply=True,
    expected_tasks=[
        "Finalize press release draft",
        "Coordinate with dev team on beta bugs",
        "Schedule all-hands meeting",
        "Review launch checklist",
        "Follow up with Dr. Martinez on Terms of Service"
    ],
    expected_dates=[
        "January 28th",  # Launch date
        "Friday, January 24th at 5pm",  # Press release deadline
        "Tuesday",  # Bug resolution deadline
        "next Monday at 2pm",  # All-hands meeting
        "EOD tomorrow",  # Checklist review
        "January 25th",  # Beta completion
        "January 27th",  # QA sign-off
        "Wednesday"  # Legal follow-up
    ],
    expected_people=[
        "Sarah Chen",
        "John",
        "Maria",
        "David",
        "Dr. Martinez"
    ],
    expected_decisions=[
        "January 28th launch date approved",
        "$75,000 marketing budget approved",
        "TechReview.com partnership for exclusive first look"
    ],
    expected_scheduling_intent=False,
    expected_scheduling_type="none"
)


# Test Email 2: Scheduling Request with Availability Question
TEST_EMAIL_2 = TestEmail(
    name="Meeting Scheduling Request",
    description="""
    Tests: Scheduling Intent Detection, Needs Reply, People
    This email specifically tests the scheduling intent detection capabilities.
    """,
    subject="Re: Partnership Discussion - Can we find a time to meet?",
    sender="Michael Roberts <m.roberts@partnerco.com>",
    body="""Hi,

I hope this email finds you well. Following up on our conversation at the conference last week.

I'd love to schedule a 45-minute call to discuss the potential partnership between our companies. Our CEO, Jennifer Walsh, and I would like to understand more about your API integration capabilities.

Would you be available sometime next week? I'm flexible on Monday or Wednesday afternoon, or Thursday morning works as well. We're in the Pacific timezone.

If none of those work, please share a few times that would be convenient for you, and I'll make sure we accommodate your schedule.

Looking forward to connecting!

Best regards,
Michael Roberts
VP of Business Development
PartnerCo Inc.""",
    expected_needs_reply=True,
    expected_tasks=[
        "Schedule partnership call"
    ],
    expected_dates=[
        "next week",
        "Monday",
        "Wednesday afternoon",
        "Thursday morning"
    ],
    expected_people=[
        "Michael Roberts",
        "Jennifer Walsh"
    ],
    expected_decisions=[],
    expected_scheduling_intent=True,
    expected_scheduling_type="availability_request"
)


# Test Email 3: Newsletter/Notification (No Reply Needed)
TEST_EMAIL_3 = TestEmail(
    name="Newsletter/Notification",
    description="""
    Tests: Needs Reply (should be False), Summary, minimal extractions
    This email tests the model's ability to recognize non-actionable content.
    """,
    subject="[Monthly Newsletter] January 2026 Product Updates",
    sender="Product Team <noreply@updates.saasproduct.com>",
    body="""Hi there,

Here's what's new in SaaSProduct this month!

**🚀 New Features**

1. **Dark Mode** - Finally! Switch to dark mode in Settings > Appearance
2. **Bulk Export** - Export up to 10,000 records at once
3. **Mobile App Update** - Version 3.2 is now available on iOS and Android

**🐛 Bug Fixes**
- Fixed: Dashboard loading slowly on Firefox
- Fixed: Email notifications not sending for some users
- Fixed: Date picker showing wrong timezone

**📅 Upcoming Webinar**
Join us on February 5th at 11am EST for our monthly product demo. Register at saasproduct.com/webinar

**💡 Pro Tip**
Did you know you can use keyboard shortcuts to navigate faster? Press '?' anywhere in the app to see the full list.

Thanks for being a valued customer!

The SaaSProduct Team

---
You're receiving this because you're subscribed to product updates.
Unsubscribe: https://saasproduct.com/unsubscribe""",
    expected_needs_reply=False,
    expected_tasks=[],  # No action items for the recipient
    expected_dates=[
        "January 2026",
        "February 5th at 11am EST"
    ],
    expected_people=[],
    expected_decisions=[],
    expected_scheduling_intent=False,
    expected_scheduling_type="none"
)


# All test emails
TEST_EMAILS = [TEST_EMAIL_1, TEST_EMAIL_2, TEST_EMAIL_3]


# =============================================================================
# Model Configurations
# =============================================================================

# Gemma models available via Gemini API
GEMMA_MODELS = [
    "gemma-3-12b-it",  # Gemma 3 12B Instruct
]

# Gemini models
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",  # Gemini 2.5 Flash Lite
]


# =============================================================================
# Test Runner
# =============================================================================

@dataclass
class ModelResult:
    """Results from processing an email with a specific model."""
    model_name: str
    email_name: str
    processing_time_ms: float
    result: Dict[str, Any]
    error: str = None


def process_email_with_model(
    email: TestEmail,
    model_name: str,
    prompts_dir: str = "prompts"
) -> ModelResult:
    """Process a single email with a specific model."""
    
    # Create config for this specific model
    config = LLMConfig(
        provider="gemini",
        gemini_model=model_name,
    )
    
    # Create processor with this config
    processor = AIProcessor(prompts_dir=prompts_dir, llm_config=config)
    
    message_data = {
        "subject": email.subject,
        "sender": email.sender,
        "body": email.body
    }
    
    start_time = time.time()
    
    try:
        result = processor.process_message(message_data)
        processing_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return ModelResult(
            model_name=model_name,
            email_name=email.name,
            processing_time_ms=processing_time,
            result=result
        )
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        return ModelResult(
            model_name=model_name,
            email_name=email.name,
            processing_time_ms=processing_time,
            result={},
            error=str(e)
        )


def calculate_extraction_score(result: Dict[str, Any], email: TestEmail) -> Dict[str, float]:
    """Calculate a score for each extraction type based on expected values."""
    scores = {}
    
    # Needs reply accuracy (binary)
    actual_needs_reply = result.get("needs_reply")
    scores["needs_reply"] = 1.0 if actual_needs_reply == email.expected_needs_reply else 0.0
    
    # Tasks score (percentage of expected tasks found)
    extracted_tasks = result.get("extracted_tasks", [])
    if email.expected_tasks:
        task_matches = 0
        for expected in email.expected_tasks:
            # Check if any extracted task contains key words from expected
            expected_words = set(expected.lower().split())
            for task in extracted_tasks:
                task_str = task.get("title", task) if isinstance(task, dict) else str(task)
                if any(word in task_str.lower() for word in expected_words if len(word) > 3):
                    task_matches += 1
                    break
        scores["tasks"] = task_matches / len(email.expected_tasks)
    else:
        # No tasks expected - score based on whether we correctly extracted none/few
        scores["tasks"] = 1.0 if len(extracted_tasks) <= 1 else 0.5
    
    # Dates score
    extracted_dates = result.get("extracted_dates", [])
    if email.expected_dates:
        date_matches = 0
        for expected in email.expected_dates:
            for date in extracted_dates:
                date_str = date.get("date", date) if isinstance(date, dict) else str(date)
                if expected.lower() in date_str.lower():
                    date_matches += 1
                    break
        scores["dates"] = min(1.0, date_matches / len(email.expected_dates))
    else:
        scores["dates"] = 1.0 if len(extracted_dates) == 0 else 0.8
    
    # People score
    extracted_people = result.get("extracted_people", [])
    if email.expected_people:
        people_matches = 0
        for expected in email.expected_people:
            for person in extracted_people:
                person_str = person.get("name", person) if isinstance(person, dict) else str(person)
                if expected.lower() in person_str.lower() or any(
                    word in person_str.lower() for word in expected.lower().split() if len(word) > 2
                ):
                    people_matches += 1
                    break
        scores["people"] = people_matches / len(email.expected_people)
    else:
        scores["people"] = 1.0 if len(extracted_people) == 0 else 0.8
    
    # Decisions score
    extracted_decisions = result.get("extracted_decisions", [])
    if email.expected_decisions:
        decision_matches = 0
        for expected in email.expected_decisions:
            expected_words = set(expected.lower().split())
            for decision in extracted_decisions:
                decision_str = decision.get("decision", decision) if isinstance(decision, dict) else str(decision)
                if sum(1 for word in expected_words if word in decision_str.lower()) >= 2:
                    decision_matches += 1
                    break
        scores["decisions"] = decision_matches / len(email.expected_decisions)
    else:
        scores["decisions"] = 1.0 if len(extracted_decisions) == 0 else 0.8
    
    # Scheduling intent accuracy
    actual_intent = result.get("scheduling_intent", False)
    scores["scheduling_intent"] = 1.0 if actual_intent == email.expected_scheduling_intent else 0.0
    
    if email.expected_scheduling_intent:
        actual_type = result.get("scheduling_intent_type", "none")
        scores["scheduling_type"] = 1.0 if actual_type == email.expected_scheduling_type else 0.5
    else:
        scores["scheduling_type"] = 1.0
    
    # Overall score (weighted average)
    weights = {
        "needs_reply": 2.0,
        "tasks": 2.0,
        "dates": 1.0,
        "people": 1.0,
        "decisions": 1.5,
        "scheduling_intent": 1.5,
        "scheduling_type": 1.0
    }
    
    total_weight = sum(weights.values())
    weighted_sum = sum(scores[k] * weights[k] for k in scores)
    scores["overall"] = weighted_sum / total_weight
    
    return scores


def print_result_comparison(results: List[ModelResult], email: TestEmail):
    """Print a formatted comparison of results for a single email."""
    print("\n" + "=" * 80)
    print(f"📧 EMAIL: {email.name}")
    print(f"   Subject: {email.subject}")
    print(f"   From: {email.sender}")
    print("=" * 80)
    
    for result in results:
        print(f"\n🤖 MODEL: {result.model_name}")
        print(f"   ⏱️  Processing time: {result.processing_time_ms:.0f}ms")
        
        if result.error:
            print(f"   ❌ Error: {result.error}")
            continue
        
        r = result.result
        scores = calculate_extraction_score(r, email)
        
        # Summary
        print(f"\n   📝 Summary:")
        summary = r.get("summary", "N/A")
        print(f"      {summary[:200]}..." if len(summary) > 200 else f"      {summary}")
        
        # Needs Reply
        needs_reply = r.get("needs_reply")
        expected = email.expected_needs_reply
        status = "✅" if needs_reply == expected else "❌"
        print(f"\n   📬 Needs Reply: {needs_reply} (expected: {expected}) {status}")
        
        # Tasks
        tasks = r.get("extracted_tasks", [])
        print(f"\n   ✅ Tasks ({len(tasks)} found, {len(email.expected_tasks)} expected):")
        for task in tasks[:5]:
            if isinstance(task, dict):
                print(f"      - {task.get('title', task)}")
            else:
                print(f"      - {task}")
        if len(tasks) > 5:
            print(f"      ... and {len(tasks) - 5} more")
        
        # Dates
        dates = r.get("extracted_dates", [])
        print(f"\n   📅 Dates ({len(dates)} found):")
        for date in dates[:5]:
            if isinstance(date, dict):
                print(f"      - {date.get('date', date)}")
            else:
                print(f"      - {date}")
        
        # People
        people = r.get("extracted_people", [])
        print(f"\n   👥 People ({len(people)} found):")
        for person in people[:5]:
            if isinstance(person, dict):
                print(f"      - {person.get('name', person)}")
            else:
                print(f"      - {person}")
        
        # Decisions
        decisions = r.get("extracted_decisions", [])
        print(f"\n   🎯 Decisions ({len(decisions)} found):")
        for decision in decisions[:3]:
            if isinstance(decision, dict):
                print(f"      - {decision.get('decision', decision)}")
            else:
                print(f"      - {decision}")
        
        # Scheduling Intent
        sched_intent = r.get("scheduling_intent", False)
        sched_type = r.get("scheduling_intent_type", "none")
        sched_conf = r.get("scheduling_intent_confidence", 0.0)
        expected_intent = email.expected_scheduling_intent
        status = "✅" if sched_intent == expected_intent else "❌"
        print(f"\n   📆 Scheduling Intent: {sched_intent} (type: {sched_type}, confidence: {sched_conf:.2f}) {status}")
        
        # Scores
        print(f"\n   📊 Extraction Scores:")
        print(f"      Needs Reply:     {scores['needs_reply']:.0%}")
        print(f"      Tasks:           {scores['tasks']:.0%}")
        print(f"      Dates:           {scores['dates']:.0%}")
        print(f"      People:          {scores['people']:.0%}")
        print(f"      Decisions:       {scores['decisions']:.0%}")
        print(f"      Scheduling:      {scores['scheduling_intent']:.0%}")
        print(f"      ──────────────────────")
        print(f"      OVERALL:         {scores['overall']:.0%}")


def save_results_to_json(
    all_results: Dict[str, List[ModelResult]], 
    test_emails: List[TestEmail],
    output_path: str = None
) -> str:
    """
    Save all raw results to a JSON file for later analysis.
    
    Returns the path to the saved file.
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = f"tests/results_gemma_vs_gemini_{timestamp}.json"
    
    # Build the output structure
    output = {
        "test_run": {
            "timestamp": datetime.now().isoformat(),
            "models_tested": list(all_results.keys()),
            "emails_tested": len(test_emails)
        },
        "test_emails": [],
        "results_by_model": {},
        "results_by_email": {},
        "summary": {}
    }
    
    # Add test email details
    for email in test_emails:
        output["test_emails"].append({
            "name": email.name,
            "subject": email.subject,
            "sender": email.sender,
            "body": email.body,
            "description": email.description.strip(),
            "expected": {
                "needs_reply": email.expected_needs_reply,
                "tasks": email.expected_tasks,
                "dates": email.expected_dates,
                "people": email.expected_people,
                "decisions": email.expected_decisions,
                "scheduling_intent": email.expected_scheduling_intent,
                "scheduling_type": email.expected_scheduling_type
            }
        })
    
    # Add results organized by model
    for model_name, results in all_results.items():
        output["results_by_model"][model_name] = []
        for result, email in zip(results, test_emails):
            result_data = {
                "email_name": email.name,
                "processing_time_ms": result.processing_time_ms,
                "error": result.error,
                "raw_output": result.result,
                "scores": calculate_extraction_score(result.result, email) if not result.error else None
            }
            output["results_by_model"][model_name].append(result_data)
    
    # Add results organized by email (for easy side-by-side comparison)
    for i, email in enumerate(test_emails):
        output["results_by_email"][email.name] = {}
        for model_name, results in all_results.items():
            result = results[i]
            output["results_by_email"][email.name][model_name] = {
                "processing_time_ms": result.processing_time_ms,
                "error": result.error,
                "raw_output": result.result,
                "scores": calculate_extraction_score(result.result, email) if not result.error else None
            }
    
    # Add summary scores
    model_scores = {}
    model_times = {}
    for model_name, results in all_results.items():
        scores = []
        times = []
        for result, email in zip(results, test_emails):
            if not result.error:
                score = calculate_extraction_score(result.result, email)
                scores.append(score["overall"])
                times.append(result.processing_time_ms)
        if scores:
            model_scores[model_name] = sum(scores) / len(scores)
            model_times[model_name] = sum(times) / len(times)
    
    output["summary"] = {
        "model_scores": model_scores,
        "model_avg_times_ms": model_times,
        "ranking": sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
    }
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_path}")
    return output_path


def print_final_summary(all_results: Dict[str, List[ModelResult]], test_emails: List[TestEmail]):
    print("\n" + "=" * 80)
    print("📊 FINAL COMPARISON SUMMARY")
    print("=" * 80)
    
    model_scores = {}
    model_times = {}
    
    for model_name, results in all_results.items():
        scores = []
        times = []
        
        for result, email in zip(results, test_emails):
            if not result.error:
                score = calculate_extraction_score(result.result, email)
                scores.append(score["overall"])
                times.append(result.processing_time_ms)
        
        if scores:
            model_scores[model_name] = sum(scores) / len(scores)
            model_times[model_name] = sum(times) / len(times)
    
    # Sort by score
    sorted_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
    
    print("\n🏆 Model Rankings (by overall extraction accuracy):\n")
    for rank, (model, score) in enumerate(sorted_models, 1):
        avg_time = model_times.get(model, 0)
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
        print(f"   {medal} {rank}. {model}")
        print(f"      Score: {score:.1%}  |  Avg Time: {avg_time:.0f}ms")
    
    print("\n" + "-" * 80)
    print("📝 Notes:")
    print("   - Scores are based on extraction accuracy compared to expected values")
    print("   - Higher is better for accuracy, lower is better for processing time")
    print("   - Results may vary based on prompt engineering and model versions")
    print("=" * 80)


def run_comparison_test(
    models: List[str] = None,
    emails: List[TestEmail] = None,
    prompts_dir: str = "prompts",
    output_path: str = None
):
    """Run the full comparison test across all models and emails."""
    
    if models is None:
        models = GEMMA_MODELS + GEMINI_MODELS
    
    if emails is None:
        emails = TEST_EMAILS
    
    print("=" * 80)
    print("🧪 LLM MODEL COMPARISON TEST: Gemma vs Gemini for Email Processing")
    print("=" * 80)
    print(f"\n📋 Testing {len(models)} models with {len(emails)} test emails")
    print(f"\n🤖 Models to test:")
    for model in models:
        family = "Gemma" if "gemma" in model.lower() else "Gemini"
        print(f"   - {model} ({family} family)")
    
    print(f"\n📧 Test emails:")
    for email in emails:
        print(f"   - {email.name}: {email.description.strip()[:60]}...")
    
    # Run tests
    all_results: Dict[str, List[ModelResult]] = {}
    
    for model in models:
        print(f"\n\n{'='*80}")
        print(f"⏳ Testing model: {model}")
        print("=" * 80)
        
        model_results = []
        
        for email in emails:
            print(f"\n   Processing: {email.name}...", end=" ", flush=True)
            result = process_email_with_model(email, model, prompts_dir)
            model_results.append(result)
            
            if result.error:
                print(f"❌ Error: {result.error[:50]}")
            else:
                print(f"✅ ({result.processing_time_ms:.0f}ms)")
        
        all_results[model] = model_results
    
    # Print detailed comparisons for each email
    for i, email in enumerate(emails):
        email_results = [all_results[model][i] for model in models]
        print_result_comparison(email_results, email)
    
    # Print final summary
    print_final_summary(all_results, emails)
    
    # Save results to JSON file
    save_results_to_json(all_results, emails, output_path)
    
    return all_results


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare Gemma vs Gemini for email processing")
    parser.add_argument(
        "--models", 
        nargs="+", 
        default=None,
        help="Specific models to test (default: all Gemma and Gemini models)"
    )
    parser.add_argument(
        "--prompts-dir",
        default="prompts",
        help="Path to prompts directory"
    )
    parser.add_argument(
        "--email",
        type=int,
        default=None,
        help="Test only a specific email (1, 2, or 3)"
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output path for JSON results file (default: tests/results_gemma_vs_gemini_<timestamp>.json)"
    )
    
    args = parser.parse_args()
    
    # Select emails
    emails = TEST_EMAILS
    if args.email:
        if 1 <= args.email <= 3:
            emails = [TEST_EMAILS[args.email - 1]]
        else:
            print(f"Invalid email number: {args.email}. Must be 1, 2, or 3.")
            sys.exit(1)
    
    # Run comparison
    results = run_comparison_test(
        models=args.models,
        emails=emails,
        prompts_dir=args.prompts_dir,
        output_path=args.output
    )
    
    print("\n✅ Test completed!")

