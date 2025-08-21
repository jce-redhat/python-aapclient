"""
Execution Environment commands for AAP Controller API v2.

This module implements Click-based commands for managing AAP execution environments,
providing rich output formatting and enhanced user experience.
"""

import click
import sys
from typing import Dict, Any

from rich.console import Console
from rich.table import Table

from aapclient.cli.decorators import (
    list_command, show_command, create_command, update_command, delete_command,
    standard_command, handle_api_errors, common_options, validate_resource_identifier
)
from aapclient.cli.output import (
    create_table, show_details_table, show_error_message, show_success_message,
    format_datetime_rich, show_raw_json, show_raw_yaml
)
from aapclient.common.constants import CONTROLLER_API_VERSION_ENDPOINT, HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT
from aapclient.common.functions import (
    resolve_execution_environment_name, resolve_organization_name, resolve_credential_name,
    format_datetime
)
from aapclient.common.exceptions import AAPClientError, AAPAPIError


def get_client_from_context():
    """Get the client manager from the current click context."""
    ctx = click.get_current_context()
    return ctx.find_root().obj['client_manager']


@click.group()
def execution_environment():
    """Manage AAP execution environments. (Alias: ee)"""
    pass


@execution_environment.command('list')
@click.option('--organization', help='Filter by organization name or ID')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'organization', 'image', 'created', 'modified'],
    default_sort='id'
)
def list_execution_environments(console, output_format, utc, limit, offset, organization, show_all, sort_by, reverse):
    """List execution environments."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build query parameters
    params = {}

    # Apply server-side sorting
    sort_param = _map_sort_field_to_api(sort_by)
    if reverse:
        sort_param = f"-{sort_param}"
    params['order_by'] = sort_param

    # Apply pagination unless --all is specified
    if not show_all:
        params['page_size'] = limit
        if offset:
            params['offset'] = offset

    # Apply organization filter
    if organization:
        try:
            org_id = resolve_organization_name(client, organization, api="controller")
            params['organization'] = org_id
        except Exception as e:
            show_error_message(console, f"Error resolving organization '{organization}': {e}")
            sys.exit(1)

    # Fetch execution environments
    try:
        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/", params=params)
        data = response.json()
        execution_environments = data.get('results', [])

        if not execution_environments:
            if output_format == 'json':
                show_raw_json([])
            elif output_format == 'yaml':
                show_raw_yaml([])
            else:
                console.print("[yellow]No execution environments found.[/yellow]")
            return

        if output_format in ['json', 'yaml']:
            # Process data into the format that matches table columns
            processed_data = []
            for ee in execution_environments:
                org_name = ee.get('summary_fields', {}).get('organization', {}).get('name', '')
                processed_data.append({
                    'ID': ee.get('id'),
                    'Name': ee.get('name', ''),
                    'Image': ee.get('image', ''),
                    'Organization': org_name
                })

            if output_format == 'json':
                show_raw_json(processed_data)
            else:
                show_raw_yaml(processed_data)
            return

        # Format the data for table output
        else:
            # Table format
            columns = ['ID', 'Name', 'Image', 'Organization']
            rows = []

            for ee in execution_environments:
                organization_name = ee.get('summary_fields', {}).get('organization', {}).get('name', '')

                rows.append([
                    str(ee['id']),
                    ee.get('name', ''),
                    ee.get('image', ''),
                    organization_name
                ])

            table = create_table(columns, rows)
            console.print(table)

            # Show pagination info
            if not show_all and data.get('count', 0) > len(execution_environments):
                console.print(f"[dim]Showing {len(execution_environments)} of {data['count']} total execution environments[/dim]")

    except Exception as e:
        show_error_message(console, f"Failed to list execution environments: {e}")
        sys.exit(1)


@execution_environment.command('show')
@click.argument('execution_environment_name', metavar='<execution_environment>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Execution Environment ID (overrides name argument)')
@show_command
def show_execution_environment(console, output_format, utc, execution_environment_name, id):
    """Show details of a specific execution environment."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve execution environment ID
    if id:
        ee_id = id
    else:
        ee_id = resolve_execution_environment_name(client, execution_environment_name)

    # Fetch execution environment details
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/")
    execution_environment = response.json()

    # Format the data for display
    formatted_data = _format_execution_environment_data(execution_environment, use_utc=utc, output_format=output_format)

    if output_format == 'json':
        show_raw_json(formatted_data)
    elif output_format == 'yaml':
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


@execution_environment.command('create')
@click.argument('name', metavar='<name>')
@click.option('--image', required=True, help='Container image for this execution environment')
@click.option('--description', help='Execution Environment description')
@click.option('--organization', help='Organization name or ID')
@click.option('--credential', help='Container Registry credential name or ID')
@click.option('--pull-policy', type=click.Choice(['always', 'missing', 'never']), help='Pull policy for execution environment image')
@create_command
def create_execution_environment(console, name, image, description, organization, credential, pull_policy):
    """Create a new execution environment."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build the execution environment data
    ee_data = {
        'name': name,
        'image': image
    }

    # Add optional fields
    if description:
        ee_data['description'] = description

    if organization:
        try:
            org_id = resolve_organization_name(client, organization, api="controller")
            ee_data['organization'] = org_id
        except Exception as e:
            show_error_message(console, f"Error resolving organization '{organization}': {e}")
            sys.exit(1)

    if credential:
        try:
            cred_id = resolve_credential_name(client, credential, api="controller")
            ee_data['credential'] = cred_id
        except Exception as e:
            show_error_message(console, f"Error resolving credential '{credential}': {e}")
            sys.exit(1)

    if pull_policy:
        ee_data['pull'] = pull_policy

    try:
        # Create the execution environment
        response = client.post(f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/", json=ee_data)

        if response.status_code == HTTP_CREATED:
            ee_result = response.json()
            ee_id = ee_result.get('id')

            # Fetch the complete execution environment details for display
            response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/")
            execution_environment = response.json()

            # Format and display the created execution environment
            formatted_data = _format_execution_environment_data(execution_environment, output_format='table')
            show_details_table(console, formatted_data)
        else:
            show_error_message(console, f"Failed to create execution environment: HTTP {response.status_code}")
            sys.exit(1)

    except Exception as e:
        show_error_message(console, f"Failed to create execution environment: {e}")
        sys.exit(1)


@execution_environment.command('set')
@click.argument('execution_environment_name', metavar='<execution_environment>', required=False)
@click.option('--id', type=int, help='Execution Environment ID (overrides name argument)')
@click.option('--set-name', help='New execution environment name')
@click.option('--image', help='Container image for this execution environment')
@click.option('--description', help='Execution Environment description')
@click.option('--organization', help='Organization name or ID')
@click.option('--credential', help='Container Registry credential name or ID')
@click.option('--pull-policy', type=click.Choice(['always', 'missing', 'never']), help='Pull policy for execution environment image')
@update_command
def set_execution_environment(console, execution_environment_name, id, set_name, image, description, organization, credential, pull_policy):
    """Update an existing execution environment."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve execution environment ID
    if id:
        ee_id = id
        ee_identifier = str(id)
    elif execution_environment_name:
        ee_id = resolve_execution_environment_name(client, execution_environment_name)
        ee_identifier = execution_environment_name
    else:
        show_error_message(console, "Execution Environment identifier is required")
        sys.exit(1)

    # Build update data from provided arguments
    update_data = {}

    if set_name:
        update_data['name'] = set_name

    if image:
        update_data['image'] = image

    if description is not None:  # Allow empty string to clear description
        update_data['description'] = description

    if organization:
        try:
            org_id = resolve_organization_name(client, organization, api="controller")
            update_data['organization'] = org_id
        except Exception as e:
            show_error_message(console, f"Error resolving organization '{organization}': {e}")
            sys.exit(1)

    if credential:
        try:
            cred_id = resolve_credential_name(client, credential, api="controller")
            update_data['credential'] = cred_id
        except Exception as e:
            show_error_message(console, f"Error resolving credential '{credential}': {e}")
            sys.exit(1)

    if pull_policy:
        update_data['pull'] = pull_policy

    if not update_data:
        show_error_message(console, "No update fields provided")
        sys.exit(1)

    try:
        # Update the execution environment
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/"
        response = client.patch(endpoint, json=update_data)

        if response.status_code == HTTP_OK:
            execution_environment_data = response.json()
            data = _format_execution_environment_data(execution_environment_data, use_utc=False, output_format='table')
            show_details_table(console, data)
        else:
            show_error_message(console, f"Failed to update execution environment: HTTP {response.status_code}")
            sys.exit(1)

    except Exception as e:
        show_error_message(console, f"Failed to update execution environment '{ee_identifier}': {e}")
        sys.exit(1)


@execution_environment.command('delete')
@click.argument('execution_environment_name', metavar='<execution_environment>', required=False)
@click.option('--id', type=int, help='Execution Environment ID (overrides name argument)')
@delete_command()
def delete_execution_environment(console, execution_environment_name, id):
    """Delete an execution environment."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve execution environment ID
    if id:
        ee_id = id
        ee_identifier = str(id)
    elif execution_environment_name:
        ee_id = resolve_execution_environment_name(client, execution_environment_name)
        ee_identifier = execution_environment_name
    else:
        show_error_message(console, "Execution Environment identifier is required")
        sys.exit(1)

    try:
        # Get execution environment details for confirmation message
        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/")
        execution_environment = response.json()
        ee_name = execution_environment.get('name', 'Unknown')

        # Delete the execution environment
        response = client.delete(f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/")

        if response.status_code == HTTP_NO_CONTENT:
            show_success_message(console, f"Execution environment '{ee_name}' deleted successfully")
        else:
            show_error_message(console, f"Failed to delete execution environment: HTTP {response.status_code}")
            sys.exit(1)

    except Exception as e:
        show_error_message(console, f"Failed to delete execution environment '{ee_identifier}': {e}")
        sys.exit(1)


def _map_sort_field_to_api(sort_field: str) -> str:
    """Map user-friendly sort field names to API field names."""
    mapping = {
        'id': 'id',
        'name': 'name',
        'organization': 'organization__name',
        'image': 'image',
        'created': 'created',
        'modified': 'modified'
    }
    return mapping.get(sort_field, 'id')


def _format_execution_environment_data(ee: Dict[str, Any], use_utc: bool = False, output_format: str = 'table') -> Dict[str, Any]:
    """Format execution environment data for consistent display across commands."""
    data = {}

    # Basic fields
    data['ID'] = str(ee.get('id', ''))
    data['Name'] = ee.get('name', '')
    data['Description'] = ee.get('description', '')
    data['Image'] = ee.get('image', '')

    # Organization
    organization = ee.get('summary_fields', {}).get('organization', {})
    data['Organization'] = organization.get('name', '') if organization else ''

    # Credential
    credential = ee.get('summary_fields', {}).get('credential', {})
    data['Credential'] = credential.get('name', '') if credential else ''

    # Pull policy
    data['Pull policy'] = ee.get('pull', '')

    # Timestamps
    data['Created'] = format_datetime_rich(ee.get('created'), use_utc, output_format)
    data['Modified'] = format_datetime_rich(ee.get('modified'), use_utc, output_format)

    return data


# Create an alias command
@click.group(name='ee')
def ee_alias():
    """Alias for 'execution-environment' command."""
    pass

# Add the execution environment group to the main CLI
def register_execution_environment_commands(main_group: click.Group) -> None:
    """Register execution environment commands with the main CLI group."""
    main_group.add_command(execution_environment)

    # Copy all subcommands from execution_environment to ee_alias
    for cmd_name, cmd in execution_environment.commands.items():
        ee_alias.add_command(cmd, name=cmd_name)

    main_group.add_command(ee_alias)
