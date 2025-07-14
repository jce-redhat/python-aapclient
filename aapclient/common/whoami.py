"""Whoami command for getting current user information from AAP."""
from cliff.show import ShowOne
from .client import AAPHTTPClient
from .config import AAPConfig
from .constants import GATEWAY_API_VERSION_ENDPOINT, HTTP_OK
from .exceptions import AAPClientError


class WhoamiCommand(ShowOne):
    """Get current user information from AAP Gateway API."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        return parser

    def take_action(self, parsed_args):
        """Execute the whoami command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Get current user information from Gateway API me endpoint
            me_endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}me/"

            # Call the API
            response = client.get(me_endpoint)

            if response.status_code == HTTP_OK:
                data = response.json()

                # Gateway API returns paginated response with results array
                if 'results' not in data or not data['results']:
                    raise AAPClientError("No user data returned from API")

                user_data = data['results'][0]  # Get first (and only) user result

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # Basic User Information
                if 'id' in user_data:
                    columns.append('ID')
                    values.append(str(user_data['id']))

                if 'username' in user_data:
                    columns.append('Username')
                    values.append(user_data['username'])

                if 'email' in user_data:
                    columns.append('Email')
                    values.append(user_data['email'])

                # Name fields (only show if not empty)
                first_name = user_data.get('first_name', '').strip()
                last_name = user_data.get('last_name', '').strip()

                if first_name:
                    columns.append('First Name')
                    values.append(first_name)

                if last_name:
                    columns.append('Last Name')
                    values.append(last_name)

                # Permission flags
                if 'is_superuser' in user_data:
                    columns.append('Superuser')
                    values.append('Yes' if user_data['is_superuser'] else 'No')

                if 'is_platform_auditor' in user_data:
                    columns.append('Platform Auditor')
                    values.append('Yes' if user_data['is_platform_auditor'] else 'No')

                if 'managed' in user_data:
                    columns.append('Managed Account')
                    values.append('Yes' if user_data['managed'] else 'No')

                # Timestamps
                if 'last_login' in user_data and user_data['last_login']:
                    columns.append('Last Login')
                    values.append(user_data['last_login'])

                if 'created' in user_data:
                    columns.append('Account Created')
                    values.append(user_data['created'])

                if 'modified' in user_data:
                    columns.append('Last Modified')
                    values.append(user_data['modified'])

                return (columns, values)
            else:
                raise AAPClientError(f"Gateway API failed with status {response.status_code}")

        except AAPClientError as e:
            raise SystemExit(f"Configuration error: {e}")
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
