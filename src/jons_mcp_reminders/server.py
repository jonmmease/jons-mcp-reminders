"""FastMCP server for macOS Reminders via EventKit."""

import argparse
import logging
import os
import signal
import sys
from typing import Any

from fastmcp import FastMCP

from .store import ReminderStore
from .tools.batch import add_reminders, complete_reminders, delete_reminders
from .tools.lists import (
    create_reminder_list,
    delete_reminder_list,
    get_reminder_list,
    list_reminder_lists,
    update_reminder_list,
)
from .tools.reminders import (
    complete_reminder,
    create_reminder,
    delete_reminder,
    get_reminder,
    get_reminders,
    move_reminder,
    update_reminder,
)
from .tools.search import search_reminders

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP(
    name="jons-mcp-reminders",
    instructions="""
An MCP server for macOS Reminders via EventKit.

Provides native access to the macOS Reminders app for creating, reading,
updating, and deleting reminders and lists.

## Available Tools

### List Management (5 tools)
| Tool | Purpose |
|------|---------|
| list_reminder_lists | Get all reminder lists |
| get_reminder_list | Get a specific list by ID |
| create_reminder_list | Create a new list with optional color |
| update_reminder_list | Update list title/color |
| delete_reminder_list | Delete a list |

### Reminder CRUD (7 tools)
| Tool | Purpose |
|------|---------|
| get_reminders | Get reminders with filters (list, completion, due date) |
| get_reminder | Get single reminder by ID |
| create_reminder | Create with title, notes, url, due date, priority |
| update_reminder | Update any reminder fields |
| complete_reminder | Toggle completion status |
| delete_reminder | Delete a reminder |
| move_reminder | Move reminder to different list |

### Batch Operations (3 tools)
| Tool | Purpose |
|------|---------|
| complete_reminders | Batch complete multiple reminders |
| delete_reminders | Batch delete multiple reminders |
| add_reminders | Quick-add multiple reminders by title |

### Search (1 tool)
| Tool | Purpose |
|------|---------|
| search_reminders | Search reminders by title/notes |

## Limitations
- Sections/headers within lists are not accessible (UI-only feature)
- Colors may shift slightly due to iCloud color space conversion
""",
)

# Register all MCP tools

# List management tools
mcp.tool(list_reminder_lists)
mcp.tool(get_reminder_list)
mcp.tool(create_reminder_list)
mcp.tool(update_reminder_list)
mcp.tool(delete_reminder_list)

# Reminder CRUD tools
mcp.tool(get_reminders)
mcp.tool(get_reminder)
mcp.tool(create_reminder)
mcp.tool(update_reminder)
mcp.tool(complete_reminder)
mcp.tool(delete_reminder)
mcp.tool(move_reminder)

# Batch tools
mcp.tool(complete_reminders)
mcp.tool(delete_reminders)
mcp.tool(add_reminders)

# Search tool
mcp.tool(search_reminders)


# Signal handling for graceful shutdown
def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="An MCP Server for macOS Reminders")
    parser.add_argument(
        "project_path",
        nargs="?",
        help="Path to the project (defaults to current directory)",
    )
    args = parser.parse_args()

    if args.project_path:
        logger.info(f"Starting server with project path: {args.project_path}")
    else:
        logger.info("Starting server with current directory")

    # Initialize the ReminderStore to request permissions at startup
    # This ensures the permission dialog appears immediately rather than
    # on the first tool call
    try:
        logger.info("Requesting Reminders access...")
        ReminderStore.get_instance()
        logger.info("Reminders access granted")
    except Exception as e:
        logger.error(f"Failed to initialize Reminders access: {e}")
        logger.error(
            "Please grant Reminders access in System Settings > "
            "Privacy & Security > Reminders"
        )
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    mcp.run()


if __name__ == "__main__":
    main()
