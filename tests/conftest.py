"""Pytest configuration and fixtures for MCP Server for macOS reminders tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_name() -> str:
    """Provide a sample name for testing."""
    return "Test User"


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory for testing.

    Args:
        tmp_path: Pytest's temporary path fixture

    Returns:
        Path to the temporary project directory
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    sample_file = src_dir / "main.py"
    sample_file.write_text(
        '"""Sample module."""\n\ndef hello() -> str:\n    return "Hello"\n'
    )

    return tmp_path
