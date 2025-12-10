"""MCP tools for searching reminders."""

from typing import Any

from ..models import Reminder
from ..store import ReminderStore


def _paginate(items: list[Any], offset: int = 0, limit: int | None = None) -> list[Any]:
    """Apply simple offset/limit pagination."""
    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]
    return items


async def search_reminders(
    query: str,
    list_id: str | None = None,
    include_completed: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[Reminder]:
    """Search reminders by title or notes.

    Searches for reminders where the title OR notes contain the query
    string (case-insensitive).

    Args:
        query: The text to search for in titles and notes.
        list_id: Limit search to a specific list (optional).
        include_completed: Include completed reminders in search (default False).
        limit: Maximum number of results to return (optional).
        offset: Number of results to skip for pagination (default 0).

    Returns:
        List of reminders matching the search query.

    Note:
        EventKit has limited search capabilities, so this fetches all
        matching reminders and filters in Python. For large datasets,
        consider using list_id to narrow the scope.
    """
    store = ReminderStore.get_instance()

    # Fetch all reminders matching the list/completion filters
    reminders = await ReminderStore.run_eventkit(
        store.get_reminders_sync, list_id, include_completed, None, None
    )

    # Filter by query (case-insensitive search in title and notes)
    query_lower = query.lower()
    matching = []
    for data in reminders:
        title = data.get("title", "") or ""
        notes = data.get("notes", "") or ""
        if query_lower in title.lower() or query_lower in notes.lower():
            matching.append(data)

    # Apply pagination
    paginated = _paginate(matching, offset, limit)

    return [Reminder(**data) for data in paginated]


__all__ = ["search_reminders"]
