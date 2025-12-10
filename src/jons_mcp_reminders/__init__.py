"""MCP Server for macOS Reminders."""

from .exceptions import (
    AccessDeniedError,
    EventKitError,
    NotFoundError,
    NoWritableSourceError,
    PermissionTimeoutError,
    RemindersError,
)
from .models import BatchResult, Priority, Reminder, ReminderList
from .server import main, mcp
from .store import ReminderStore

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "main",
    "mcp",
    # Store
    "ReminderStore",
    # Models
    "Priority",
    "ReminderList",
    "Reminder",
    "BatchResult",
    # Exceptions
    "RemindersError",
    "AccessDeniedError",
    "PermissionTimeoutError",
    "NotFoundError",
    "NoWritableSourceError",
    "EventKitError",
]
