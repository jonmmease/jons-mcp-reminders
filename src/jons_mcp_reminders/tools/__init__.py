"""MCP tools for macOS Reminders."""

from .batch import add_reminders, complete_reminders, delete_reminders
from .lists import (
    create_reminder_list,
    delete_reminder_list,
    get_reminder_list,
    list_reminder_lists,
    update_reminder_list,
)
from .reminders import (
    complete_reminder,
    create_reminder,
    delete_reminder,
    get_reminder,
    get_reminders,
    move_reminder,
    update_reminder,
)
from .search import search_reminders

__all__ = [
    # List management
    "list_reminder_lists",
    "get_reminder_list",
    "create_reminder_list",
    "update_reminder_list",
    "delete_reminder_list",
    # Reminder CRUD
    "get_reminders",
    "get_reminder",
    "create_reminder",
    "update_reminder",
    "complete_reminder",
    "delete_reminder",
    "move_reminder",
    # Batch operations
    "complete_reminders",
    "delete_reminders",
    "add_reminders",
    # Search
    "search_reminders",
]
