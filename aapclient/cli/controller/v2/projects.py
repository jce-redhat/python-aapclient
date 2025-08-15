"""
Project commands for AAP Controller API v2.

This module implements Click-based commands for managing AAP projects,
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
    resolve_project_name, resolve_organization_name, resolve_execution_environment_name,
    resolve_credential_name, format_datetime, format_variables_display
)
from aapclient.common.exceptions import AAPClientError, AAPAPIError


def get_client_from_context():
    """Get the client manager from the current click context."""
    ctx = click.get_current_context()
    return ctx.find_root().obj['client_manager']


@click.group()
def project():
    """Manage AAP projects."""
    pass


@project.command('list')
@click.option('--organization', help='Filter by organization name or ID')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'organization', 'scm_type', 'status', 'created', 'modified'],
    default_sort='id'
)
def list_projects(console, output_format, utc, limit, offset, organization, show_all, sort_by, reverse):
    """List projects."""
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

        # Add sorting
        if sort_by:
            order_field = _map_sort_field_to_api(sort_by)
            if reverse:
                order_field = f'-{order_field}'
            params['order_by'] = order_field

        # Collect all results if --all is specified
        all_projects = []
        if show_all:
            while True:
                response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/", params=params)
                if response.status_code != HTTP_OK:
                    show_error_message(console, f"Failed to fetch projects: HTTP {response.status_code}")
                    sys.exit(1)

                data = response.json()
                all_projects.extend(data.get('results', []))

                if not data.get('next'):
                    break
                params['page'] = params.get('page', 1) + 1

            projects = all_projects
            total_count = len(all_projects)
        else:
            # Single page request
            response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/", params=params)
            if response.status_code != HTTP_OK:
                show_error_message(console, f"Failed to fetch projects: HTTP {response.status_code}")
                sys.exit(1)

            data = response.json()
            projects = data.get('results', [])
            total_count = data.get('count', 0)

        if output_format in ['json', 'yaml']:
            # Process data into the format that matches table columns
            processed_data = []
            for project in projects:
                processed_data.append({
                    'ID': project.get('id'),
                    'Name': project.get('name', ''),
                    'Status': project.get('status', ''),
                    'Type': project.get('scm_type', ''),
                    'Revision': project.get('scm_revision', '')[:8] if project.get('scm_revision') else '',
                    'Organization': project.get('summary_fields', {}).get('organization', {}).get('name', '')
                })

            if output_format == 'json':
                show_raw_json(processed_data)
            else:
                show_raw_yaml(processed_data)
            return

        # Table format
        columns = ['ID', 'Name', 'Status', 'Type', 'Revision', 'Organization']
        rows = []

        for project in projects:
            # Extract organization name from summary fields
            org_name = project.get('summary_fields', {}).get('organization', {}).get('name', '')

            # Truncate revision to first 8 characters like legacy
            revision = project.get('scm_revision', '')
            if revision:
                revision = revision[:8]

            rows.append([
                str(project.get('id', '')),
                project.get('name', ''),
                project.get('status', ''),
                project.get('scm_type', ''),
                revision,
                org_name
            ])

        # Create and display table
        table = create_table(columns, rows)
        console.print(table)

        # Show pagination info
        if not show_all:
            console.print(f"[dim]Showing {len(projects)} of {total_count} total projects[/dim]")

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
        'organization': 'organization__name',
        'scm_type': 'scm_type',
        'status': 'status',
        'created': 'created',
        'modified': 'modified'
    }
    return mapping.get(sort_field, sort_field)


@project.command('show')
@click.argument('project_name', metavar='<project>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Project ID (overrides name argument)')
@show_command
def show_project(console, output_format, utc, project_name, id):
    """Show details of a specific project."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve project ID
    if id:
        project_id = id
    else:
        project_id = resolve_project_name(client, project_name)

    # Get project details
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/")
    project_data = response.json()

    # Format the data for display
    formatted_data = _format_project_data(project_data, use_utc=utc, client=client, output_format=output_format)

    if output_format == 'json':
        show_raw_json(formatted_data)
    elif output_format == 'yaml':
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


def _format_project_data(project: Dict[str, Any], use_utc: bool = False, client=None, output_format: str = 'table') -> Dict[str, Any]:
    """Format project data for consistent display across commands."""
    summary_fields = project.get('summary_fields', {})

    data = {}
    data['ID'] = str(project.get('id', ''))
    data['Name'] = project.get('name', '')
    data['Description'] = project.get('description', '')
    data['Organization'] = summary_fields.get('organization', {}).get('name', '')
    data['Status'] = project.get('status', '')
    data['SCM Type'] = project.get('scm_type', '')
    data['SCM URL'] = project.get('scm_url', '')

    # SCM Credential
    scm_credential = summary_fields.get('credential', {}).get('name')
    data['SCM Credential'] = scm_credential if scm_credential else 'None'

    data['SCM Branch'] = project.get('scm_branch', '')
    data['SCM Refspec'] = project.get('scm_refspec', '')
    data['SCM Revision'] = project.get('scm_revision', '')

    # Boolean fields - match legacy format
    data['SCM Clean'] = 'Yes' if project.get('scm_clean') else 'No'
    data['SCM Delete on Update'] = 'Yes' if project.get('scm_delete_on_update') else 'No'
    data['SCM Track Submodules'] = 'Yes' if project.get('scm_track_submodules') else 'No'
    data['SCM Update on Launch'] = 'Yes' if project.get('scm_update_on_launch') else 'No'
    data['SCM Update Cache Timeout'] = str(project.get('scm_update_cache_timeout', 0))
    data['Allow Branch Override'] = 'Yes' if project.get('allow_override') else 'No'

    data['Local Path'] = project.get('local_path', '')
    data['Timeout'] = str(project.get('timeout', 0))

    # Custom Virtualenv (this field might not exist in newer versions)
    custom_virtualenv = project.get('custom_virtualenv')
    data['Custom Virtualenv'] = custom_virtualenv if custom_virtualenv else 'None'

    # Execution Environment
    exec_env = summary_fields.get('execution_environment', {}).get('name')
    data['Execution Environment'] = exec_env if exec_env else 'None'

    # Signature Validation Credential
    sig_cred = summary_fields.get('signature_validation_credential', {}).get('name')
    data['Signature Validation Credential'] = sig_cred if sig_cred else 'None'

    # Job and update timing fields
    last_job = summary_fields.get('last_job', {})
    if last_job and last_job.get('finished'):
        data['Last Job Run'] = format_datetime_rich(last_job['finished'], use_utc, output_format)
        data['Last Job Failed'] = 'Yes' if last_job.get('failed') else 'No'
    else:
        data['Last Job Run'] = 'Never'
        data['Last Job Failed'] = 'No'

    last_update = summary_fields.get('last_update', {})
    if last_update and last_update.get('finished'):
        data['Last Updated'] = format_datetime_rich(last_update['finished'], use_utc, output_format)
        data['Last Update Failed'] = 'Yes' if last_update.get('failed') else 'No'
    else:
        data['Last Updated'] = 'Never'
        data['Last Update Failed'] = 'No'

    next_job = summary_fields.get('next_job_run')
    data['Next Job Run'] = format_datetime_rich(next_job, use_utc, output_format) if next_job else 'None'

    # Timestamps
    data['Created'] = format_datetime_rich(project.get('created'), use_utc, output_format)
    data['Created By'] = summary_fields.get('created_by', {}).get('username', '')
    data['Modified'] = format_datetime_rich(project.get('modified'), use_utc, output_format)
    data['Modified By'] = summary_fields.get('modified_by', {}).get('username', '')

    return data


@project.command('create')
@click.argument('name', metavar='<name>')
@click.option('--organization', required=True, help='Organization name or ID')
@click.option('--scm-type', 'scm_type', required=True,
              type=click.Choice(['git', 'svn', 'insights', 'archive']),
              help='Source control type')
@click.option('--scm-url', help='Source control URL')
@click.option('--description', help='Project description')
@click.option('--scm-branch', default='', help='SCM branch/tag/revision to use (default: "")')
@click.option('--scm-refspec', default='', help='SCM refspec to use')
@click.option('--credential', help='SCM credential name or ID')
@click.option('--execution-environment', help='Default execution environment name or ID')
@click.option('--signature-validation-credential', help='Signature validation credential name or ID')
@click.option('--scm-update-cache-timeout', type=int, default=0, help='SCM update cache timeout in seconds')
@click.option('--timeout', type=int, default=0, help='Project timeout in seconds')
@click.option('--scm-track-submodules', is_flag=True, help='Track submodules for git SCM type')
@click.option('--scm-update-on-launch', is_flag=True, help='Update SCM on job launch')
@click.option('--scm-allow-branch-override', is_flag=True, help='Allow job templates to override branch/revision')
@click.option('--scm-clean', is_flag=True, help='Remove local modifications before update')
@click.option('--scm-delete-on-update', is_flag=True, help='Delete local repository before update')
@create_command
def create_project(console, name, organization, scm_type, scm_url, description, scm_branch,
                  scm_refspec, credential, execution_environment, signature_validation_credential,
                  scm_update_cache_timeout, timeout, scm_track_submodules, scm_update_on_launch,
                  scm_allow_branch_override, scm_clean, scm_delete_on_update):
    """Create a new project."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Validate SCM URL requirement for certain types
        if scm_type in ['git', 'svn', 'archive'] and not scm_url:
            show_error_message(console, f"--scm-url is required for SCM type '{scm_type}'")
            sys.exit(1)

        # Resolve resources
        org_id = resolve_organization_name(client, organization)

        credential_id = None
        if credential:
            credential_id = resolve_credential_name(client, credential)

        exec_env_id = None
        if execution_environment:
            exec_env_id = resolve_execution_environment_name(client, execution_environment)

        sig_val_cred_id = None
        if signature_validation_credential:
            sig_val_cred_id = resolve_credential_name(client, signature_validation_credential)

        # Build project data
        project_data = {
            'name': name,
            'organization': org_id,
            'scm_type': scm_type,
            'scm_url': scm_url or '',
            'scm_branch': scm_branch,
            'scm_refspec': scm_refspec,
            'scm_update_cache_timeout': scm_update_cache_timeout,
            'timeout': timeout,
            'scm_track_submodules': scm_track_submodules,
            'scm_update_on_launch': scm_update_on_launch,
            'allow_override': scm_allow_branch_override,
            'scm_clean': scm_clean,
            'scm_delete_on_update': scm_delete_on_update
        }

        if description:
            project_data['description'] = description
        if credential_id:
            project_data['credential'] = credential_id
        if exec_env_id:
            project_data['execution_environment'] = exec_env_id
        if sig_val_cred_id:
            project_data['signature_validation_credential'] = sig_val_cred_id

        # Create the project
        response = client.post(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/", json=project_data)

        if response.status_code == HTTP_CREATED:
            created_project = response.json()
            show_success_message(console, f"Project '{name}' created successfully (ID: {created_project['id']})")

            # Display the created project details
            formatted_data = _format_project_data(created_project, use_utc=False, client=client)
            show_details_table(console, formatted_data)
        else:
            show_error_message(console, f"Failed to create project: HTTP {response.status_code}")
            if response.content:
                console.print(f"[red]Response:[/red] {response.text}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


@project.command('set')
@click.argument('project_name', metavar='<project>')
@click.option('--id', type=int, help='Project ID (overrides project name)')
@click.option('--set-name', help='Update project name')
@click.option('--organization', help='Update organization name or ID')
@click.option('--scm-type', type=click.Choice(['git', 'svn', 'insights', 'archive']),
              help='Update source control type')
@click.option('--scm-url', help='Update source control URL')
@click.option('--description', help='Update project description')
@click.option('--scm-branch', help='Update SCM branch/tag/revision')
@click.option('--scm-refspec', help='Update SCM refspec')
@click.option('--credential', help='Update SCM credential name or ID')
@click.option('--execution-environment', help='Update execution environment name or ID')
@click.option('--signature-validation-credential', help='Update signature validation credential name or ID')
@click.option('--scm-update-cache-timeout', type=int, help='Update SCM cache timeout in seconds')
@click.option('--timeout', type=int, help='Update project timeout in seconds')
@click.option('--enable-scm-track-submodules', is_flag=True, help='Enable tracking submodules')
@click.option('--disable-scm-track-submodules', is_flag=True, help='Disable tracking submodules')
@click.option('--enable-scm-update-on-launch', is_flag=True, help='Enable SCM update on launch')
@click.option('--disable-scm-update-on-launch', is_flag=True, help='Disable SCM update on launch')
@click.option('--enable-scm-allow-branch-override', is_flag=True, help='Enable branch override')
@click.option('--disable-scm-allow-branch-override', is_flag=True, help='Disable branch override')
@click.option('--enable-scm-clean', is_flag=True, help='Enable SCM clean')
@click.option('--disable-scm-clean', is_flag=True, help='Disable SCM clean')
@click.option('--enable-scm-delete-on-update', is_flag=True, help='Enable SCM delete on update')
@click.option('--disable-scm-delete-on-update', is_flag=True, help='Disable SCM delete on update')
@update_command
def set_project(console, project_name, id, set_name, organization, scm_type, scm_url, description,
               scm_branch, scm_refspec, credential, execution_environment, signature_validation_credential,
               scm_update_cache_timeout, timeout, enable_scm_track_submodules, disable_scm_track_submodules,
               enable_scm_update_on_launch, disable_scm_update_on_launch, enable_scm_allow_branch_override,
               disable_scm_allow_branch_override, enable_scm_clean, disable_scm_clean,
               enable_scm_delete_on_update, disable_scm_delete_on_update):
    """Update an existing project."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Validate mutually exclusive options
        if enable_scm_track_submodules and disable_scm_track_submodules:
            show_error_message(console, "--enable-scm-track-submodules and --disable-scm-track-submodules cannot be used together")
            sys.exit(1)
        if enable_scm_update_on_launch and disable_scm_update_on_launch:
            show_error_message(console, "--enable-scm-update-on-launch and --disable-scm-update-on-launch cannot be used together")
            sys.exit(1)
        if enable_scm_allow_branch_override and disable_scm_allow_branch_override:
            show_error_message(console, "--enable-scm-allow-branch-override and --disable-scm-allow-branch-override cannot be used together")
            sys.exit(1)
        if enable_scm_clean and disable_scm_clean:
            show_error_message(console, "--enable-scm-clean and --disable-scm-clean cannot be used together")
            sys.exit(1)
        if enable_scm_delete_on_update and disable_scm_delete_on_update:
            show_error_message(console, "--enable-scm-delete-on-update and --disable-scm-delete-on-update cannot be used together")
            sys.exit(1)

        # Resolve project ID
        if id:
            project_id = id
        elif project_name:
            project_id = resolve_project_name(client, project_name)
        else:
            show_error_message(console, "Project identifier is required")
            sys.exit(1)

        # Build update data
        project_data = {}

        if set_name:
            project_data['name'] = set_name
        if description is not None:
            project_data['description'] = description
        if scm_type:
            project_data['scm_type'] = scm_type
        if scm_url is not None:
            project_data['scm_url'] = scm_url
        if scm_branch is not None:
            project_data['scm_branch'] = scm_branch
        if scm_refspec is not None:
            project_data['scm_refspec'] = scm_refspec
        if scm_update_cache_timeout is not None:
            project_data['scm_update_cache_timeout'] = scm_update_cache_timeout
        if timeout is not None:
            project_data['timeout'] = timeout

        # Resolve resources
        if organization:
            project_data['organization'] = resolve_organization_name(client, organization)
        if credential:
            project_data['credential'] = resolve_credential_name(client, credential)
        if execution_environment:
            project_data['execution_environment'] = resolve_execution_environment_name(client, execution_environment)
        if signature_validation_credential:
            project_data['signature_validation_credential'] = resolve_credential_name(client, signature_validation_credential)

        # Handle boolean enable/disable pairs
        if enable_scm_track_submodules:
            project_data['scm_track_submodules'] = True
        elif disable_scm_track_submodules:
            project_data['scm_track_submodules'] = False

        if enable_scm_update_on_launch:
            project_data['scm_update_on_launch'] = True
        elif disable_scm_update_on_launch:
            project_data['scm_update_on_launch'] = False

        if enable_scm_allow_branch_override:
            project_data['allow_override'] = True
        elif disable_scm_allow_branch_override:
            project_data['allow_override'] = False

        if enable_scm_clean:
            project_data['scm_clean'] = True
        elif disable_scm_clean:
            project_data['scm_clean'] = False

        if enable_scm_delete_on_update:
            project_data['scm_delete_on_update'] = True
        elif disable_scm_delete_on_update:
            project_data['scm_delete_on_update'] = False

        if not project_data:
            show_error_message(console, "At least one field must be specified to update")
            sys.exit(1)

        # Update the project
        response = client.patch(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/", json=project_data)

        if response.status_code == HTTP_OK:
            updated_project = response.json()
            show_success_message(console, f"Project updated successfully")

            # Display the updated project details
            formatted_data = _format_project_data(updated_project, use_utc=False, client=client)
            show_details_table(console, formatted_data)
        else:
            show_error_message(console, f"Failed to update project: HTTP {response.status_code}")
            if response.content:
                console.print(f"[red]Response:[/red] {response.text}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


@project.command('delete')
@click.argument('project_name', metavar='<project>')
@click.option('--id', type=int, help='Project ID (overrides project name)')
@delete_command()
def delete_project(console, project_name, id):
    """Delete a project."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve project ID
        if id:
            project_id = id
            project_identifier = str(id)
        elif project_name:
            project_id = resolve_project_name(client, project_name)
            project_identifier = project_name
        else:
            show_error_message(console, "Project identifier is required")
            sys.exit(1)

        # Get project details for confirmation
        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/")
        project_data = response.json()
        project_name_actual = project_data.get('name', 'Unknown')

        # The delete_command decorator handles confirmation automatically
        # No need for manual confirmation here

        # Delete the project
        response = client.delete(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/")

        if response.status_code in [200, 202, 204]:
            show_success_message(console, f"Project '{project_name_actual}' deleted successfully")
        else:
            show_error_message(console, f"Failed to delete project: HTTP {response.status_code}")
            if response.content:
                console.print(f"[red]Response:[/red] {response.text}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


@project.command('sync')
@click.argument('project_name', metavar='<project>')
@click.option('--id', type=int, help='Project ID (overrides project name)')
@click.option('--wait', is_flag=True, help='Wait for sync to complete')
@click.option('--timeout', type=int, default=300, help='Timeout for --wait in seconds (default: 300)')
@standard_command
def sync_project(console, project_name, id, wait, timeout):
    """Synchronize a project's source control repository."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve project ID
        if id:
            project_id = id
            project_identifier = str(id)
        elif project_name:
            project_id = resolve_project_name(client, project_name)
            project_identifier = project_name
        else:
            show_error_message(console, "Project identifier is required")
            sys.exit(1)

        # Get project details first
        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/")
        project_data = response.json()
        project_name_actual = project_data.get('name', 'Unknown')

        # Trigger project update/sync
        response = client.post(f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/update/")

        if response.status_code in [200, 202]:
            update_data = response.json()
            update_id = update_data.get('id')

            if update_id:
                show_success_message(console, f"Project sync started for '{project_name_actual}' (Update ID: {update_id})")

                if wait:
                    import time
                    console.print(f"[yellow]Waiting for sync to complete (timeout: {timeout}s)...[/yellow]")

                    start_time = time.time()
                    while time.time() - start_time < timeout:
                        # Check update status
                        status_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}project_updates/{update_id}/")
                        if status_response.status_code == HTTP_OK:
                            status_data = status_response.json()
                            status = status_data.get('status')

                            if status in ['successful', 'failed', 'error', 'canceled']:
                                if status == 'successful':
                                    show_success_message(console, f"Project sync completed successfully")
                                else:
                                    show_error_message(console, f"Project sync failed with status: {status}")
                                break

                        time.sleep(2)
                    else:
                        console.print(f"[yellow]Timeout reached. Sync may still be running.[/yellow]")
            else:
                show_success_message(console, f"Project sync started for '{project_name_actual}'")
        else:
            show_error_message(console, f"Failed to start project sync: HTTP {response.status_code}")
            if response.content:
                console.print(f"[red]Response:[/red] {response.text}")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        show_error_message(console, f"Unexpected error: {e}")
        sys.exit(1)


def register_project_commands(main_group: click.Group) -> None:
    """Register project commands with the main CLI group."""
    main_group.add_command(project)
