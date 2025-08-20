"""
Inventory commands for AAP CLI using Click and Rich.

This module provides enhanced versions of inventory management commands
with beautiful rich output formatting and improved user experience.
"""

from typing import Dict, Any, List

import click
from click_option_group import optgroup, MutuallyExclusiveOptionGroup

from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_ACCEPTED,
    HTTP_NOT_FOUND
)
from aapclient.common.functions import (
    resolve_inventory_name,
    resolve_organization_name,
    format_variables_display
)
from aapclient.cli.decorators import (
    list_command,
    show_command,
    create_command,
    delete_command,
    update_command,
    get_client_from_context,
    validate_resource_identifier
)
from aapclient.cli.output import (
    create_table,
    show_key_value,
    show_details_table,
    show_raw_json,
    show_raw_yaml,
    show_success_message,
    show_error_message,
    format_datetime_rich
)


@click.group()
def inventory():
    """Manage inventories."""
    pass


@inventory.command('list')
@click.option('--organization', help='Filter by organization name or ID')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'organization', 'type', 'created', 'modified'],
    default_sort='id'
)
def list_inventories(console, output_format, utc, limit, offset, organization, show_all, sort_by, reverse):
    """List inventories."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build query parameters
    params = {}

    # Add server-side sorting
    sort_field = _map_sort_field_to_api(sort_by)
    if reverse:
        sort_field = f"-{sort_field}"
    params['order_by'] = sort_field

    # Add filters
    if organization:
        try:
            org_id = resolve_organization_name(client_manager.gateway, organization)
            params['organization'] = org_id
        except Exception:
            params['organization__name'] = organization

    # Fetch inventories with proper pagination handling
    if show_all:
        # Fetch all results by paginating through all pages
        inventories = []
        page = 1
        params['page_size'] = 200  # Use large page size for efficiency

        while True:
            params['page'] = page
            response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/", params=params)

            if response.status_code != HTTP_OK:
                show_error_message(console, f"Failed to fetch inventories: HTTP {response.status_code}")
                click.get_current_context().exit(1)

            page_data = response.json()
            page_inventories = page_data.get('results', [])

            if not page_inventories:
                break

            inventories.extend(page_inventories)

            # Check if we have more pages
            if not page_data.get('next'):
                break

            page += 1

        # Create a mock data structure for consistency
        data = {
            'count': len(inventories),
            'results': inventories
        }
    else:
        # Regular pagination
        params['page_size'] = limit
        params['page'] = (offset // limit) + 1

        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/", params=params)

        if response.status_code != HTTP_OK:
            show_error_message(console, f"Failed to fetch inventories: HTTP {response.status_code}")
            click.get_current_context().exit(1)

        data = response.json()
        inventories = data.get('results', [])

    if not inventories:
        console.print("[yellow]No inventories found.[/yellow]")
        return

    # Process data into structured format first
    columns = ['ID', 'Name', 'Status', 'Type', 'Organization']
    processed_data = []

    for inventory in inventories:
        # Determine status - match cliff version exactly
        status = "failing" if inventory.get('inventory_sources_with_failures', 0) > 0 else "ok"

        # Type is always 'inventory' for regular inventories, 'smart' for smart inventories
        inv_type = 'smart' if inventory.get('kind') == 'smart' else 'inventory'

        processed_data.append({
            'ID': inventory['id'],
            'Name': inventory['name'],
            'Status': status,
            'Type': inv_type,
            'Organization': inventory.get('summary_fields', {}).get('organization', {}).get('name', 'N/A')
        })

    # Format the processed data according to requested format
    if output_format == 'json':
        show_raw_json(processed_data)
    elif output_format == 'yaml':
        show_raw_yaml(processed_data)
    else:
        # Table format
        rows = []
        for item in processed_data:
            rows.append([str(item[col]) for col in columns])

        table = create_table(columns, rows)
        console.print(table)

        # Show pagination info
        if not show_all and data.get('count', 0) > len(inventories):
            console.print(f"[dim]Showing {len(inventories)} of {data['count']} total inventories[/dim]")


@inventory.command('show')
@click.argument('inventory_name', metavar='<inventory>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Inventory ID (overrides name argument)')
@show_command
def show_inventory(console, output_format, utc, inventory_name, id):
    """Show details of a specific inventory."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve inventory ID
    if id:
        inventory_id = id
    else:
        inventory_id = resolve_inventory_name(client, inventory_name)

    # Fetch inventory details
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/")
    inventory = response.json()

    # Rich formatted display - pass client for complete data
    data = _format_inventory_data(inventory, utc, client, output_format)

    if output_format == 'json':
        show_raw_json(data)
    elif output_format == 'yaml':
        show_raw_yaml(data)
    else:
        show_details_table(console, data)


@inventory.command('create')
@click.argument('name', metavar='<name>')
@click.option('--organization', required=True, help='Organization name or ID')
@click.option('--description', help='Inventory description')
@click.option('--variables', help='Inventory variables as JSON string')
@click.option('--prevent-instance-group-fallback', is_flag=True, help='Prevent instance group fallback')
@click.option('--instance-groups', multiple=True, help='Instance group names or IDs to assign to inventory')
@create_command
def create_inventory(console, name, organization, description, variables, prevent_instance_group_fallback, instance_groups):
    """Create a new inventory."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build inventory data - match legacy version exactly
    inventory_data = {
        'name': name
    }

    # Resolve organization ID
    try:
        org_id = resolve_organization_name(client_manager.gateway, organization)
        inventory_data['organization'] = org_id
    except Exception as e:
        show_error_message(console, f"Failed to resolve organization '{organization}': {e}")
        click.get_current_context().exit(1)

    # Optional fields
    if description:
        inventory_data['description'] = description

    # Boolean field for instance group fallback
    if prevent_instance_group_fallback:
        inventory_data['prevent_instance_group_fallback'] = True

    if variables:
        # Validate and set variables
        try:
            import json
            import yaml
            # Try to parse as JSON first, then YAML
            try:
                json.loads(variables)
                inventory_data['variables'] = variables
            except json.JSONDecodeError:
                # Try YAML
                parsed = yaml.safe_load(variables)
                inventory_data['variables'] = json.dumps(parsed)
        except Exception as e:
            show_error_message(console, f"Invalid variables format: {e}")
            click.get_current_context().exit(1)

    # Create the inventory
    response = client.post(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/", json=inventory_data)

    if response.status_code != HTTP_CREATED:
        try:
            error_data = response.json()
            if isinstance(error_data, dict):
                for field, errors in error_data.items():
                    if isinstance(errors, list):
                        show_error_message(console, f"{field}: {', '.join(errors)}")
                    else:
                        show_error_message(console, f"{field}: {errors}")
            else:
                show_error_message(console, f"API error: {error_data}")
        except:
            show_error_message(console, f"Failed to create inventory: HTTP {response.status_code}")
        click.get_current_context().exit(1)

    created_inventory = response.json()
    inventory_id = created_inventory['id']

    # Assign instance groups if provided - match legacy behavior
    association_errors = []
    if instance_groups and inventory_id:
        association_errors = _assign_instance_groups(client, inventory_id, instance_groups)

    # Display warnings for association errors
    for error in association_errors:
        show_error_message(console, f"Warning: {error}")

    # Display created inventory
    data = _format_inventory_data(created_inventory, False, client)
    show_success_message(console, f"Inventory '{name}' created successfully")
    show_details_table(console, data)


@inventory.command('delete')
@click.argument('inventory_name', metavar='<inventory>', required=False)
@click.option('--id', type=int, help='Inventory ID (overrides name argument)')
@delete_command()
def delete_inventory(console, inventory_name, id):
    """Delete an inventory."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve inventory ID
    if id:
        inventory_id = id
        identifier = str(id)
    elif inventory_name:
        inventory_id = resolve_inventory_name(client, inventory_name)
        identifier = inventory_name
    else:
        show_error_message(console, "Inventory identifier is required")
        click.get_current_context().exit(1)

    # Delete the inventory
    response = client.delete(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/")
    show_success_message(console, f"Inventory '{identifier}' deleted successfully")


@inventory.command('set')
@click.argument('inventory_name', metavar='<inventory>', required=False)
@click.option('--id', type=int, help='Inventory ID (overrides name argument)')
@click.option('--set-name', help='New inventory name')
@click.option('--organization', help='Organization name or ID')
@click.option('--description', help='Inventory description')
@click.option('--variables', help='Inventory variables as JSON string')
@optgroup.group('Instance Group Fallback', cls=MutuallyExclusiveOptionGroup,
                help='Control instance group fallback behavior')
@optgroup.option('--allow-instance-group-fallback', is_flag=True, help='Allow instance group fallback')
@optgroup.option('--prevent-instance-group-fallback', is_flag=True, help='Prevent instance group fallback')
@click.option('--add-instance-group', 'add_instance_groups', multiple=True,
              help='Instance group name or ID to add to inventory (can be used multiple times)')
@click.option('--remove-instance-group', 'remove_instance_groups', multiple=True,
              help='Instance group name or ID to remove from inventory (can be used multiple times)')
@update_command
def set_inventory(console, inventory_name, id, set_name, organization, description, variables,
                  allow_instance_group_fallback, prevent_instance_group_fallback, add_instance_groups, remove_instance_groups):
    """Update an existing inventory."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve inventory ID
    if id:
        inventory_id = id
    elif inventory_name:
        inventory_id = resolve_inventory_name(client, inventory_name)
    else:
        show_error_message(console, "Inventory identifier is required")
        click.get_current_context().exit(1)

    # Build update data
    update_data = {}

    if set_name:
        update_data['name'] = set_name

    if organization:
        try:
            org_id = resolve_organization_name(client_manager.gateway, organization)
            update_data['organization'] = org_id
        except Exception as e:
            show_error_message(console, f"Failed to resolve organization '{organization}': {e}")
            click.get_current_context().exit(1)

    if description is not None:  # Allow empty string to clear description
        update_data['description'] = description

    if allow_instance_group_fallback:
        update_data['prevent_instance_group_fallback'] = False
    elif prevent_instance_group_fallback:
        update_data['prevent_instance_group_fallback'] = True

    if variables is not None:
        # Validate and set variables
        try:
            import json
            import yaml
            # Try to parse as JSON first, then YAML
            try:
                json.loads(variables)
                update_data['variables'] = variables
            except json.JSONDecodeError:
                # Try YAML
                parsed = yaml.safe_load(variables)
                update_data['variables'] = json.dumps(parsed)
        except Exception as e:
            show_error_message(console, f"Invalid variables format: {e}")
            click.get_current_context().exit(1)

    # Check if we have any updates to make
    has_updates = bool(update_data or add_instance_groups or remove_instance_groups)
    if not has_updates:
        show_error_message(console, "At least one field must be specified to update")
        click.get_current_context().exit(1)

    # Update inventory if we have field changes
    if update_data:
        response = client.patch(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/", json=update_data)

        if response.status_code != HTTP_OK:
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    for field, errors in error_data.items():
                        if isinstance(errors, list):
                            show_error_message(console, f"{field}: {', '.join(errors)}")
                        else:
                            show_error_message(console, f"{field}: {errors}")
                else:
                    show_error_message(console, f"API error: {error_data}")
            except:
                show_error_message(console, f"Failed to update inventory: HTTP {response.status_code}")
            click.get_current_context().exit(1)

    # Handle instance group additions and removals
    association_errors = []
    if add_instance_groups:
        association_errors.extend(_assign_instance_groups(client, inventory_id, add_instance_groups))

    if remove_instance_groups:
        association_errors.extend(_remove_instance_groups(client, inventory_id, remove_instance_groups))

    # Display warnings for association errors
    for error in association_errors:
        show_error_message(console, f"Warning: {error}")

    # Get updated inventory data and display
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/")
    if response.status_code == HTTP_OK:
        updated_inventory = response.json()
        data = _format_inventory_data(updated_inventory, False, client)
        show_success_message(console, f"Inventory '{inventory_name}' updated successfully")
        show_details_table(console, data)
    else:
        show_success_message(console, f"Inventory '{inventory_name}' updated successfully")


@inventory.group('variables')
def inventory_variables():
    """Manage inventory variables."""
    pass


@inventory_variables.command('show')
@click.argument('inventory_name', metavar='<inventory>', required=False)
@click.option('--id', type=int, help='Inventory ID (overrides positional parameter)')
@show_command
def show_inventory_variables(console, output_format, utc, inventory_name, id):
    """Show inventory variables in YAML format."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve inventory ID
    if id:
        inventory_id = id
        identifier = str(id)
    elif inventory_name:
        inventory_id = resolve_inventory_name(client, inventory_name)
        identifier = inventory_name
    else:
        show_error_message(console, "Inventory identifier is required")
        click.get_current_context().exit(1)

    # Fetch inventory details to get variables
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/")
    inventory_data = response.json()

    # Extract and parse variables for display
    variables_raw = inventory_data.get('variables', {})

    # Parse variables for JSON/YAML output
    from aapclient.common.functions import parse_variables_for_output
    variables_parsed = parse_variables_for_output(variables_raw)

    if output_format == 'json':
        show_raw_json(variables_parsed)
    elif output_format == 'yaml':
        show_raw_yaml(variables_parsed)
    else:
        # Table format showing inventory name and variables in YAML
        from aapclient.common.functions import format_variables_yaml_display
        variables_yaml = format_variables_yaml_display(variables_raw)

        # Create a simple key-value display
        data = {
            'Inventory': inventory_data['name'],
            'Variables': variables_yaml
        }
        show_details_table(console, data)


def _assign_instance_groups(client, inventory_id: int, instance_groups: list) -> list:
    """Assign instance groups to inventory, returning list of errors."""
    from aapclient.common.functions import resolve_instance_group_name
    from aapclient.common.exceptions import AAPResourceNotFoundError

    association_errors = []

    for ig_name in instance_groups:
        try:
            # Resolve instance group name to ID
            ig_id = resolve_instance_group_name(client, ig_name)

            # Associate instance group with inventory
            assoc_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/instance_groups/"
            assoc_response = client.post(assoc_endpoint, json={'id': ig_id})

            if assoc_response.status_code not in [HTTP_OK, HTTP_CREATED, 204]:
                association_errors.append(f"Failed to associate instance group '{ig_name}': HTTP {assoc_response.status_code}")

        except AAPResourceNotFoundError:
            association_errors.append(f"Instance group '{ig_name}' not found")
        except Exception as e:
            association_errors.append(f"Failed to associate instance group '{ig_name}': {e}")

    return association_errors


def _remove_instance_groups(client, inventory_id: int, instance_groups: list) -> list:
    """Remove instance groups from inventory, returning list of errors."""
    from aapclient.common.functions import resolve_instance_group_name
    from aapclient.common.exceptions import AAPResourceNotFoundError

    association_errors = []

    for ig_name in instance_groups:
        try:
            # Resolve instance group name to ID
            ig_id = resolve_instance_group_name(client, ig_name)

            # Disassociate instance group from inventory
            disassoc_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/instance_groups/"
            disassoc_response = client.post(disassoc_endpoint, json={'id': ig_id, 'disassociate': True})

            if disassoc_response.status_code not in [HTTP_OK, HTTP_CREATED, 204]:
                association_errors.append(f"Failed to remove instance group '{ig_name}': HTTP {disassoc_response.status_code}")

        except AAPResourceNotFoundError:
            association_errors.append(f"Instance group '{ig_name}' not found")
        except Exception as e:
            association_errors.append(f"Failed to remove instance group '{ig_name}': {e}")

    return association_errors


def _map_sort_field_to_api(sort_field: str) -> str:
    """Map user-friendly sort field names to API field names."""
    field_mapping = {
        'id': 'id',
        'name': 'name',
        'organization': 'organization__name',
        'type': 'kind',  # Map 'type' sort to 'kind' API field
        'created': 'created',
        'modified': 'modified'
    }
    return field_mapping.get(sort_field, 'id')


def _format_inventory_data(inventory: Dict[str, Any], use_utc: bool = False, client=None, output_format: str = 'table') -> Dict[str, Any]:
    """Format inventory data for rich display - match cliff version exactly."""
    data = {}

    # Basic fields - match cliff order and names exactly
    data['ID'] = str(inventory['id'])
    data['Name'] = inventory['name']
    data['Description'] = inventory.get('description', '') or ''  # Empty string, not "N/A"

    # Type - match cliff version (not "Kind")
    kind = inventory.get('kind', '')
    data['Type'] = kind if kind else 'inventory'

    # Organization
    org = inventory.get('summary_fields', {}).get('organization', {})
    data['Organization'] = org.get('name', '')

    # Host and group information - match cliff order
    data['Total Hosts'] = str(inventory.get('total_hosts', 0))
    data['Total Groups'] = str(inventory.get('total_groups', 0))

    # Inventory sources information - match cliff exactly
    data['Total Inventory Sources'] = str(inventory.get('total_inventory_sources', 0))
    data['Inventory Sources with Failures'] = str(inventory.get('inventory_sources_with_failures', 0))

    # Instance groups information - match cliff exactly with API call
    instance_groups_display = ""
    if client:
        inventory_id = inventory.get('id')
        if inventory_id:
            try:
                ig_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/instance_groups/")
                if ig_response.status_code == HTTP_OK:
                    ig_data = ig_response.json()
                    instance_groups = ig_data.get('results', [])
                    if instance_groups:
                        ig_names = [ig.get('name', '') for ig in instance_groups if ig.get('name')]
                        instance_groups_display = ', '.join(ig_names)
            except Exception:
                instance_groups_display = ""

    data['Instance Groups'] = instance_groups_display

    # Prevent instance group fallback
    data['Prevent Instance Group Fallback'] = str(inventory.get('prevent_instance_group_fallback', False))

    # Variables - match cliff formatting
    variables = inventory.get('variables', '')
    if variables:
        data['Variables'] = format_variables_display(variables, 'inventory')
    else:
        data['Variables'] = ''

    # Timestamps - match cliff exactly
    data['Created'] = format_datetime_rich(inventory.get('created'), use_utc, output_format)
    created_by = inventory.get('summary_fields', {}).get('created_by', {})
    data['Created By'] = created_by.get('username', '') if created_by else ''

    data['Modified'] = format_datetime_rich(inventory.get('modified'), use_utc, output_format)
    modified_by = inventory.get('summary_fields', {}).get('modified_by', {})
    data['Modified By'] = modified_by.get('username', '') if modified_by else ''

    return data


# Add the inventory group to the main CLI
def register_inventory_commands(main_group: click.Group) -> None:
    """Register inventory commands with the main CLI group."""
    main_group.add_command(inventory)
