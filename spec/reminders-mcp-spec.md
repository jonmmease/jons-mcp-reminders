# Reminders MCP Server Spec

## Overview

A Python MCP server using PyObjC to access macOS Reminders via EventKit. Provides native, fast access to Reminders without AppleScript.

## ⚠️ Limitation: Sections Not Supported

**EventKit does NOT expose sections/headers within reminder lists** (e.g., "Frozen", "Produce", "Dairy" in a Grocery list). This is a known limitation confirmed in [Apple Developer Forums](https://developer.apple.com/forums/thread/683611). Sections are a UI-only feature with no public API.

---

## Dependencies

```toml
[project]
dependencies = [
    "mcp[cli]",
    "pyobjc-framework-EventKit",
]
```

### Existing Prior Art

There's an existing library [pyremindkit](https://github.com/namuan/pyremindkit) that wraps EventKit. Worth studying for implementation patterns.

---

## EventKit Fundamentals

```python
from EventKit import (
    EKEventStore,
    EKEntityTypeReminder,
    EKReminder,
    EKAlarm,
)
from Foundation import NSDate, NSDateComponents, NSCalendar

# Singleton store (reuse across calls - it's heavyweight)
store = EKEventStore.alloc().init()
```

### Requesting Access

```python
import threading

def request_access() -> bool:
    """
    Request access to Reminders. Blocks until user responds.
    Returns True if access granted.
    """
    semaphore = threading.Semaphore(0)
    result = {"granted": False}
    
    def handler(granted: bool, error) -> None:
        result["granted"] = granted
        semaphore.release()
    
    store.requestFullAccessToReminders_(handler)
    semaphore.acquire()
    
    return result["granted"]
```

**Note**: On macOS 14+, use `requestFullAccessToReminders_`. On earlier versions, use `requestAccessToEntityType_completion_` with `EKEntityTypeReminder`.

---

## Data Models

```python
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

class Priority(IntEnum):
    NONE = 0
    HIGH = 1      # !!! in Reminders UI
    MEDIUM = 5    # !! in Reminders UI
    LOW = 9       # ! in Reminders UI

@dataclass
class ReminderList:
    id: str                 # calendar.calendarIdentifier
    title: str              # calendar.title
    color: str | None       # calendar.CGColor as hex
    is_default: bool        # is this the default list for new reminders

@dataclass 
class Reminder:
    id: str                         # reminder.calendarItemIdentifier
    title: str                      # reminder.title
    notes: str | None               # reminder.notes
    url: str | None                 # reminder.URL
    completed: bool                 # reminder.completed
    completed_date: datetime | None # reminder.completionDate
    due_date: datetime | None       # reminder.dueDateComponents
    start_date: datetime | None     # reminder.startDateComponents
    priority: Priority              # reminder.priority
    list_id: str                    # reminder.calendar.calendarIdentifier
    list_title: str                 # reminder.calendar.title
```

---

## MCP Tools

### List Management

| Tool | Parameters | Returns | Description |
|------|------------|---------|-------------|
| `list_reminder_lists` | — | `list[ReminderList]` | Get all reminder lists |
| `get_reminder_list` | `list_id: str` | `ReminderList` | Get a specific list |
| `create_reminder_list` | `title: str`, `color?: str` | `ReminderList` | Create a new list |
| `update_reminder_list` | `list_id: str`, `title?: str`, `color?: str` | `ReminderList` | Update list properties |
| `delete_reminder_list` | `list_id: str` | `bool` | Delete a list |

### Reminder CRUD

| Tool | Parameters | Returns | Description |
|------|------------|---------|-------------|
| `get_reminders` | `list_id?: str`, `include_completed?: bool`, `due_before?: str`, `due_after?: str` | `list[Reminder]` | Get reminders with optional filters |
| `get_reminder` | `reminder_id: str` | `Reminder` | Get single reminder by ID |
| `create_reminder` | `title: str`, `list_id?: str`, `notes?: str`, `url?: str`, `due_date?: str`, `priority?: int` | `Reminder` | Create reminder |
| `update_reminder` | `reminder_id: str`, `title?: str`, `notes?: str`, `due_date?: str`, `priority?: int` | `Reminder` | Update reminder |
| `complete_reminder` | `reminder_id: str`, `completed?: bool` | `Reminder` | Mark complete/incomplete |
| `delete_reminder` | `reminder_id: str` | `bool` | Delete reminder |
| `move_reminder` | `reminder_id: str`, `list_id: str` | `Reminder` | Move to different list |

### Batch Operations

| Tool | Parameters | Returns | Description |
|------|------------|---------|-------------|
| `complete_reminders` | `reminder_ids: list[str]` | `dict` | Batch complete, returns success/failure counts |
| `delete_reminders` | `reminder_ids: list[str]` | `dict` | Batch delete |
| `add_reminders` | `list_id: str`, `items: list[str]` | `list[Reminder]` | Quick-add multiple reminders by title |

### Search

| Tool | Parameters | Returns | Description |
|------|------------|---------|-------------|
| `search_reminders` | `query: str`, `list_id?: str`, `include_completed?: bool` | `list[Reminder]` | Search by title/notes |

---

## Key Implementation Details

### Fetching Reminders (Async Predicate Query)

EventKit uses async callbacks for fetching. Wrap with semaphore for sync API:

```python
import threading
from datetime import datetime

def get_reminders(
    list_id: str | None = None,
    include_completed: bool = False,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
) -> list[dict]:
    """Fetch reminders using predicate query."""
    
    # Get calendars (lists) to search
    if list_id:
        calendar = store.calendarWithIdentifier_(list_id)
        if not calendar:
            raise ValueError(f"List not found: {list_id}")
        calendars = [calendar]
    else:
        calendars = store.calendarsForEntityType_(EKEntityTypeReminder)
    
    # Build predicate based on filters
    if include_completed:
        predicate = store.predicateForRemindersInCalendars_(calendars)
    else:
        # Convert datetimes to NSDate if provided
        start_date = _datetime_to_nsdate(due_after) if due_after else None
        end_date = _datetime_to_nsdate(due_before) if due_before else None
        
        predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
            start_date,
            end_date,
            calendars,
        )
    
    # Async fetch with semaphore
    results = []
    semaphore = threading.Semaphore(0)
    
    def handler(reminders):
        if reminders:
            results.extend(reminders)
        semaphore.release()
    
    store.fetchRemindersMatchingPredicate_completion_(predicate, handler)
    semaphore.acquire()
    
    return [_reminder_to_dict(r) for r in results]
```

### Creating a Reminder

```python
def create_reminder(
    title: str,
    list_id: str | None = None,
    notes: str | None = None,
    url: str | None = None,
    due_date: datetime | None = None,
    priority: int = 0,
) -> dict:
    """Create a new reminder."""
    
    reminder = EKReminder.reminderWithEventStore_(store)
    reminder.setTitle_(title)
    
    # Set calendar (list)
    if list_id:
        calendar = store.calendarWithIdentifier_(list_id)
        if not calendar:
            raise ValueError(f"List not found: {list_id}")
    else:
        calendar = store.defaultCalendarForNewReminders()
    reminder.setCalendar_(calendar)
    
    # Optional fields
    if notes:
        reminder.setNotes_(notes)
    
    if url:
        from Foundation import NSURL
        reminder.setURL_(NSURL.URLWithString_(url))
    
    if due_date:
        components = _datetime_to_components(due_date)
        reminder.setDueDateComponents_(components)
    
    if priority:
        reminder.setPriority_(priority)
    
    # Save
    success, error = store.saveReminder_commit_error_(reminder, True, None)
    if not success:
        raise Exception(f"Failed to save: {error}")
    
    return _reminder_to_dict(reminder)
```

### Date Handling

```python
from Foundation import NSDateComponents, NSCalendar, NSDate

# Magic constant for "not set"
NSUndefinedDateComponent = 0x7FFFFFFF  # NSIntegerMax

def _datetime_to_components(dt: datetime) -> NSDateComponents:
    """Convert Python datetime to NSDateComponents."""
    components = NSDateComponents.alloc().init()
    components.setYear_(dt.year)
    components.setMonth_(dt.month)
    components.setDay_(dt.day)
    components.setHour_(dt.hour)
    components.setMinute_(dt.minute)
    components.setSecond_(dt.second)
    return components

def _components_to_datetime(components) -> datetime | None:
    """Convert NSDateComponents to Python datetime."""
    if not components:
        return None
    
    year = components.year()
    if year == NSUndefinedDateComponent:
        return None
    
    return datetime(
        year=year,
        month=components.month(),
        day=components.day(),
        hour=components.hour() if components.hour() != NSUndefinedDateComponent else 0,
        minute=components.minute() if components.minute() != NSUndefinedDateComponent else 0,
        second=components.second() if components.second() != NSUndefinedDateComponent else 0,
    )

def _datetime_to_nsdate(dt: datetime) -> NSDate:
    """Convert Python datetime to NSDate."""
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

def _nsdate_to_datetime(nsdate) -> datetime | None:
    """Convert NSDate to Python datetime."""
    if not nsdate:
        return None
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970())
```

---

## Permissions

### Runtime Access

First call triggers system permission prompt. User must grant access in:
**System Settings → Privacy & Security → Reminders**

### For Distribution

If packaging as an app, include in `Info.plist`:

```xml
<key>NSRemindersFullAccessUsageDescription</key>
<string>This app needs access to manage your reminders.</string>
```

For Python scripts run from Terminal, the Terminal app (or Python executable) needs the permission.

---

## Error Handling

```python
class RemindersError(Exception):
    """Base exception for Reminders MCP."""
    pass

class AccessDeniedError(RemindersError):
    """User hasn't granted Reminders access."""
    pass

class NotFoundError(RemindersError):
    """Reminder or list not found."""
    pass

class SaveError(RemindersError):
    """Failed to save reminder or list."""
    pass
```

---

## MCP Server Structure

```
reminders-mcp/
├── pyproject.toml
├── README.md
└── src/
    └── reminders_mcp/
        ├── __init__.py
        ├── server.py          # MCP server definition
        ├── store.py           # EventKit wrapper (singleton)
        ├── models.py          # Pydantic models for tool I/O
        └── converters.py      # EK* <-> Python type conversions
```

### Server Entry Point

```python
# server.py
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .store import ReminderStore

app = Server("reminders-mcp")
store = ReminderStore()

@app.tool()
async def list_reminder_lists() -> list[dict]:
    """Get all reminder lists."""
    return store.get_lists()

@app.tool()
async def get_reminders(
    list_id: str | None = None,
    include_completed: bool = False,
) -> list[dict]:
    """Get reminders, optionally filtered by list."""
    return store.get_reminders(list_id, include_completed)

# ... more tools ...

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## Future Enhancements

### If Apple Adds Section API

Monitor WWDC and EventKit release notes. If sections become available, add tools to manage them.

### Other Nice-to-Haves

- **Alarms**: `EKAlarm` for time-based or location-based alerts
- **Recurrence**: `EKRecurrenceRule` for repeating reminders
- **Location**: `EKStructuredLocation` for location-based reminders
- **Subtasks**: Parent/child relationships (iOS 17+ / macOS 14+)
- **Tags**: Available in newer OS versions
- **Attachments**: Images/files attached to reminders

---

## Testing Strategy

1. **Unit tests**: Mock EventKit objects, test converters and section parsing
2. **Integration tests**: Real EventKit calls against a test list (create list → add reminders → cleanup)
3. **Manual testing**: Verify sync with Reminders.app UI

```python
# Example integration test setup
import pytest

@pytest.fixture
def test_list(store):
    """Create a test list, yield it, then clean up."""
    list_obj = store.create_list("__MCP_TEST__")
    yield list_obj
    store.delete_list(list_obj.id)
```
