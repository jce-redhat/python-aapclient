"""Instance management commands for AAP Controller API."""
from cliff.lister import Lister
from cliff.show import ShowOne
from aapclient.common.client import AAPHTTPClient
from aapclient.common.config import AAPConfig
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError


def _format_instance_data(instance_data):
    """Format instance data for display in ShowOne commands."""

    # Extract all available scalar information from API
    instance_id = instance_data.get('id', '')
    hostname = instance_data.get('hostname', '')
    instance_type = instance_data.get('type', '')
    url = instance_data.get('url', '')
    uuid = instance_data.get('uuid', '')
    version = instance_data.get('version', '')
    node_type = instance_data.get('node_type', '')
    node_state = instance_data.get('node_state', '')
    enabled = instance_data.get('enabled', False)
    capacity = instance_data.get('capacity', 0)
    consumed_capacity = instance_data.get('consumed_capacity', 0)
    percent_capacity_remaining = instance_data.get('percent_capacity_remaining', 0.0)
    cpu_capacity = instance_data.get('cpu_capacity', 0)
    mem_capacity = instance_data.get('mem_capacity', 0)
    cpu = instance_data.get('cpu', '')
    memory = instance_data.get('memory', 0)
    capacity_adjustment = instance_data.get('capacity_adjustment', '')
    jobs_running = instance_data.get('jobs_running', 0)
    jobs_total = instance_data.get('jobs_total', 0)
    ip_address = instance_data.get('ip_address', '')
    listener_port = instance_data.get('listener_port')
    protocol = instance_data.get('protocol', '')
    peers_from_control_nodes = instance_data.get('peers_from_control_nodes', False)
    managed = instance_data.get('managed', False)
    managed_by_policy = instance_data.get('managed_by_policy', False)
    health_check_pending = instance_data.get('health_check_pending', False)
    health_check_started = instance_data.get('health_check_started')
    last_health_check = instance_data.get('last_health_check')
    last_seen = instance_data.get('last_seen')
    errors = instance_data.get('errors', '')
    created = instance_data.get('created', '')
    modified = instance_data.get('modified', '')

    # Extract peer information
    peers = instance_data.get('peers', [])
    reverse_peers = instance_data.get('reverse_peers', [])
    peers_count = len(peers) if peers else 0
    reverse_peers_count = len(reverse_peers) if reverse_peers else 0

    # Extract summary fields data
    summary_fields = instance_data.get('summary_fields', {})
    user_capabilities = summary_fields.get('user_capabilities', {})
    can_edit = user_capabilities.get('edit', False)

    # Format boolean values
    enabled_display = "Yes" if enabled else "No"
    managed_display = "Yes" if managed else "No"
    managed_by_policy_display = "Yes" if managed_by_policy else "No"
    health_check_pending_display = "Yes" if health_check_pending else "No"
    peers_from_control_nodes_display = "Yes" if peers_from_control_nodes else "No"
    can_edit_display = "Yes" if can_edit else "No"

    # Format memory in GB for readability
    memory_gb = round(memory / (1024**3), 2) if memory else 0

    # Format null values for display
    def format_null_value(value):
        if value is None:
            return ""
        return str(value)

    # Return as tuple for Cliff ShowOne format
    columns = [
        'ID',
        'Name',
        'Type',
        'URL',
        'UUID',
        'Node Type',
        'Node State',
        'Enabled',
        'Capacity',
        'Consumed Capacity',
        'Capacity Remaining',
        'CPU',
        'CPU Capacity',
        'Memory (GB)',
        'Memory Capacity',
        'Capacity Adjustment',
        'Jobs Running',
        'Jobs Total',
        'Version',
        'IP Address',
        'Listener Port',
        'Protocol',
        'Peers From Control Nodes',
        'Peers Count',
        'Reverse Peers Count',
        'Managed',
        'Managed By Policy',
        'Health Check Pending',
        'Health Check Started',
        'Last Health Check',
        'Last Seen',
        'Can Edit',
        'Errors',
        'Created',
        'Modified',
    ]

    values = [
        str(instance_id),
        hostname,
        instance_type,
        url,
        uuid,
        node_type,
        node_state,
        enabled_display,
        str(capacity),
        str(consumed_capacity),
        f"{percent_capacity_remaining}%",
        cpu,
        str(cpu_capacity),
        str(memory_gb),
        str(mem_capacity),
        capacity_adjustment,
        str(jobs_running),
        str(jobs_total),
        version,
        ip_address,
        format_null_value(listener_port),
        protocol,
        peers_from_control_nodes_display,
        str(peers_count),
        str(reverse_peers_count),
        managed_display,
        managed_by_policy_display,
        health_check_pending_display,
        format_null_value(health_check_started),
        format_null_value(last_health_check),
        format_null_value(last_seen),
        can_edit_display,
        errors,
        created,
        modified,
    ]

    return (columns, values)


def resolve_instance_parameter(client, identifier):
    """
    Resolve instance identifier (hostname or ID) to ID.

    Args:
        client: AAPHTTPClient instance
        identifier: Instance hostname or ID

    Returns:
        int: Instance ID

    Raises:
        AAPResourceNotFoundError: If instance not found
    """
    # First try as hostname lookup
    try:
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/"
        params = {'hostname': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
    except AAPAPIError:
        pass

    # Try as ID if it's numeric
    try:
        instance_id = int(identifier)
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return instance_id
        else:
            raise AAPResourceNotFoundError("Instance", identifier)
    except ValueError:
        raise AAPResourceNotFoundError("Instance", identifier)
    except AAPAPIError:
        raise AAPResourceNotFoundError("Instance", identifier)


class InstanceListCommand(Lister):
    """List instances from AAP Controller API."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        # Get instances with server-side sorting by ID
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/"
        params = {'order_by': 'id'}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            instances = data.get('results', [])

            # Define columns for display
            columns = ['ID', 'Hostname', 'Status', 'Node Type', 'Capacity', 'Percent Remaining', 'Enabled']
            rows = []

            for instance in instances:
                instance_id = instance.get('id', '')
                hostname = instance.get('hostname', '')
                node_state = instance.get('node_state', '')
                node_type = instance.get('node_type', '')
                capacity = instance.get('capacity', 0)
                percent_remaining = instance.get('percent_capacity_remaining', 0.0)
                enabled = instance.get('enabled', False)

                # Format display values
                enabled_display = "Yes" if enabled else "No"

                row = [
                    str(instance_id),
                    hostname,
                    node_state,
                    node_type,
                    str(capacity),
                    f"{percent_remaining}%",
                    enabled_display
                ]
                rows.append(row)

            return (columns, rows)
        else:
            raise AAPClientError(f"Failed to list instances: {response.status_code}")


class InstanceShowCommand(ShowOne):
    """Show instance details from AAP Controller API."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Instance ID (overrides positional parameter)'
        )

        # Positional parameter for hostname lookup with ID fallback
        parser.add_argument(
            'instance',
            nargs='?',
            metavar='<instance>',
            help='Instance hostname or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Determine how to resolve the instance
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                instance_id = parsed_args.id
            elif parsed_args.instance:
                # Use positional parameter - hostname first, then ID fallback if numeric
                instance_id = resolve_instance_parameter(client, parsed_args.instance)
            else:
                raise AAPClientError("Instance identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                instance_data = response.json()
                return _format_instance_data(instance_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance", parsed_args.instance or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get instance: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance", parsed_args.instance or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {api_error}")


class InstanceCreateCommand(ShowOne):
    """Create a new instance in AAP Controller API."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Required positional argument
        parser.add_argument(
            'hostname',
            metavar='<hostname>',
            help='Hostname for the new instance'
        )

        # Required and optional arguments
        parser.add_argument(
            '--instance-type',
            choices=['execution', 'hop'],
            default='execution',
            help='Type of instance (default: execution)'
        )
        parser.add_argument(
            '--listener-port',
            type=int,
            default=27199,
            help='Listener port for the instance (default: 27199)'
        )
        parser.add_argument(
            '--disabled',
            action='store_true',
            help='Disable the instance (default: enabled)'
        )
        parser.add_argument(
            '--enable-peers-from-control-nodes',
            action='store_true',
            dest='peers_from_control_nodes',
            help='Enable peers from control nodes'
        )
        parser.add_argument(
            '--disable-manage-by-policy',
            action='store_true',
            help='Disable manage by policy (default: enabled)'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Get parser for usage message
            parser = self.get_parser('aap instance create')

            instance_data = {
                'hostname': parsed_args.hostname,
                'node_type': parsed_args.instance_type,
                'listener_port': parsed_args.listener_port,
                'enabled': not parsed_args.disable_instance,  # Default enabled unless --disable
                'peers_from_control_nodes': parsed_args.peers_from_control_nodes,
                'managed_by_policy': not parsed_args.disable_manage_by_policy  # Default enabled unless --disable-manage-by-policy
            }

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/"
            response = client.post(endpoint, json=instance_data)

            if response.status_code == HTTP_CREATED:
                instance_data = response.json()
                print(f"Instance '{parsed_args.hostname}' created successfully")
                return _format_instance_data(instance_data)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                parser.error(f"Bad request: {error_data}")
            else:
                raise AAPClientError(f"Failed to create instance: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                parser = self.get_parser('aap instance create')
                parser.error(f"Bad request: {api_error}")
            else:
                raise AAPClientError(f"API error: {api_error}")


class InstanceSetCommand(ShowOne):
    """Update an existing instance in AAP Controller API."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Instance ID (overrides positional parameter)'
        )

        # Positional parameter for hostname lookup with ID fallback
        parser.add_argument(
            'instance',
            nargs='?',
            metavar='<instance>',
            help='Instance hostname or ID to update'
        )

        # Update fields
        parser.add_argument(
            '--listener-port',
            type=int,
            help='Listener port for the instance'
        )

        # Mutually exclusive group for enabled/disabled
        enabled_group = parser.add_mutually_exclusive_group()
        enabled_group.add_argument(
            '--enabled',
            action='store_true',
            dest='enable_instance',
            help='Enable the instance'
        )
        enabled_group.add_argument(
            '--disabled',
            action='store_true',
            dest='disable_instance',
            help='Disable the instance'
        )

        # Mutually exclusive group for manage by policy
        manage_policy_group = parser.add_mutually_exclusive_group()
        manage_policy_group.add_argument(
            '--enable-manage-by-policy',
            action='store_true',
            dest='enable_manage_by_policy',
            help='Enable manage by policy'
        )
        manage_policy_group.add_argument(
            '--disable-manage-by-policy',
            action='store_true',
            dest='disable_manage_by_policy',
            help='Disable manage by policy'
        )

        # Mutually exclusive group for peers from control nodes
        peers_group = parser.add_mutually_exclusive_group()
        peers_group.add_argument(
            '--enable-peers-from-control-nodes',
            action='store_true',
            dest='enable_peers_from_control_nodes',
            help='Enable peers from control nodes'
        )
        peers_group.add_argument(
            '--disable-peers-from-control-nodes',
            action='store_true',
            dest='disable_peers_from_control_nodes',
            help='Disable peers from control nodes'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap instance set')

            # Determine how to resolve the instance
            if parsed_args.id:
                instance_id = parsed_args.id
            elif parsed_args.instance:
                instance_id = resolve_instance_parameter(client, parsed_args.instance)
            else:
                parser.error("Instance identifier is required")

            instance_data = {}

            # Update fields if provided
            if parsed_args.listener_port is not None:
                instance_data['listener_port'] = parsed_args.listener_port

            # Handle enabled/disabled boolean
            if parsed_args.enable_instance:
                instance_data['enabled'] = True
            elif parsed_args.disable_instance:
                instance_data['enabled'] = False

            # Handle manage by policy boolean
            if parsed_args.enable_manage_by_policy:
                instance_data['managed_by_policy'] = True
            elif parsed_args.disable_manage_by_policy:
                instance_data['managed_by_policy'] = False

            # Handle peers from control nodes boolean
            if parsed_args.enable_peers_from_control_nodes:
                instance_data['peers_from_control_nodes'] = True
            elif parsed_args.disable_peers_from_control_nodes:
                instance_data['peers_from_control_nodes'] = False

            if not instance_data:
                parser.error("At least one field must be specified to update")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/"
            response = client.patch(endpoint, json=instance_data)

            if response.status_code == HTTP_OK:
                instance_data = response.json()
                print(f"Instance '{parsed_args.instance or parsed_args.id}' updated successfully")
                return _format_instance_data(instance_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance", parsed_args.instance or parsed_args.id)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                parser.error(f"Bad request: {error_data}")
            else:
                raise AAPClientError(f"Failed to update instance: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance", parsed_args.instance or parsed_args.id)
            elif api_error.status_code == HTTP_BAD_REQUEST:
                parser = self.get_parser('aap instance set')
                parser.error(f"Bad request: {api_error}")
            else:
                raise AAPClientError(f"API error: {api_error}")
