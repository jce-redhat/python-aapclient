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

        # Check if identifier is a positive integer
        is_positive_integer = False
        try:
            int_value = int(identifier)
            if int_value > 0:
                is_positive_integer = True
        except (ValueError, TypeError):
            pass

        if is_positive_integer:
            message = f"{resource_type} with ID or name of {identifier} not found"
        else:
            message = f"{resource_type} '{identifier}' not found"

        super().__init__(message)


class AAPAPIError(AAPClientError):
    """Exception raised when API returns an error."""

    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response
