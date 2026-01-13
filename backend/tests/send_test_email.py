"""
Test Email Sender using Resend API

Send test emails to your inbox to test the AI Assistant app features.

Usage:
    python tests/send_test_email.py                    # Interactive mode
    python tests/send_test_email.py --template task    # Send specific template
    python tests/send_test_email.py --list             # List available templates

Environment (from tests/.env):
    RESEND_API_KEY: Your Resend API key
    TEST_EMAIL_TO: Target email address (your Gmail)
    TEST_EMAIL_FROM: Sender email (must be verified domain in Resend, or use onboarding@resend.dev)
"""
import os
import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import resend

from test_email_templates import TEMPLATES, TEMPLATE_CATEGORIES, get_all_template_names

# Load environment from tests/.env (not root .env)
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    print(f"⚠️  No .env file found at {ENV_FILE}")
    print(f"   Create one with RESEND_API_KEY and TEST_EMAIL_TO")

# Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
TEST_EMAIL_TO = os.getenv("TEST_EMAIL_TO")  # Your Gmail address
TEST_EMAIL_FROM = os.getenv("TEST_EMAIL_FROM", "onboarding@resend.dev")  # Default Resend test sender


def send_email(template_name: str, to_email: str = None, from_email: str = None):
    """Send a test email using the specified template."""
    if template_name not in TEMPLATES:
        print(f"❌ Unknown template: {template_name}")
        print(f"Available templates: {', '.join(TEMPLATES.keys())}")
        return None
    
    template = TEMPLATES[template_name]
    to_addr = to_email or TEST_EMAIL_TO
    from_addr = from_email or TEST_EMAIL_FROM
    
    if not to_addr:
        print("❌ No recipient email. Set TEST_EMAIL_TO env var or pass --to")
        return None
    
    if not RESEND_API_KEY:
        print("❌ No API key. Set RESEND_API_KEY environment variable")
        return None
    
    resend.api_key = RESEND_API_KEY
    
    # Add timestamp to make each email unique
    timestamp = datetime.now().strftime("%H:%M:%S")
    subject = f"[TEST {timestamp}] {template['subject']}"
    
    try:
        params = {
            "from": from_addr,
            "to": [to_addr],
            "subject": subject,
            "text": template["body"],
        }
        
        email = resend.Emails.send(params)
        print(f"✅ Email sent successfully!")
        print(f"   Template: {template_name}")
        print(f"   To: {to_addr}")
        print(f"   Subject: {subject}")
        print(f"   ID: {email.get('id', 'unknown')}")
        return email
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return None


def send_batch(template_names: list, delay_seconds: int = 2):
    """Send multiple test emails with a delay between each."""
    import time
    
    print(f"Sending {len(template_names)} emails with {delay_seconds}s delay...\n")
    
    for i, name in enumerate(template_names, 1):
        print(f"[{i}/{len(template_names)}] Sending '{name}'...")
        send_email(name)
        if i < len(template_names):
            time.sleep(delay_seconds)
    
    print(f"\n✅ Batch complete! Sent {len(template_names)} emails.")


def interactive_mode():
    """Interactive menu for sending test emails."""
    print("\n" + "="*50)
    print("  📧 Test Email Sender (Resend)")
    print("="*50)
    
    if not TEST_EMAIL_TO:
        print("\n⚠️  No TEST_EMAIL_TO set. Please enter recipient:")
        to_email = input("To email: ").strip()
    else:
        to_email = TEST_EMAIL_TO
        print(f"\nSending to: {to_email}")
    
    print("\nAvailable templates:\n")
    
    all_templates = []
    for category, templates in TEMPLATE_CATEGORIES.items():
        print(f"  {category}:")
        for t in templates:
            idx = len(all_templates)
            all_templates.append(t)
            print(f"    [{idx}] {t}")
        print()
    
    print("  [a] Send ALL templates")
    print("  [q] Quit\n")
    
    choice = input("Select template (number, name, or 'a' for all): ").strip().lower()
    
    if choice == 'q':
        print("Bye!")
        return
    
    if choice == 'a':
        confirm = input(f"Send ALL {len(all_templates)} templates? (y/n): ").strip().lower()
        if confirm == 'y':
            send_batch(all_templates)
        return
    
    # Try as number
    try:
        idx = int(choice)
        if 0 <= idx < len(all_templates):
            send_email(all_templates[idx], to_email)
        else:
            print(f"❌ Invalid index. Choose 0-{len(all_templates)-1}")
    except ValueError:
        # Try as template name
        if choice in TEMPLATES:
            send_email(choice, to_email)
        else:
            print(f"❌ Unknown template: {choice}")


def list_templates():
    """List all available templates with descriptions."""
    print("\n📧 Available Email Templates:\n")
    
    for name, template in TEMPLATES.items():
        print(f"  • {name}")
        print(f"    Subject: {template['subject']}")
        # Show first line of body
        first_line = template['body'].strip().split('\n')[0][:60]
        print(f"    Preview: {first_line}...")
        print()


def main():
    parser = argparse.ArgumentParser(description="Send test emails using Resend API")
    parser.add_argument("--template", "-t", help="Template name to send")
    parser.add_argument("--to", help="Recipient email (overrides TEST_EMAIL_TO)")
    parser.add_argument("--from", dest="from_email", help="Sender email (overrides TEST_EMAIL_FROM)")
    parser.add_argument("--list", "-l", action="store_true", help="List available templates")
    parser.add_argument("--all", "-a", action="store_true", help="Send all templates")
    parser.add_argument("--batch", "-b", nargs="+", help="Send multiple templates")
    
    args = parser.parse_args()
    
    if args.list:
        list_templates()
        return
    
    if args.all:
        send_batch(list(TEMPLATES.keys()))
        return
    
    if args.batch:
        send_batch(args.batch)
        return
    
    if args.template:
        send_email(args.template, args.to, args.from_email)
        return
    
    # Default: interactive mode
    interactive_mode()


if __name__ == "__main__":
    main()
