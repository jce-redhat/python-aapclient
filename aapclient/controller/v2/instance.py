"""Instance commands."""
from aapclient.common.basecommands import AAPShowCommand, AAPListCommand
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
from aapclient.common.functions import resolve_instance_name





def _format_instance_data(instance_data):
    """
    Format instance data consistently

    Args:
        instance_data (dict): Instance data from API response

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract instance details
    id_value = instance_data.get('id', '')
    hostname = instance_data.get('hostname', '')
    node_type = instance_data.get('node_type', '')
    node_state = instance_data.get('node_state', '')
    enabled = instance_data.get('enabled', False)
    managed_by_policy = instance_data.get('managed_by_policy', False)
    cpu_capacity = instance_data.get('cpu_capacity', '')
    mem_capacity = instance_data.get('mem_capacity', '')
    capacity = instance_data.get('capacity', '')
    version = instance_data.get('version', '')
    listener_port = instance_data.get('listener_port', '')
    created = instance_data.get('created', '')
    modified = instance_data.get('modified', '')

    # Format fields for display
    columns = [
        'ID',
        'Hostname',
        'Node Type',
        'Node State',
        'Enabled',
        'Managed by Policy',
        'CPU Capacity',
        'Memory Capacity',
        'Capacity',
        'Version',
        'Listener Port',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        hostname,
        node_type,
        node_state,
        "Yes" if enabled else "No",
        "Yes" if managed_by_policy else "No",
        cpu_capacity,
        mem_capacity,
        capacity,
        version,
        listener_port,
        created,
        modified
    ]

    return (columns, values)


class InstanceListCommand(AAPListCommand):
    """List instances."""

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
        """Execute the instance list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query instances endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "instances endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                instances = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Hostname', 'Node Type', 'Node State', 'Enabled']
                rows = []

                for instance in instances:
                    row = [
                        instance.get('id', ''),
                        instance.get('hostname', ''),
                        instance.get('node_type', ''),
                        instance.get('node_state', ''),
                        "Yes" if instance.get('enabled', False) else "No"
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


class InstanceShowCommand(AAPShowCommand):
    """Show details of a specific instance."""

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
        """Execute the instance show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the instance
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                instance_id = parsed_args.id
            elif parsed_args.instance:
                # Use positional parameter - hostname first, then ID fallback if numeric
                instance_id = resolve_instance_name(client, parsed_args.instance, api="controller")
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

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class InstanceCreateCommand(AAPShowCommand):
    """Create a new instance."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'hostname',
            help='Instance hostname'
        )
        parser.add_argument(
            '--instance-type',
            choices=['execution', 'control', 'hybrid'],
            required=True,
            dest='instance_type',
            help='Type of instance'
        )
        parser.add_argument(
            '--listener-port',
            type=int,
            default=27199,
            dest='listener_port',
            help='Port for instance communication (default: 27199)'
        )
        parser.add_argument(
            '--disable-instance',
            action='store_true',
            help='Create instance in disabled state'
        )
        parser.add_argument(
            '--peers-from-control-nodes',
            action='store_true',
            help='Enable peers from control nodes'
        )
        parser.add_argument(
            '--disable-manage-by-policy',
            action='store_true',
            help='Disable management by policy'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the instance create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

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

            # Create instance
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/"
            try:
                response = client.post(endpoint, json=instance_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.hostname)

            if response.status_code == HTTP_CREATED:
                instance_data = response.json()
                print(f"Instance '{instance_data.get('hostname', '')}' created successfully")
                return _format_instance_data(instance_data)
            else:
                raise AAPClientError(f"Instance creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class InstanceSetCommand(AAPShowCommand):
    """Update an existing instance."""

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

        parser.add_argument(
            '--listener-port',
            type=int,
            dest='listener_port',
            help='Port for instance communication'
        )

        # Enable/disable flags for various boolean settings
        enable_group = parser.add_mutually_exclusive_group()
        enable_group.add_argument(
            '--enable',
            action='store_true',
            dest='enable_instance',
            help='Enable the instance'
        )
        enable_group.add_argument(
            '--disable',
            action='store_true',
            dest='disable_instance',
            help='Disable the instance'
        )

        peers_group = parser.add_mutually_exclusive_group()
        peers_group.add_argument(
            '--enable-peers-from-control-nodes',
            action='store_true',
            dest='enable_peers',
            help='Enable peers from control nodes'
        )
        peers_group.add_argument(
            '--disable-peers-from-control-nodes',
            action='store_true',
            dest='disable_peers',
            help='Disable peers from control nodes'
        )

        policy_group = parser.add_mutually_exclusive_group()
        policy_group.add_argument(
            '--enable-manage-by-policy',
            action='store_true',
            dest='enable_policy',
            help='Enable management by policy'
        )
        policy_group.add_argument(
            '--disable-manage-by-policy',
            action='store_true',
            dest='disable_policy',
            help='Disable management by policy'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the instance set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap instance set')

            # Resolve instance - handle both ID and hostname
            instance_id = resolve_instance_name(client, parsed_args.instance, api="controller")

            # Prepare instance update data
            instance_data = {}

            if getattr(parsed_args, 'listener_port', None):
                instance_data['listener_port'] = parsed_args.listener_port

            # Handle enable/disable flags
            if parsed_args.enable_instance:
                instance_data['enabled'] = True
            elif parsed_args.disable_instance:
                instance_data['enabled'] = False

            if parsed_args.enable_peers:
                instance_data['peers_from_control_nodes'] = True
            elif parsed_args.disable_peers:
                instance_data['peers_from_control_nodes'] = False

            if parsed_args.enable_policy:
                instance_data['managed_by_policy'] = True
            elif parsed_args.disable_policy:
                instance_data['managed_by_policy'] = False

            if not instance_data:
                parser.error("No update fields provided")

            # Update instance
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/"
            try:
                response = client.patch(endpoint, json=instance_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.instance)

            if response.status_code == HTTP_OK:
                instance_data = response.json()
                print(f"Instance '{instance_data.get('hostname', '')}' updated successfully")

                return _format_instance_data(instance_data)
            else:
                raise AAPClientError(f"Instance update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
