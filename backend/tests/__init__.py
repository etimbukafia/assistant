"""
Test Suite for AI Assistant.

Directory Structure:
    tests/
    ├── conftest.py      # Shared fixtures (db, mocks, factories)
    ├── unit/            # Isolated unit tests
    ├── integration/     # Component interaction tests  
    ├── api/             # FastAPI endpoint tests
    ├── fixtures/        # Reusable test data
    └── llm/             # LLM-specific tests (legacy)

Usage:
    pytest                          # Run all tests
    pytest -m unit                  # Run only unit tests
    pytest -m integration           # Run only integration tests
    pytest -m "not slow"            # Skip slow tests
    pytest --cov=app --cov-report=html  # With coverage
"""
