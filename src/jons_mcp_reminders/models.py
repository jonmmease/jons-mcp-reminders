"""Pydantic models for Reminders MCP server."""

from datetime import datetime
from enum import Enum, IntEnum

from pydantic import BaseModel, Field, field_validator


class Priority(IntEnum):
    """Reminder priority levels matching Apple's EKReminderPriority.

    Values match the Apple Reminders app UI:
    - NONE (0): No priority flag
    - HIGH (1): !!! in UI
    - MEDIUM (5): !! in UI
    - LOW (9): ! in UI
    """

    NONE = 0
    HIGH = 1
    MEDIUM = 5
    LOW = 9


class Proximity(str, Enum):
    """Trigger proximity for location-based reminders.

    Maps to EKAlarmProximity constants:
    - ENTER: Trigger when arriving at the location
    - LEAVE: Trigger when departing from the location
    """

    ENTER = "enter"
    LEAVE = "leave"


class LocationTrigger(BaseModel):
    """Location trigger for a reminder alarm.

    Creates a geofence that triggers the reminder when the user
    enters or leaves the specified location.
    """

    title: str = Field(description="Display name for the location (e.g., 'Home', 'Work')")
    latitude: float = Field(description="Latitude coordinate (-90 to 90)")
    longitude: float = Field(description="Longitude coordinate (-180 to 180)")
    radius: float = Field(
        default=100.0,
        description="Geofence radius in meters (default 100m)",
    )
    proximity: Proximity = Field(
        default=Proximity.ENTER,
        description="When to trigger: 'enter' or 'leave' the location",
    )

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is in valid range."""
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is in valid range."""
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, v: float) -> float:
        """Validate radius is positive and reasonable."""
        if v <= 0:
            raise ValueError("Radius must be positive")
        if v > 10000:
            raise ValueError("Radius cannot exceed 10,000 meters (10km)")
        return v


class ReminderList(BaseModel):
    """A Reminders list (calendar in EventKit terms)."""

    id: str = Field(description="Unique identifier for the list")
    title: str = Field(description="Display title of the list")
    color: str | None = Field(
        default=None, description="Hex color code (e.g., #FF5733)"
    )
    is_default: bool = Field(
        default=False, description="Whether this is the default list for new reminders"
    )

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        """Validate hex color format."""
        if v is None:
            return None
        v = v.strip()
        if not v.startswith("#"):
            v = f"#{v}"
        # Remove # and validate hex digits
        hex_part = v[1:]
        if len(hex_part) not in (3, 6):
            raise ValueError("Color must be 3 or 6 hex digits")
        try:
            int(hex_part, 16)
        except ValueError as e:
            raise ValueError("Color must contain valid hex digits") from e
        # Normalize to 6 digits uppercase
        if len(hex_part) == 3:
            hex_part = "".join(c * 2 for c in hex_part)
        return f"#{hex_part.upper()}"


class Reminder(BaseModel):
    """A reminder item."""

    id: str = Field(description="Unique identifier for the reminder")
    title: str = Field(description="Title/name of the reminder")
    list_id: str = Field(description="ID of the list this reminder belongs to")
    notes: str | None = Field(default=None, description="Additional notes/description")
    url: str | None = Field(default=None, description="Associated URL")
    is_completed: bool = Field(
        default=False, description="Whether the reminder is done"
    )
    completion_date: datetime | None = Field(
        default=None, description="When the reminder was completed"
    )
    due_date: datetime | None = Field(
        default=None, description="Due date/time for the reminder"
    )
    start_date: datetime | None = Field(
        default=None, description="Start date for the reminder"
    )
    priority: Priority = Field(
        default=Priority.NONE,
        description="Priority level (0=none, 1=high, 5=medium, 9=low)",
    )
    creation_date: datetime | None = Field(
        default=None, description="When the reminder was created"
    )
    last_modified_date: datetime | None = Field(
        default=None, description="When the reminder was last modified"
    )
    location: LocationTrigger | None = Field(
        default=None, description="Location-based trigger for this reminder"
    )


class BatchResult(BaseModel):
    """Result of a batch operation."""

    successes: int = Field(description="Number of successful operations")
    failures: int = Field(description="Number of failed operations")
    failed_ids: list[str] = Field(
        default_factory=list, description="IDs of items that failed"
    )
    errors: list[str] = Field(
        default_factory=list, description="Error messages for failed operations"
    )

    @property
    def total(self) -> int:
        """Total number of items processed."""
        return self.successes + self.failures

    @property
    def all_succeeded(self) -> bool:
        """Whether all operations succeeded."""
        return self.failures == 0


class CreateReminderInput(BaseModel):
    """Input for creating a reminder."""

    title: str = Field(description="Title of the reminder")
    list_id: str | None = Field(
        default=None, description="List to add to (uses default if not specified)"
    )
    notes: str | None = Field(default=None, description="Additional notes")
    url: str | None = Field(default=None, description="Associated URL")
    due_date: datetime | None = Field(default=None, description="Due date/time")
    start_date: datetime | None = Field(default=None, description="Start date")
    priority: Priority = Field(default=Priority.NONE, description="Priority level")
    location: LocationTrigger | None = Field(
        default=None, description="Location trigger for the reminder"
    )


class UpdateReminderInput(BaseModel):
    """Input for updating a reminder (all fields optional)."""

    title: str | None = Field(default=None, description="New title")
    notes: str | None = Field(default=None, description="New notes")
    url: str | None = Field(default=None, description="New URL")
    due_date: datetime | None = Field(default=None, description="New due date")
    start_date: datetime | None = Field(default=None, description="New start date")
    priority: Priority | None = Field(default=None, description="New priority")
