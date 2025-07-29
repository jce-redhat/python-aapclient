"""Token commands."""

from aapclient.common.basecommands import AAPShowCommand, AAPListCommand, AAPCommand
from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST,
    HTTP_ACCEPTED
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import format_datetime


def _format_token_data(token_data, use_utc=False):
    """
    Format token data consistently

    Args:
        token_data (dict): Token data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract token details
    id_value = token_data.get('id', '')
    description = token_data.get('description', '')
    scope = token_data.get('scope', '')
    token_value = token_data.get('token', '')

    # Get OAuth application name from summary_fields if available
    oauth_application_name = 'Personal access token'  # Default for tokens without OAuth application
    if 'summary_fields' in token_data and 'application' in token_data['summary_fields']:
        if token_data['summary_fields']['application']:
            oauth_application_name = token_data['summary_fields']['application'].get('name', 'Personal access token')

    # Get username from summary_fields if available
    username = ''
    if 'summary_fields' in token_data and 'user' in token_data['summary_fields']:
        if token_data['summary_fields']['user']:
            username = token_data['summary_fields']['user'].get('username', '')

    # Get created_by username from summary_fields if available
    created_by_username = ''
    if 'summary_fields' in token_data and 'created_by' in token_data['summary_fields']:
        if token_data['summary_fields']['created_by']:
            created_by_username = token_data['summary_fields']['created_by'].get('username', '')

    # Get modified_by username from summary_fields if available
    modified_by_username = ''
    if 'summary_fields' in token_data and 'modified_by' in token_data['summary_fields']:
        if token_data['summary_fields']['modified_by']:
            modified_by_username = token_data['summary_fields']['modified_by'].get('username', '')

    # Format datetime fields using common function
    expires = format_datetime(token_data.get('expires', ''), use_utc)
    created = format_datetime(token_data.get('created', ''), use_utc)
    modified = format_datetime(token_data.get('modified', ''), use_utc)
    last_used = format_datetime(token_data.get('last_used', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'User',
        'Token',
        'Scope',
        'Description',
        'OAuth Application',
        'Expires',
        'Created',
        'Created By',
        'Modified',
        'Modified By',
        'Last Used'
    ]

    values = [
        id_value,
        username,
        token_value,
        scope,
        description,
        oauth_application_name,
        expires,
        created,
        created_by_username,
        modified,
        modified_by_username,
        last_used
    ]

    return (columns, values)


class TokenListCommand(AAPListCommand):
    """List tokens for the currently authenticated user."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--limit',
            type=int,
            metavar='N',
            help='Limit the number of results returned (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the token list command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query tokens endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", "tokens endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                tokens = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'User', 'Scope', 'Description', 'OAuth Application', 'Expiration']
                rows = []

                for token in tokens:
                    # Get OAuth application name from summary_fields
                    oauth_application_name = 'Personal access token'  # Default for tokens without OAuth application
                    if 'summary_fields' in token and 'application' in token['summary_fields']:
                        if token['summary_fields']['application']:
                            oauth_application_name = token['summary_fields']['application'].get('name', 'Personal access token')

                    # Get username from summary_fields
                    username = ''
                    if 'summary_fields' in token and 'user' in token['summary_fields']:
                        if token['summary_fields']['user']:
                            username = token['summary_fields']['user'].get('username', '')

                    # Format expiration date
                    expires = format_datetime(token.get('expires', ''))

                    row = [
                        token.get('id', ''),
                        username,
                        token.get('scope', ''),
                        token.get('description', ''),
                        oauth_application_name,
                        expires
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                raise AAPClientError(f"Gateway API failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class TokenShowCommand(AAPShowCommand):
    """Show details of a specific token."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # Positional parameter for token ID (numeric only)
        parser.add_argument(
            'token_id',
            type=int,
            metavar='<token_id>',
            help='Token ID (numeric only)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the token show command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Get specific token by ID
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/{parsed_args.token_id}/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", parsed_args.token_id)

            if response.status_code == HTTP_OK:
                token_data = response.json()
                return _format_token_data(token_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Token", parsed_args.token_id)
            else:
                raise AAPClientError(f"Failed to get token: {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class TokenSetCommand(AAPShowCommand):
    """Modify a specific token."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # Positional parameter for token ID (numeric only)
        parser.add_argument(
            'token_id',
            type=int,
            metavar='<token_id>',
            help='Token ID (numeric only)'
        )

        # Token modification options
        parser.add_argument(
            '--description',
            help='Set the token description'
        )

        parser.add_argument(
            '--scope',
            choices=['read', 'write'],
            help='Set the token scope'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the token set command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Build update data from arguments
            update_data = {}
            if parsed_args.description is not None:
                update_data['description'] = parsed_args.description
            if parsed_args.scope:
                update_data['scope'] = parsed_args.scope

            if not update_data:
                raise AAPClientError("At least one field to update must be specified")

            # Update the token
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/{parsed_args.token_id}/"
            try:
                response = client.patch(endpoint, json=update_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", parsed_args.token_id)

            if response.status_code == HTTP_OK:
                token_data = response.json()
                return _format_token_data(token_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Token", parsed_args.token_id)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_details = response.text
                raise AAPClientError(f"Bad request: {error_details}")
            else:
                raise AAPClientError(f"Failed to update token: {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class TokenDeleteCommand(AAPCommand):
    """Delete a token."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Positional parameter for token ID (numeric only)
        parser.add_argument(
            'token_id',
            type=int,
            metavar='<token_id>',
            help='Token ID (numeric only)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the token delete command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/{parsed_args.token_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Token '{parsed_args.token_id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Token", parsed_args.token_id)
            else:
                raise AAPClientError(f"Failed to delete token: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class TokenCreateCommand(AAPShowCommand):
    """Create a new token for the currently authenticated user."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # Optional description argument
        parser.add_argument(
            '--description',
            help='Description for the token'
        )

        # Required scope argument
        parser.add_argument(
            '--scope',
            choices=['read', 'write'],
            required=True,
            help='Token scope'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the token create command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Build create data from arguments
            create_data = {
                'scope': parsed_args.scope
            }

            # Add description if provided
            if parsed_args.description:
                create_data['description'] = parsed_args.description

            # Create the token
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/"
            try:
                response = client.post(endpoint, json=create_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", "token creation")

            if response.status_code == HTTP_CREATED:
                token_data = response.json()
                return _format_token_data(token_data, parsed_args.utc)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_details = response.text
                raise AAPClientError(f"Bad request: {error_details}")
            else:
                raise AAPClientError(f"Failed to create token: {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
