"""Instance and Instance Group CLI commands for AAP Controller API v2."""

import click
from click_option_group import optgroup, MutuallyExclusiveOptionGroup
import sys
from typing import Dict, Any

from aapclient.cli.decorators import (
    list_command,
    show_command,
    create_command,
    update_command,
    delete_command,
    standard_command,
    validate_resource_identifier,
    get_client_from_context,
    get_console_from_context
)
from aapclient.cli.output import (
    create_table,
    show_details_table,
    show_raw_json,
    show_raw_yaml,
    show_success_message,
    show_error_message,
    format_datetime_rich,
    format_value_for_output
)
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_ACCEPTED
)
from aapclient.common.functions import (
    resolve_instance_name,
    resolve_instance_group_name,
    resolve_credential_name
)
from aapclient.common.exceptions import AAPAPIError


# Instance Commands
@click.group()
def instance():
    """Manage AAP instances."""
    pass


@instance.command('list')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'hostname', 'node_type', 'node_state', 'capacity', 'version'],
    default_sort='id'
)
def list_instances(console, output_format, utc, offset, limit, sort_by, reverse, show_all):
    """List instances."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build query parameters
    params = {}

    # Add sorting
    order_field = sort_by
    if reverse:
        order_field = f'-{sort_by}'
    params['order_by'] = order_field

    # Add pagination
    if not show_all:
        params['page_size'] = limit
        if offset:
            params['offset'] = offset

    # Query instances endpoint
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/"
    response = client.get(endpoint, params=params)

    data = response.json()
    instances = data.get('results', [])

    # Define columns for output
    columns = ['ID', 'Hostname', 'Node Type', 'Node State', 'Enabled', 'Capacity', 'Version']
    rows = []

    for instance in instances:
        # Format capacity with "forks" unit
        capacity_value = instance.get('capacity', '')
        capacity_display = f"{capacity_value} forks" if capacity_value else ""

        row = [
            str(instance.get('id', '')),
            instance.get('hostname', ''),
            instance.get('node_type', ''),
            instance.get('node_state', ''),
            format_value_for_output(instance.get('enabled', False), 'enabled', output_format),
            capacity_display,
            instance.get('version', '')
        ]
        rows.append(row)

    if output_format == 'json':
        show_raw_json(rows)
    elif output_format == 'yaml':
        show_raw_yaml(rows)
    else:
        table = create_table(columns, rows)
        console.print(table)
        total_count = data.get('count', len(instances))
        if len(instances) < total_count:
            console.print(f"\nShowing {len(instances)} of {total_count} total instances")


@instance.command('create')
@click.argument('hostname', metavar='<hostname>')
@click.option('--listener-port', type=click.IntRange(1024, 65535), help='Port for instance communication (1024-65535)')
@click.option('--instance-type', type=click.Choice(['execution', 'hop']), required=True, help='Instance type')
@click.option('--enabled', is_flag=True, help='Enable the instance (sets enabled=true)')
@click.option('--managed-by-policy', is_flag=True, help='Enable management by policy (sets managed_by_policy=true)')
@click.option('--peers-from-control-node', is_flag=True, help='Enable peers from control nodes (sets peers_from_control_nodes=true)')
@create_command
def create_instance(console, hostname, listener_port, instance_type, enabled, managed_by_policy, peers_from_control_node):
    """Create a new instance."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build instance data
    instance_data = {
        'hostname': hostname,
        'node_type': instance_type,
    }

    # Add optional fields if specified
    if listener_port is not None:
        instance_data['listener_port'] = listener_port

    if enabled:
        instance_data['enabled'] = True

    if managed_by_policy:
        instance_data['managed_by_policy'] = True

    if peers_from_control_node:
        instance_data['peers_from_control_nodes'] = True

    # Create instance
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/"
    response = client.post(endpoint, json=instance_data)

    if response.status_code == HTTP_CREATED:
        instance_data = response.json()
        show_success_message(console, f"Instance '{hostname}' created successfully")

        formatted_data = _format_instance_data(instance_data, use_utc=False, output_format='table')
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Instance creation failed with status {response.status_code}")
        sys.exit(1)


@instance.command('show')
@click.argument('instance_name', metavar='<instance>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Instance ID (overrides name argument)')
@show_command
def show_instance(console, output_format, utc, instance_name, id):
    """Show details of a specific instance."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve instance ID
    if id:
        instance_id = id
    elif instance_name:
        instance_id = resolve_instance_name(client, instance_name)
    else:
        show_error_message(console, "Instance identifier is required")
        sys.exit(1)

    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/"
    response = client.get(endpoint)

    instance_data = response.json()
    formatted_data = _format_instance_data(instance_data, utc, output_format)

    if output_format == 'json':
        show_raw_json(formatted_data)
    elif output_format == 'yaml':
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


@instance.command('delete')
@click.argument('instance_name', metavar='<instance>', required=False)
@click.option('--id', type=int, help='Instance ID (overrides name argument)')
@delete_command("Are you sure you want to delete this instance?")
def delete_instance(console, instance_name, id):
    """Delete an instance."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve instance ID
    if id:
        instance_id = id
        instance_identifier = str(id)
    elif instance_name:
        instance_id = resolve_instance_name(client, instance_name)
        instance_identifier = instance_name
    else:
        show_error_message(console, "Instance identifier is required")
        sys.exit(1)

    # Delete instance by setting node_state to "deprovisioning"
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/"
    patch_data = {'node_state': 'deprovisioning'}
    response = client.patch(endpoint, json=patch_data)

    if response.status_code == HTTP_OK:
        show_success_message(console, f"Instance '{instance_identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete instance: {response.status_code}")
        sys.exit(1)


@instance.command('download')
@click.argument('instance_name', metavar='<instance>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Instance ID (overrides name argument)')
@click.option('--output', '-o', help='Output filename (default: <hostname>_install_bundle.tar.gz)')
@standard_command
def download_instance(console, instance_name, id, output):
    """Download instance install bundle."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve instance ID and get instance details
    if id:
        instance_id = id
        instance_identifier = str(id)
        # Get instance details to find hostname for filename
        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/")
        instance_data = response.json()
        hostname = instance_data.get('hostname', f'instance_{instance_id}')
    elif instance_name:
        instance_id = resolve_instance_name(client, instance_name)
        instance_identifier = instance_name
        hostname = instance_name
    else:
        show_error_message(console, "Instance identifier is required")
        sys.exit(1)

    # Download install bundle first to get the API-suggested filename
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/install_bundle/"

    try:
        response = client.get(endpoint)

        if response.status_code == HTTP_OK:
            # Determine output filename
            if not output:
                # Extract filename from Content-Disposition header
                content_disp = response.headers.get('Content-Disposition', '')
                if 'filename=' in content_disp:
                    # Parse the filename from the header
                    parts = content_disp.split('filename=')
                    if len(parts) > 1:
                        output = parts[1].strip()
                    else:
                        # Fallback to constructed name if parsing fails
                        output = f"{hostname}_install_bundle.tar.gz"
                else:
                    # Fallback to constructed name if no Content-Disposition
                    output = f"{hostname}_install_bundle.tar.gz"

            # Check if file already exists and prompt for overwrite
            import os
            if os.path.exists(output):
                if not click.confirm(f"File '{output}' already exists. Overwrite?"):
                    show_error_message(console, "Download cancelled")
                    sys.exit(1)

            # Write the binary content to file
            with open(output, 'wb') as f:
                f.write(response.content)

            file_size = len(response.content)
            show_success_message(console, f"Install bundle downloaded: {output} ({file_size:,} bytes)")
        else:
            # Try to get error message from response
            try:
                error_data = response.json()
                error_msg = error_data.get('msg', error_data.get('detail', f'HTTP {response.status_code}'))
            except:
                error_msg = f"HTTP {response.status_code}"

            show_error_message(console, f"Failed to download install bundle: {error_msg}")
            sys.exit(1)

    except Exception as e:
        show_error_message(console, f"Error downloading install bundle: {str(e)}")
        sys.exit(1)


@instance.command('set')
@click.argument('instance_name', metavar='<instance>', required=False)
@click.option('--id', type=int, help='Instance ID (overrides name argument)')
@click.option('--capacity-adjustment', type=click.IntRange(0, 100), help='Capacity adjustment percentage (0-100)')

@optgroup.group('Instance State', cls=MutuallyExclusiveOptionGroup,
                help='Control instance enabled/disabled state')
@optgroup.option('--enable', is_flag=True, help='Enable the instance')
@optgroup.option('--disable', is_flag=True, help='Disable the instance')

@optgroup.group('Peers from Control Nodes', cls=MutuallyExclusiveOptionGroup,
                help='Control peers from control nodes setting')
@optgroup.option('--enable-peers-from-control-nodes', is_flag=True, help='Enable peers from control nodes')
@optgroup.option('--disable-peers-from-control-nodes', is_flag=True, help='Disable peers from control nodes')

@optgroup.group('Management by Policy', cls=MutuallyExclusiveOptionGroup,
                help='Control management by policy setting')
@optgroup.option('--enable-manage-by-policy', is_flag=True, help='Enable management by policy')
@optgroup.option('--disable-manage-by-policy', is_flag=True, help='Disable management by policy')
@update_command
def set_instance(console, instance_name, id, capacity_adjustment, enable, disable,
                enable_peers_from_control_nodes, disable_peers_from_control_nodes,
                enable_manage_by_policy, disable_manage_by_policy):
    """Update an existing instance."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve instance ID
    if id:
        instance_id = id
        instance_identifier = str(id)
    elif instance_name:
        instance_id = resolve_instance_name(client, instance_name)
        instance_identifier = instance_name
    else:
        show_error_message(console, "Instance identifier is required")
        sys.exit(1)

    # Build update data from provided arguments
    update_data = {}

    if capacity_adjustment is not None:
        update_data['capacity_adjustment'] = capacity_adjustment / 100.0

    if enable:
        update_data['enabled'] = True
    elif disable:
        update_data['enabled'] = False

    if enable_peers_from_control_nodes:
        update_data['peers_from_control_nodes'] = True
    elif disable_peers_from_control_nodes:
        update_data['peers_from_control_nodes'] = False

    if enable_manage_by_policy:
        update_data['managed_by_policy'] = True
    elif disable_manage_by_policy:
        update_data['managed_by_policy'] = False

    if not update_data:
        show_error_message(console, "No update fields provided")
        sys.exit(1)

    # Update instance
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instances/{instance_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        instance_data = response.json()
        show_success_message(console, f"Instance '{instance_identifier}' updated successfully")

        formatted_data = _format_instance_data(instance_data, use_utc=False, output_format='table')
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Instance update failed with status {response.status_code}")
        sys.exit(1)


# Instance Group Commands
@click.group(name='group')
def instance_group():
    """Manage AAP instance groups."""
    pass


@instance_group.command('list')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'is_container_group', 'jobs_running', 'jobs_total', 'percent_capacity_remaining'],
    default_sort='id'
)
def list_instance_groups(console, output_format, utc, offset, limit, sort_by, reverse, show_all):
    """List instance groups."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build query parameters
    params = {}

    # Add sorting
    order_field = sort_by
    if reverse:
        order_field = f'-{sort_by}'
    params['order_by'] = order_field

    # Add pagination
    if not show_all:
        params['page_size'] = limit
        if offset:
            params['offset'] = offset

    # Query instance groups endpoint
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/"
    response = client.get(endpoint, params=params)

    data = response.json()
    instance_groups = data.get('results', [])

    # Define columns for output
    columns = ['ID', 'Name', 'Type', 'Running Jobs', 'Total Jobs', 'Instances', 'Capacity Remaining']
    rows = []

    for instance_group in instance_groups:
        # Determine type based on is_container_group
        is_container_group = instance_group.get('is_container_group', False)
        group_type = "Container" if is_container_group else "Instance"

        # Calculate instances count - handle both list and integer from API
        instances_value = instance_group.get('instances', [])
        if isinstance(instances_value, list):
            instances_count = len(instances_value)
        else:
            # API returned count as integer
            instances_count = instances_value

        # Capacity remaining only applies to instance groups, not container groups
        capacity_remaining = "" if is_container_group else f"{instance_group.get('percent_capacity_remaining', 0)}%"

        row = [
            str(instance_group.get('id', '')),
            instance_group.get('name', ''),
            group_type,
            str(instance_group.get('jobs_running', 0)),
            str(instance_group.get('jobs_total', 0)),
            str(instances_count),
            capacity_remaining
        ]
        rows.append(row)

    if output_format == 'json':
        show_raw_json(rows)
    elif output_format == 'yaml':
        show_raw_yaml(rows)
    else:
        table = create_table(columns, rows)
        console.print(table)
        total_count = data.get('count', len(instance_groups))
        if len(instance_groups) < total_count:
            console.print(f"\nShowing {len(instance_groups)} of {total_count} total instance groups")


@instance_group.command('show')
@click.argument('instance_group_name', metavar='<instance_group>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Instance Group ID (overrides name argument)')
@show_command
def show_instance_group(console, output_format, utc, instance_group_name, id):
    """Show details of a specific instance group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve instance group ID
    if id:
        instance_group_id = id
    elif instance_group_name:
        instance_group_id = resolve_instance_group_name(client, instance_group_name)
    else:
        show_error_message(console, "Instance Group identifier is required")
        sys.exit(1)

    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
    response = client.get(endpoint)

    instance_group_data = response.json()
    formatted_data = _format_instance_group_data(instance_group_data, utc, output_format)

    if output_format == 'json':
        show_raw_json(formatted_data)
    elif output_format == 'yaml':
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


@instance_group.command('create')
@click.argument('name', metavar='<name>')
@click.option('--is-container-group', is_flag=True, help='Create a container group')
@click.option('--credential', help='Container Registry credential name or ID (container groups only)')
@click.option('--pod-spec-override', help='Pod spec override for container groups (JSON format)')
@click.option('--policy-instance-minimum', type=int, help='Minimum number of instances (instance groups only)')
@click.option('--policy-instance-percentage', type=int, help='Percentage of instances to maintain (instance groups only)')
@click.option('--max-forks', type=int, help='Maximum number of forks')
@click.option('--max-concurrent-jobs', type=int, help='Maximum number of concurrent jobs')
@create_command
def create_instance_group(console, name, is_container_group, credential, pod_spec_override,
                         policy_instance_minimum, policy_instance_percentage, max_forks, max_concurrent_jobs):
    """Create a new instance group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build the instance group data
    instance_group_data = {
        'name': name,
        'is_container_group': is_container_group
    }

    # Add optional fields
    if max_forks is not None:
        instance_group_data['max_forks'] = max_forks

    if max_concurrent_jobs is not None:
        instance_group_data['max_concurrent_jobs'] = max_concurrent_jobs

    # Add container-specific fields
    if is_container_group:
        if credential:
            credential_id = resolve_credential_name(client, credential)
            instance_group_data['credential'] = credential_id
        if pod_spec_override:
            try:
                import json
                instance_group_data['pod_spec_override'] = json.loads(pod_spec_override)
            except json.JSONDecodeError:
                show_error_message(console, "Pod spec override must be valid JSON")
                sys.exit(1)
    else:
        # Add instance-specific fields
        if policy_instance_minimum is not None:
            instance_group_data['policy_instance_minimum'] = policy_instance_minimum
        if policy_instance_percentage is not None:
            instance_group_data['policy_instance_percentage'] = policy_instance_percentage

    # Create instance group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/"
    response = client.post(endpoint, json=instance_group_data)

    if response.status_code == HTTP_CREATED:
        instance_group_data = response.json()
        show_success_message(console, f"Instance Group '{instance_group_data.get('name', '')}' created successfully")

        formatted_data = _format_instance_group_data(instance_group_data, use_utc=False, output_format='table')
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Instance Group creation failed with status {response.status_code}")
        sys.exit(1)


@instance_group.command('set')
@click.argument('instance_group_name', metavar='<instance_group>', required=False)
@click.option('--id', type=int, help='Instance Group ID (overrides name argument)')
@click.option('--set-name', help='New instance group name')
@click.option('--credential', help='Container Registry credential name or ID (container groups only)')
@click.option('--pod-spec-override', help='Pod spec override for container groups (JSON format)')
@click.option('--policy-instance-minimum', type=int, help='Minimum number of instances (instance groups only)')
@click.option('--policy-instance-percentage', type=int, help='Percentage of instances to maintain (instance groups only)')
@click.option('--max-forks', type=int, help='Maximum number of forks')
@click.option('--max-concurrent-jobs', type=int, help='Maximum number of concurrent jobs')
@update_command
def set_instance_group(console, instance_group_name, id, set_name, credential, pod_spec_override,
                      policy_instance_minimum, policy_instance_percentage, max_forks, max_concurrent_jobs):
    """Update an existing instance group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve instance group ID
    if id:
        instance_group_id = id
        instance_group_identifier = str(id)
    elif instance_group_name:
        instance_group_id = resolve_instance_group_name(client, instance_group_name)
        instance_group_identifier = instance_group_name
    else:
        show_error_message(console, "Instance Group identifier is required")
        sys.exit(1)

    # Build update data from provided arguments
    update_data = {}

    if set_name:
        update_data['name'] = set_name

    if max_forks is not None:
        update_data['max_forks'] = max_forks

    if max_concurrent_jobs is not None:
        update_data['max_concurrent_jobs'] = max_concurrent_jobs

    if credential:
        credential_id = resolve_credential_name(client, credential)
        update_data['credential'] = credential_id

    if pod_spec_override:
        try:
            import json
            update_data['pod_spec_override'] = json.loads(pod_spec_override)
        except json.JSONDecodeError:
            show_error_message(console, "Pod spec override must be valid JSON")
            sys.exit(1)

    if policy_instance_minimum is not None:
        update_data['policy_instance_minimum'] = policy_instance_minimum

    if policy_instance_percentage is not None:
        update_data['policy_instance_percentage'] = policy_instance_percentage

    if not update_data:
        show_error_message(console, "No update fields provided")
        sys.exit(1)

    # Update instance group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        instance_group_data = response.json()
        show_success_message(console, f"Instance Group '{instance_group_identifier}' updated successfully")

        formatted_data = _format_instance_group_data(instance_group_data, use_utc=False, output_format='table')
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Instance Group update failed with status {response.status_code}")
        sys.exit(1)


@instance_group.command('delete')
@click.argument('instance_group_name', metavar='<instance_group>', required=False)
@click.option('--id', type=int, help='Instance Group ID (overrides name argument)')
@delete_command("Are you sure you want to delete this instance group?")
def delete_instance_group(console, instance_group_name, id):
    """Delete an instance group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve instance group ID
    if id:
        instance_group_id = id
        instance_group_identifier = str(id)
    elif instance_group_name:
        instance_group_id = resolve_instance_group_name(client, instance_group_name)
        instance_group_identifier = instance_group_name
    else:
        show_error_message(console, "Instance Group identifier is required")
        sys.exit(1)

    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
    response = client.delete(endpoint)

    if response.status_code in [HTTP_NO_CONTENT, HTTP_ACCEPTED]:
        show_success_message(console, f"Instance Group '{instance_group_identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete instance group: {response.status_code}")
        sys.exit(1)


def _format_instance_data(instance: Dict[str, Any], use_utc: bool = False, output_format: str = 'table') -> Dict[str, Any]:
    """Format instance data for consistent display across commands."""
    data = {}

    # Basic fields
    data['ID'] = str(instance.get('id', ''))
    data['Hostname'] = instance.get('hostname', '')
    data['Node Type'] = instance.get('node_type', '')
    data['Node State'] = instance.get('node_state', '')
    data['Enabled'] = format_value_for_output(instance.get('enabled', False), 'enabled', output_format)
    data['Managed by Policy'] = format_value_for_output(instance.get('managed_by_policy', False), 'managed_by_policy', output_format)
    data['CPU Capacity'] = str(instance.get('cpu_capacity', ''))
    data['Memory Capacity'] = str(instance.get('mem_capacity', ''))

    # Format capacity with "forks" unit
    capacity_value = instance.get('capacity', '')
    data['Capacity'] = f"{capacity_value} forks" if capacity_value else ""

    data['Version'] = instance.get('version', '')
    data['Listener Port'] = str(instance.get('listener_port', ''))

    # Timestamps
    data['Created'] = format_datetime_rich(instance.get('created'), use_utc, output_format)
    data['Modified'] = format_datetime_rich(instance.get('modified'), use_utc, output_format)

    return data


def _format_instance_group_data(instance_group: Dict[str, Any], use_utc: bool = False, output_format: str = 'table') -> Dict[str, Any]:
    """Format instance group data for consistent display across commands."""
    data = {}

    # Basic fields
    data['ID'] = str(instance_group.get('id', ''))
    data['Name'] = instance_group.get('name', '')

    # Determine type based on is_container_group
    is_container_group = instance_group.get('is_container_group', False)
    data['Type'] = "Container" if is_container_group else "Instance"

    # Calculate instances count - handle both list and integer from API
    instances_value = instance_group.get('instances', [])
    if isinstance(instances_value, list):
        instances_count = len(instances_value)
    else:
        # API returned count as integer
        instances_count = instances_value

    data['Instances'] = str(instances_count)
    data['Running Jobs'] = str(instance_group.get('jobs_running', 0))
    data['Total Jobs'] = str(instance_group.get('jobs_total', 0))

    # Display credential if it's a container group
    if is_container_group and 'summary_fields' in instance_group and instance_group['summary_fields'].get('credential'):
        credential_name = instance_group['summary_fields']['credential'].get('name', '')
        data['Credential'] = credential_name
    else:
        data['Credential'] = ''

    # Optional fields
    if instance_group.get('max_forks') is not None:
        data['Max Forks'] = str(instance_group.get('max_forks'))

    if instance_group.get('max_concurrent_jobs') is not None:
        data['Max Concurrent Jobs'] = str(instance_group.get('max_concurrent_jobs'))

    # Capacity remaining only applies to instance groups, not container groups (placed after Max Concurrent Jobs)
    if is_container_group:
        data['Capacity Remaining'] = ""
    else:
        data['Capacity Remaining'] = f"{instance_group.get('percent_capacity_remaining', 0)}%"

    # Instance group specific fields
    if not is_container_group:
        if instance_group.get('policy_instance_minimum') is not None:
            data['Policy Instance Minimum'] = str(instance_group.get('policy_instance_minimum'))
        if instance_group.get('policy_instance_percentage') is not None:
            data['Policy Instance Percentage'] = str(instance_group.get('policy_instance_percentage'))

    # Timestamps
    data['Created'] = format_datetime_rich(instance_group.get('created'), use_utc, output_format)
    data['Modified'] = format_datetime_rich(instance_group.get('modified'), use_utc, output_format)

    return data


# Add the instance group subcommand to the instance group
instance.add_command(instance_group)


def register_instance_commands(main_group: click.Group) -> None:
    """Register instance commands with the main CLI group."""
    main_group.add_command(instance)
