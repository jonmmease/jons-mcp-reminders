"""Converter functions for EventKit <-> Python types."""

from datetime import datetime
from typing import Any

from AppKit import NSColor
from CoreLocation import CLLocation
from EventKit import (
    EKAlarm,
    EKAlarmProximityEnter,
    EKAlarmProximityLeave,
    EKAlarmProximityNone,
    EKStructuredLocation,
)
from Foundation import NSURL, NSDate, NSDateComponents
from Quartz import CGColorGetComponents, CGColorGetNumberOfComponents

from .models import LocationTrigger, Priority, Proximity

# Magic constant for "not set" in NSDateComponents
NSUndefinedDateComponent = 0x7FFFFFFF  # NSIntegerMax


# Date/Time Conversions


def datetime_to_nsdate(dt: datetime) -> NSDate:
    """Convert Python datetime to NSDate."""
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def nsdate_to_datetime(nsdate: Any) -> datetime | None:
    """Convert NSDate to Python datetime."""
    if nsdate is None:
        return None
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970())


def datetime_to_components(dt: datetime) -> NSDateComponents:
    """Convert Python datetime to NSDateComponents for due dates."""
    components = NSDateComponents.alloc().init()
    components.setYear_(dt.year)
    components.setMonth_(dt.month)
    components.setDay_(dt.day)
    components.setHour_(dt.hour)
    components.setMinute_(dt.minute)
    components.setSecond_(dt.second)
    return components


def components_to_datetime(components: Any) -> datetime | None:
    """Convert NSDateComponents to Python datetime.

    Returns None if components is None or year is undefined.
    """
    if components is None:
        return None

    year = components.year()
    if year == NSUndefinedDateComponent:
        return None

    # Handle undefined time components - default to 0
    month = components.month()
    day = components.day()
    hour = components.hour()
    minute = components.minute()
    second = components.second()

    # If any date component is undefined, we can't construct a datetime
    if month == NSUndefinedDateComponent or day == NSUndefinedDateComponent:
        return None

    return datetime(
        year=year,
        month=month,
        day=day,
        hour=hour if hour != NSUndefinedDateComponent else 0,
        minute=minute if minute != NSUndefinedDateComponent else 0,
        second=second if second != NSUndefinedDateComponent else 0,
    )


# Color Conversions


def hex_to_cgcolor(hex_string: str) -> Any:
    """Convert hex color string to CGColor for EKCalendar.

    Args:
        hex_string: Hex color like "#FF5733" or "FF5733"

    Returns:
        CGColor object suitable for EKCalendar.CGColor
    """
    hex_string = hex_string.lstrip("#")
    if len(hex_string) == 3:
        hex_string = "".join(c * 2 for c in hex_string)

    r = int(hex_string[0:2], 16) / 255.0
    g = int(hex_string[2:4], 16) / 255.0
    b = int(hex_string[4:6], 16) / 255.0

    nscolor = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, 1.0)
    return nscolor.CGColor()


def cgcolor_to_hex(cgcolor: Any) -> str | None:
    """Convert CGColor back to hex string.

    Note: Colors may shift ~30 units per RGB channel during iCloud sync
    due to color space conversion. This is expected behavior.

    Args:
        cgcolor: CGColor object from EKCalendar

    Returns:
        Hex string like "#FF5733" or None if conversion fails
    """
    if cgcolor is None:
        return None

    num_components = CGColorGetNumberOfComponents(cgcolor)
    components = CGColorGetComponents(cgcolor)

    if num_components >= 3:
        # RGB color
        r = int(components[0] * 255)
        g = int(components[1] * 255)
        b = int(components[2] * 255)
        return f"#{r:02X}{g:02X}{b:02X}"
    elif num_components == 2:
        # Grayscale - convert to RGB (gray, gray, gray)
        gray = int(components[0] * 255)
        return f"#{gray:02X}{gray:02X}{gray:02X}"

    return None


# EKReminder -> dict conversion


def ek_reminder_to_dict(reminder: Any) -> dict[str, Any]:
    """Convert EKReminder to Python dict.

    IMPORTANT: Call this INSIDE the worker thread to prevent
    thread-affinity issues with ObjC proxies.

    Args:
        reminder: EKReminder instance

    Returns:
        Dict with reminder fields as pure Python types
    """
    # Get URL as string if present
    url = reminder.URL()
    url_str = str(url.absoluteString()) if url else None

    # Get priority as enum
    priority_val = reminder.priority()
    try:
        priority = Priority(priority_val)
    except ValueError:
        priority = Priority.NONE

    return {
        "id": reminder.calendarItemExternalIdentifier(),
        "title": str(reminder.title()) if reminder.title() else "",
        "list_id": reminder.calendar().calendarIdentifier(),
        "notes": str(reminder.notes()) if reminder.notes() else None,
        "url": url_str,
        "is_completed": bool(reminder.isCompleted()),
        "completion_date": nsdate_to_datetime(reminder.completionDate()),
        "due_date": components_to_datetime(reminder.dueDateComponents()),
        "start_date": components_to_datetime(reminder.startDateComponents()),
        "priority": priority,
        "creation_date": nsdate_to_datetime(reminder.creationDate()),
        "last_modified_date": nsdate_to_datetime(reminder.lastModifiedDate()),
        "location": extract_location_from_reminder(reminder),
    }


def ek_calendar_to_dict(calendar: Any, is_default: bool = False) -> dict[str, Any]:
    """Convert EKCalendar (reminder list) to Python dict.

    IMPORTANT: Call this INSIDE the worker thread to prevent
    thread-affinity issues with ObjC proxies.

    Args:
        calendar: EKCalendar instance
        is_default: Whether this is the default calendar for new reminders

    Returns:
        Dict with calendar fields as pure Python types
    """
    return {
        "id": calendar.calendarIdentifier(),
        "title": str(calendar.title()) if calendar.title() else "",
        "color": cgcolor_to_hex(calendar.CGColor()),
        "is_default": is_default,
    }


# Helper for URL conversion


def str_to_nsurl(url_string: str) -> Any:
    """Convert string URL to NSURL."""
    return NSURL.URLWithString_(url_string)


# Location/Alarm Conversions


def location_trigger_to_ek_alarm(location: LocationTrigger) -> Any:
    """Convert LocationTrigger to EKAlarm with structured location.

    Creates an EKAlarm configured for location-based triggering:
    - EKStructuredLocation with title and CLLocation (lat/lng/radius)
    - Proximity setting (enter or leave)

    Args:
        location: LocationTrigger with lat/lng/radius/proximity

    Returns:
        EKAlarm configured for location-based notification
    """
    # Create CLLocation with coordinates
    cl_location = CLLocation.alloc().initWithLatitude_longitude_(
        location.latitude,
        location.longitude,
    )

    # Create EKStructuredLocation
    structured_location = EKStructuredLocation.locationWithTitle_(location.title)
    structured_location.setGeoLocation_(cl_location)
    structured_location.setRadius_(location.radius)

    # Create alarm using alloc/init for location-only alarms
    # (alarmWithAbsoluteDate_ requires a non-nil date)
    alarm = EKAlarm.alloc().init()
    alarm.setStructuredLocation_(structured_location)

    # Set proximity (enter or leave)
    if location.proximity == Proximity.LEAVE:
        alarm.setProximity_(EKAlarmProximityLeave)
    else:
        alarm.setProximity_(EKAlarmProximityEnter)

    return alarm


def extract_location_from_reminder(reminder: Any) -> dict[str, Any] | None:
    """Extract location alarm data from an EKReminder.

    Searches through alarms for a location-based alarm and extracts
    its structured location data.

    Args:
        reminder: EKReminder instance

    Returns:
        Dict with location fields or None if no location alarm exists
    """
    alarms = reminder.alarms()
    if not alarms:
        return None

    for alarm in alarms:
        structured_location = alarm.structuredLocation()
        if structured_location is None:
            continue

        proximity = alarm.proximity()
        if proximity == EKAlarmProximityNone:
            continue

        # Get geo coordinates
        geo_location = structured_location.geoLocation()
        if geo_location is None:
            continue

        title = structured_location.title()
        radius = structured_location.radius()

        # Map proximity constant to string
        proximity_str = "leave" if proximity == EKAlarmProximityLeave else "enter"

        return {
            "title": str(title) if title else "Location",
            "latitude": geo_location.coordinate().latitude,
            "longitude": geo_location.coordinate().longitude,
            "radius": float(radius) if radius > 0 else 100.0,
            "proximity": proximity_str,
        }

    return None
