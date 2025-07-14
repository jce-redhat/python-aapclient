"""Custom exceptions for AAP client."""


class AAPClientError(Exception):
    """Base exception for AAP client errors."""
    pass


class AAPConnectionError(AAPClientError):
    """Exception raised when connection to AAP fails."""
    pass


class AAPAuthenticationError(AAPClientError):
    """Exception raised when authentication fails."""
    pass


class AAPAPIError(AAPClientError):
    """Exception raised when API returns an error."""

    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
