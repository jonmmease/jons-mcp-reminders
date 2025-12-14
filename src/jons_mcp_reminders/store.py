"""EventKit wrapper for Reminders access.

This module provides the ReminderStore singleton that handles all EventKit
interactions with thread-safe serialization and proper memory management.
"""

import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

import anyio
import objc
from EventKit import (
    EKCalendar,
    EKEntityTypeReminder,
    EKEventStore,
    EKReminder,
    EKSourceTypeCalDAV,
    EKSourceTypeLocal,
)
from Foundation import NSURL

from .converters import (
    datetime_to_components,
    datetime_to_nsdate,
    ek_calendar_to_dict,
    ek_reminder_to_dict,
    hex_to_cgcolor,
    location_trigger_to_ek_alarm,
)
from .models import LocationTrigger
from .exceptions import (
    AccessDeniedError,
    EventKitError,
    NotFoundError,
    NoWritableSourceError,
    PermissionTimeoutError,
)

T = TypeVar("T")

# Default timeout for EventKit operations
DEFAULT_TIMEOUT = 60


class ReminderStore:
    """Singleton wrapper for EKEventStore with thread-safe async access.

    All EventKit operations are serialized using a CapacityLimiter(1) to ensure
    thread-safety since EventKit's thread-safety is undocumented.

    Usage:
        store = ReminderStore.get_instance()
        reminders = await store.run_eventkit(store.get_reminders_sync)
    """

    _instance: "ReminderStore | None" = None
    _limiter: anyio.CapacityLimiter | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize the store and request Reminders access.

        Raises:
            PermissionTimeoutError: If permission request times out
            AccessDeniedError: If user denies Reminders access
        """
        self._store: EKEventStore = EKEventStore.alloc().init()
        self._access_granted = False
        self._request_access_sync()

    def _request_access_sync(self) -> None:
        """Request Reminders access synchronously.

        Blocks until user responds to permission dialog or timeout.
        """
        event = threading.Event()
        result: dict[str, Any] = {"granted": False, "error": None}

        def handler(granted: bool, error: Any) -> None:
            result["granted"] = granted
            result["error"] = error
            event.set()

        self._store.requestFullAccessToRemindersWithCompletion_(handler)

        if not event.wait(timeout=DEFAULT_TIMEOUT):
            raise PermissionTimeoutError(DEFAULT_TIMEOUT)

        if result["error"]:
            raise EventKitError.from_nserror(result["error"])

        if not result["granted"]:
            raise AccessDeniedError()

        self._access_granted = True

    @classmethod
    def get_instance(cls) -> "ReminderStore":
        """Get or create the singleton instance.

        Thread-safe singleton pattern with double-checked locking.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def _get_limiter(cls) -> anyio.CapacityLimiter:
        """Get the capacity limiter, creating if needed."""
        if cls._limiter is None:
            cls._limiter = anyio.CapacityLimiter(1)
        return cls._limiter

    @classmethod
    async def run_eventkit(cls, fn: Callable[..., T], *args: Any) -> T:
        """Execute an EventKit operation with serialization and memory management.

        All EventKit operations should go through this method to ensure:
        1. Only one operation runs at a time (CapacityLimiter)
        2. Proper memory management (autorelease pool)
        3. Non-blocking async interface

        Args:
            fn: Synchronous function to execute
            *args: Arguments to pass to the function

        Returns:
            Result of the function call
        """
        limiter = cls._get_limiter()

        async with limiter:

            def wrapped() -> T:
                with objc.autorelease_pool():
                    return fn(*args)

            return await anyio.to_thread.run_sync(wrapped)

    # List (Calendar) Operations

    def get_lists_sync(self) -> list[dict[str, Any]]:
        """Get all reminder lists synchronously.

        Returns:
            List of dicts with id, title, color, is_default fields
        """
        calendars = self._store.calendarsForEntityType_(EKEntityTypeReminder)
        default_cal = self._store.defaultCalendarForNewReminders()
        default_id = default_cal.calendarIdentifier() if default_cal else None

        return [
            ek_calendar_to_dict(
                cal, is_default=(cal.calendarIdentifier() == default_id)
            )
            for cal in calendars
        ]

    def get_list_sync(self, list_id: str) -> dict[str, Any]:
        """Get a specific reminder list by ID.

        Args:
            list_id: Calendar identifier

        Returns:
            Dict with list fields

        Raises:
            NotFoundError: If list doesn't exist
        """
        calendar = self._store.calendarWithIdentifier_(list_id)
        if not calendar:
            raise NotFoundError("List", list_id)

        default_cal = self._store.defaultCalendarForNewReminders()
        is_default = default_cal and default_cal.calendarIdentifier() == list_id

        return ek_calendar_to_dict(calendar, is_default=is_default)

    def create_list_sync(self, title: str, color: str | None = None) -> dict[str, Any]:
        """Create a new reminder list.

        Args:
            title: Name of the list
            color: Optional hex color (e.g., "#FF5733")

        Returns:
            Dict with created list fields

        Raises:
            NoWritableSourceError: If no writable source is available
            EventKitError: If save fails
        """
        source = self._get_writable_source()

        calendar = EKCalendar.calendarForEntityType_eventStore_(
            EKEntityTypeReminder, self._store
        )
        calendar.setTitle_(title)
        calendar.setSource_(source)

        if color:
            calendar.setCGColor_(hex_to_cgcolor(color))

        error = None
        success = self._store.saveCalendar_commit_error_(calendar, True, error)

        if not success:
            raise EventKitError(f"Failed to create list: {title}")

        return ek_calendar_to_dict(calendar, is_default=False)

    def update_list_sync(
        self, list_id: str, title: str | None = None, color: str | None = None
    ) -> dict[str, Any]:
        """Update a reminder list.

        Args:
            list_id: Calendar identifier
            title: New title (optional)
            color: New hex color (optional)

        Returns:
            Dict with updated list fields

        Raises:
            NotFoundError: If list doesn't exist
            EventKitError: If save fails
        """
        calendar = self._store.calendarWithIdentifier_(list_id)
        if not calendar:
            raise NotFoundError("List", list_id)

        if title is not None:
            calendar.setTitle_(title)
        if color is not None:
            calendar.setCGColor_(hex_to_cgcolor(color))

        error = None
        success = self._store.saveCalendar_commit_error_(calendar, True, error)

        if not success:
            raise EventKitError(f"Failed to update list: {list_id}")

        default_cal = self._store.defaultCalendarForNewReminders()
        is_default = default_cal and default_cal.calendarIdentifier() == list_id

        return ek_calendar_to_dict(calendar, is_default=is_default)

    def delete_list_sync(self, list_id: str) -> bool:
        """Delete a reminder list.

        Args:
            list_id: Calendar identifier

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If list doesn't exist
            EventKitError: If delete fails
        """
        calendar = self._store.calendarWithIdentifier_(list_id)
        if not calendar:
            raise NotFoundError("List", list_id)

        error = None
        success = self._store.removeCalendar_commit_error_(calendar, True, error)

        if not success:
            raise EventKitError(f"Failed to delete list: {list_id}")

        return True

    # Reminder Operations

    def get_reminders_sync(
        self,
        list_id: str | None = None,
        include_completed: bool = False,
        due_before: datetime | None = None,
        due_after: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get reminders with optional filters.

        Args:
            list_id: Limit to specific list (optional)
            include_completed: Include completed reminders
            due_before: Only reminders due before this date
            due_after: Only reminders due after this date

        Returns:
            List of reminder dicts
        """
        # Get calendars to search
        if list_id:
            calendar = self._store.calendarWithIdentifier_(list_id)
            if not calendar:
                raise NotFoundError("List", list_id)
            calendars = [calendar]
        else:
            calendars = None  # None means all calendars

        # Build predicate based on filters
        if include_completed:
            predicate = self._store.predicateForRemindersInCalendars_(calendars)
        elif due_before is not None or due_after is not None:
            start_date = datetime_to_nsdate(due_after) if due_after else None
            end_date = datetime_to_nsdate(due_before) if due_before else None
            predicate = self._store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
                start_date, end_date, calendars
            )
        else:
            predicate = self._store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
                None, None, calendars
            )

        # Fetch with callback
        event = threading.Event()
        reminder_list: list[dict[str, Any]] = []

        def handler(reminders: Any) -> None:
            if reminders:
                # Convert to dicts INSIDE worker thread
                reminder_list.extend([ek_reminder_to_dict(r) for r in reminders])
            event.set()

        self._store.fetchRemindersMatchingPredicate_completion_(predicate, handler)

        if not event.wait(timeout=DEFAULT_TIMEOUT):
            raise TimeoutError(f"Fetch reminders timed out after {DEFAULT_TIMEOUT}s")

        return reminder_list

    def get_reminder_sync(self, reminder_id: str) -> dict[str, Any]:
        """Get a single reminder by ID.

        Tries local ID first (faster), then falls back to external ID lookup.

        Args:
            reminder_id: Reminder identifier

        Returns:
            Reminder dict

        Raises:
            NotFoundError: If reminder doesn't exist
        """
        # Try local ID first (faster)
        reminder = self._store.calendarItemWithIdentifier_(reminder_id)
        if reminder and isinstance(reminder, EKReminder):
            return ek_reminder_to_dict(reminder)

        # Fall back to external ID lookup
        items = self._store.calendarItemsWithExternalIdentifier_(reminder_id)
        if items and len(items) > 0:
            for item in items:
                if isinstance(item, EKReminder):
                    return ek_reminder_to_dict(item)

        raise NotFoundError("Reminder", reminder_id)

    def create_reminder_sync(
        self,
        title: str,
        list_id: str | None = None,
        notes: str | None = None,
        url: str | None = None,
        due_date: datetime | None = None,
        start_date: datetime | None = None,
        priority: int = 0,
        location: LocationTrigger | None = None,
    ) -> dict[str, Any]:
        """Create a new reminder.

        Args:
            title: Reminder title
            list_id: Target list (uses default if not specified)
            notes: Optional notes
            url: Optional URL
            due_date: Optional due date
            start_date: Optional start date
            priority: Priority (0=none, 1=high, 5=medium, 9=low)
            location: Optional location trigger for geofence-based reminder

        Returns:
            Created reminder dict

        Raises:
            NotFoundError: If specified list doesn't exist
            EventKitError: If save fails
        """
        reminder = EKReminder.reminderWithEventStore_(self._store)
        reminder.setTitle_(title)

        # Set calendar (list)
        if list_id:
            calendar = self._store.calendarWithIdentifier_(list_id)
            if not calendar:
                raise NotFoundError("List", list_id)
        else:
            calendar = self._store.defaultCalendarForNewReminders()
            if not calendar:
                raise NoWritableSourceError()
        reminder.setCalendar_(calendar)

        # Optional fields
        if notes:
            reminder.setNotes_(notes)
        if url:
            reminder.setURL_(NSURL.URLWithString_(url))
        if due_date:
            reminder.setDueDateComponents_(datetime_to_components(due_date))
        if start_date:
            reminder.setStartDateComponents_(datetime_to_components(start_date))
        if priority:
            reminder.setPriority_(priority)

        # Location-based alarm
        if location:
            alarm = location_trigger_to_ek_alarm(location)
            reminder.addAlarm_(alarm)

        # Save
        error = None
        success = self._store.saveReminder_commit_error_(reminder, True, error)

        if not success:
            raise EventKitError(f"Failed to create reminder: {title}")

        return ek_reminder_to_dict(reminder)

    def update_reminder_sync(
        self,
        reminder_id: str,
        title: str | None = None,
        notes: str | None = None,
        url: str | None = None,
        due_date: datetime | None = None,
        start_date: datetime | None = None,
        priority: int | None = None,
        location: LocationTrigger | None = None,
        clear_location: bool = False,
    ) -> dict[str, Any]:
        """Update an existing reminder.

        Args:
            reminder_id: Reminder identifier
            title: New title (optional)
            notes: New notes (optional)
            url: New URL (optional)
            due_date: New due date (optional)
            start_date: New start date (optional)
            priority: New priority (optional)
            location: New location trigger (optional)
            clear_location: If True, remove any existing location alarm

        Returns:
            Updated reminder dict

        Raises:
            NotFoundError: If reminder doesn't exist
            EventKitError: If save fails
        """
        reminder = self._get_reminder_by_id(reminder_id)

        if title is not None:
            reminder.setTitle_(title)
        if notes is not None:
            reminder.setNotes_(notes)
        if url is not None:
            reminder.setURL_(NSURL.URLWithString_(url))
        if due_date is not None:
            reminder.setDueDateComponents_(datetime_to_components(due_date))
        if start_date is not None:
            reminder.setStartDateComponents_(datetime_to_components(start_date))
        if priority is not None:
            reminder.setPriority_(priority)

        # Handle location updates
        if clear_location:
            # Remove all location-based alarms
            self._remove_location_alarms(reminder)
        elif location is not None:
            # Remove existing location alarms then add new one
            self._remove_location_alarms(reminder)
            alarm = location_trigger_to_ek_alarm(location)
            reminder.addAlarm_(alarm)

        error = None
        success = self._store.saveReminder_commit_error_(reminder, True, error)

        if not success:
            raise EventKitError(f"Failed to update reminder: {reminder_id}")

        return ek_reminder_to_dict(reminder)

    def complete_reminder_sync(
        self, reminder_id: str, completed: bool = True
    ) -> dict[str, Any]:
        """Mark a reminder as complete or incomplete.

        Args:
            reminder_id: Reminder identifier
            completed: Whether to mark as completed (default True)

        Returns:
            Updated reminder dict

        Raises:
            NotFoundError: If reminder doesn't exist
            EventKitError: If save fails
        """
        reminder = self._get_reminder_by_id(reminder_id)
        reminder.setCompleted_(completed)

        error = None
        success = self._store.saveReminder_commit_error_(reminder, True, error)

        if not success:
            raise EventKitError(f"Failed to update reminder: {reminder_id}")

        return ek_reminder_to_dict(reminder)

    def delete_reminder_sync(self, reminder_id: str) -> bool:
        """Delete a reminder.

        Args:
            reminder_id: Reminder identifier

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If reminder doesn't exist
            EventKitError: If delete fails
        """
        reminder = self._get_reminder_by_id(reminder_id)

        error = None
        success = self._store.removeReminder_commit_error_(reminder, True, error)

        if not success:
            raise EventKitError(f"Failed to delete reminder: {reminder_id}")

        return True

    def move_reminder_sync(self, reminder_id: str, list_id: str) -> dict[str, Any]:
        """Move a reminder to a different list.

        Args:
            reminder_id: Reminder identifier
            list_id: Target list identifier

        Returns:
            Updated reminder dict

        Raises:
            NotFoundError: If reminder or list doesn't exist
            EventKitError: If save fails
        """
        reminder = self._get_reminder_by_id(reminder_id)

        calendar = self._store.calendarWithIdentifier_(list_id)
        if not calendar:
            raise NotFoundError("List", list_id)

        reminder.setCalendar_(calendar)

        error = None
        success = self._store.saveReminder_commit_error_(reminder, True, error)

        if not success:
            raise EventKitError(f"Failed to move reminder: {reminder_id}")

        return ek_reminder_to_dict(reminder)

    # Private Helpers

    def _get_reminder_by_id(self, reminder_id: str) -> EKReminder:
        """Get EKReminder by ID with fallback lookup.

        Args:
            reminder_id: Reminder identifier

        Returns:
            EKReminder instance

        Raises:
            NotFoundError: If reminder doesn't exist
        """
        # Try local ID first (faster)
        reminder = self._store.calendarItemWithIdentifier_(reminder_id)
        if reminder and isinstance(reminder, EKReminder):
            return reminder

        # Fall back to external ID lookup
        items = self._store.calendarItemsWithExternalIdentifier_(reminder_id)
        if items and len(items) > 0:
            for item in items:
                if isinstance(item, EKReminder):
                    return item

        raise NotFoundError("Reminder", reminder_id)

    def _remove_location_alarms(self, reminder: EKReminder) -> int:
        """Remove all location-based alarms from a reminder.

        Args:
            reminder: EKReminder instance (modified in place)

        Returns:
            Number of alarms removed
        """
        alarms = reminder.alarms()
        if not alarms:
            return 0

        removed = 0
        # Iterate over a copy to safely remove while iterating
        for alarm in list(alarms):
            if alarm.structuredLocation() is not None:
                reminder.removeAlarm_(alarm)
                removed += 1

        return removed

    def _get_writable_source(self) -> Any:
        """Get a writable source for creating new calendars.

        Priority: default calendar's source > iCloud/CalDAV > Local > any

        Returns:
            EKSource instance

        Raises:
            NoWritableSourceError: If no writable source is available
        """
        # Try default calendar's source first
        default_cal = self._store.defaultCalendarForNewReminders()
        if default_cal and default_cal.allowsContentModifications():
            return default_cal.source()

        # Try iCloud/CalDAV sources
        for source in self._store.sources():
            if source.sourceType() == EKSourceTypeCalDAV:
                cals = source.calendarsForEntityType_(EKEntityTypeReminder)
                if cals and any(c.allowsContentModifications() for c in cals):
                    return source

        # Try Local source
        for source in self._store.sources():
            if source.sourceType() == EKSourceTypeLocal:
                cals = source.calendarsForEntityType_(EKEntityTypeReminder)
                if cals and any(c.allowsContentModifications() for c in cals):
                    return source

        # Try any writable source
        for source in self._store.sources():
            cals = source.calendarsForEntityType_(EKEntityTypeReminder)
            if cals and any(c.allowsContentModifications() for c in cals):
                return source

        raise NoWritableSourceError()
