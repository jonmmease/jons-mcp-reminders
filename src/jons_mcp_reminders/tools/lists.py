"""MCP tools for reminder list management."""

from ..models import ReminderList
from ..store import ReminderStore


async def list_reminder_lists() -> dict[str, list[ReminderList]]:
    """Get all reminder lists.

    Returns a list of all reminder lists (calendars) available in the
    user's Reminders app, including their IDs, titles, colors, and
    whether each is the default list for new reminders.
    """
    store = ReminderStore.get_instance()
    lists = await ReminderStore.run_eventkit(store.get_lists_sync)
    # Wrap in dict to ensure FastMCP always returns a TextContent
    # (empty lists cause "No result received" in Claude Desktop)
    return {"lists": [ReminderList(**data) for data in lists]}


async def get_reminder_list(list_id: str) -> ReminderList:
    """Get a specific reminder list by ID.

    Args:
        list_id: The unique identifier of the list to retrieve.

    Returns:
        The reminder list with its details.

    Raises:
        NotFoundError: If no list exists with the given ID.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(store.get_list_sync, list_id)
    return ReminderList(**data)


async def create_reminder_list(
    title: str,
    color: str | None = None,
) -> ReminderList:
    """Create a new reminder list.

    Args:
        title: The name for the new list.
        color: Optional hex color code (e.g., "#FF5733"). If not provided,
               the system will assign a default color.

    Returns:
        The newly created reminder list.

    Note:
        Colors may shift slightly (~30 units per RGB channel) due to
        iCloud color space conversion.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(store.create_list_sync, title, color)
    return ReminderList(**data)


async def update_reminder_list(
    list_id: str,
    title: str | None = None,
    color: str | None = None,
) -> ReminderList:
    """Update a reminder list's properties.

    Args:
        list_id: The unique identifier of the list to update.
        title: New title for the list (optional).
        color: New hex color code (optional).

    Returns:
        The updated reminder list.

    Raises:
        NotFoundError: If no list exists with the given ID.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(
        store.update_list_sync, list_id, title, color
    )
    return ReminderList(**data)


async def delete_reminder_list(list_id: str) -> bool:
    """Delete a reminder list.

    Warning: This will also delete all reminders in the list.

    Args:
        list_id: The unique identifier of the list to delete.

    Returns:
        True if the list was successfully deleted.

    Raises:
        NotFoundError: If no list exists with the given ID.
    """
    store = ReminderStore.get_instance()
    return await ReminderStore.run_eventkit(store.delete_list_sync, list_id)


__all__ = [
    "list_reminder_lists",
    "get_reminder_list",
    "create_reminder_list",
    "update_reminder_list",
    "delete_reminder_list",
]
