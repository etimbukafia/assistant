"""
Local test script to debug email sync and chat issues.
Run from backend directory: python test_local.py
"""
import sys
sys.path.insert(0, 'src')

import asyncio
import json

def test_routes():
    """Test 1: Check if routes are correctly configured"""
    print("\n" + "="*50)
    print("TEST 1: Registered Routes")
    print("="*50)

    from main import app

    # Find routes containing 'sync' or 'chat'
    for route in app.routes:
        if hasattr(route, 'path'):
            path = route.path
            if 'sync' in path or 'chat' in path or 'messages' in path:
                methods = getattr(route, 'methods', {'GET'})
                print(f"  {list(methods)} {path}")


def test_json_parsing():
    """Test 2: Check JSON parsing with malformed unicode"""
    print("\n" + "="*50)
    print("TEST 2: JSON Parsing with Unicode Escapes")
    print("="*50)

    import re

    test_cases = [
        r'{"text": "C:\users\test"}',
        r'{"text": "\u"}',
        r'"\u"',
        r'{"response": "Hello, how can I help?"}',
        r'{"tool_call": {"name": "search", "arguments": {}}}',
    ]

    def fix_unicode_escapes(s: str) -> str:
        return re.sub(r'\\u(?![0-9a-fA-F]{4})', r'\\\\u', s)

    for tc in test_cases:
        print(f"\n  Input: {tc[:50]}...")
        fixed = fix_unicode_escapes(tc)
        print(f"  Fixed: {fixed[:50]}...")
        try:
            result = json.loads(fixed)
            print(f"  Result: OK -> {result}")
        except json.JSONDecodeError as e:
            print(f"  Result: FAILED -> {e}")


def test_chat_orchestrator():
    """Test 3: Test chat orchestrator initialization"""
    print("\n" + "="*50)
    print("TEST 3: Chat Orchestrator")
    print("="*50)

    try:
        from app.chat.orchestrator import ChatOrchestrator
        print("  ChatOrchestrator imported OK")

        # Check if prompts exist
        from pathlib import Path
        prompts_dir = Path(__file__).parent / "src" / "prompts"
        if not prompts_dir.exists():
            prompts_dir = Path(__file__).parent / "prompts"

        print(f"  Prompts directory: {prompts_dir}")
        print(f"  Exists: {prompts_dir.exists()}")

        if prompts_dir.exists():
            for f in prompts_dir.glob("*.md"):
                print(f"    - {f.name}")

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_llm_provider():
    """Test 4: Test LLM provider JSON parsing"""
    print("\n" + "="*50)
    print("TEST 4: LLM Provider JSON Parsing")
    print("="*50)

    try:
        from core.llm.providers.base import BaseLLMProvider
        from core.llm.config import LLMConfig

        # Create a mock provider to test _parse_json
        class TestProvider(BaseLLMProvider):
            def initialize(self):
                pass
            def _raw_generate(self, prompt, system_prompt=None):
                return "{}"
            def cleanup(self):
                pass

        config = LLMConfig.from_env()
        provider = TestProvider(config)

        # Test cases that might fail
        test_inputs = [
            '{"response": "Hello"}',
            'Here is my response:\n```json\n{"response": "test"}\n```',
            r'{"path": "C:\users\test"}',  # Malformed unicode escape
            '{"text": "\\u0048ello"}',  # Valid unicode escape
        ]

        for inp in test_inputs:
            print(f"\n  Input: {inp[:40]}...")
            try:
                result = provider._parse_json(inp)
                if "_error" in result:
                    print(f"  Result: PARSE ERROR -> {result.get('_raw', '')[:30]}...")
                else:
                    print(f"  Result: OK -> {result}")
            except Exception as e:
                print(f"  Result: EXCEPTION -> {e}")

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()


async def test_chat_service():
    """Test 5: Test chat service with mock session"""
    print("\n" + "="*50)
    print("TEST 5: Chat Service (requires DB)")
    print("="*50)

    try:
        from app.infra.database import SessionLocal
        from app.chat.service import ChatService
        from app.data.models import ChatSession, UserSettings

        db = SessionLocal()

        # Get a test user
        user_settings = db.query(UserSettings).first()
        if not user_settings:
            print("  No users found in database")
            db.close()
            return

        user_id = user_settings.user_id
        print(f"  Testing with user: {user_id[:8]}...")

        service = ChatService(db, user_id)

        # Create a test session
        session = service.create_session("reflection")
        print(f"  Created session: {session.id}")

        # Try to send a simple message
        print("  Sending test message...")
        try:
            result = await service.send_message(session.id, "Hello, this is a test")
            print(f"  Result status: {result.status}")
            if result.error:
                print(f"  Error: {result.error}")
            if result.response:
                print(f"  Response: {result.response[:100]}...")
        except Exception as e:
            print(f"  Message failed: {e}")
            import traceback
            traceback.print_exc()

        # Cleanup
        service.delete_session(session.id)
        print("  Cleaned up test session")

        db.close()

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()


def test_initial_sync_endpoint():
    """Test 6: Check initial sync endpoint exists"""
    print("\n" + "="*50)
    print("TEST 6: Initial Sync Endpoint")
    print("="*50)

    try:
        from app.routes.v1.messages import router

        print(f"  Router prefix: {router.prefix}")

        for route in router.routes:
            if hasattr(route, 'path') and 'sync' in route.path:
                methods = getattr(route, 'methods', {'GET'})
                print(f"  {list(methods)} {router.prefix}{route.path}")

    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "#"*50)
    print("# LOCAL DEBUG TESTS")
    print("#"*50)

    test_routes()
    test_json_parsing()
    test_chat_orchestrator()
    test_llm_provider()
    test_initial_sync_endpoint()

    # Async test
    print("\n" + "="*50)
    print("Running async tests...")
    print("="*50)
    asyncio.run(test_chat_service())

    print("\n" + "#"*50)
    print("# TESTS COMPLETE")
    print("#"*50 + "\n")
