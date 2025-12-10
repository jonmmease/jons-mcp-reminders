"""MCP tools for batch reminder operations."""

from ..models import BatchResult, Reminder
from ..store import ReminderStore


async def complete_reminders(reminder_ids: list[str]) -> BatchResult:
    """Mark multiple reminders as complete.

    Processes each reminder individually, capturing any failures.
    Partial success is possible - some reminders may be completed
    while others fail.

    Args:
        reminder_ids: List of reminder IDs to mark as complete.

    Returns:
        BatchResult with counts of successes and failures.
    """
    store = ReminderStore.get_instance()
    successes = 0
    failures = 0
    failed_ids: list[str] = []
    errors: list[str] = []

    for reminder_id in reminder_ids:
        try:
            await ReminderStore.run_eventkit(
                store.complete_reminder_sync, reminder_id, True
            )
            successes += 1
        except Exception as e:
            failures += 1
            failed_ids.append(reminder_id)
            errors.append(str(e))

    return BatchResult(
        successes=successes,
        failures=failures,
        failed_ids=failed_ids,
        errors=errors,
    )


async def delete_reminders(reminder_ids: list[str]) -> BatchResult:
    """Delete multiple reminders.

    Processes each reminder individually, capturing any failures.
    Partial success is possible - some reminders may be deleted
    while others fail.

    Args:
        reminder_ids: List of reminder IDs to delete.

    Returns:
        BatchResult with counts of successes and failures.
    """
    store = ReminderStore.get_instance()
    successes = 0
    failures = 0
    failed_ids: list[str] = []
    errors: list[str] = []

    for reminder_id in reminder_ids:
        try:
            await ReminderStore.run_eventkit(store.delete_reminder_sync, reminder_id)
            successes += 1
        except Exception as e:
            failures += 1
            failed_ids.append(reminder_id)
            errors.append(str(e))

    return BatchResult(
        successes=successes,
        failures=failures,
        failed_ids=failed_ids,
        errors=errors,
    )


async def add_reminders(
    list_id: str | None,
    items: list[str],
) -> list[Reminder]:
    """Quick-add multiple reminders by title.

    Creates multiple reminders with just titles, all in the same list.
    Useful for quickly adding a batch of items like a shopping list.

    Args:
        list_id: The list to add reminders to (uses default if None).
        items: List of reminder titles to create.

    Returns:
        List of created Reminder objects for successful items.
        Failed items are silently skipped.
    """
    store = ReminderStore.get_instance()
    created: list[Reminder] = []

    for title in items:
        try:
            data = await ReminderStore.run_eventkit(
                store.create_reminder_sync,
                title,
                list_id,
                None,  # notes
                None,  # url
                None,  # due_date
                None,  # start_date
                0,  # priority
            )
            created.append(Reminder(**data))
        except Exception:
            # Skip failed items
            pass

    return created


__all__ = [
    "complete_reminders",
    "delete_reminders",
    "add_reminders",
]
