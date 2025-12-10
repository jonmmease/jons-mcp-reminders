"""Exceptions for MCP Server for macOS reminders."""


class ServerError(Exception):
    """Base exception for server errors.

    Attributes:
        message: Human-readable error description
        is_retryable: Whether the error might succeed on retry
    """

    def __init__(
        self,
        message: str,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.is_retryable = is_retryable

    def __str__(self) -> str:
        return self.message


class NotInitializedError(Exception):
    """Raised when the server is not properly initialized."""

    pass


# Reminders-specific exceptions


class RemindersError(Exception):
    """Base exception for Reminders MCP operations."""

    pass


class AccessDeniedError(RemindersError):
    """User hasn't granted Reminders access.

    To fix: Open System Settings > Privacy & Security > Reminders
    and grant access to this application.
    """

    def __init__(self, message: str | None = None) -> None:
        default_msg = (
            "Reminders access denied. Please grant access in "
            "System Settings > Privacy & Security > Reminders."
        )
        super().__init__(message or default_msg)


class PermissionTimeoutError(RemindersError):
    """Permission request timed out waiting for user response."""

    def __init__(self, timeout_seconds: int = 60) -> None:
        super().__init__(
            f"Permission request timed out after {timeout_seconds} seconds. "
            "Please respond to the permission dialog and try again."
        )
        self.timeout_seconds = timeout_seconds


class NotFoundError(RemindersError):
    """Reminder or list not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(f"{resource_type} not found: {resource_id}")
        self.resource_type = resource_type
        self.resource_id = resource_id


class NoWritableSourceError(RemindersError):
    """No writable calendar source available for reminders.

    This can happen if all calendar accounts are read-only or
    if no reminder accounts are configured.
    """

    def __init__(self) -> None:
        super().__init__(
            "No writable source available for reminders. "
            "Please configure a reminder account in System Settings > Internet Accounts."
        )


class EventKitError(RemindersError):
    """General EventKit operation error with NSError details."""

    def __init__(
        self,
        message: str,
        domain: str | None = None,
        code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.domain = domain
        self.code = code

    @classmethod
    def from_nserror(cls, error: object) -> "EventKitError":
        """Create from an NSError object."""
        if error is None:
            return cls("Unknown EventKit error")

        # Extract NSError details
        try:
            domain = str(error.domain()) if hasattr(error, "domain") else None
            code = int(error.code()) if hasattr(error, "code") else None
            description = (
                str(error.localizedDescription())
                if hasattr(error, "localizedDescription")
                else str(error)
            )
        except Exception:
            return cls(str(error))

        return cls(description, domain=domain, code=code)
