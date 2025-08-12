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
from aapclient.common.config import AAPConfig
from aapclient.common.constants import (
    DEFAULT_REQUEST_TIMEOUT,
    HTTP_UNAUTHORIZED,
    HTTP_FORBIDDEN,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_BAD_GATEWAY,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_GATEWAY_TIMEOUT
)
from aapclient.common.exceptions import AAPConnectionError, AAPAuthenticationError, AAPAPIError


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
        self.request_timeout = self.config.request_timeout

        # Configure SSL warnings based on verification setting
        if not self.config.validate_certs:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        kwargs.setdefault('timeout', self.request_timeout)

        # Set SSL verification based on configuration
        kwargs.setdefault('verify', self.config.ssl_verify_value)

        return method, url, kwargs

    def _handle_response(self, response):
        """Handle API response and raise appropriate exceptions."""
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            # Try to extract detailed error message from API response
            error_message = None
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    if 'detail' in error_data:
                        error_message = error_data['detail']
                    else:
                        # Handle field-specific errors (e.g., {"name": ["This field may not be blank."]})
                        field_errors = []
                        for field, errors in error_data.items():
                            if isinstance(errors, list):
                                for error in errors:
                                    field_errors.append(f"{field}: {error}")
                            else:
                                field_errors.append(f"{field}: {errors}")
                        if field_errors:
                            error_message = "\n".join(field_errors)
            except:
                pass  # If JSON parsing fails, use fallback messages

            if response.status_code == HTTP_UNAUTHORIZED:
                raise AAPAuthenticationError(error_message or "Authentication failed")
            elif response.status_code == HTTP_FORBIDDEN:
                raise AAPAuthenticationError(error_message or "Access denied")
            else:
                raise AAPAPIError(
                    error_message or f"API error: {response.status_code} - {response.text}",
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
