"""Configuration management for AAP client."""
import os
from dotenv import load_dotenv
from aapclient.common.constants import AAP_HOST, AAP_USERNAME, AAP_PASSWORD, AAP_TOKEN, AAP_TIMEOUT, AAP_VERIFY_SSL, AAP_CA_BUNDLE, DEFAULT_TIMEOUT, DEFAULT_VERIFY_SSL
from aapclient.common.exceptions import AAPClientError

# Load environment variables from .env file
load_dotenv()


class AAPConfig:
    """Configuration class for AAP client."""

    def __init__(self, config_overrides=None):
        """
        Initialize configuration.

        Args:
            config_overrides: Dict of configuration overrides from command-line arguments.
                             Keys can be 'host', 'username', 'password', 'token', 'timeout',
                             'verify_ssl', 'ca_bundle'.
        """
        overrides = config_overrides or {}

        # Apply overrides with precedence: command-line > environment variables
        self.host = overrides.get('host') or os.getenv(AAP_HOST)
        self.username = overrides.get('username') or os.getenv(AAP_USERNAME)
        self.password = overrides.get('password') or os.getenv(AAP_PASSWORD)
        self.token = overrides.get('token') or os.getenv(AAP_TOKEN)
        self._timeout = overrides.get('timeout') or os.getenv(AAP_TIMEOUT)

        # Handle verify_ssl carefully to preserve False values
        if 'verify_ssl' in overrides:
            self._verify_ssl = overrides['verify_ssl']
        else:
            self._verify_ssl = os.getenv(AAP_VERIFY_SSL)

        self.ca_bundle = overrides.get('ca_bundle') or os.getenv(AAP_CA_BUNDLE)

    def validate(self):
        """Validate configuration."""
        if not self.host:
            raise AAPClientError("AAP_HOST environment variable or --aap-host argument is required")

        if not (self.token or (self.username and self.password)):
            raise AAPClientError(
                "Either AAP_TOKEN/--aap-token or both AAP_USERNAME/--aap-username and AAP_PASSWORD/--aap-password are required"
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

    @property
    def verify_ssl(self):
        """Get SSL verification setting."""
        if self._verify_ssl is not None:
            # Handle string values from environment variables
            if isinstance(self._verify_ssl, str):
                return self._verify_ssl.lower() in ('true', '1', 'yes', 'on')
            # Handle boolean values from command-line overrides
            return bool(self._verify_ssl)
        # Default to DEFAULT_VERIFY_SSL (verify SSL certificates)
        return DEFAULT_VERIFY_SSL

    @property
    def ssl_verify_value(self):
        """Get SSL verification value for requests library."""
        if not self.verify_ssl:
            return False
        if self.ca_bundle:
            return self.ca_bundle
        return True
