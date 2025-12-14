# MCP Server for macOS Reminders

An MCP server for managing macOS Reminders via EventKit.

This FastMCP server provides native access to the macOS Reminders app through the Model Context Protocol (MCP), enabling AI assistants to create, read, update, and delete reminders and lists.

## Requirements

- macOS 14.0+ (Sonoma or later)
- Python 3.10+

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd jons-mcp-reminders

# Install with uv
uv pip install -e .
```

## Permissions

On first run, the server will request access to Reminders. You must grant this permission in:

**System Settings > Privacy & Security > Reminders**

The Terminal app (or your Python environment) must have permission to access Reminders.

## Running the Server

```bash
uv run jons-mcp-reminders
```

## Adding to Claude Code

```bash
# Register the MCP server with Claude Code
claude mcp add jons-mcp-reminders -- uv run --project /path/to/jons-mcp-reminders jons-mcp-reminders
```

## Adding to Claude Desktop

Add this to your Claude Desktop config file (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jons-mcp-reminders": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/jons-mcp-reminders",
        "jons-mcp-reminders"
      ]
    }
  }
}
```

Replace `/path/to/jons-mcp-reminders` with the actual path to this repository.

## Available Tools

### List Management (5 tools)

| Tool | Description |
|------|-------------|
| `list_reminder_lists` | Get all reminder lists |
| `get_reminder_list` | Get a specific list by ID |
| `create_reminder_list` | Create a new list with optional hex color |
| `update_reminder_list` | Update list title/color |
| `delete_reminder_list` | Delete a list (and all its reminders) |

### Reminder CRUD (7 tools)

| Tool | Description |
|------|-------------|
| `get_reminders` | Get reminders with filters (list, completion, due date) |
| `get_reminder` | Get single reminder by ID |
| `create_reminder` | Create with title, notes, URL, due date, priority |
| `update_reminder` | Update any reminder fields |
| `complete_reminder` | Toggle completion status |
| `delete_reminder` | Delete a reminder |
| `move_reminder` | Move reminder to different list |

### Batch Operations (3 tools)

| Tool | Description |
|------|-------------|
| `complete_reminders` | Batch complete multiple reminders |
| `delete_reminders` | Batch delete multiple reminders |
| `add_reminders` | Quick-add multiple reminders by title |

### Search (1 tool)

| Tool | Description |
|------|-------------|
| `search_reminders` | Search reminders by title/notes (case-insensitive) |

## Priority Values

| Priority | Value | Reminders App |
|----------|-------|---------------|
| NONE | 0 | No flag |
| HIGH | 1 | !!! |
| MEDIUM | 5 | !! |
| LOW | 9 | ! |

## Known Limitations

1. **Sections not supported**: EventKit does not expose sections/headers within reminder lists (e.g., "Frozen", "Produce" in a Grocery list). This is a UI-only feature with no public API.

2. **Color shifting**: Colors may shift slightly (~30 units per RGB channel) due to iCloud color space conversion when syncing. This is expected behavior.

3. **Exchange calendars**: Reminder IDs on Exchange accounts may change after initial sync. iCloud calendars have stable IDs.

## Development

### Setup

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run integration tests (requires Reminders access)
uv run pytest tests/test_integration.py -v

# Run with coverage
uv run pytest --cov=src
```

### Code Quality

```bash
# Type check
uv run mypy src/jons_mcp_reminders

# Format code
uv run black src tests

# Lint code
uv run ruff check src tests
```

## Project Structure

```
jons-mcp-reminders/
├── src/
│   └── jons_mcp_reminders/
│       ├── __init__.py          # Package exports
│       ├── constants.py         # Configuration constants
│       ├── exceptions.py        # Custom exceptions
│       ├── models.py            # Pydantic models
│       ├── converters.py        # EventKit <-> Python conversions
│       ├── store.py             # ReminderStore singleton
│       ├── server.py            # FastMCP server setup
│       └── tools/
│           ├── __init__.py      # Tool exports
│           ├── lists.py         # List management tools
│           ├── reminders.py     # Reminder CRUD tools
│           ├── batch.py         # Batch operation tools
│           └── search.py        # Search tool
├── tests/
│   ├── conftest.py              # Test fixtures
│   └── test_integration.py      # Integration tests
├── pyproject.toml               # Project configuration
├── CLAUDE.md                    # AI assistant guidance
└── README.md                    # This file
```

## License

MIT
