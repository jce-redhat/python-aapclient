"""Organization commands."""
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
from aapclient.common.functions import (
    resolve_organization_name,
    format_datetime
)


class OrganizationListCommand(AAPListCommand):
    """List organizations."""

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
        """Execute the organization list command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query organizations endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", "organizations endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                organizations = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Description']
                rows = []

                for organization in organizations:
                    row = [
                        organization.get('id', ''),
                        organization.get('name', ''),
                        organization.get('description', '')
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


def _format_organization_data(organization_data, use_utc=False):
    """
    Format organization data consistently

    Args:
        organization_data (dict): Organization data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract organization details
    id_value = organization_data.get('id', '')
    name = organization_data.get('name', '')
    description = organization_data.get('description', '')
    max_hosts = organization_data.get('max_hosts', '')

    # Format datetime fields using common function
    created = format_datetime(organization_data.get('created', ''), use_utc)
    modified = format_datetime(organization_data.get('modified', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Max Hosts',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        name,
        description,
        max_hosts,
        created,
        modified
    ]

    return (columns, values)


class OrganizationShowCommand(AAPShowCommand):
    """Show details of a specific organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Organization ID (overrides positional parameter)'
        )

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'organization',
            nargs='?',
            metavar='<organization>',
            help='Organization name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the organization show command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine how to resolve the organization
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                organization_id = parsed_args.id
            elif parsed_args.organization:
                # Use positional parameter - name first, then ID fallback if numeric
                organization_id = resolve_organization_name(client, parsed_args.organization, api="gateway")
            else:
                raise AAPClientError("Organization identifier is required")

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                organization_data = response.json()
                return _format_organization_data(organization_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Organization", parsed_args.organization or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get organization: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class OrganizationBaseCommand(AAPShowCommand):
    """Base class for organization create and set commands."""

    def add_common_arguments(self, parser, required_args=True):
        """Add common arguments for organization commands."""
        if required_args:
            # For create command
            parser.add_argument(
                'name',
                help='Organization name'
            )
        else:
            # For set command
            parser.add_argument(
                '--id',
                type=int,
                help='Organization ID (overrides positional parameter)'
            )
            parser.add_argument(
                'organization',
                nargs='?',
                metavar='<organization>',
                help='Organization name or ID to update'
            )
            parser.add_argument(
                '--set-name',
                dest='set_name',
                help='New organization name'
            )

        # Common arguments for both commands
        parser.add_argument(
            '--description',
            help='Organization description'
        )
        parser.add_argument(
            '--max-hosts',
            type=int,
            dest='max_hosts',
            help='Maximum number of hosts allowed in this organization'
        )

    def resolve_resources(self, client, parsed_args, for_create=True):
        """Resolve resource names to IDs."""
        resolved = {}

        if not for_create:
            # For set command - organization resolution
            if parsed_args.id:
                resolved['organization_id'] = parsed_args.id
            elif parsed_args.organization:
                resolved['organization_id'] = resolve_organization_name(client, parsed_args.organization, api="gateway")
            else:
                raise AAPClientError("Organization identifier is required")

        return resolved

    def build_organization_data(self, parsed_args, resolved_resources, for_create=True):
        """Build organization data for API requests."""
        organization_data = {}

        if for_create:
            organization_data['name'] = parsed_args.name
        else:
            # For set command
            if getattr(parsed_args, 'set_name', None):
                organization_data['name'] = parsed_args.set_name

        # Common fields
        if hasattr(parsed_args, 'description') and parsed_args.description is not None:
            organization_data['description'] = parsed_args.description

        if hasattr(parsed_args, 'max_hosts') and getattr(parsed_args, 'max_hosts', None) is not None:
            organization_data['max_hosts'] = parsed_args.max_hosts

        return organization_data


class OrganizationCreateCommand(OrganizationBaseCommand):
    """Create a new organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=True)
        return parser

    def take_action(self, parsed_args):
        """Execute the organization create command."""
        try:
            client = self.gateway_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=True)

            # Build organization data
            organization_data = self.build_organization_data(parsed_args, resolved_resources, for_create=True)

            # Create organization
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
            try:
                response = client.post(endpoint, json=organization_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Organization", parsed_args.name)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_CREATED:
                organization_data = response.json()
                print(f"Organization '{organization_data.get('name', '')}' created successfully")

                return _format_organization_data(organization_data)
            else:
                raise AAPClientError(f"Organization creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class OrganizationSetCommand(OrganizationBaseCommand):
    """Update an existing organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=False)
        return parser

    def take_action(self, parsed_args):
        """Execute the organization set command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Get parser for usage message
            parser = self.get_parser('aap organization set')

            # Resolve organization - handle both ID and name
            organization_id = resolve_organization_name(client, parsed_args.organization, api="gateway")

            # Prepare organization update data
            organization_data = {}

            if parsed_args.set_name:
                organization_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:  # Allow empty string
                organization_data['description'] = parsed_args.description
            if getattr(parsed_args, 'max_hosts', None):
                organization_data['max_hosts'] = parsed_args.max_hosts

            if not organization_data:
                parser.error("No update fields provided")

            # Update organization
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
            try:
                response = client.patch(endpoint, json=organization_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Organization", parsed_args.organization)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                organization_data = response.json()
                print(f"Organization '{organization_data.get('name', '')}' updated successfully")

                return _format_organization_data(organization_data)
            else:
                raise AAPClientError(f"Organization update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class OrganizationDeleteCommand(AAPCommand):
    """Delete an organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Organization ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'organization',
            nargs='?',
            metavar='<organization>',
            help='Organization name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the organization delete command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine how to resolve the organization
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                organization_id = parsed_args.id
            elif parsed_args.organization:
                # Use positional parameter - name first, then ID fallback if numeric
                organization_id = resolve_organization_name(client, parsed_args.organization, api="gateway")
            else:
                raise AAPClientError("Organization identifier is required")

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Organization '{parsed_args.organization or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Organization", parsed_args.organization or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete organization: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
