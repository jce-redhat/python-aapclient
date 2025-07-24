"""Ping commands."""
import time
from aapclient.common.basecommands import AAPShowCommand
from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError


class PingCommand(AAPShowCommand):
    """Test connectivity to AAP API."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--detail',
            action='store_true',
            default=False,
            help='Show detailed controller information including instances and instance groups'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the ping command."""
        try:
            # Get clients from centralized client manager
            gateway_client = self.gateway_client
            controller_client = self.controller_client

            # Test connectivity using both Gateway and Controller API ping endpoints
            gateway_ping_endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}ping/"
            controller_ping_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}ping/"

            # Measure round-trip time for both endpoints
            start_time = time.time()

            # Call Gateway API ping
            gateway_response = gateway_client.get(gateway_ping_endpoint)
            gateway_time = time.time()

            # Call Controller API ping
            controller_response = controller_client.get(controller_ping_endpoint)
            end_time = time.time()

            # Calculate response times in milliseconds
            gateway_time_ms = int((gateway_time - start_time) * 1_000)
            controller_time_ms = int((end_time - gateway_time) * 1_000)

            if gateway_response.status_code == HTTP_OK and controller_response.status_code == HTTP_OK:
                gateway_data = gateway_response.json()
                controller_data = controller_response.json()

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # === Gateway API Data ===

                # Host
                columns.append('Host')
                values.append(self.client_manager.config.host)

                # Service Status (from Gateway API)
                if 'status' in gateway_data:
                    columns.append('Service Status')
                    values.append(gateway_data['status'])

                # AAP Version (from Gateway API)
                if 'version' in gateway_data:
                    columns.append('AAP Version')
                    values.append(gateway_data['version'])

                # Gateway Response Time
                columns.append('Gateway Response Time')
                values.append(f"{gateway_time_ms}ms")

                # Database Connected (from Gateway API)
                if 'db_connected' in gateway_data:
                    columns.append('Database Connected')
                    values.append('Yes' if gateway_data['db_connected'] else 'No')

                # Proxy Connected (from Gateway API)
                if 'proxy_connected' in gateway_data:
                    columns.append('Proxy Connected')
                    values.append('Yes' if gateway_data['proxy_connected'] else 'No')

                # === Controller API Data ===

                # Controller Version (from Controller API)
                if 'version' in controller_data:
                    columns.append('Controller Version')
                    values.append(controller_data['version'])

                # Controller Response Time
                columns.append('Controller Response Time')
                values.append(f"{controller_time_ms}ms")

                # High Availability (from Controller API)
                if 'ha' in controller_data:
                    columns.append('High Availability')
                    values.append('Yes' if controller_data['ha'] else 'No')

                # Active Node (from Controller API)
                if 'active_node' in controller_data:
                    columns.append('Active Node')
                    values.append(controller_data['active_node'])

                # Controller Capacity (from Controller API)
                if 'instance_groups' in controller_data:
                    total_capacity = sum(ig.get('capacity', 0) for ig in controller_data['instance_groups'])
                    columns.append('Controller Capacity')
                    values.append(str(total_capacity))

                # === Detailed Controller Data (if --detail is specified) ===
                if parsed_args.detail:
                    # Install UUID
                    if 'install_uuid' in controller_data:
                        columns.append('Install UUID')
                        values.append(controller_data['install_uuid'])

                    # Instance Details
                    if 'instances' in controller_data:
                        for i, instance in enumerate(controller_data['instances']):
                            prefix = f"Instance {i+1}"

                            if 'node' in instance:
                                columns.append(f'{prefix} Node')
                                values.append(instance['node'])

                            if 'node_type' in instance:
                                columns.append(f'{prefix} Type')
                                values.append(instance['node_type'])

                            if 'uuid' in instance:
                                columns.append(f'{prefix} UUID')
                                values.append(instance['uuid'])

                            if 'heartbeat' in instance:
                                columns.append(f'{prefix} Heartbeat')
                                values.append(instance['heartbeat'])

                            if 'capacity' in instance:
                                columns.append(f'{prefix} Capacity')
                                values.append(str(instance['capacity']))

                    # Instance Group Details
                    if 'instance_groups' in controller_data:
                        for i, group in enumerate(controller_data['instance_groups']):
                            prefix = f"Instance Group {i+1}"

                            if 'name' in group:
                                columns.append(f'{prefix} Name')
                                values.append(group['name'])

                            if 'capacity' in group:
                                columns.append(f'{prefix} Capacity')
                                values.append(str(group['capacity']))

                            if 'instances' in group:
                                instances_list = ', '.join(group['instances']) if group['instances'] else 'None'
                                columns.append(f'{prefix} Instances')
                                values.append(instances_list)

                return (columns, values)
            else:
                errors = []
                if gateway_response.status_code != HTTP_OK:
                    errors.append(f"Gateway API failed with status {gateway_response.status_code}")
                if controller_response.status_code != HTTP_OK:
                    errors.append(f"Controller API failed with status {controller_response.status_code}")
                raise AAPClientError("; ".join(errors))

        except AAPClientError as e:
            raise SystemExit(f"Configuration error: {e}")
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
