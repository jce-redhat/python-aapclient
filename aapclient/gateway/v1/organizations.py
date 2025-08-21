"""Organization commands for AAP CLI using Click and Rich."""

import sys
import time
from typing import Dict, Any, Optional

import click
from click_option_group import optgroup, MutuallyExclusiveOptionGroup
from rich.console import Console
from rich.table import Table

from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError
from aapclient.common.functions import (
    resolve_organization_name,
    resolve_execution_environment_name,
    resolve_credential_name,
    resolve_instance_group_name
)
from aapclient.decorators import (
    list_command,
    show_command,
    create_command,
    update_command,
    delete_command,
    standard_command,
    get_client_from_context,
    get_console_from_context,
    validate_resource_identifier
)
from aapclient.output import (
    show_key_value,
    show_details_table,
    show_raw_json,
    show_raw_yaml,
    show_success_message,
    show_error_message,
    format_datetime_rich,
    format_value_for_output
)


@click.group()
def organization():
    """Manage AAP organizations."""
    pass


def _format_organization_data(organization_data: Dict[str, Any], use_utc: bool = False, output_format: str = 'table', client_manager=None) -> Dict[str, Any]:
    """Format organization data for display with enhanced fields from both gateway and controller APIs."""
    from collections import OrderedDict

    # Use OrderedDict to maintain field order
    data = OrderedDict()

    # Get organization ID for controller API lookups
    org_id = organization_data.get('id')
    org_name = organization_data.get('name', '')

    # Basic information in specified order
    data['ID'] = str(org_id or '')
    data['Name'] = org_name

    # User and team counts from gateway API
    related_counts = organization_data.get('summary_fields', {}).get('related_field_counts', {})
    data['Users'] = str(related_counts.get('users', 0))
    data['Teams'] = str(related_counts.get('teams', 0))

    # Controller API data (execution environment, galaxy credentials, and instance groups)
    execution_environment = ''
    galaxy_credentials = ''
    instance_groups = ''

    if client_manager and org_id:
        try:
            controller_client = client_manager.controller

            # Get controller organization data for execution environment
            controller_response = controller_client.get(f"/api/controller/v2/organizations/")
            controller_orgs = controller_response.json().get('results', [])

            controller_org = None
            for org in controller_orgs:
                if org.get('name') == org_name:
                    controller_org = org
                    break

            if controller_org:
                controller_org_id = controller_org['id']

                # Get execution environment
                default_ee = controller_org.get('summary_fields', {}).get('default_environment')
                if default_ee:
                    execution_environment = default_ee.get('name', '')

                # Get galaxy credentials
                gc_response = controller_client.get(f"/api/controller/v2/organizations/{controller_org_id}/galaxy_credentials/")
                gc_data = gc_response.json()
                cred_names = [cred.get('name', '') for cred in gc_data.get('results', [])]
                galaxy_credentials = ', '.join(cred_names) if cred_names else ''

                # Get instance groups
                ig_response = controller_client.get(f"/api/controller/v2/organizations/{controller_org_id}/instance_groups/")
                ig_data = ig_response.json()
                ig_names = [ig.get('name', '') for ig in ig_data.get('results', [])]
                instance_groups = ', '.join(ig_names) if ig_names else ''

        except Exception:
            # If controller API access fails, continue with empty values
            pass

    data['Execution Environment'] = execution_environment
    data['Galaxy Credentials'] = galaxy_credentials
    data['Instance Groups'] = instance_groups

    # Max hosts
    max_hosts = organization_data.get('max_hosts')
    data['Max Hosts'] = str(max_hosts) if max_hosts is not None else ''

    # Timestamps
    data['Created'] = format_datetime_rich(organization_data.get('created'), use_utc, output_format)
    data['Modified'] = format_datetime_rich(organization_data.get('modified'), use_utc, output_format)

    # Created/Modified by
    created_by = organization_data.get('summary_fields', {}).get('created_by', {})
    data['Created By'] = created_by.get('username', '') if created_by else ''

    modified_by = organization_data.get('summary_fields', {}).get('modified_by', {})
    data['Modified By'] = modified_by.get('username', '') if modified_by else ''

    # Remove empty fields for cleaner display, but keep certain fields always visible
    always_show = ['ID', 'Name', 'Users', 'Teams', 'Execution Environment', 'Galaxy Credentials', 'Instance Groups', 'Max Hosts']
    data = OrderedDict((k, v) for k, v in data.items() if v not in ['', None, 'N/A'] or k in always_show)

    return data


@organization.command('list')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'created', 'modified'],
    default_sort='id'
)
def list_organizations(console: Console, output_format: str, utc: bool, sort_by: str, reverse: bool, limit: int, offset: int, show_all: bool) -> None:
    """List organizations."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Build API parameters
    params = {}

    # Pagination
    if not show_all:
        params['page_size'] = limit
        params['page'] = (offset // limit) + 1

    # Sorting
    sort_field = sort_by if sort_by else 'id'
    if reverse:
        params['order_by'] = f'-{sort_field}'
    else:
        params['order_by'] = sort_field

    # Fetch data
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
    response = client.get(endpoint, params=params)
    data = response.json()
    organizations = data.get('results', [])

    if output_format in ['json', 'yaml']:
        # Process data into the format that matches table columns
        processed_data = []
        for org in organizations:
            processed_data.append({
                'ID': org.get('id'),
                'Name': org.get('name', ''),
                'Description': org.get('description', ''),
                'Max Hosts': org.get('max_hosts') if org.get('max_hosts') is not None else '',
                'Created': format_datetime_rich(org.get('created', ''), utc, output_format)
            })

        if output_format == 'json':
            show_raw_json(processed_data)
        else:
            show_raw_yaml(processed_data)
        return

    # Table format
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Description", style="white")
    table.add_column("Max Hosts", style="yellow")
    table.add_column("Created", style="green")

    for org in organizations:
        max_hosts = org.get('max_hosts')
        max_hosts_display = str(max_hosts) if max_hosts is not None else ''

        table.add_row(
            str(org.get('id', '')),
            org.get('name', ''),
            org.get('description', '')[:50] + ('...' if len(org.get('description', '')) > 50 else ''),
            max_hosts_display,
            format_datetime_rich(org.get('created', ''), utc, output_format)
        )

    console.print(table)

    # Show pagination info
    total_count = data.get('count', len(organizations))
    if not show_all and len(organizations) < total_count:
        console.print(f"\nShowing {len(organizations)} of {total_count} total organizations")


@organization.command('show')
@click.argument('organization_name', metavar='<organization>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Organization ID (overrides name argument)')
@show_command
def show_organization(console: Console, output_format: str, utc: bool, organization_name: Optional[str], id: Optional[int]) -> None:
    """Show details of a specific organization."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve organization ID
    if id:
        organization_id = id
    elif organization_name:
        organization_id = resolve_organization_name(client, organization_name, api="gateway")
    else:
        show_error_message(console, "Organization identifier is required")
        sys.exit(1)

    # Get organization details
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
    response = client.get(endpoint)
    organization_data = response.json()

    # Format organization data for display
    formatted_data = _format_organization_data(organization_data, utc, output_format, client_manager)

    if output_format == 'json':
        show_raw_json(formatted_data)
    elif output_format == 'yaml':
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


@organization.command('create')
@click.argument('name', metavar='<name>')
@click.option('--description', help='Organization description')
@click.option('--max-hosts', type=int, help='Maximum number of hosts for this organization')
@click.option('--execution-environment', help='Default execution environment name or ID')
@click.option('--galaxy-credential', multiple=True, help='Galaxy credential name or ID (can be used multiple times)')
@click.option('--instance-group', multiple=True, help='Instance group name or ID (can be used multiple times)')
@create_command
def create_organization(console: Console, name: str, description: Optional[str], max_hosts: Optional[int], execution_environment: Optional[str], galaxy_credential: tuple, instance_group: tuple) -> None:
    """Create a new organization."""
    client_manager = get_client_from_context()
    gateway_client = client_manager.gateway
    controller_client = client_manager.controller

    # Build organization data for gateway API
    organization_data = {
        'name': name
    }

    if description:
        organization_data['description'] = description

    if max_hosts is not None:
        organization_data['max_hosts'] = max_hosts

    # Step 1: Create organization in gateway API
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
    response = gateway_client.post(endpoint, json=organization_data)

    if response.status_code != HTTP_CREATED:
        show_error_message(console, f"Failed to create organization: {response.status_code}")
        sys.exit(1)

    created_organization = response.json()
    gateway_org_id = created_organization['id']
    show_success_message(console, f"Organization '{name}' created successfully")

        # Step 2: Handle controller-specific resources if any are specified
    if execution_environment or galaxy_credential or instance_group:
        # Wait for synchronization to controller API (with timeout)
        controller_org_id = None
        max_wait = 30  # 30 seconds timeout
        wait_interval = 2  # Check every 2 seconds

        for attempt in range(max_wait // wait_interval):
            try:
                # Look for the organization in controller API
                controller_response = controller_client.get(f"/api/controller/v2/organizations/")
                controller_orgs = controller_response.json().get('results', [])

                for org in controller_orgs:
                    if org.get('name') == name:
                        controller_org_id = org['id']
                        break

                if controller_org_id:
                    break

                time.sleep(wait_interval)
            except Exception as e:
                time.sleep(wait_interval)

        if not controller_org_id:
            show_error_message(console, "Organization created but controller synchronization timed out. You may need to configure controller resources manually.")
            formatted_data = _format_organization_data(created_organization, use_utc=False, output_format='table', client_manager=client_manager)
            show_details_table(console, formatted_data)
            return

        # Step 3: Configure controller resources
        try:
            # Set default execution environment
            if execution_environment:
                ee_id = resolve_execution_environment_name(controller_client, execution_environment, api="controller")
                update_data = {'default_environment': ee_id}
                controller_client.patch(f"/api/controller/v2/organizations/{controller_org_id}/", json=update_data)

            # Associate galaxy credentials
            for gc_name in galaxy_credential:
                gc_id = resolve_credential_name(controller_client, gc_name, api="controller")
                controller_client.post(f"/api/controller/v2/organizations/{controller_org_id}/galaxy_credentials/",
                                     json={'id': gc_id})

            # Associate instance groups
            for ig_name in instance_group:
                ig_id = resolve_instance_group_name(controller_client, ig_name, api="controller")
                controller_client.post(f"/api/controller/v2/organizations/{controller_org_id}/instance_groups/",
                                     json={'id': ig_id})

        except Exception as e:
            show_error_message(console, f"Organization created but failed to configure controller resources: {e}")
            formatted_data = _format_organization_data(created_organization, use_utc=False, output_format='table', client_manager=client_manager)
            show_details_table(console, formatted_data)
            return

    # Show the final organization details
    formatted_data = _format_organization_data(created_organization, use_utc=False, output_format='table', client_manager=client_manager)
    show_details_table(console, formatted_data)


@organization.command('set')
@click.argument('organization_name', metavar='<organization>', required=False)
@click.option('--id', type=int, help='Organization ID (overrides name argument)')
@click.option('--name', help='New organization name')
@click.option('--description', help='New organization description')
@click.option('--max-hosts', type=int, help='Maximum number of hosts for this organization')
@click.option('--execution-environment', help='Default execution environment name or ID')
@optgroup.group('Galaxy Credentials', cls=MutuallyExclusiveOptionGroup,
                help='Add or remove galaxy credentials')
@optgroup.option('--add-galaxy-credential', multiple=True, help='Add galaxy credential name or ID (can be used multiple times)')
@optgroup.option('--remove-galaxy-credential', multiple=True, help='Remove galaxy credential name or ID (can be used multiple times)')
@optgroup.group('Instance Groups', cls=MutuallyExclusiveOptionGroup,
                help='Add or remove instance groups')
@optgroup.option('--add-instance-group', multiple=True, help='Add instance group name or ID (can be used multiple times)')
@optgroup.option('--remove-instance-group', multiple=True, help='Remove instance group name or ID (can be used multiple times)')
@update_command
def set_organization(console: Console, organization_name: Optional[str], id: Optional[int], name: Optional[str], description: Optional[str], max_hosts: Optional[int], execution_environment: Optional[str],
                    add_galaxy_credential: tuple, remove_galaxy_credential: tuple, add_instance_group: tuple, remove_instance_group: tuple) -> None:
    """Update organization settings."""
    client_manager = get_client_from_context()
    gateway_client = client_manager.gateway
    controller_client = client_manager.controller

    # Resolve organization ID
    if id:
        organization_id = id
        identifier = str(id)
    elif organization_name:
        organization_id = resolve_organization_name(gateway_client, organization_name, api="gateway")
        identifier = organization_name
    else:
        show_error_message(console, "Organization identifier is required")
        sys.exit(1)

    # Build gateway update data
    gateway_update_data = {}

    if name:
        gateway_update_data['name'] = name
    if description is not None:  # Allow empty string
        gateway_update_data['description'] = description
    if max_hosts is not None:
        gateway_update_data['max_hosts'] = max_hosts

    # Check if any updates are specified
    has_gateway_updates = bool(gateway_update_data)
    has_controller_updates = bool(execution_environment or add_galaxy_credential or remove_galaxy_credential or
                                 add_instance_group or remove_instance_group)

    if not has_gateway_updates and not has_controller_updates:
        show_error_message(console, "No updates specified")
        sys.exit(1)

    # Update gateway organization if needed
    if has_gateway_updates:
        endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
        response = gateway_client.patch(endpoint, json=gateway_update_data)

        if response.status_code != HTTP_OK:
            show_error_message(console, f"Failed to update organization: {response.status_code}")
            sys.exit(1)

    # Handle controller-specific updates if needed
    if has_controller_updates:
        # Find the organization in controller API
        controller_org_id = None

        try:
            controller_response = controller_client.get(f"/api/controller/v2/organizations/")
            controller_orgs = controller_response.json().get('results', [])

            # Get the current organization name from gateway API for lookup
            gateway_response = gateway_client.get(f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/")
            current_org_data = gateway_response.json()
            current_org_name = current_org_data.get('name', '')

            for org in controller_orgs:
                if org.get('name') == current_org_name:
                    controller_org_id = org['id']
                    break

            if not controller_org_id:
                show_error_message(console, "Organization not found in controller API for resource updates")
                sys.exit(1)

            # Update execution environment
            if execution_environment:
                ee_id = resolve_execution_environment_name(controller_client, execution_environment, api="controller")
                update_data = {'default_environment': ee_id}
                controller_client.patch(f"/api/controller/v2/organizations/{controller_org_id}/", json=update_data)

            # Add galaxy credentials
            for gc_name in add_galaxy_credential:
                gc_id = resolve_credential_name(controller_client, gc_name, api="controller")
                controller_client.post(f"/api/controller/v2/organizations/{controller_org_id}/galaxy_credentials/",
                                     json={'id': gc_id})

            # Remove galaxy credentials
            for gc_name in remove_galaxy_credential:
                gc_id = resolve_credential_name(controller_client, gc_name, api="controller")
                controller_client.post(f"/api/controller/v2/organizations/{controller_org_id}/galaxy_credentials/",
                                     json={'id': gc_id, 'disassociate': True})

            # Add instance groups
            for ig_name in add_instance_group:
                ig_id = resolve_instance_group_name(controller_client, ig_name, api="controller")
                controller_client.post(f"/api/controller/v2/organizations/{controller_org_id}/instance_groups/",
                                     json={'id': ig_id})

            # Remove instance groups
            for ig_name in remove_instance_group:
                ig_id = resolve_instance_group_name(controller_client, ig_name, api="controller")
                controller_client.post(f"/api/controller/v2/organizations/{controller_org_id}/instance_groups/",
                                     json={'id': ig_id, 'disassociate': True})

        except Exception as e:
            show_error_message(console, f"Failed to update controller resources: {e}")
            sys.exit(1)

    # Get the final organization state for display
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
    response = gateway_client.get(endpoint)
    updated_organization = response.json()

    show_success_message(console, f"Organization '{identifier}' updated successfully")

    # Show the updated organization details
    formatted_data = _format_organization_data(updated_organization, use_utc=False, output_format='table', client_manager=client_manager)
    show_details_table(console, formatted_data)


@organization.command('delete')
@click.argument('organization_name', metavar='<organization>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Organization ID (overrides name argument)')
@delete_command("Are you sure you want to delete this organization?")
def delete_organization(console: Console, organization_name: Optional[str], id: Optional[int]) -> None:
    """Delete an organization."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve organization ID
    if id:
        organization_id = id
        identifier = str(id)
    elif organization_name:
        organization_id = resolve_organization_name(client, organization_name, api="gateway")
        identifier = organization_name
    else:
        show_error_message(console, "Organization identifier is required")
        sys.exit(1)

    # Delete organization
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Organization '{identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete organization: {response.status_code}")
        sys.exit(1)


def register_organization_commands(main_group: click.Group) -> None:
    """Register organization commands with the main CLI group."""
    main_group.add_command(organization)
