"""Base HTTP client for AAP API interactions."""
import time
try:
    from urllib3.util.retry import Retry
    import urllib3
except ImportError:
    from requests.packages.urllib3.util.retry import Retry
    import requests.packages.urllib3 as urllib3
import requests
from requests.adapters import HTTPAdapter
from .config import AAPConfig
from .constants import (
    DEFAULT_TIMEOUT,
    HTTP_UNAUTHORIZED,
    HTTP_FORBIDDEN,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_BAD_GATEWAY,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_GATEWAY_TIMEOUT
)
from .exceptions import AAPConnectionError, AAPAuthenticationError, AAPAPIError


class AAPHTTPClient:
    """Base HTTP client for AAP API interactions."""

    def __init__(self, config=None):
        self.config = config or AAPConfig()
        self.session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[
                HTTP_TOO_MANY_REQUESTS,
                HTTP_INTERNAL_SERVER_ERROR,
                HTTP_BAD_GATEWAY,
                HTTP_SERVICE_UNAVAILABLE,
                HTTP_GATEWAY_TIMEOUT
            ],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set timeout from config
        self.timeout = self.config.timeout

        # Disable SSL warnings for self-signed certificates
        import urllib3
        urllib3.disable_warnings()

    def _build_url(self, endpoint):
        """Build full URL for API endpoint."""
        base_url = self.config.base_url
        if not base_url:
            raise AAPConnectionError("No AAP host configured")
        return f"{base_url}{endpoint}"

    def _prepare_request(self, method, endpoint, **kwargs):
        """Prepare request with authentication and common settings."""
        url = self._build_url(endpoint)

        # Set authentication
        if self.config.auth_headers:
            headers = kwargs.get('headers', {})
            headers.update(self.config.auth_headers)
            kwargs['headers'] = headers
        elif self.config.auth_tuple:
            kwargs['auth'] = self.config.auth_tuple

        # Set timeout
        kwargs.setdefault('timeout', self.timeout)

        # Disable SSL verification for self-signed certificates
        kwargs.setdefault('verify', False)

        return method, url, kwargs

    def _handle_response(self, response):
        """Handle API response and raise appropriate exceptions."""
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == HTTP_UNAUTHORIZED:
                raise AAPAuthenticationError("Authentication failed")
            elif response.status_code == HTTP_FORBIDDEN:
                raise AAPAuthenticationError("Access denied")
            else:
                raise AAPAPIError(
                    f"API error: {response.status_code} - {response.text}",
                    status_code=response.status_code,
                    response=response
                )
        except requests.exceptions.ConnectionError as e:
            raise AAPConnectionError(f"Connection error: {e}")
        except requests.exceptions.Timeout as e:
            raise AAPConnectionError(f"Connection timeout: {e}")
        except requests.exceptions.RequestException as e:
            raise AAPConnectionError(f"Request error: {e}")

        return response

    def get(self, endpoint, **kwargs):
        """Make GET request."""
        method, url, kwargs = self._prepare_request('GET', endpoint, **kwargs)
        response = self.session.get(url, **kwargs)
        return self._handle_response(response)

    def post(self, endpoint, **kwargs):
        """Make POST request."""
        method, url, kwargs = self._prepare_request('POST', endpoint, **kwargs)
        response = self.session.post(url, **kwargs)
        return self._handle_response(response)

    def put(self, endpoint, **kwargs):
        """Make PUT request."""
        method, url, kwargs = self._prepare_request('PUT', endpoint, **kwargs)
        response = self.session.put(url, **kwargs)
        return self._handle_response(response)

    def patch(self, endpoint, **kwargs):
        """Make PATCH request."""
        method, url, kwargs = self._prepare_request('PATCH', endpoint, **kwargs)
        response = self.session.patch(url, **kwargs)
        return self._handle_response(response)

    def delete(self, endpoint, **kwargs):
        """Make DELETE request."""
        method, url, kwargs = self._prepare_request('DELETE', endpoint, **kwargs)
        response = self.session.delete(url, **kwargs)
        return self._handle_response(response)
