"""
Import test suite for the backend codebase.

This module discovers and imports all Python modules in src/app and src/core
to catch import errors early. It also verifies that all prompt files are readable.

Usage:
    python -m pytest tests/test_imports.py -v
"""
import importlib
import sys
from pathlib import Path

import pytest


# Get the backend root and src directory
BACKEND_ROOT = Path(__file__).parent.parent
SRC_DIR = BACKEND_ROOT / "src"
PROMPTS_DIR = BACKEND_ROOT / "prompts"


def discover_python_modules() -> list[tuple[str, Path]]:
    """
    Discover all Python modules in src/app and src/core.
    
    Returns:
        List of tuples (module_path, file_path)
    """
    modules = []
    
    for package_dir in ["app", "core"]:
        package_path = SRC_DIR / package_dir
        if not package_path.exists():
            continue
            
        for py_file in package_path.rglob("*.py"):
            # Skip __pycache__ directories
            if "__pycache__" in str(py_file):
                continue
            
            # Convert file path to module path
            # e.g., src/app/routes/v1/auth.py -> app.routes.v1.auth
            relative = py_file.relative_to(SRC_DIR)
            parts = list(relative.parts)
            
            # Remove .py extension from last part
            parts[-1] = parts[-1][:-3]
            
            # Skip __init__ from module name (but include the package)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            
            if parts:  # Skip if empty (would be just __init__.py at root)
                module_path = ".".join(parts)
                modules.append((module_path, py_file))
    
    return modules


def discover_prompt_files() -> list[Path]:
    """
    Discover all prompt markdown files.
    
    Returns:
        List of prompt file paths
    """
    if not PROMPTS_DIR.exists():
        return []
    
    return list(PROMPTS_DIR.glob("*.md"))


# =============================================================================
# Test: Python Module Imports
# =============================================================================

# Ensure src is in path for imports
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


PYTHON_MODULES = discover_python_modules()


@pytest.mark.parametrize("module_path,file_path", PYTHON_MODULES, ids=[m[0] for m in PYTHON_MODULES])
def test_module_import(module_path: str, file_path: Path):
    """Test that a Python module can be imported without errors."""
    try:
        importlib.import_module(module_path)
    except ImportError as e:
        pytest.fail(f"Failed to import {module_path} ({file_path}): {e}")
    except Exception as e:
        pytest.fail(f"Error importing {module_path} ({file_path}): {type(e).__name__}: {e}")


# =============================================================================
# Test: Prompt Files
# =============================================================================

PROMPT_FILES = discover_prompt_files()


@pytest.mark.parametrize("prompt_file", PROMPT_FILES, ids=[f.name for f in PROMPT_FILES])
def test_prompt_file_readable(prompt_file: Path):
    """Test that a prompt file exists and is readable as UTF-8."""
    assert prompt_file.exists(), f"Prompt file does not exist: {prompt_file}"
    
    try:
        content = prompt_file.read_text(encoding="utf-8")
        assert len(content) > 0, f"Prompt file is empty: {prompt_file}"
    except UnicodeDecodeError as e:
        pytest.fail(f"Failed to decode {prompt_file} as UTF-8: {e}")
    except Exception as e:
        pytest.fail(f"Failed to read {prompt_file}: {type(e).__name__}: {e}")


# =============================================================================
# Summary Test (runs last)
# =============================================================================

def test_import_summary():
    """Summary of discovered modules and prompts."""
    print(f"\n{'=' * 60}")
    print(f"Import Test Summary")
    print(f"{'=' * 60}")
    print(f"Python modules discovered: {len(PYTHON_MODULES)}")
    print(f"Prompt files discovered: {len(PROMPT_FILES)}")
    print(f"{'=' * 60}")
