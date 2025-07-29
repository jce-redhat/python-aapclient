"""Oauth application management commands for AAP Gateway API."""

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
from aapclient.common.functions import resolve_organization_name, resolve_application_name, format_datetime


def _format_application_data(application_data, use_utc=False):
    """
    Format OAuth application data consistently

    Args:
        application_data (dict): Application data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract application details
    id_value = application_data.get('id', '')
    name = application_data.get('name', '')
    description = application_data.get('description', '')
    client_id = application_data.get('client_id', '')
    client_secret = application_data.get('client_secret', '')
    client_type = application_data.get('client_type', '')
    authorization_grant_type = application_data.get('authorization_grant_type', '')
    redirect_uris = application_data.get('redirect_uris', '')
    skip_authorization = application_data.get('skip_authorization', False)

    # Get organization name from summary_fields if available
    organization_name = ''
    if 'summary_fields' in application_data and 'organization' in application_data['summary_fields']:
        if application_data['summary_fields']['organization']:
            organization_name = application_data['summary_fields']['organization'].get('name', '')

    # Get created_by username from summary_fields if available
    created_by_username = ''
    if 'summary_fields' in application_data and 'created_by' in application_data['summary_fields']:
        if application_data['summary_fields']['created_by']:
            created_by_username = application_data['summary_fields']['created_by'].get('username', '')

    # Get modified_by username from summary_fields if available
    modified_by_username = ''
    if 'summary_fields' in application_data and 'modified_by' in application_data['summary_fields']:
        if application_data['summary_fields']['modified_by']:
            modified_by_username = application_data['summary_fields']['modified_by'].get('username', '')

    # Get tokens count from summary_fields if available
    tokens_count = 0
    if 'summary_fields' in application_data and 'tokens' in application_data['summary_fields']:
        if application_data['summary_fields']['tokens']:
            tokens_count = application_data['summary_fields']['tokens'].get('count', 0)

    # Format datetime fields using common function
    created = format_datetime(application_data.get('created', ''), use_utc)
    modified = format_datetime(application_data.get('modified', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Organization',
        'Client ID',
        'Client Secret',
        'Client Type',
        'Authorization Grant Type',
        'Redirect URIs',
        'Skip Authorization',
        'Tokens',
        'Created',
        'Created By',
        'Modified',
        'Modified By'
    ]

    values = [
        id_value,
        name,
        description,
        organization_name,
        client_id,
        client_secret,
        client_type,
        authorization_grant_type,
        redirect_uris,
        'Yes' if skip_authorization else 'No',
        tokens_count,
        created,
        created_by_username,
        modified,
        modified_by_username
    ]

    return (columns, values)



class ApplicationListCommand(AAPListCommand):
    """List OAuth applications."""

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
        """Execute the application list command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query applications endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", "applications endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                applications = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Organization', 'Description', 'Tokens']
                rows = []

                for application in applications:
                    # Get organization name from summary_fields
                    organization_name = ''
                    if 'summary_fields' in application and 'organization' in application['summary_fields']:
                        if application['summary_fields']['organization']:
                            organization_name = application['summary_fields']['organization'].get('name', '')

                    # Get tokens count from summary_fields
                    tokens_count = 0
                    if 'summary_fields' in application and 'tokens' in application['summary_fields']:
                        if application['summary_fields']['tokens']:
                            tokens_count = application['summary_fields']['tokens'].get('count', 0)

                    row = [
                        application.get('id', ''),
                        application.get('name', ''),
                        organization_name,
                        application.get('description', ''),
                        tokens_count
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


class ApplicationShowCommand(AAPShowCommand):
    """Show details of a specific OAuth application."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # ID override option
        parser.add_argument(
            '--id',
            type=int,
            metavar='<id>',
            help='OAuth application ID (overrides positional parameter)'
        )

        # Positional parameter for application name or ID
        parser.add_argument(
            'application',
            nargs='?',
            metavar='<application>',
            help='OAuth application name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the application show command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine application ID
            if parsed_args.id:
                application_id = parsed_args.id
            elif parsed_args.application:
                application_id = resolve_application_name(client, parsed_args.application)
            else:
                raise AAPClientError("Application name or ID must be specified")

            # Get specific application by ID
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/{application_id}/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", application_id)

            if response.status_code == HTTP_OK:
                application_data = response.json()
                return _format_application_data(application_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Application", application_id)
            else:
                raise AAPClientError(f"Failed to get application: {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ApplicationCreateCommand(AAPShowCommand):
    """Create a new OAuth application."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # Positional parameter for application name
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Application name'
        )

        # Required organization argument
        parser.add_argument(
            '--organization',
            required=True,
            help='Organization name or ID'
        )

        # Required client type argument
        parser.add_argument(
            '--client-type',
            choices=['public', 'confidential'],
            required=True,
            help='OAuth client type'
        )

        # Required authorization grant type
        parser.add_argument(
            '--grant-type',
            choices=['authorization-code', 'password'],
            required=True,
            help='OAuth authorization grant type'
        )

        # Optional description argument
        parser.add_argument(
            '--description',
            help='OAuth application description'
        )

        # Redirect URIs
        parser.add_argument(
            '--redirect-uris',
            help='Redirect URIs (space-separated URLs)'
        )

        # Skip authorization flag
        parser.add_argument(
            '--skip-authorization',
            action='store_true',
            help='Skip authorization step'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the application create command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Resolve organization name to ID
            organization_id = resolve_organization_name(client, parsed_args.organization)

            # Build create data from arguments
            create_data = {
                'name': parsed_args.name,
                'organization': organization_id,
                'client_type': parsed_args.client_type,
                'authorization_grant_type': parsed_args.grant_type,
                'skip_authorization': parsed_args.skip_authorization
            }

            # Add optional fields if provided
            if parsed_args.description:
                create_data['description'] = parsed_args.description
            if parsed_args.redirect_uris:
                create_data['redirect_uris'] = parsed_args.redirect_uris

            # Create the application
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/"
            try:
                response = client.post(endpoint, json=create_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", "application creation")

            if response.status_code == HTTP_CREATED:
                application_data = response.json()
                return _format_application_data(application_data, parsed_args.utc)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_details = response.text
                raise AAPClientError(f"Bad request: {error_details}")
            else:
                raise AAPClientError(f"Failed to create application: {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ApplicationSetCommand(AAPShowCommand):
    """Modify a specific OAuth application."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # ID override option
        parser.add_argument(
            '--id',
            type=int,
            metavar='<id>',
            help='OAuth application ID (overrides positional parameter)'
        )

        # Positional parameter for application name or ID
        parser.add_argument(
            'application',
            nargs='?',
            metavar='<application>',
            help='OAuth application name or ID'
        )

        # Application modification options
        parser.add_argument(
            '--set-name',
            help='Set the application name'
        )

        parser.add_argument(
            '--description',
            help='Set the application description'
        )

        parser.add_argument(
            '--organization',
            help='Set the organization (name or ID)'
        )

        parser.add_argument(
            '--client-type',
            choices=['public', 'confidential'],
            help='Set the OAuth client type'
        )

        parser.add_argument(
            '--grant-type',
            choices=['authorization-code', 'password'],
            help='Set the OAuth authorization grant type'
        )

        parser.add_argument(
            '--redirect-uris',
            help='Set the redirect URIs'
        )

        # Boolean flag options
        skip_auth_group = parser.add_mutually_exclusive_group()
        skip_auth_group.add_argument(
            '--enable-skip-authorization',
            action='store_true',
            help='Enable skip authorization'
        )
        skip_auth_group.add_argument(
            '--disable-skip-authorization',
            action='store_true',
            help='Disable skip authorization'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the application set command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine application ID
            if parsed_args.id:
                application_id = parsed_args.id
            elif parsed_args.application:
                application_id = resolve_application_name(client, parsed_args.application)
            else:
                raise AAPClientError("Application name or ID must be specified")

            # Build update data from arguments
            update_data = {}
            if parsed_args.set_name is not None:
                update_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:
                update_data['description'] = parsed_args.description
            if parsed_args.organization:
                organization_id = resolve_organization_name(client, parsed_args.organization)
                update_data['organization'] = organization_id
            if parsed_args.client_type:
                update_data['client_type'] = parsed_args.client_type
            if parsed_args.grant_type:
                update_data['authorization_grant_type'] = parsed_args.grant_type
            if parsed_args.redirect_uris is not None:
                update_data['redirect_uris'] = parsed_args.redirect_uris
            if parsed_args.enable_skip_authorization:
                update_data['skip_authorization'] = True
            if parsed_args.disable_skip_authorization:
                update_data['skip_authorization'] = False

            if not update_data:
                raise AAPClientError("At least one field to update must be specified")

            # Update the application
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/{application_id}/"
            try:
                response = client.patch(endpoint, json=update_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", application_id)

            if response.status_code == HTTP_OK:
                application_data = response.json()
                return _format_application_data(application_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Application", application_id)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_details = response.text
                raise AAPClientError(f"Bad request: {error_details}")
            else:
                raise AAPClientError(f"Failed to update application: {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ApplicationDeleteCommand(AAPCommand):
    """Delete an OAuth application."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID override option
        parser.add_argument(
            '--id',
            type=int,
            metavar='<id>',
            help='OAuth application ID (overrides positional parameter)'
        )

        # Positional parameter for application name or ID
        parser.add_argument(
            'application',
            nargs='?',
            metavar='<application>',
            help='OAuth application name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the application delete command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine application ID
            if parsed_args.id:
                application_id = parsed_args.id
            elif parsed_args.application:
                application_id = resolve_application_name(client, parsed_args.application)
            else:
                raise AAPClientError("Application name or ID must be specified")

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/{application_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Application '{application_id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Application", application_id)
            else:
                raise AAPClientError(f"Failed to delete application: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
