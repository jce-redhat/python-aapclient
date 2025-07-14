"""Configuration management for AAP client."""
import os
from dotenv import load_dotenv
from .constants import AAP_HOST, AAP_USERNAME, AAP_PASSWORD, AAP_TOKEN, AAP_TIMEOUT, DEFAULT_TIMEOUT
from .exceptions import AAPClientError

# Load environment variables from .env file
load_dotenv()


class AAPConfig:
    """Configuration class for AAP client."""

    def __init__(self):
        self.host = os.getenv(AAP_HOST)
        self.username = os.getenv(AAP_USERNAME)
        self.password = os.getenv(AAP_PASSWORD)
        self.token = os.getenv(AAP_TOKEN)
        self._timeout = os.getenv(AAP_TIMEOUT)

    def validate(self):
        """Validate configuration."""
        if not self.host:
            raise AAPClientError("AAP_HOST environment variable is required")

        if not (self.token or (self.username and self.password)):
            raise AAPClientError(
                "Either AAP_TOKEN or both AAP_USERNAME and AAP_PASSWORD are required"
            )

    @property
    def base_url(self):
        """Get base URL for AAP."""
        if not self.host:
            return None

        # AAP_HOST must be a full URL with scheme
        if not self.host.startswith(('http://', 'https://')):
            raise AAPClientError(
                f"AAP_HOST must be a full URL with scheme (http:// or https://), "
                f"got: {self.host}"
            )

        return self.host.rstrip('/')

    @property
    def auth_headers(self):
        """Get authentication headers."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    @property
    def auth_tuple(self):
        """Get authentication tuple for requests."""
        if self.username and self.password:
            return (self.username, self.password)
        return None

    @property
    def timeout(self):
        """Get connection timeout."""
        if self._timeout:
            try:
                return int(self._timeout)
            except ValueError:
                return DEFAULT_TIMEOUT
        return DEFAULT_TIMEOUT
