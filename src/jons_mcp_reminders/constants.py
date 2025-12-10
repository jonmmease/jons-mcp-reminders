"""Constants for MCP Server for macOS reminders."""

import os

# Timeouts
REQUEST_TIMEOUT: float = float(os.environ.get("REQUEST_TIMEOUT", "60.0"))
SHUTDOWN_TIMEOUT: float = 5.0

# Pagination defaults
DEFAULT_PAGINATION_LIMIT: int = 20
DEFAULT_PAGINATION_OFFSET: int = 0
