"""Configuration management for AAP client."""
import os
from dotenv import load_dotenv
from aapclient.common.constants import DEFAULT_REQUEST_TIMEOUT, DEFAULT_VALIDATE_CERTS
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
                             Keys can be 'hostname', 'username', 'password', 'token', 'request_timeout',
                             'validate_certs', 'ca_bundle'.
        """
        overrides = config_overrides or {}

        # Apply overrides with precedence: command-line > environment variables
        self.hostname = overrides.get('hostname') or os.getenv('AAP_HOSTNAME')
        self.username = overrides.get('username') or os.getenv('AAP_USERNAME')
        self.password = overrides.get('password') or os.getenv('AAP_PASSWORD')
        self.token = overrides.get('token') or os.getenv('AAP_TOKEN')
        self._request_timeout = overrides.get('request_timeout') or os.getenv('AAP_REQUEST_TIMEOUT')

        # Handle validate_certs carefully to preserve False values
        if 'validate_certs' in overrides:
            self._validate_certs = overrides['validate_certs']
        else:
            self._validate_certs = os.getenv('AAP_VALIDATE_CERTS')

        self.ca_bundle = overrides.get('ca_bundle') or os.getenv('AAP_CA_BUNDLE')

    def validate(self):
        """Validate configuration."""
        if not self.hostname:
            raise AAPClientError("AAP_HOSTNAME environment variable or --hostname argument is required")

        if not (self.token or (self.username and self.password)):
            raise AAPClientError(
                "Either AAP_TOKEN/--token or both AAP_USERNAME/--username and AAP_PASSWORD/--password are required"
            )

    @property
    def base_url(self):
        """Get base URL for AAP."""
        if not self.hostname:
            return None

        # AAP_HOSTNAME must be a full URL with scheme
        if not self.hostname.startswith(('http://', 'https://')):
            raise AAPClientError(
                f"AAP_HOSTNAME must be a full URL with scheme (http:// or https://), "
                f"got: {self.hostname}"
            )

        return self.hostname.rstrip('/')

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
    def request_timeout(self):
        """Get connection timeout."""
        if self._request_timeout:
            try:
                return int(self._request_timeout)
            except ValueError:
                return DEFAULT_REQUEST_TIMEOUT
        return DEFAULT_REQUEST_TIMEOUT

    @property
    def validate_certs(self):
        """Get SSL verification setting."""
        if self._validate_certs is not None:
            # Handle string values from environment variables
            if isinstance(self._validate_certs, str):
                return self._validate_certs.lower() in ('true', '1', 'yes', 'on')
            # Handle boolean values from command-line overrides
            return bool(self._validate_certs)
        # Default to DEFAULT_VALIDATE_CERTS (verify SSL certificates)
        return DEFAULT_VALIDATE_CERTS

    @property
    def ssl_verify_value(self):
        """Get SSL verification value for requests library."""
        if not self.validate_certs:
            return False
        if self.ca_bundle:
            return self.ca_bundle
        return True
