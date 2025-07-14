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


class AAPResourceNotFoundError(AAPClientError):
    """Exception raised when a resource is not found."""

    def __init__(self, resource_type, identifier):
        """Initialize with resource type and identifier.

        Args:
            resource_type (str): The type of resource (e.g., 'Organization', 'Project')
            identifier (str): The resource identifier (name, ID, etc.)
        """
        self.resource_type = resource_type
        self.identifier = identifier
        message = f"{resource_type} '{identifier}' not found"
        super().__init__(message)


class AAPAPIError(AAPClientError):
    """Exception raised when API returns an error."""

    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
