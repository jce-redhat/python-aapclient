"""Status command for AAP Gateway API."""
from cliff.lister import Lister
from .client import AAPHTTPClient
from .config import AAPConfig
from .constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from .exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError


class StatusCommand(Lister):
    """Show AAP platform status."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Add service argument for detailed service information
        parser.add_argument(
            '--service',
            choices=['controller', 'eda', 'hub'],
            help='Show detailed information for a specific service'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the status command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Get status from Gateway API
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}status/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Status", "status endpoint")
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                data = response.json()

                # Services information
                services = data.get('services', {})

                # Handle service detail views based on --service argument
                if parsed_args.service == 'controller':
                    controller_service = services.get('controller', {})
                    if not controller_service:
                        raise AAPClientError("Controller service data not found")

                    # Define columns for controller detail display
                    columns = [
                        'Node Name',
                        'Node Status',
                        'HA',
                        'Version',
                        'Active Node',
                        'Install UUID'
                    ]

                    # Build controller node rows
                    rows = []
                    nodes = controller_service.get('nodes', {})
                    for node_name, node_info in nodes.items():
                        node_status = node_info.get('status', 'Unknown')

                        # Extract detailed information from response
                        response_data = node_info.get('response', {})
                        ha = 'Yes' if response_data.get('ha', False) else 'No'
                        version = response_data.get('version', 'Unknown')
                        active_node = response_data.get('active_node', 'Unknown')
                        install_uuid = response_data.get('install_uuid', 'Unknown')

                        row = [
                            node_name,
                            node_status,
                            ha,
                            version,
                            active_node,
                            install_uuid
                        ]
                        rows.append(row)

                    return (columns, rows)

                elif parsed_args.service == 'eda':
                    eda_service = services.get('eda', {})
                    if not eda_service:
                        raise AAPClientError("EDA service data not found")

                    # Define columns for EDA detail display
                    columns = [
                        'Node Name',
                        'Node Status'
                    ]

                    # Build EDA node rows
                    rows = []
                    nodes = eda_service.get('nodes', {})
                    for node_name, node_info in nodes.items():
                        node_status = node_info.get('status', 'Unknown')

                        row = [
                            node_name,
                            node_status
                        ]
                        rows.append(row)

                    return (columns, rows)

                elif parsed_args.service == 'hub':
                    hub_service = services.get('hub', {})
                    if not hub_service:
                        raise AAPClientError("Hub service data not found")

                    # Define columns for Hub detail display
                    columns = [
                        'Status',
                        'Database',
                        'Redis',
                        'Storage',
                        'Workers',
                        'API Apps',
                        'Content Apps'
                    ]

                    # Build Hub service row
                    rows = []
                    service_status = hub_service.get('status', 'Unknown')

                    # Extract detailed information from the first (and typically only) node
                    nodes = hub_service.get('nodes', {})
                    if nodes:
                        # Get the first node's response data
                        first_node = next(iter(nodes.values()))
                        response_data = first_node.get('response', {})

                        # Extract workers
                        workers = response_data.get('online_workers', [])
                        worker_names = [worker.get('name', 'Unknown') for worker in workers]
                        workers_str = '\n'.join(worker_names) if worker_names else 'None'

                        # Extract API apps
                        api_apps = response_data.get('online_api_apps', [])
                        api_app_names = [app.get('name', 'Unknown') for app in api_apps]
                        api_apps_str = '\n'.join(api_app_names) if api_app_names else 'None'

                        # Extract content apps
                        content_apps = response_data.get('online_content_apps', [])
                        content_app_names = [app.get('name', 'Unknown') for app in content_apps]
                        content_apps_str = '\n'.join(content_app_names) if content_app_names else 'None'

                        # Extract connection status
                        db_connected = response_data.get('database_connection', {}).get('connected', False)
                        redis_connected = response_data.get('redis_connection', {}).get('connected', False)

                        # Extract storage information
                        storage = response_data.get('storage', {})
                        if storage:
                            total = storage.get('total', 0)
                            used = storage.get('used', 0)
                            free = storage.get('free', 0)
                            # Convert bytes to GB for readability
                            total_gb = round(total / (1024**3), 2) if total else 0
                            used_gb = round(used / (1024**3), 2) if used else 0
                            free_gb = round(free / (1024**3), 2) if free else 0
                            storage_str = f"Total: {total_gb}GB\nUsed: {used_gb}GB\nFree: {free_gb}GB"
                        else:
                            storage_str = 'Unknown'

                    else:
                        workers_str = 'Unknown'
                        api_apps_str = 'Unknown'
                        content_apps_str = 'Unknown'
                        db_connected = False
                        redis_connected = False
                        storage_str = 'Unknown'

                    row = [
                        service_status,
                        'connected' if db_connected else 'not connected',
                        'connected' if redis_connected else 'not connected',
                        storage_str,
                        workers_str,
                        api_apps_str,
                        content_apps_str
                    ]
                    rows.append(row)

                    return (columns, rows)

                # Default view - show all services
                # Define columns for table display
                columns = [
                    'Service Name',
                    'Service Status',
                    'Service Nodes'
                ]

                # Build rows data
                rows = []
                for service_name, service_info in services.items():
                    service_status = service_info.get('status', 'Unknown')

                    # Build nodes information
                    if 'nodes' in service_info:
                        nodes = service_info['nodes']
                        node_list = []
                        for node_name, node_info in nodes.items():
                            node_status = node_info.get('status', 'Unknown')
                            node_list.append(f"{node_name} ({node_status})")
                        service_nodes = ', '.join(node_list)
                    elif service_name == 'redis':
                        # Special handling for Redis
                        mode = service_info.get('mode', 'Unknown')
                        ping = service_info.get('ping', False)
                        ping_status = 'OK' if ping else 'Failed'
                        service_nodes = f"Mode: {mode}, Ping: {ping_status}"
                    else:
                        service_nodes = 'N/A'

                    row = [
                        service_name.title(),
                        service_status,
                        service_nodes
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
