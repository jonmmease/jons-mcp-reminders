"""Integration tests for the Reminders MCP server.

These tests require Reminders access to be granted in System Settings.
They create a test list called __MCP_TEST__ and clean up after each test.
"""

import asyncio
import uuid

import pytest

from src.jons_mcp_reminders.exceptions import AccessDeniedError, NotFoundError
from src.jons_mcp_reminders.models import LocationTrigger, Priority, Proximity
from src.jons_mcp_reminders.store import ReminderStore
from src.jons_mcp_reminders.tools.batch import add_reminders, complete_reminders, delete_reminders
from src.jons_mcp_reminders.tools.lists import (
    create_reminder_list,
    delete_reminder_list,
    get_reminder_list,
    list_reminder_lists,
    update_reminder_list,
)
from src.jons_mcp_reminders.tools.reminders import (
    complete_reminder,
    create_reminder,
    delete_reminder,
    get_reminder,
    get_reminders,
    move_reminder,
    update_reminder,
)
from src.jons_mcp_reminders.tools.search import search_reminders


# Test list name
TEST_LIST_NAME = "__MCP_TEST__"


def _can_access_reminders() -> bool:
    """Check if Reminders access is available."""
    try:
        ReminderStore.get_instance()
        return True
    except (AccessDeniedError, Exception):
        return False


# Skip all tests if Reminders access is not granted
pytestmark = pytest.mark.skipif(
    not _can_access_reminders(),
    reason="Reminders access not granted. Enable in System Settings > Privacy & Security > Reminders",
)


@pytest.fixture
async def test_list():
    """Create a test list and clean it up after the test."""
    # Create test list with unique suffix to avoid conflicts
    suffix = uuid.uuid4().hex[:8]
    list_name = f"{TEST_LIST_NAME}_{suffix}"

    test_list = await create_reminder_list(list_name, "#FF5733")

    yield test_list

    # Cleanup: delete the test list (and all reminders in it)
    try:
        await delete_reminder_list(test_list.id)
    except NotFoundError:
        pass  # Already deleted


@pytest.mark.integration
async def test_list_reminder_lists(test_list):
    """Test that list_reminder_lists returns the test list."""
    result = await list_reminder_lists()
    lists = result["lists"]

    assert len(lists) > 0
    list_ids = [lst.id for lst in lists]
    assert test_list.id in list_ids


@pytest.mark.integration
async def test_get_reminder_list(test_list):
    """Test getting a specific list by ID."""
    fetched = await get_reminder_list(test_list.id)

    assert fetched.id == test_list.id
    assert TEST_LIST_NAME in fetched.title


@pytest.mark.integration
async def test_update_reminder_list(test_list):
    """Test updating a list's properties."""
    new_title = f"{test_list.title}_updated"
    updated = await update_reminder_list(test_list.id, title=new_title)

    assert updated.title == new_title


@pytest.mark.integration
async def test_create_and_get_reminder(test_list):
    """Test creating a reminder and getting it back."""
    reminder = await create_reminder(
        title="Test Reminder",
        list_id=test_list.id,
        notes="Test notes",
        priority=Priority.HIGH,
    )

    assert reminder.title == "Test Reminder"
    assert reminder.list_id == test_list.id
    assert reminder.notes == "Test notes"
    assert reminder.priority == Priority.HIGH
    assert not reminder.is_completed

    # Get it back
    fetched = await get_reminder(reminder.id)
    assert fetched.id == reminder.id
    assert fetched.title == "Test Reminder"


@pytest.mark.integration
async def test_update_reminder(test_list):
    """Test updating a reminder's fields."""
    reminder = await create_reminder(
        title="Update Test",
        list_id=test_list.id,
    )

    updated = await update_reminder(
        reminder.id,
        title="Updated Title",
        notes="New notes",
        priority=Priority.MEDIUM,
    )

    assert updated.title == "Updated Title"
    assert updated.notes == "New notes"
    assert updated.priority == Priority.MEDIUM


@pytest.mark.integration
async def test_complete_reminder(test_list):
    """Test marking a reminder as complete/incomplete."""
    reminder = await create_reminder(
        title="Complete Test",
        list_id=test_list.id,
    )

    # Mark as complete
    completed = await complete_reminder(reminder.id, completed=True)
    assert completed.is_completed

    # Mark as incomplete
    uncompleted = await complete_reminder(reminder.id, completed=False)
    assert not uncompleted.is_completed


@pytest.mark.integration
async def test_delete_reminder(test_list):
    """Test deleting a reminder."""
    reminder = await create_reminder(
        title="Delete Test",
        list_id=test_list.id,
    )

    result = await delete_reminder(reminder.id)
    assert result is True

    # Verify it's gone
    with pytest.raises(NotFoundError):
        await get_reminder(reminder.id)


@pytest.mark.integration
async def test_move_reminder():
    """Test moving a reminder between lists."""
    # Create two lists
    suffix = uuid.uuid4().hex[:8]
    list1 = await create_reminder_list(f"{TEST_LIST_NAME}_source_{suffix}")
    list2 = await create_reminder_list(f"{TEST_LIST_NAME}_target_{suffix}")

    try:
        reminder = await create_reminder(
            title="Move Test",
            list_id=list1.id,
        )

        assert reminder.list_id == list1.id

        # Move to second list
        moved = await move_reminder(reminder.id, list2.id)
        assert moved.list_id == list2.id

    finally:
        # Cleanup both lists
        try:
            await delete_reminder_list(list1.id)
        except NotFoundError:
            pass
        try:
            await delete_reminder_list(list2.id)
        except NotFoundError:
            pass


@pytest.mark.integration
async def test_get_reminders_with_filters(test_list):
    """Test getting reminders with various filters."""
    # Create some reminders
    await create_reminder(title="Filter Test 1", list_id=test_list.id)
    await create_reminder(title="Filter Test 2", list_id=test_list.id)
    reminder3 = await create_reminder(title="Filter Test 3", list_id=test_list.id)
    await complete_reminder(reminder3.id)

    # Get incomplete reminders from test list
    result = await get_reminders(list_id=test_list.id, include_completed=False)
    incomplete = result["reminders"]
    assert len(incomplete) >= 2

    # Get all reminders including completed
    result = await get_reminders(list_id=test_list.id, include_completed=True)
    all_reminders = result["reminders"]
    assert len(all_reminders) >= 3


@pytest.mark.integration
async def test_batch_add_reminders(test_list):
    """Test adding multiple reminders at once."""
    items = ["Batch Item 1", "Batch Item 2", "Batch Item 3"]
    result = await add_reminders(test_list.id, items)
    created = result["reminders"]

    assert len(created) == 3
    titles = [r.title for r in created]
    for item in items:
        assert item in titles


@pytest.mark.integration
async def test_batch_complete_reminders(test_list):
    """Test completing multiple reminders at once."""
    # Create some reminders
    r1 = await create_reminder(title="Batch Complete 1", list_id=test_list.id)
    r2 = await create_reminder(title="Batch Complete 2", list_id=test_list.id)

    result = await complete_reminders([r1.id, r2.id])

    assert result.successes == 2
    assert result.failures == 0
    assert result.all_succeeded


@pytest.mark.integration
async def test_batch_delete_reminders(test_list):
    """Test deleting multiple reminders at once."""
    # Create some reminders
    r1 = await create_reminder(title="Batch Delete 1", list_id=test_list.id)
    r2 = await create_reminder(title="Batch Delete 2", list_id=test_list.id)

    result = await delete_reminders([r1.id, r2.id])

    assert result.successes == 2
    assert result.failures == 0


@pytest.mark.integration
async def test_search_reminders(test_list):
    """Test searching reminders by title/notes."""
    await create_reminder(
        title="Searchable Reminder",
        list_id=test_list.id,
        notes="Contains search term: FINDME",
    )
    await create_reminder(
        title="Another Reminder",
        list_id=test_list.id,
    )

    # Search by title
    result = await search_reminders("Searchable", list_id=test_list.id)
    by_title = result["reminders"]
    assert len(by_title) >= 1
    assert "Searchable" in by_title[0].title

    # Search by notes
    result = await search_reminders("FINDME", list_id=test_list.id)
    by_notes = result["reminders"]
    assert len(by_notes) >= 1


@pytest.mark.integration
async def test_pagination(test_list):
    """Test pagination with limit and offset."""
    # Create 5 reminders
    items = [f"Pagination Test {i}" for i in range(5)]
    await add_reminders(test_list.id, items)

    # Get first 2
    result = await get_reminders(list_id=test_list.id, limit=2, offset=0)
    first_batch = result["reminders"]
    assert len(first_batch) == 2

    # Get next 2
    result = await get_reminders(list_id=test_list.id, limit=2, offset=2)
    second_batch = result["reminders"]
    assert len(second_batch) == 2

    # Verify different items
    first_ids = {r.id for r in first_batch}
    second_ids = {r.id for r in second_batch}
    assert first_ids.isdisjoint(second_ids)


# Location-based reminder tests


@pytest.mark.integration
async def test_create_reminder_with_location(test_list):
    """Test creating a reminder with a location trigger."""
    location = LocationTrigger(
        title="Test Location",
        latitude=37.7749,
        longitude=-122.4194,
        radius=150.0,
        proximity=Proximity.ENTER,
    )

    reminder = await create_reminder(
        title="Location Test Reminder",
        list_id=test_list.id,
        location=location,
    )

    assert reminder.title == "Location Test Reminder"
    assert reminder.location is not None
    assert reminder.location.title == "Test Location"
    assert abs(reminder.location.latitude - 37.7749) < 0.0001
    assert abs(reminder.location.longitude - (-122.4194)) < 0.0001
    assert reminder.location.radius == pytest.approx(150.0, abs=1.0)
    assert reminder.location.proximity == Proximity.ENTER


@pytest.mark.integration
async def test_create_reminder_with_leave_proximity(test_list):
    """Test creating a reminder with leave proximity."""
    location = LocationTrigger(
        title="Leave Location",
        latitude=40.7128,
        longitude=-74.0060,
        proximity=Proximity.LEAVE,
    )

    reminder = await create_reminder(
        title="Leave Proximity Test",
        list_id=test_list.id,
        location=location,
    )

    assert reminder.location is not None
    assert reminder.location.proximity == Proximity.LEAVE


@pytest.mark.integration
async def test_update_reminder_add_location(test_list):
    """Test adding a location to an existing reminder."""
    # Create reminder without location
    reminder = await create_reminder(
        title="Add Location Test",
        list_id=test_list.id,
    )
    assert reminder.location is None

    # Add location via update
    location = LocationTrigger(
        title="Added Location",
        latitude=51.5074,
        longitude=-0.1278,
        radius=200.0,
    )

    updated = await update_reminder(reminder.id, location=location)

    assert updated.location is not None
    assert updated.location.title == "Added Location"
    assert abs(updated.location.latitude - 51.5074) < 0.0001


@pytest.mark.integration
async def test_update_reminder_change_location(test_list):
    """Test changing a reminder's location."""
    location1 = LocationTrigger(
        title="First Location",
        latitude=37.0,
        longitude=-122.0,
    )

    reminder = await create_reminder(
        title="Change Location Test",
        list_id=test_list.id,
        location=location1,
    )
    assert reminder.location.title == "First Location"

    # Change to new location
    location2 = LocationTrigger(
        title="Second Location",
        latitude=38.0,
        longitude=-123.0,
        radius=300.0,
    )

    updated = await update_reminder(reminder.id, location=location2)

    assert updated.location is not None
    assert updated.location.title == "Second Location"
    assert abs(updated.location.latitude - 38.0) < 0.0001


@pytest.mark.integration
async def test_update_reminder_clear_location(test_list):
    """Test removing a location from a reminder."""
    location = LocationTrigger(
        title="To Be Removed",
        latitude=35.6762,
        longitude=139.6503,
    )

    reminder = await create_reminder(
        title="Clear Location Test",
        list_id=test_list.id,
        location=location,
    )
    assert reminder.location is not None

    # Clear the location
    updated = await update_reminder(reminder.id, clear_location=True)
    assert updated.location is None


@pytest.mark.integration
async def test_get_reminder_includes_location(test_list):
    """Test that get_reminder returns location data."""
    location = LocationTrigger(
        title="Get Test Location",
        latitude=48.8566,
        longitude=2.3522,
        radius=250.0,
        proximity=Proximity.ENTER,
    )

    reminder = await create_reminder(
        title="Get Location Test",
        list_id=test_list.id,
        location=location,
    )

    # Fetch fresh
    fetched = await get_reminder(reminder.id)

    assert fetched.location is not None
    assert fetched.location.title == "Get Test Location"
    assert abs(fetched.location.latitude - 48.8566) < 0.0001
    assert fetched.location.radius == pytest.approx(250.0, abs=1.0)
