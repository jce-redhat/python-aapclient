"""
Common CLI commands (ping, whoami, status) implemented with Click and Rich.

This module provides enhanced versions of common AAP commands using the new
click+rich architecture for better user experience.
"""

import time
from typing import Dict, Any

import click

from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK
)
from aapclient.common.exceptions import AAPAPIError
from aapclient.cli.decorators import show_command, standard_command
from aapclient.cli.output import show_key_value, show_details_table, show_raw_json, show_raw_yaml, show_error_message


def register_common_commands(main_group: click.Group) -> None:
    """
    Register common commands with the main CLI group.

    Args:
        main_group: The main click group to register commands with
    """
    main_group.add_command(ping)
    main_group.add_command(whoami)
    main_group.add_command(status)


@click.command()
@click.option(
    '--detail',
    is_flag=True,
    help='Show detailed connectivity information'
)
@show_command
def ping(console, detail, output_format, utc):
    """
    Test connectivity to AAP API endpoints.

    Checks connectivity to both Gateway and Controller APIs and displays
    response times and service status information.
    """
    from aapclient.cli.decorators import get_client_from_context

    client_manager = get_client_from_context()

    # Get clients
    gateway_client = client_manager.gateway
    controller_client = client_manager.controller

    # Test connectivity using both Gateway and Controller API ping endpoints
    gateway_ping_endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}ping/"
    controller_ping_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}ping/"

    # Measure round-trip time for both endpoints
    start_time = time.time()

    try:
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

            # Build data structure for display
            data = _build_ping_data(
                client_manager,
                gateway_data,
                controller_data,
                gateway_time_ms,
                controller_time_ms,
                detail
            )

            # Format output according to user preference
            if output_format == 'json':
                show_raw_json(data)
            elif output_format == 'yaml':
                show_raw_yaml(data)
            else:
                # Table format
                show_details_table(console, data)

        else:
            show_error_message(console, f"API ping failed - Gateway: {gateway_response.status_code}, Controller: {controller_response.status_code}")

    except AAPAPIError as e:
        show_error_message(console, f"API Error: {e}")
        click.get_current_context().exit(1)


@click.command()
@show_command
def whoami(console, output_format, utc):
    """
    Display current user information.

    Shows details about the currently authenticated user including
    username, email, permissions, and login information.
    """
    from aapclient.cli.decorators import get_client_from_context

    client_manager = get_client_from_context()

    try:
        # Get user information from Gateway API
        gateway_client = client_manager.gateway
        response = gateway_client.get(f"{GATEWAY_API_VERSION_ENDPOINT}me/")

        if response.status_code == HTTP_OK:
            data = response.json()

            # Gateway API returns paginated response with results array
            if 'results' not in data or not data['results']:
                show_error_message(console, "No user data returned from API")
                click.get_current_context().exit(1)

            user_data = data['results'][0]  # Get first (and only) user result

            # Build display data
            display_data = _build_whoami_data(user_data)

            # Format output according to user preference
            if output_format == 'json':
                show_raw_json(display_data)
            elif output_format == 'yaml':
                show_raw_yaml(display_data)
            else:
                # Table format
                show_details_table(console, display_data)

        else:
            show_error_message(console, f"Failed to get user information: HTTP {response.status_code}")
            click.get_current_context().exit(1)

    except AAPAPIError as e:
        show_error_message(console, f"API Error: {e}")
        click.get_current_context().exit(1)


@click.command()
@show_command
def status(console, output_format, utc):
    """
    Display AAP system status and health information.

    Shows overall system status, component health, and basic metrics.
    """
    from aapclient.cli.decorators import get_client_from_context

    client_manager = get_client_from_context()

    try:
        # Get status from Gateway API (this is a placeholder - adjust based on actual AAP API)
        gateway_client = client_manager.gateway
        response = gateway_client.get(f"{GATEWAY_API_VERSION_ENDPOINT}ping/")

        if response.status_code == HTTP_OK:
            data = response.json()

            # Build status display data
            status_data = _build_status_data(data)

            # Format output according to user preference
            if output_format == 'json':
                show_raw_json(status_data)
            elif output_format == 'yaml':
                show_raw_yaml(status_data)
            else:
                # Table format
                show_details_table(console, status_data)

        else:
            show_error_message(console, f"Failed to get system status: HTTP {response.status_code}")
            click.get_current_context().exit(1)

    except AAPAPIError as e:
        show_error_message(console, f"API Error: {e}")
        click.get_current_context().exit(1)


def _build_ping_data(
    client_manager,
    gateway_data: Dict[str, Any],
    controller_data: Dict[str, Any],
    gateway_time_ms: int,
    controller_time_ms: int,
    show_detail: bool
) -> Dict[str, Any]:
    """
    Build ping data structure for display.

    Args:
        client_manager: AAP client manager
        gateway_data: Gateway API response data
        controller_data: Controller API response data
        gateway_time_ms: Gateway response time in milliseconds
        controller_time_ms: Controller response time in milliseconds
        show_detail: Whether to show detailed information

    Returns:
        Dictionary of ping data for display
    """
    data = {}

    # Host information
    data['Host'] = client_manager.config.hostname

    # Gateway API Data
    if 'status' in gateway_data:
        data['Service Status'] = gateway_data['status']

    if 'version' in gateway_data:
        data['AAP Version'] = gateway_data['version']

    data['Gateway Response Time'] = f"{gateway_time_ms}ms"

    if 'db_connected' in gateway_data:
        data['Database Connected'] = 'Yes' if gateway_data['db_connected'] else 'No'

    if 'proxy_connected' in gateway_data:
        data['Proxy Connected'] = 'Yes' if gateway_data['proxy_connected'] else 'No'

    # Controller API Data
    if 'version' in controller_data:
        data['Controller Version'] = controller_data['version']

    data['Controller Response Time'] = f"{controller_time_ms}ms"

    if 'ha' in controller_data:
        data['High Availability'] = 'Yes' if controller_data['ha'] else 'No'

    if 'active_node' in controller_data:
        data['Active Node'] = controller_data['active_node']

    if 'capacity' in controller_data:
        data['Controller Capacity'] = controller_data['capacity']

    # Detailed information (only if requested)
    if show_detail:
        total_time_ms = gateway_time_ms + controller_time_ms
        data['Total Response Time'] = f"{total_time_ms}ms"

        # Add any additional detailed fields here
        if 'redis_connected' in gateway_data:
            data['Redis Connected'] = 'Yes' if gateway_data['redis_connected'] else 'No'

    return data


def _build_whoami_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build whoami data structure for display.

    Args:
        user_data: User data from Gateway API

    Returns:
        Dictionary of user data for display
    """
    data = {}

    # Basic user information
    if 'id' in user_data:
        data['ID'] = str(user_data['id'])

    if 'username' in user_data:
        data['Username'] = user_data['username']

    if 'email' in user_data:
        data['Email'] = user_data['email']

    # Name fields (only show if not empty)
    first_name = user_data.get('first_name', '').strip()
    last_name = user_data.get('last_name', '').strip()

    if first_name:
        data['First Name'] = first_name

    if last_name:
        data['Last Name'] = last_name

    # Permission flags
    if 'is_superuser' in user_data:
        data['Superuser'] = 'Yes' if user_data['is_superuser'] else 'No'

    if 'is_platform_auditor' in user_data:
        data['Platform Auditor'] = 'Yes' if user_data['is_platform_auditor'] else 'No'

    if 'managed' in user_data:
        data['Managed Account'] = 'Yes' if user_data['managed'] else 'No'

    # Timestamps - use existing formatting function
    from aapclient.cli.output import format_datetime_rich

    if 'date_joined' in user_data:
        data['Date Joined'] = format_datetime_rich(user_data['date_joined'])

    if 'last_login' in user_data:
        data['Last Login'] = format_datetime_rich(user_data['last_login'])

    return data


def _build_status_data(ping_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build status data structure for display.

    Args:
        ping_data: Data from ping endpoint

    Returns:
        Dictionary of status data for display
    """
    data = {}

    # Overall status
    if 'status' in ping_data:
        data['Overall Status'] = ping_data['status']

    if 'version' in ping_data:
        data['Platform Version'] = ping_data['version']

    # Component health
    if 'db_connected' in ping_data:
        data['Database Health'] = 'Healthy' if ping_data['db_connected'] else 'Unhealthy'

    if 'proxy_connected' in ping_data:
        data['Proxy Health'] = 'Healthy' if ping_data['proxy_connected'] else 'Unhealthy'

    # Add more status fields as available from the API

    return data
