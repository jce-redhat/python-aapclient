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
from aapclient.common.functions import resolve_inventory_name, resolve_host_name





def _format_host_data(host_data):
    """
    Format host data consistently

    Args:
        host_data (dict): Host data from API response

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

    # Handle variables with length check
    variables_value = host_data.get('variables', '')
    if len(str(variables_value)) > 120:
        variables_display = "(Display with `host variables show` command)"
    else:
        variables_display = str(variables_value)

    created = host_data.get('created', '')
    modified = host_data.get('modified', '')

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
                return _format_host_data(host_data)
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


class HostCreateCommand(AAPShowCommand):
    """Create a new host."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Host name'
        )
        parser.add_argument(
            '--description',
            help='Host description'
        )
        parser.add_argument(
            '--inventory',
            required=True,
            help='Inventory name or ID'
        )
        parser.add_argument(
            '--variables',
            help='Host variables as JSON string'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the host create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap host create')

            # Resolve inventory
            inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")

            host_data = {
                'name': parsed_args.name,
                'inventory': inventory_id
            }

            # Add optional fields
            if parsed_args.description:
                host_data['description'] = parsed_args.description
            if getattr(parsed_args, 'variables', None):
                try:
                    host_data['variables'] = json.loads(parsed_args.variables)
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

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


class HostSetCommand(AAPShowCommand):
    """Update an existing host."""

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
            help='Host name or ID to update'
        )

        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='New host name'
        )
        parser.add_argument(
            '--description',
            help='Host description'
        )
        parser.add_argument(
            '--variables',
            help='Host variables as JSON string'
        )

        # Enable/disable flags for enabled status
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

        return parser

    def take_action(self, parsed_args):
        """Execute the host set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap host set')

            # Resolve host - handle both ID and name
            host_id = resolve_host_name(client, parsed_args.host, api="controller")

            # Prepare host update data
            host_data = {}

            if parsed_args.set_name:
                host_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:  # Allow empty string
                host_data['description'] = parsed_args.description
            if getattr(parsed_args, 'variables', None):
                try:
                    host_data['variables'] = json.loads(parsed_args.variables)
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

            # Handle enable/disable flags
            if parsed_args.enable_host:
                host_data['enabled'] = True
            elif parsed_args.disable_host:
                host_data['enabled'] = False

            if not host_data:
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
                columns = ['ID', 'Name']
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

                # Extract variables
                variables = host_data.get('variables', {})

                # Always convert to YAML format
                if variables:
                    try:
                        # If variables is a string, try to parse it as JSON first
                        if isinstance(variables, str):
                            variables = json.loads(variables)
                        # Convert to YAML
                        variables_yaml = yaml.dump(variables, default_flow_style=False)
                    except (json.JSONDecodeError, yaml.YAMLError):
                        # If conversion fails, display as string
                        variables_yaml = str(variables)
                else:
                    variables_yaml = "{}"

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
