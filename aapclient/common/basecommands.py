"""Base command classes for AAP CLI commands."""
from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne
from aapclient.common.constants import (
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST,
    HTTP_UNAUTHORIZED,
    HTTP_FORBIDDEN
)
from aapclient.common.exceptions import AAPAPIError, AAPResourceNotFoundError


def _is_non_aap_host_error(api_error):
    """
    Check if API error indicates a non-AAP host.

    Args:
        api_error: AAPAPIError instance

    Returns:
        bool: True if error indicates non-AAP host, False otherwise
    """
    error_message = str(api_error).lower()

    # Check for HTML content indicators
    html_indicators = [
        "<!doctype html>",
        "<html",
        "</html>",
        "<head>",
        "<body>",
        "text/html",
        "content-type: text/html"
    ]

    # Check for specific non-AAP host messages
    non_aap_indicators = [
        "html response",
        "does not appear to be an aap instance",
        "received html response instead"
    ]

    all_indicators = html_indicators + non_aap_indicators
    return any(indicator in error_message for indicator in all_indicators)


class AAPCommandMixin:
    """
    Mixin providing centralized client access for AAP commands.

    Provides convenient properties to access AAP clients through the
    centralized client manager without repeating config/validation logic.

    Note: This mixin expects to be used with Cliff command classes that
    provide the 'app' attribute.
    """

    @property
    def client_manager(self):
        """Get the centralized client manager from the app."""
        # The 'app' attribute is provided by Cliff command base classes
        return self.app.client_manager  # type: ignore

    @property
    def controller_client(self):
        """Get Controller API client (shortcut)."""
        return self.client_manager.controller

    @property
    def gateway_client(self):
        """Get Gateway API client (shortcut)."""
        return self.client_manager.gateway

    @property
    def eda_client(self):
        """Get EDA API client (shortcut)."""
        return self.client_manager.eda

    @property
    def galaxy_client(self):
        """Get Galaxy API client (shortcut)."""
        return self.client_manager.galaxy

    def handle_api_error(self, api_error, resource_type, context):
        """
        Standardized API error handling for all commands.

        Args:
            api_error: AAPAPIError instance
            resource_type: String describing the resource (e.g., "Project", "Host")
            context: Context for the error (endpoint name or identifier)

        Raises:
            SystemExit: With appropriate error message
        """
        if api_error.status_code == HTTP_NOT_FOUND:
            # Check for specific error patterns indicating non-AAP hosts
            if _is_non_aap_host_error(api_error):
                raise SystemExit(
                    "Configuration error: The specified host does not appear to be an AAP instance. "
                    "Received HTML response instead of AAP API data. Please verify the AAP host URL."
                )
            else:
                # Standard AAP endpoint/resource not found
                raise AAPResourceNotFoundError(resource_type, context)
        elif api_error.status_code == HTTP_BAD_REQUEST:
            raise SystemExit(f"Bad request: {api_error}")
        elif api_error.status_code in [HTTP_UNAUTHORIZED, HTTP_FORBIDDEN]:
            raise SystemExit(f"Authentication error: {api_error}")
        else:
            raise SystemExit(f"API error: {api_error}")

    def handle_standard_exceptions(self):
        """
        Standard exception handling wrapper for command execution.
        Should be used in take_action methods after try/except blocks.
        """
        def exception_handler(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except AAPResourceNotFoundError as e:
                    raise SystemExit(str(e))
                except Exception as e:
                    raise SystemExit(f"Unexpected error: {e}")
            return wrapper
        return exception_handler


class AAPShowCommand(ShowOne, AAPCommandMixin):
    """Base class for AAP show commands with centralized client access."""
    pass


class AAPListCommand(Lister, AAPCommandMixin):
    """Base class for AAP list commands with centralized client access."""
    pass


class AAPCommand(Command, AAPCommandMixin):
    """Base class for AAP commands with centralized client access."""
    pass
