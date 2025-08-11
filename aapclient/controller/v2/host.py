"""Host commands."""
import json
import yaml
from aapclient.common.basecommands import AAPShowCommand, AAPListCommand, AAPCommand
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST,
    HTTP_ACCEPTED
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import (
    resolve_inventory_name,
    resolve_host_name,
    format_datetime,
    format_variables_display,
    format_variables_yaml_display
)





def _format_host_data(host_data, use_utc=False):
    """
    Format host data consistently

    Args:
        host_data (dict): Host data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract host details
    id_value = host_data.get('id', '')
    name = host_data.get('name', '')
    description = host_data.get('description', '')
    inventory_name = ''
    enabled = host_data.get('enabled', False)

    # Resolve inventory name if available
    if 'summary_fields' in host_data and 'inventory' in host_data['summary_fields']:
        if host_data['summary_fields']['inventory']:
            inventory_name = host_data['summary_fields']['inventory'].get('name', '')

    # Handle variables using unified function
    variables_value = host_data.get('variables', '')
    variables_display = format_variables_display(variables_value, "host")

    # Format datetime fields using common function
    created = format_datetime(host_data.get('created', ''), use_utc)
    modified = format_datetime(host_data.get('modified', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Inventory',
        'Enabled',
        'Variables',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        name,
        description,
        inventory_name,
        "Yes" if enabled else "No",
        variables_display,
        created,
        modified
    ]

    return (columns, values)


class HostListCommand(AAPListCommand):
    """List hosts."""

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
        """Execute the host list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query hosts endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "hosts endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                hosts = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Description', 'Inventory', 'Enabled']
                rows = []

                for host in hosts:
                    # Get inventory name from summary_fields
                    inventory_name = ''
                    if 'summary_fields' in host and 'inventory' in host['summary_fields']:
                        if host['summary_fields']['inventory']:
                            inventory_name = host['summary_fields']['inventory'].get('name', '')

                    row = [
                        host.get('id', ''),
                        host.get('name', ''),
                        host.get('description', ''),
                        inventory_name,
                        'Yes' if host.get('enabled', False) else 'No'
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                raise AAPClientError(f"Controller API failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class HostShowCommand(AAPShowCommand):
    """Show details of a specific host."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Host ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'host',
            nargs='?',
            metavar='<host>',
            help='Host name or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the host show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the host
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                host_id = parsed_args.id
            elif parsed_args.host:
                # Use positional parameter - name first, then ID fallback if numeric
                host_id = resolve_host_name(client, parsed_args.host, api="controller")
            else:
                raise AAPClientError("Host identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                host_data = response.json()
                return _format_host_data(host_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get host: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class HostBaseCommand(AAPShowCommand):
    """Base class for host create and set commands."""

    def add_common_arguments(self, parser, required_args=True):
        """Add common arguments for host commands."""
        if required_args:
            # For create command
            parser.add_argument(
                'name',
                help='Host name'
            )
            parser.add_argument(
                '--inventory',
                required=True,
                help='Inventory name or ID'
            )
        else:
            # For set command
            parser.add_argument(
                '--id',
                type=int,
                help='Host ID (overrides positional parameter)'
            )
            parser.add_argument(
                'host',
                nargs='?',
                metavar='<host>',
                help='Host name or ID to update'
            )
            parser.add_argument(
                '--set-name',
                dest='set_name',
                help='New host name'
            )

        # Common arguments for both commands
        parser.add_argument(
            '--description',
            help='Host description'
        )
        parser.add_argument(
            '--variables',
            help='Host variables as JSON string'
        )

    def add_boolean_arguments(self, parser, mutually_exclusive=False):
        """Add boolean arguments for host commands."""
        if mutually_exclusive:
            # For set command with enable/disable options
            enable_group = parser.add_mutually_exclusive_group()
            enable_group.add_argument(
                '--enable',
                action='store_true',
                dest='enable_host',
                help='Enable the host'
            )
            enable_group.add_argument(
                '--disable',
                action='store_true',
                dest='disable_host',
                help='Disable the host'
            )

    def resolve_resources(self, client, parsed_args, for_create=True):
        """Resolve resource names to IDs."""
        resolved_resources = {}

        if for_create:
            # For create command, resolve inventory
            resolved_resources['inventory_id'] = resolve_inventory_name(
                client, parsed_args.inventory, api="controller"
            )
        else:
            # For set command, resolve host
            host_identifier = getattr(parsed_args, 'id', None) or parsed_args.host
            if not host_identifier:
                parser = self.get_parser('aap host set')
                parser.error("Host name/ID is required")

            resolved_resources['host_id'] = resolve_host_name(
                client, host_identifier, api="controller"
            )

        return resolved_resources

    def build_host_data(self, parsed_args, resolved_resources, for_create=True):
        """Build host data dictionary for API requests."""
        host_data = {}

        if for_create:
            # Required fields for create
            host_data['name'] = parsed_args.name
            host_data['inventory'] = resolved_resources['inventory_id']
        else:
            # Optional name update for set
            if getattr(parsed_args, 'set_name', None):
                host_data['name'] = parsed_args.set_name

        # Common optional fields
        for field in ['description']:
            value = getattr(parsed_args, field, None)
            if value is not None:
                host_data[field] = value

        # Handle variables (JSON validation)
        if getattr(parsed_args, 'variables', None):
            try:
                if for_create:
                    # For create, store as parsed JSON
                    host_data['variables'] = json.loads(parsed_args.variables)
                else:
                    # For set, store as string (API expects string for PATCH)
                    json.loads(parsed_args.variables)  # Validate JSON
                    host_data['variables'] = parsed_args.variables
            except json.JSONDecodeError:
                parser = self.get_parser('aap host create' if for_create else 'aap host set')
                parser.error("argument --variables: must be valid JSON")

        # Boolean fields for set command
        if not for_create:
            if getattr(parsed_args, 'enable_host', False):
                host_data['enabled'] = True
            elif getattr(parsed_args, 'disable_host', False):
                host_data['enabled'] = False

        return host_data


class HostCreateCommand(HostBaseCommand):
    """Create a new host."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=True)
        return parser

    def take_action(self, parsed_args):
        """Execute the host create command."""
        try:
            client = self.controller_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=True)

            # Build host data
            host_data = self.build_host_data(parsed_args, resolved_resources, for_create=True)

            # Create host
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/"
            try:
                response = client.post(endpoint, json=host_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.name)

            if response.status_code == HTTP_CREATED:
                host_data = response.json()
                print(f"Host '{host_data.get('name', '')}' created successfully")

                return _format_host_data(host_data)
            else:
                raise AAPClientError(f"Host creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class HostSetCommand(HostBaseCommand):
    """Update an existing host."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=False)
        self.add_boolean_arguments(parser, mutually_exclusive=True)
        return parser

    def take_action(self, parsed_args):
        """Execute the host set command."""
        try:
            client = self.controller_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=False)
            host_id = resolved_resources['host_id']

            # Build host data
            host_data = self.build_host_data(parsed_args, resolved_resources, for_create=False)

            if not host_data:
                parser = self.get_parser('aap host set')
                parser.error("No update fields provided")

            # Update host
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            try:
                response = client.patch(endpoint, json=host_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.host)

            if response.status_code == HTTP_OK:
                host_data = response.json()
                print(f"Host '{host_data.get('name', '')}' updated successfully")

                return _format_host_data(host_data)
            else:
                raise AAPClientError(f"Host update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class HostDeleteCommand(AAPCommand):
    """Delete a host."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Host ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'host',
            nargs='?',
            metavar='<host>',
            help='Host name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the host delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the host
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                host_id = parsed_args.id
            elif parsed_args.host:
                # Use positional parameter - name first, then ID fallback if numeric
                host_id = resolve_host_name(client, parsed_args.host, api="controller")
            else:
                raise AAPClientError("Host identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Host '{parsed_args.host or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete host: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class HostGroupsListCommand(AAPListCommand):
    """List groups associated with a host."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Host ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'host',
            metavar='<host>',
            help='Host name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the host groups list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the host
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                host_id = parsed_args.id
            else:
                # Use positional parameter - name first, then ID fallback if numeric
                host_id = resolve_host_name(client, parsed_args.host, api="controller")

            # Get host details to access summary_fields.groups
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                host_data = response.json()

                # Extract groups from summary_fields
                groups = []
                if 'summary_fields' in host_data and 'groups' in host_data['summary_fields']:
                    groups_data = host_data['summary_fields']['groups']
                    if 'results' in groups_data:
                        groups = groups_data['results']

                # Define columns for output
                columns = ['Group ID', 'Name']
                rows = []

                for group in groups:
                    row = [
                        group.get('id', ''),
                        group.get('name', '')
                    ]
                    rows.append(row)

                return (columns, rows)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get host: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class HostVariablesShowCommand(AAPShowCommand):
    """Show host variables in YAML format."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Host ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'host',
            metavar='<host>',
            help='Host name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the host variables show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the host
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                host_id = parsed_args.id
            else:
                # Use positional parameter - name first, then ID fallback if numeric
                host_id = resolve_host_name(client, parsed_args.host, api="controller")

            # Get host details
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                host_data = response.json()

                # Extract variables and format using unified function
                variables = host_data.get('variables', {})
                variables_yaml = format_variables_yaml_display(variables)

                # Format for display
                columns = ['Host', 'Variables']
                values = [
                    parsed_args.host or parsed_args.id,
                    variables_yaml
                ]

                return (columns, values)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get host: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
