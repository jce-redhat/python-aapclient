"""Base command classes for AAP CLI commands."""
from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne


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


class AAPShowCommand(ShowOne, AAPCommandMixin):
    """Base class for AAP show commands with centralized client access."""
    pass


class AAPListCommand(Lister, AAPCommandMixin):
    """Base class for AAP list commands with centralized client access."""
    pass


class AAPCommand(Command, AAPCommandMixin):
    """Base class for AAP commands with centralized client access."""
    pass
