"""Team commands for AAP CLI using Click and Rich."""

import sys
from typing import Dict, Any
from collections import OrderedDict

import click
from rich.table import Table

from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError
from aapclient.common.functions import (
    resolve_organization_name,
    resolve_team_name
)
from aapclient.cli.decorators import (
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
from aapclient.cli.output import (
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
def team():
    """Manage AAP teams."""
    pass


def _format_team_data(team_data: Dict[str, Any], use_utc: bool = False, output_format: str = 'table') -> Dict[str, Any]:
    """Format team data for display."""
    from collections import OrderedDict

    # Use OrderedDict to maintain field order
    data = OrderedDict()

    # Basic information
    data['ID'] = str(team_data.get('id', ''))
    data['Name'] = team_data.get('name', '')
    data['Description'] = team_data.get('description', '')

    # Organization
    organization_info = team_data.get('summary_fields', {}).get('organization', {})
    data['Organization'] = organization_info.get('name', '') if organization_info else ''

    # Timestamps
    data['Created'] = format_datetime_rich(team_data.get('created'), use_utc, output_format)
    data['Modified'] = format_datetime_rich(team_data.get('modified'), use_utc, output_format)

    # Created/Modified by
    created_by = team_data.get('summary_fields', {}).get('created_by', {})
    data['Created By'] = created_by.get('username', '') if created_by else ''

    modified_by = team_data.get('summary_fields', {}).get('modified_by', {})
    data['Modified By'] = modified_by.get('username', '') if modified_by else ''

    # Remove empty fields for cleaner display, but keep certain fields always visible
    always_show = ['ID', 'Name', 'Description', 'Organization']
    data = OrderedDict((k, v) for k, v in data.items() if v not in ['', None, 'N/A'] or k in always_show)

    return data


@team.command('list')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'organization', 'created', 'modified'],
    default_sort='id'
)
def list_teams(console, output_format, utc, sort_by, reverse, limit, offset, show_all):
    """List teams."""
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
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/"
    response = client.get(endpoint, params=params)
    data = response.json()
    teams = data.get('results', [])

    if output_format in ['json', 'yaml']:
        # Process data into the format that matches table columns
        processed_data = []
        for team in teams:
            org_info = team.get('summary_fields', {}).get('organization', {})
            org_name = org_info.get('name', '') if org_info else ''

            processed_data.append({
                'ID': team.get('id'),
                'Name': team.get('name', ''),
                'Organization': org_name
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
    table.add_column("Organization", style="yellow")

    for team in teams:
        # Get organization name from summary fields
        org_info = team.get('summary_fields', {}).get('organization', {})
        org_name = org_info.get('name', '') if org_info else ''

        table.add_row(
            str(team.get('id', '')),
            team.get('name', ''),
            org_name
        )

    console.print(table)

    # Show pagination info
    total_count = data.get('count', len(teams))
    if not show_all and len(teams) < total_count:
        console.print(f"\nShowing {len(teams)} of {total_count} total teams")


@team.command('show')
@click.argument('team_name', metavar='<team>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Team ID (overrides name argument)')
@show_command
def show_team(console, output_format, utc, team_name, id):
    """Show details of a specific team."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve team ID
    if id:
        team_id = id
    elif team_name:
        team_id = resolve_team_name(client, team_name, api="gateway")
    else:
        show_error_message(console, "Team identifier is required")
        sys.exit(1)

    # Get team details
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
    response = client.get(endpoint)
    team_data = response.json()

    # Format team data for display
    formatted_data = _format_team_data(team_data, utc, output_format)

    if output_format == 'json':
        show_raw_json(formatted_data)
    elif output_format == 'yaml':
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


@team.command('create')
@click.argument('name', metavar='<name>')
@click.option('--organization', required=True, help='Organization name or ID')
@click.option('--description', help='Team description')
@create_command
def create_team(console, name, organization, description):
    """Create a new team."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve organization ID
    try:
        org_id = resolve_organization_name(client, organization, api="gateway")
    except Exception as e:
        show_error_message(console, f"Error resolving organization '{organization}': {e}")
        sys.exit(1)

    # Build team data
    team_data = {
        'name': name,
        'organization': org_id
    }

    if description:
        team_data['description'] = description

    # Create team
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/"
    response = client.post(endpoint, json=team_data)

    if response.status_code == HTTP_CREATED:
        created_team = response.json()
        show_success_message(console, f"Team '{name}' created successfully")

        # Show the created team details
        formatted_data = _format_team_data(created_team, use_utc=False, output_format='table')
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Failed to create team: {response.status_code}")
        sys.exit(1)


@team.command('set')
@click.argument('team_name', metavar='<team>', required=False)
@click.option('--id', type=int, help='Team ID (overrides name argument)')
@click.option('--new-name', help='New team name')
@click.option('--organization', help='Organization name or ID')
@click.option('--description', help='Team description')
@update_command
def set_team(console, team_name, id, new_name, organization, description):
    """Update team settings."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve team ID
    if id:
        team_id = id
        identifier = str(id)
    elif team_name:
        team_id = resolve_team_name(client, team_name, api="gateway")
        identifier = team_name
    else:
        show_error_message(console, "Team identifier is required")
        sys.exit(1)

    # Build update data
    update_data = {}

    if new_name:
        update_data['name'] = new_name
    if description is not None:  # Allow empty string
        update_data['description'] = description
    if organization:
        try:
            org_id = resolve_organization_name(client, organization, api="gateway")
            update_data['organization'] = org_id
        except Exception as e:
            show_error_message(console, f"Error resolving organization '{organization}': {e}")
            sys.exit(1)

    if not update_data:
        show_error_message(console, "No updates specified")
        sys.exit(1)

    # Update team
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        updated_team = response.json()
        show_success_message(console, f"Team '{identifier}' updated successfully")

        # Show the updated team details
        formatted_data = _format_team_data(updated_team, use_utc=False, output_format='table')
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Failed to update team: {response.status_code}")
        sys.exit(1)


@team.command('delete')
@click.argument('team_name', metavar='<team>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Team ID (overrides name argument)')
@delete_command("Are you sure you want to delete this team?")
def delete_team(console, team_name, id):
    """Delete a team."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve team ID
    if id:
        team_id = id
        identifier = str(id)
    elif team_name:
        team_id = resolve_team_name(client, team_name, api="gateway")
        identifier = team_name
    else:
        show_error_message(console, "Team identifier is required")
        sys.exit(1)

    # Delete team
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Team '{identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete team: {response.status_code}")
        sys.exit(1)


def register_team_commands(main_group: click.Group) -> None:
    """Register team commands with the main CLI group."""
    main_group.add_command(team)
