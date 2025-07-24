"""Host commands for AAP Controller API."""

import json
import yaml
from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.config import AAPConfig
from aapclient.common.client import AAPHTTPClient
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import (
    AAPClientError,
    AAPResourceNotFoundError,
    AAPAPIError
)
from aapclient.common.functions import (
    resolve_inventory_name,
    resolve_host_name
)





def _format_host_data(host_data):
    """Format host data for display."""
    # Resolve inventory name from summary_fields
    inventory_name = ""
    if host_data.get('summary_fields', {}).get('inventory', {}).get('name'):
        inventory_name = host_data['summary_fields']['inventory']['name']
    elif host_data.get('inventory'):
        inventory_name = str(host_data['inventory'])

    columns = [
        'ID',
        'Name',
        'Description',
        'Inventory',
        'Enabled',
        'Instance ID',
        'Has Active Failures',
        'Has Inventory Sources',
        'Variables',
        'Created',
        'Modified',
    ]

    # Handle variables display - check character count
    variables_value = host_data.get('variables', '')
    if len(str(variables_value)) > 120:
        variables_display = "(Display with `host variables show` command)"
    else:
        variables_display = variables_value

    values = [
        host_data.get('id', ''),
        host_data.get('name', ''),
        host_data.get('description', ''),
        inventory_name,
        'Yes' if host_data.get('enabled', False) else 'No',
        host_data.get('instance_id', ''),
        'Yes' if host_data.get('has_active_failures', False) else 'No',
        'Yes' if host_data.get('has_inventory_sources', False) else 'No',
        variables_display,
        host_data.get('created', ''),
        host_data.get('modified', ''),
    ]

    return (columns, values)


class HostListCommand(Lister):
    """List hosts from AAP Controller API."""

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
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        # Parameters for API request
        params = {'order_by': 'id'}  # Server-side sorting by ID
        if parsed_args.limit:
            params['page_size'] = parsed_args.limit

        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/"
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            hosts = data.get('results', [])

            columns = ['ID', 'Name', 'Description', 'Inventory', 'Enabled']
            host_list = []

            for host in hosts:
                # Resolve inventory name from summary_fields
                inventory_name = ""
                if host.get('summary_fields', {}).get('inventory', {}).get('name'):
                    inventory_name = host['summary_fields']['inventory']['name']
                elif host.get('inventory'):
                    inventory_name = str(host['inventory'])

                host_list.append([
                    host.get('id', ''),
                    host.get('name', ''),
                    host.get('description', ''),
                    inventory_name,
                    'Yes' if host.get('enabled', False) else 'No'
                ])

            return (columns, host_list)
        else:
            raise AAPClientError(f"Failed to retrieve hosts: {response.status_code}")


class HostShowCommand(ShowOne):
    """Show details of a specific host from AAP Controller API."""

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
            help='Host name or ID to show'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Determine how to resolve the host
            if parsed_args.id:
                host_id = parsed_args.id
            elif parsed_args.host:
                host_id = resolve_host_name(client, parsed_args.host, api="controller")
            else:
                parser = self.get_parser('aap host show')
                parser.error("Host identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                host_data = response.json()
                return _format_host_data(host_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to retrieve host: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {api_error}")


class HostCreateCommand(ShowOne):
    """Create a new host in AAP Controller API."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Required positional argument
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Name for the new host'
        )

        # Required inventory argument
        parser.add_argument(
            '--inventory',
            required=True,
            help='Inventory name or ID to add the host to'
        )

        # Optional arguments
        parser.add_argument(
            '--description',
            help='Description for the host'
        )
        parser.add_argument(
            '--variables',
            help='Variables for the host (JSON format)'
        )
        parser.add_argument(
            '--disabled',
            action='store_true',
            help='Disable the host'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap host create')

            # Resolve inventory name to ID
            try:
                inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")
            except AAPResourceNotFoundError:
                parser.error(f"Inventory '{parsed_args.inventory}' not found")

            # Handle enabled/disabled flags
            enabled = True  # Default
            if parsed_args.disabled:
                enabled = False

            host_data = {
                'name': parsed_args.name,
                'inventory': inventory_id,
                'enabled': enabled
            }

            # Add optional fields
            if parsed_args.description:
                host_data['description'] = parsed_args.description
            if parsed_args.variables:
                host_data['variables'] = parsed_args.variables

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/"
            response = client.post(endpoint, json=host_data)

            if response.status_code == HTTP_CREATED:
                host_data = response.json()
                print(f"Host '{parsed_args.name}' created successfully")
                return _format_host_data(host_data)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                parser.error(f"Bad request: {error_data}")
            else:
                raise AAPClientError(f"Failed to create host: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                parser = self.get_parser('aap host create')
                parser.error(f"Bad request: {api_error}")
            else:
                raise AAPClientError(f"API error: {api_error}")


class HostSetCommand(ShowOne):
    """Update an existing host in AAP Controller API."""

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

        # Update fields
        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='New name for the host'
        )
        parser.add_argument(
            '--description',
            help='New description for the host'
        )
        parser.add_argument(
            '--variables',
            help='New variables for the host (JSON format)'
        )

        # Mutually exclusive group for enabled/disabled
        enabled_group = parser.add_mutually_exclusive_group()
        enabled_group.add_argument(
            '--enable',
            action='store_true',
            help='Enable the host'
        )
        enabled_group.add_argument(
            '--disable',
            action='store_true',
            help='Disable the host'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap host set')

            # Determine how to resolve the host
            if parsed_args.id:
                host_id = parsed_args.id
            elif parsed_args.host:
                host_id = resolve_host_name(client, parsed_args.host, api="controller")
            else:
                parser.error("Host identifier is required")

            host_data = {}

            # Update fields if provided
            if parsed_args.set_name is not None:
                host_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:
                host_data['description'] = parsed_args.description
            if parsed_args.variables is not None:
                host_data['variables'] = parsed_args.variables

            # Handle enabled/disabled boolean
            if parsed_args.enable:
                host_data['enabled'] = True
            elif parsed_args.disable:
                host_data['enabled'] = False

            if not host_data:
                parser.error("At least one field must be specified to update")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.patch(endpoint, json=host_data)

            if response.status_code == HTTP_OK:
                host_data = response.json()
                print(f"Host '{parsed_args.host or parsed_args.id}' updated successfully")
                return _format_host_data(host_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            elif response.status_code == HTTP_BAD_REQUEST:
                parser.error(f"Bad request: {response.json()}")
            else:
                raise AAPClientError(f"Failed to update host: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            elif api_error.status_code == HTTP_BAD_REQUEST:
                parser = self.get_parser('aap host set')
                parser.error(f"Bad request: {api_error}")
            else:
                raise AAPClientError(f"API error: {api_error}")


class HostDeleteCommand(Command):
    """Delete a host from AAP Controller API."""

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
            help='Host name or ID to delete'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap host delete')

            # Determine how to resolve the host
            if parsed_args.id:
                host_id = parsed_args.id
                host_identifier = str(parsed_args.id)
            elif parsed_args.host:
                host_id = resolve_host_name(client, parsed_args.host, api="controller")
                host_identifier = parsed_args.host
            else:
                parser.error("Host identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.delete(endpoint)

            if response.status_code == HTTP_NO_CONTENT:
                print(f"Host '{host_identifier}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", host_identifier)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                parser.error(f"Bad request: {error_data}")
            else:
                raise AAPClientError(f"Failed to delete host: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            elif api_error.status_code == HTTP_BAD_REQUEST:
                parser = self.get_parser('aap host delete')
                parser.error(f"Bad request: {api_error}")
            else:
                raise AAPClientError(f"API error: {api_error}")


class HostGroupsListCommand(Lister):
    """List groups associated with a host from AAP Controller API."""

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
            help='Host name or ID to list groups for'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap host group list')

            # Determine how to resolve the host
            if parsed_args.id:
                host_id = parsed_args.id
                host_identifier = str(parsed_args.id)
            elif parsed_args.host:
                host_id = resolve_host_name(client, parsed_args.host, api="controller")
                host_identifier = parsed_args.host
            else:
                parser.error("Host identifier is required")

            # Fetch host data to get groups from summary_fields
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                host_data = response.json()

                # Extract groups from summary_fields
                summary_fields = host_data.get('summary_fields', {})
                groups_data = summary_fields.get('groups', {})
                groups = groups_data.get('results', [])

                columns = ['Group ID', 'Name']
                group_list = []

                for group in groups:
                    group_list.append([
                        group.get('id', ''),
                        group.get('name', '')
                    ])

                return (columns, group_list)

            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", host_identifier)
            else:
                raise AAPClientError(f"Failed to retrieve host: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {api_error}")


class HostVariablesShowCommand(ShowOne):
    """Show variables of a specific host from AAP Controller API."""

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
            help='Host name or ID to show variables for'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap host variables show')

            # Determine how to resolve the host
            if parsed_args.id:
                host_id = parsed_args.id
                host_identifier = str(parsed_args.id)
            elif parsed_args.host:
                host_id = resolve_host_name(client, parsed_args.host, api="controller")
                host_identifier = parsed_args.host
            else:
                parser.error("Host identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                host_data = response.json()
                variables = host_data.get('variables', '')

                # Convert to YAML format
                if variables:
                    try:
                        # Parse JSON variables and convert to YAML
                        if isinstance(variables, str):
                            variables_dict = json.loads(variables)
                        else:
                            variables_dict = variables
                        variables = yaml.dump(variables_dict, default_flow_style=False, allow_unicode=True)
                    except (json.JSONDecodeError, TypeError) as e:
                        # If JSON parsing fails, show error message but keep original value
                        variables = f"Error converting to YAML: {str(e)}\n\nOriginal value:\n{variables}"

                # Format for display
                columns = ['Host', 'Variables']
                values = [host_data.get('name', host_identifier), variables]

                return (columns, values)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", host_identifier)
            else:
                raise AAPClientError(f"Failed to retrieve host: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Host", parsed_args.host or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {api_error}")
