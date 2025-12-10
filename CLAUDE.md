# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An MCP Server for macOS reminders

This is a FastMCP server that exposes tools through the Model Context Protocol (MCP), enabling AI assistants to interact with your service.

## Build and Development Commands

```bash
# Install dependencies
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run the server
uv run jons-mcp-reminders

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_example.py

# Run a single test
uv run pytest tests/test_example.py::test_hello_world

# Type check
uv run mypy src/jons_mcp_reminders

# Format code
uv run black src tests

# Lint code
uv run ruff check src tests
```

## Architecture

### Package Structure

```
src/jons_mcp_reminders/
├── __init__.py          # Package exports
├── constants.py         # Configuration constants
├── exceptions.py        # Custom exception classes
├── utils.py             # Utility functions (pagination, file URIs)
├── server.py            # FastMCP server setup, main()
└── tools/
    ├── __init__.py      # Re-exports all tools
    └── example.py       # Example tool implementation
```

### Core Components

- **`server.py`**: FastMCP server setup with tool registration and main entry point

- **`tools/`**: MCP tool functions. Each tool should be an async function with docstrings (used as tool descriptions)

### Key Patterns

- **File URI handling**: `ensure_file_uri()` in `utils.py` converts paths to `file://` URIs

- **Pagination**: `apply_pagination()` provides consistent limit/offset handling for list-returning tools

- **Tool docstrings**: FastMCP uses function docstrings as tool descriptions, so keep them clear and concise

### Adding New Tools

1. Create a new file in `tools/` or add to existing file
2. Write an async function with type hints and a docstring
3. Export from `tools/__init__.py`
4. Register in `server.py` with `mcp.tool(your_function)`

Example:
```python
async def my_tool(param: str) -> str:
    """Brief description of what this tool does.

    Args:
        param: Description of the parameter.

    Returns:
        Description of what's returned.
    """
    return f"Result: {param}"
```
