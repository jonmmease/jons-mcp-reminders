"""MCP tools for reminder CRUD operations."""

from datetime import datetime
from typing import Any

from ..models import LocationTrigger, Priority, Reminder
from ..store import ReminderStore


def _paginate(items: list[Any], offset: int = 0, limit: int | None = None) -> list[Any]:
    """Apply simple offset/limit pagination."""
    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]
    return items


async def get_reminders(
    list_id: str | None = None,
    include_completed: bool = False,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, list[Reminder]]:
    """Get reminders with optional filters.

    Args:
        list_id: Only get reminders from this list (optional).
        include_completed: Include completed reminders (default False).
        due_before: Only reminders due before this date (optional).
        due_after: Only reminders due after this date (optional).
        limit: Maximum number of reminders to return (optional).
        offset: Number of reminders to skip for pagination (default 0).

    Returns:
        List of reminders matching the filters.
    """
    store = ReminderStore.get_instance()
    reminders = await ReminderStore.run_eventkit(
        store.get_reminders_sync, list_id, include_completed, due_before, due_after
    )

    # Apply pagination
    paginated = _paginate(reminders, offset, limit)

    # Wrap in dict to ensure FastMCP always returns a TextContent
    # (empty lists cause "No result received" in Claude Desktop)
    return {"reminders": [Reminder(**data) for data in paginated]}


async def get_reminder(reminder_id: str) -> Reminder:
    """Get a single reminder by ID.

    Args:
        reminder_id: The unique identifier of the reminder.

    Returns:
        The reminder with all its details.

    Raises:
        NotFoundError: If no reminder exists with the given ID.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(store.get_reminder_sync, reminder_id)
    return Reminder(**data)


async def create_reminder(
    title: str,
    list_id: str | None = None,
    notes: str | None = None,
    url: str | None = None,
    due_date: datetime | None = None,
    start_date: datetime | None = None,
    priority: Priority = Priority.NONE,
    location: LocationTrigger | None = None,
) -> Reminder:
    """Create a new reminder.

    Args:
        title: The title/name of the reminder.
        list_id: The list to add the reminder to (uses default list if not specified).
        notes: Optional additional notes or description.
        url: Optional URL to associate with the reminder.
        due_date: Optional due date and time.
        start_date: Optional start date for the reminder.
        priority: Priority level (NONE=0, HIGH=1, MEDIUM=5, LOW=9).
        location: Optional location trigger. When set, the reminder will fire when
            entering or leaving the specified location. Provide title, latitude,
            longitude, radius (meters), and proximity ("enter" or "leave").

    Returns:
        The newly created reminder.

    Raises:
        NotFoundError: If the specified list_id doesn't exist.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(
        store.create_reminder_sync,
        title,
        list_id,
        notes,
        url,
        due_date,
        start_date,
        int(priority),
        location,
    )
    return Reminder(**data)


async def update_reminder(
    reminder_id: str,
    title: str | None = None,
    notes: str | None = None,
    url: str | None = None,
    due_date: datetime | None = None,
    start_date: datetime | None = None,
    priority: Priority | None = None,
    location: LocationTrigger | None = None,
    clear_location: bool = False,
) -> Reminder:
    """Update an existing reminder.

    Only provided fields will be updated; others remain unchanged.

    Args:
        reminder_id: The unique identifier of the reminder to update.
        title: New title (optional).
        notes: New notes (optional).
        url: New URL (optional).
        due_date: New due date (optional).
        start_date: New start date (optional).
        priority: New priority level (optional).
        location: New location trigger (optional). Replaces any existing location.
        clear_location: Set to True to remove any existing location trigger.

    Returns:
        The updated reminder.

    Raises:
        NotFoundError: If no reminder exists with the given ID.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(
        store.update_reminder_sync,
        reminder_id,
        title,
        notes,
        url,
        due_date,
        start_date,
        int(priority) if priority is not None else None,
        location,
        clear_location,
    )
    return Reminder(**data)


async def complete_reminder(
    reminder_id: str,
    completed: bool = True,
) -> Reminder:
    """Mark a reminder as complete or incomplete.

    Args:
        reminder_id: The unique identifier of the reminder.
        completed: True to mark as complete, False to mark as incomplete.

    Returns:
        The updated reminder with its new completion status.

    Raises:
        NotFoundError: If no reminder exists with the given ID.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(
        store.complete_reminder_sync, reminder_id, completed
    )
    return Reminder(**data)


async def delete_reminder(reminder_id: str) -> bool:
    """Delete a reminder.

    Args:
        reminder_id: The unique identifier of the reminder to delete.

    Returns:
        True if the reminder was successfully deleted.

    Raises:
        NotFoundError: If no reminder exists with the given ID.
    """
    store = ReminderStore.get_instance()
    return await ReminderStore.run_eventkit(store.delete_reminder_sync, reminder_id)


async def move_reminder(reminder_id: str, list_id: str) -> Reminder:
    """Move a reminder to a different list.

    Args:
        reminder_id: The unique identifier of the reminder to move.
        list_id: The unique identifier of the destination list.

    Returns:
        The updated reminder with its new list assignment.

    Raises:
        NotFoundError: If the reminder or destination list doesn't exist.
    """
    store = ReminderStore.get_instance()
    data = await ReminderStore.run_eventkit(
        store.move_reminder_sync, reminder_id, list_id
    )
    return Reminder(**data)


__all__ = [
    "get_reminders",
    "get_reminder",
    "create_reminder",
    "update_reminder",
    "complete_reminder",
    "delete_reminder",
    "move_reminder",
]
