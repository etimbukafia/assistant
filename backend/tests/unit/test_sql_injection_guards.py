"""
Guardrail tests to prevent SQL string interpolation regressions.
"""

from __future__ import annotations

from pathlib import Path
import re


SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _python_files(root: Path):
    for path in root.rglob("*.py"):
        # Ignore test files and cache artifacts.
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        yield path


def test_no_interpolated_sqlalchemy_text_calls():
    """
    Block `text(f"...")` style SQL construction in app source.
    """
    pattern = re.compile(r"\btext\(\s*f[\"']")
    offenders: list[str] = []

    for path in _python_files(SRC_ROOT):
        content = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(content):
            offenders.append(str(path.relative_to(SRC_ROOT.parent)))

    assert not offenders, (
        "Unsafe SQL detected. Use bound parameters with text(..., params) instead.\n"
        f"Offending files: {', '.join(sorted(offenders))}"
    )


def test_no_execute_f_string_sql_calls():
    """
    Block `execute(f"...")` style SQL execution in app source.
    """
    pattern = re.compile(r"\bexecute\(\s*f[\"']")
    offenders: list[str] = []

    for path in _python_files(SRC_ROOT):
        content = path.read_text(encoding="utf-8", errors="ignore")
        if pattern.search(content):
            offenders.append(str(path.relative_to(SRC_ROOT.parent)))

    assert not offenders, (
        "Unsafe execute(...) f-string SQL detected. Use parameterized statements.\n"
        f"Offending files: {', '.join(sorted(offenders))}"
    )
