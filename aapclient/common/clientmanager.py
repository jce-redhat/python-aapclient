"""Client manager for AAP HTTP clients."""
from aapclient.common.client import AAPHTTPClient
from aapclient.common.config import AAPConfig


class AAPClientManager:
    """
    Centralized client manager for AAP HTTP clients.

    Provides lazy-loaded clients for different AAP APIs while maintaining
    a single configuration source. Follows OpenStack client patterns.
    """

    def __init__(self, config=None, config_overrides=None):
        """
        Initialize client manager.

        Args:
            config: AAPConfig instance. If None, will create and validate one.
            config_overrides: Dict of configuration overrides from command-line arguments.
        """
        if config is None:
            config = AAPConfig(config_overrides=config_overrides)
            config.validate()

        self.config = config
        self._controller_client = None
        self._gateway_client = None
        self._eda_client = None
        self._galaxy_client = None

    @property
    def controller(self):
        """Get Controller API client (lazy-loaded)."""
        if self._controller_client is None:
            self._controller_client = AAPHTTPClient(self.config)
        return self._controller_client

    @property
    def gateway(self):
        """Get Gateway API client (lazy-loaded)."""
        if self._gateway_client is None:
            self._gateway_client = AAPHTTPClient(self.config)
        return self._gateway_client

    @property
    def eda(self):
        """Get EDA API client (lazy-loaded)."""
        if self._eda_client is None:
            self._eda_client = AAPHTTPClient(self.config)
        return self._eda_client

    @property
    def galaxy(self):
        """Get Galaxy API client (lazy-loaded)."""
        if self._galaxy_client is None:
            self._galaxy_client = AAPHTTPClient(self.config)
        return self._galaxy_client

    def reset(self):
        """Reset all clients (useful for testing or config changes)."""
        self._controller_client = None
        self._gateway_client = None
        self._eda_client = None
        self._galaxy_client = None
