"""
Credential commands for AAP Controller API v2.

This module implements Click-based commands for managing AAP credentials,
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
from aapclient.common.constants import CONTROLLER_API_VERSION_ENDPOINT, HTTP_OK, HTTP_CREATED
from aapclient.common.functions import (
    resolve_credential_name, resolve_organization_name, format_datetime
)
from aapclient.common.exceptions import AAPClientError, AAPAPIError


def get_client_from_context():
    """Get the client manager from the current click context."""
    ctx = click.get_current_context()
    return ctx.find_root().obj['client_manager']


def _resolve_credential_type_kind(client, kind):
    """
    Resolve credential type kind to ID.

    Args:
        client: Controller API client
        kind: Credential type kind string

    Returns:
        int: Credential type ID

    Raises:
        AAPClientError: If credential type kind not found
    """
    try:
        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}credential_types/", params={'kind': kind})
        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                raise AAPClientError(f"No credential type found for kind '{kind}'")
        else:
            raise AAPClientError(f"Failed to lookup credential type kind '{kind}': HTTP {response.status_code}")
    except Exception as e:
        raise AAPClientError(f"Error resolving credential type kind '{kind}': {e}")


@click.group()
def credential():
    """Manage AAP credentials."""
    pass


@credential.command('list')
@click.option('--organization', help='Filter by organization name or ID')
@click.option('--credential-type', help='Filter by credential type name or ID')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'credential_type', 'organization', 'created', 'modified'],
    default_sort='id'
)
def list_credentials(console, output_format, utc, limit, offset, organization, credential_type, show_all, sort_by, reverse):
    """List credentials."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Build query parameters
        params = {
            'page_size': limit,
            'page': (offset // limit) + 1 if offset else 1
        }

        # Add filters
        if organization:
            try:
                org_id = resolve_organization_name(client, organization)
                params['organization'] = org_id
            except Exception as e:
                show_error_message(console, f"Invalid organization '{organization}': {e}")
                sys.exit(1)

        if credential_type:
            # For credential type, we need to resolve it to ID if it's a name
            # This would require credential type lookup, but for now accept both ID and name
            params['credential_type'] = credential_type

        # Add sorting
        if sort_by:
            order_field = _map_sort_field_to_api(sort_by)
            if reverse:
                order_field = f'-{order_field}'
            params['order_by'] = order_field

        # Collect all results if --all is specified
        all_credentials = []
        if show_all:
            while True:
                response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/", params=params)
                if response.status_code != HTTP_OK:
                    show_error_message(console, f"Failed to fetch credentials: HTTP {response.status_code}")
                    sys.exit(1)

                data = response.json()
                all_credentials.extend(data.get('results', []))

                if not data.get('next'):
                    break
                params['page'] = params.get('page', 1) + 1

            credentials = all_credentials
            total_count = len(all_credentials)
        else:
            # Single page request
            response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/", params=params)
            if response.status_code != HTTP_OK:
                show_error_message(console, f"Failed to fetch credentials: HTTP {response.status_code}")
                sys.exit(1)

            data = response.json()
            credentials = data.get('results', [])
            total_count = data.get('count', 0)

        if output_format in ['json', 'yaml']:
            # Process data into the format that matches table columns
            processed_data = []
            for credential in credentials:
                # Get credential type name from summary_fields
                cred_type_name = ''
                summary_fields = credential.get('summary_fields', {})
                if 'credential_type' in summary_fields and summary_fields['credential_type']:
                    cred_type_name = summary_fields['credential_type'].get('name', '')

                # Get organization name from summary_fields
                org_name = ''
                if 'organization' in summary_fields and summary_fields['organization']:
                    org_name = summary_fields['organization'].get('name', '')

                processed_data.append({
                    'ID': credential.get('id'),
                    'Name': credential.get('name', ''),
                    'Credential Type': cred_type_name,
                    'Organization': org_name
                })

            if output_format == 'json':
                show_raw_json(processed_data)
            else:
                show_raw_yaml(processed_data)
            return

        # Table format
        columns = ['ID', 'Name', 'Credential Type', 'Organization']
        rows = []

        for credential in credentials:
            # Get credential type name from summary_fields
            cred_type_name = ''
            summary_fields = credential.get('summary_fields', {})
            if 'credential_type' in summary_fields and summary_fields['credential_type']:
                cred_type_name = summary_fields['credential_type'].get('name', '')

            # Get organization name from summary_fields
            org_name = ''
            if 'organization' in summary_fields and summary_fields['organization']:
                org_name = summary_fields['organization'].get('name', '')

            rows.append([
                str(credential.get('id', '')),
                credential.get('name', ''),
                cred_type_name,
                org_name
            ])

        # Create and display table
        table = create_table(columns, rows)
        console.print(table)

        # Show pagination info
        if not show_all:
            console.print(f"[dim]Showing {len(credentials)} of {total_count} total credentials[/dim]")

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


def _map_sort_field_to_api(sort_field: str) -> str:
    """Map sort field names to API field names."""
    mapping = {
        'id': 'id',
        'name': 'name',
        'credential_type': 'credential_type__name',
        'organization': 'organization__name',
        'created': 'created',
        'modified': 'modified'
    }
    return mapping.get(sort_field, sort_field)


@credential.command('show')
@click.argument('credential_name', metavar='<credential>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Credential ID (overrides name argument)')
@show_command
def show_credential(console, output_format, utc, credential_name, id):
    """Show details of a specific credential."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve credential ID
    if id:
        credential_id = id
    else:
        credential_id = resolve_credential_name(client, credential_name)

    # Get credential details
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/")
    credential_data = response.json()

    # Format the data for display
    formatted_data = _format_credential_data(credential_data, use_utc=utc)

    if output_format == 'json':
        # For JSON/YAML output, use plain formatting without Rich markup
        plain_data = _format_credential_data_plain(credential_data, use_utc=utc)
        show_raw_json(plain_data)
    elif output_format == 'yaml':
        # For YAML output, use plain formatting without Rich markup
        plain_data = _format_credential_data_plain(credential_data, use_utc=utc)
        show_raw_yaml(plain_data)
    else:
        show_details_table(console, formatted_data)


def _format_credential_data(credential: Dict[str, Any], use_utc: bool = False) -> Dict[str, Any]:
    """Format credential data for consistent display across commands."""
    summary_fields = credential.get('summary_fields', {})

    data = {}
    data['ID'] = str(credential.get('id', ''))
    data['Name'] = credential.get('name', '')
    data['Description'] = credential.get('description', '')

    # Get credential type name from summary_fields
    cred_type_name = ''
    if 'credential_type' in summary_fields and summary_fields['credential_type']:
        cred_type_name = summary_fields['credential_type'].get('name', '')
    data['Credential Type'] = cred_type_name

    # Get organization name from summary_fields
    org_name = ''
    if 'organization' in summary_fields and summary_fields['organization']:
        org_name = summary_fields['organization'].get('name', '')
    data['Organization'] = org_name

    # Add inputs data as separate key-value pairs (API already handles obfuscation)
    inputs = credential.get('inputs', {})
    if inputs:
        for key, value in inputs.items():
            # Format the key to be more user-friendly (capitalize and replace underscores)
            formatted_key = key.replace('_', ' ').title()
            data[formatted_key] = str(value) if value is not None else ''

    # Timestamps
    data['Created'] = format_datetime_rich(credential.get('created'), use_utc)
    data['Modified'] = format_datetime_rich(credential.get('modified'), use_utc)

    return data


def _format_credential_data_plain(credential: Dict[str, Any], use_utc: bool = False) -> Dict[str, Any]:
    """Format credential data for JSON/YAML output without Rich markup."""
    summary_fields = credential.get('summary_fields', {})

    data = {}
    data['ID'] = str(credential.get('id', ''))
    data['Name'] = credential.get('name', '')
    data['Description'] = credential.get('description', '')

    # Get credential type name from summary_fields
    cred_type_name = ''
    if 'credential_type' in summary_fields and summary_fields['credential_type']:
        cred_type_name = summary_fields['credential_type'].get('name', '')
    data['Credential Type'] = cred_type_name

    # Get organization name from summary_fields
    org_name = ''
    if 'organization' in summary_fields and summary_fields['organization']:
        org_name = summary_fields['organization'].get('name', '')
    data['Organization'] = org_name

    # Add inputs data as separate key-value pairs (API already handles obfuscation)
    inputs = credential.get('inputs', {})
    if inputs:
        for key, value in inputs.items():
            # Format the key to be more user-friendly (capitalize and replace underscores)
            formatted_key = key.replace('_', ' ').title()
            data[formatted_key] = str(value) if value is not None else ''

    # Timestamps - use plain formatting without Rich markup
    data['Created'] = format_datetime(credential.get('created'), use_utc)
    data['Modified'] = format_datetime(credential.get('modified'), use_utc)

    return data


@credential.command('create')
@click.argument('name', metavar='<name>')
@click.option('--credential-type', 'credential_type', required=True,
              type=click.Choice(['ssh', 'vault', 'net', 'scm', 'cloud', 'registry',
                               'token', 'insights', 'external', 'kubernetes', 'galaxy', 'cryptography']),
              help='Credential type kind')
@click.option('--organization', help='Organization name or ID')
@click.option('--description', help='Credential description')
@click.option('--username', help='Username for the credential')
@click.option('--password', help='Password for the credential')
@click.option('--ssh-key-data', help='SSH private key for the credential')
@click.option('--ssh-key-unlock', help='Passphrase for SSH private key')
@click.option('--become-method', help='Privilege escalation method')
@click.option('--become-username', help='Privilege escalation username')
@click.option('--become-password', help='Privilege escalation password')
@click.option('--vault-password', help='Vault password')
@click.option('--vault-id', help='Vault identifier')
@click.option('--host', help='Host URL for the credential')
@click.option('--project', help='Project name for SCM credentials')
@click.option('--domain', help='Domain for the credential')
@click.option('--tenant', help='Tenant for the credential')
@click.option('--subscription', help='Subscription ID for cloud credentials')
@click.option('--client-id', 'client_id', help='Client ID for the credential')
@click.option('--secret', help='Client secret for the credential')
@click.option('--access-token', help='Access token for the credential')
@click.option('--authorize-password', help='Authorization password')
@click.option('--inputs', help='Credential inputs as JSON string (alternative to individual field options)')
@create_command
def create_credential(console, name, credential_type, organization, description, username, password,
                     ssh_key_data, ssh_key_unlock, become_method, become_username, become_password,
                     vault_password, vault_id, host, project, domain, tenant, subscription,
                     client_id, secret, access_token, authorize_password, inputs):
    """Create a new credential."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve credential type kind to ID
        cred_type_id = _resolve_credential_type_kind(client, credential_type)

        # Resolve organization if provided
        org_id = None
        if organization:
            org_id = resolve_organization_name(client, organization)

        # Build credential data
        credential_data = {
            'name': name,
            'credential_type': cred_type_id,
        }

        if description:
            credential_data['description'] = description
        if org_id:
            credential_data['organization'] = org_id

        # Build inputs object based on provided parameters
        inputs_dict = {}

        # If --inputs JSON string is provided, parse it
        if inputs:
            import json
            try:
                inputs_dict = json.loads(inputs)
            except json.JSONDecodeError as e:
                show_error_message(console, f"Invalid JSON in --inputs: {e}")
                sys.exit(1)

        # Add individual field parameters (they override --inputs if both are provided)
        if username:
            inputs_dict['username'] = username
        if password:
            inputs_dict['password'] = password
        if ssh_key_data:
            inputs_dict['ssh_key_data'] = ssh_key_data
        if ssh_key_unlock:
            inputs_dict['ssh_key_unlock'] = ssh_key_unlock
        if become_method:
            inputs_dict['become_method'] = become_method
        if become_username:
            inputs_dict['become_username'] = become_username
        if become_password:
            inputs_dict['become_password'] = become_password
        if vault_password:
            inputs_dict['vault_password'] = vault_password
        if vault_id:
            inputs_dict['vault_id'] = vault_id
        if host:
            inputs_dict['host'] = host
        if project:
            inputs_dict['project'] = project
        if domain:
            inputs_dict['domain'] = domain
        if tenant:
            inputs_dict['tenant'] = tenant
        if subscription:
            inputs_dict['subscription'] = subscription
        if client_id:
            inputs_dict['client'] = client_id
        if secret:
            inputs_dict['secret'] = secret
        if access_token:
            inputs_dict['access_token'] = access_token
        if authorize_password:
            inputs_dict['authorize_password'] = authorize_password

        if inputs_dict:
            credential_data['inputs'] = inputs_dict

        # Create the credential
        response = client.post(f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/", json=credential_data)

        if response.status_code == HTTP_CREATED:
            created_credential = response.json()
            show_success_message(console, f"Credential '{name}' created successfully (ID: {created_credential['id']})")

            # Display the created credential details
            formatted_data = _format_credential_data(created_credential, use_utc=False)
            show_details_table(console, formatted_data)
        else:
            show_error_message(console, f"Failed to create credential: HTTP {response.status_code}")
            if response.content:
                console.print(f"[red]Response:[/red] {response.text}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


@credential.command('set')
@click.argument('credential_name', metavar='<credential>')
@click.option('--id', type=int, help='Credential ID (overrides credential name)')
@click.option('--set-name', help='Update credential name')
@click.option('--organization', help='Update organization name or ID')
@click.option('--description', help='Update credential description')
@click.option('--username', help='Update username')
@click.option('--password', help='Update password')
@click.option('--ssh-key-data', help='Update SSH private key')
@click.option('--ssh-key-unlock', help='Update SSH key passphrase')
@click.option('--become-method', help='Update privilege escalation method')
@click.option('--become-username', help='Update privilege escalation username')
@click.option('--become-password', help='Update privilege escalation password')
@click.option('--vault-password', help='Update vault password')
@click.option('--vault-id', help='Update vault identifier')
@click.option('--host', help='Update host URL')
@click.option('--project', help='Update project name')
@click.option('--domain', help='Update domain')
@click.option('--tenant', help='Update tenant')
@click.option('--subscription', help='Update subscription ID')
@click.option('--client-id', 'client_id', help='Update client ID')
@click.option('--secret', help='Update client secret')
@click.option('--access-token', help='Update access token')
@click.option('--authorize-password', help='Update authorization password')
@click.option('--inputs', help='Credential inputs as JSON string (alternative to individual field options)')
@update_command
def set_credential(console, credential_name, id, set_name, organization, description, username, password,
                   ssh_key_data, ssh_key_unlock, become_method, become_username, become_password,
                   vault_password, vault_id, host, project, domain, tenant, subscription,
                   client_id, secret, access_token, authorize_password, inputs):
    """Update an existing credential."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve credential ID
        if id:
            credential_id = id
        elif credential_name:
            credential_id = resolve_credential_name(client, credential_name)
        else:
            show_error_message(console, "Credential identifier is required")
            sys.exit(1)

        # Build update data
        credential_data = {}

        if set_name:
            credential_data['name'] = set_name
        if description is not None:
            credential_data['description'] = description

        # Resolve organization if provided
        if organization:
            credential_data['organization'] = resolve_organization_name(client, organization)

        # Build inputs object for credential-specific fields
        inputs_dict = {}

        # If --inputs JSON string is provided, parse it
        if inputs:
            import json
            try:
                inputs_dict = json.loads(inputs)
            except json.JSONDecodeError as e:
                show_error_message(console, f"Invalid JSON in --inputs: {e}")
                sys.exit(1)

        # Add individual field parameters (they override --inputs if both are provided)
        input_fields = {
            'username': username,
            'password': password,
            'ssh_key_data': ssh_key_data,
            'ssh_key_unlock': ssh_key_unlock,
            'become_method': become_method,
            'become_username': become_username,
            'become_password': become_password,
            'vault_password': vault_password,
            'vault_id': vault_id,
            'host': host,
            'project': project,
            'domain': domain,
            'tenant': tenant,
            'subscription': subscription,
            'client': client_id,
            'secret': secret,
            'access_token': access_token,
            'authorize_password': authorize_password
        }

        for field_name, field_value in input_fields.items():
            if field_value is not None:
                inputs_dict[field_name] = field_value

        if inputs_dict:
            credential_data['inputs'] = inputs_dict

        if not credential_data:
            show_error_message(console, "At least one field must be specified to update")
            sys.exit(1)

        # Update the credential
        response = client.patch(f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/", json=credential_data)

        if response.status_code == HTTP_OK:
            updated_credential = response.json()
            show_success_message(console, f"Credential updated successfully")

            # Display the updated credential details
            formatted_data = _format_credential_data(updated_credential, use_utc=False)
            show_details_table(console, formatted_data)
        else:
            show_error_message(console, f"Failed to update credential: HTTP {response.status_code}")
            if response.content:
                console.print(f"[red]Response:[/red] {response.text}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


@credential.command('delete')
@click.argument('credential_name', metavar='<credential>')
@click.option('--id', type=int, help='Credential ID (overrides credential name)')
@delete_command()
def delete_credential(console, credential_name, id):
    """Delete a credential."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve credential ID
        if id:
            credential_id = id
            credential_identifier = str(id)
        elif credential_name:
            credential_id = resolve_credential_name(client, credential_name)
            credential_identifier = credential_name
        else:
            show_error_message(console, "Credential identifier is required")
            sys.exit(1)

        # Get credential details for confirmation
        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/")
        credential_data = response.json()
        credential_name_actual = credential_data.get('name', 'Unknown')

        # Delete the credential (confirmation is handled by delete_command decorator)
        response = client.delete(f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/")

        if response.status_code in [200, 202, 204]:
            show_success_message(console, f"Credential '{credential_name_actual}' deleted successfully")
        else:
            show_error_message(console, f"Failed to delete credential: HTTP {response.status_code}")
            if response.content:
                console.print(f"[red]Response:[/red] {response.text}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


def register_credential_commands(main_group: click.Group) -> None:
    """Register credential commands with the main CLI group."""
    main_group.add_command(credential)
