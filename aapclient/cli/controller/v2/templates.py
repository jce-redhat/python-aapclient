"""
Job template commands for AAP CLI using Click and Rich.

This module provides enhanced versions of job template management commands
with beautiful rich output formatting and improved user experience.
"""

import json
from typing import Dict, Any, List, Optional

import click
from click_option_group import optgroup, MutuallyExclusiveOptionGroup
from rich.table import Table

from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError
from aapclient.common.functions import (
    resolve_job_template_name,
    resolve_inventory_name,
    resolve_project_name,
    resolve_execution_environment_name,
    resolve_credential_name,
    resolve_instance_group_name,
    format_datetime,
    format_variables_display
)
from aapclient.cli.decorators import (
    list_command,
    show_command,
    create_command,
    update_command,
    delete_command,
    get_client_from_context,
    get_console_from_context,
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
def template():
    """Manage job templates."""
    pass


@template.command('list')
@click.option('--organization', help='Filter by organization name or ID')
@click.option('--project', help='Filter by project name or ID')
@click.option('--inventory', help='Filter by inventory name or ID')
@click.option('--all', 'show_all', is_flag=True, help='Show all results (no pagination)')
@list_command(
    default_limit=20,
    sort_fields=['id', 'name', 'organization', 'created', 'modified', 'last_job_run'],
    default_sort='id'
)
def list_templates(console, output_format, utc, limit, offset, organization, project, inventory, show_all, sort_by, reverse):
    """List job templates."""
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
            from aapclient.common.functions import resolve_organization_name
            org_id = resolve_organization_name(client, organization)
            params['organization'] = org_id
        except Exception:
            params['organization__name'] = organization

    if project:
        try:
            project_id = resolve_project_name(client, project)
            params['project'] = project_id
        except Exception:
            params['project__name'] = project

    if inventory:
        try:
            inventory_id = resolve_inventory_name(client, inventory)
            params['inventory'] = inventory_id
        except Exception:
            params['inventory__name'] = inventory

    # Fetch templates with proper pagination handling
    if show_all:
        # Fetch all results by paginating through all pages
        templates = []
        page = 1
        params['page_size'] = 200  # Use large page size for efficiency

        while True:
            params['page'] = page
            response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/", params=params)

            if response.status_code != HTTP_OK:
                show_error_message(console, f"Failed to fetch templates: HTTP {response.status_code}")
                click.get_current_context().exit(1)

            page_data = response.json()
            page_templates = page_data.get('results', [])

            if not page_templates:
                break

            templates.extend(page_templates)

            # Check if we have more pages
            if not page_data.get('next'):
                break

            page += 1

        # Create a mock data structure for consistency
        data = {
            'count': len(templates),
            'results': templates
        }
    else:
        # Regular pagination
        params['page_size'] = limit
        params['page'] = (offset // limit) + 1

        response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/", params=params)

        if response.status_code != HTTP_OK:
            show_error_message(console, f"Failed to fetch templates: HTTP {response.status_code}")
            click.get_current_context().exit(1)

        data = response.json()
        templates = data.get('results', [])

    if not templates:
        console.print("[yellow]No job templates found.[/yellow]")
        return

    # Process data into structured format first
    columns = ['ID', 'Name', 'Organization', 'Last Ran']
    processed_data = []

    for template in templates:
        last_job = template.get('last_job_run')
        last_run = format_datetime_rich(last_job, utc, output_format) if last_job else ('Never' if output_format in ['json', 'yaml'] else 'Never')

        processed_data.append({
            'ID': template['id'],
            'Name': template['name'],
            'Organization': template.get('summary_fields', {}).get('organization', {}).get('name', 'N/A'),
            'Last Ran': last_run
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
        if not show_all and data.get('count', 0) > len(templates):
            console.print(f"[dim]Showing {len(templates)} of {data['count']} total templates[/dim]")


@template.command('show')
@click.argument('template_name', metavar='<template>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Template ID (overrides name argument)')
@show_command
def show_template(console, output_format, utc, template_name, id):
    """Show details of a specific job template."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve template ID
    if id:
        template_id = id
    else:
        template_id = resolve_job_template_name(client, template_name)

    # Fetch template details
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/")
    template = response.json()

    # Rich formatted display
    data = _format_template_data(template, use_utc=utc, client=client, output_format=output_format)

    if output_format == 'json':
        show_raw_json(data)
    elif output_format == 'yaml':
        show_raw_yaml(data)
    else:
        show_details_table(console, data)


@template.command('create')
@click.argument('name', metavar='<name>')
@click.option('--job-type', type=click.Choice(['check', 'run']), required=True, help='Job type')
@click.option('--inventory', required=True, help='Inventory name or ID')
@click.option('--project', required=True, help='Project name or ID')
@click.option('--playbook', required=True, help='Playbook path within the project')
@click.option('--description', help='Job template description')
@click.option('--execution-environment', help='Execution environment name or ID')
@click.option('--credential', multiple=True, help='Credential name or ID (can be specified multiple times)')
@click.option('--forks', type=int, help='Number of parallel processes to use')
@click.option('--limit', 'job_limit', help='Limit execution to specific hosts')
@click.option('--verbosity', type=click.Choice(['0', '1', '2', '3', '4', '5']), help='Verbosity level')
@click.option('--job-slices', type=int, help='Number of job slices')
@click.option('--job-timeout', type=int, help='Job timeout in seconds')
@click.option('--job-tags', help='Job tags')
@click.option('--skip-tags', help='Skip tags')
@click.option('--extra-vars', help='Extra variables as JSON')
@click.option('--instance-group', multiple=True, help='Instance group name or ID (can be specified multiple times)')
# Boolean flags
@click.option('--enable-privileged-escalation', is_flag=True, help='Enable privileged escalation')
@click.option('--enable-concurrent-jobs', is_flag=True, help='Enable concurrent jobs')
@click.option('--enable-fact-storage', is_flag=True, help='Enable fact storage')
@click.option('--enable-show-changes', is_flag=True, help='Show changes in diff mode')
@click.option('--prevent-instance-group-fallback', is_flag=True, help='Prevent instance group fallback')
# Ask on launch flags
@click.option('--ask-diff-mode-on-launch', is_flag=True, help='Ask for diff mode on launch')
@click.option('--ask-variables-on-launch', is_flag=True, help='Ask for variables on launch')
@click.option('--ask-limit-on-launch', is_flag=True, help='Ask for limit on launch')
@click.option('--ask-tags-on-launch', is_flag=True, help='Ask for tags on launch')
@click.option('--ask-skip-tags-on-launch', is_flag=True, help='Ask for skip tags on launch')
@click.option('--ask-job-type-on-launch', is_flag=True, help='Ask for job type on launch')
@click.option('--ask-verbosity-on-launch', is_flag=True, help='Ask for verbosity on launch')
@click.option('--ask-inventory-on-launch', is_flag=True, help='Ask for inventory on launch')
@click.option('--ask-credential-on-launch', is_flag=True, help='Ask for credential on launch')
@click.option('--ask-execution-environment-on-launch', is_flag=True, help='Ask for execution environment on launch')
@click.option('--ask-labels-on-launch', is_flag=True, help='Ask for labels on launch')
@click.option('--ask-forks-on-launch', is_flag=True, help='Ask for forks on launch')
@click.option('--ask-job-slices-on-launch', is_flag=True, help='Ask for job slices on launch')
@click.option('--ask-timeout-on-launch', is_flag=True, help='Ask for timeout on launch')
@click.option('--ask-instance-groups-on-launch', is_flag=True, help='Ask for instance groups on launch')
# Webhook options
@click.option('--enable-webhook', is_flag=True, help='Enable webhook')
@click.option('--webhook-service', type=click.Choice(['gitlab', 'github', 'bitbucket_dc']), help='Webhook service (required if --enable-webhook)')
@click.option('--webhook-credential', help='Webhook credential name or ID')
@create_command
def create_template(console, name, **kwargs):
    """Create a new job template."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build template data
    template_data = _build_template_data(client, name, **kwargs)

    # Validate webhook options
    if kwargs.get('enable_webhook') and not kwargs.get('webhook_service'):
        show_error_message(console, "Webhook service is required when enabling webhook")
        click.get_current_context().exit(1)

    # Create the template
    response = client.post(f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/", json=template_data)

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
            show_error_message(console, f"Failed to create template: HTTP {response.status_code}")
        click.get_current_context().exit(1)

    created_template = response.json()
    template_id = created_template['id']

    # Handle associations (credentials, instance groups)
    _handle_template_associations(client, console, template_id, kwargs)

    # Fetch updated template for display
    response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/")
    if response.status_code == HTTP_OK:
        updated_template = response.json()
        data = _format_template_data(updated_template, False)
        show_success_message(console, f"Job template '{name}' created successfully")
        show_key_value(console, data, f"Created Job Template: {name}")
    else:
        show_success_message(console, f"Job template '{name}' created successfully (ID: {template_id})")


def _build_template_data(client, name: str, **kwargs) -> Dict[str, Any]:
    """Build template data dictionary from arguments."""
    data = {
        'name': name,
        'job_type': kwargs['job_type'],
        'playbook': kwargs['playbook']
    }

    # Resolve resource IDs
    data['inventory'] = resolve_inventory_name(client, kwargs['inventory'])
    data['project'] = resolve_project_name(client, kwargs['project'])

    # Optional fields
    if kwargs.get('description'):
        data['description'] = kwargs['description']

    if kwargs.get('execution_environment'):
        data['execution_environment'] = resolve_execution_environment_name(client, kwargs['execution_environment'])

    if kwargs.get('forks'):
        data['forks'] = kwargs['forks']

    if kwargs.get('job_limit'):
        data['limit'] = kwargs['job_limit']

    if kwargs.get('verbosity'):
        data['verbosity'] = int(kwargs['verbosity'])

    if kwargs.get('job_slices'):
        data['job_slice_count'] = kwargs['job_slices']

    if kwargs.get('job_timeout'):
        data['timeout'] = kwargs['job_timeout']

    if kwargs.get('job_tags'):
        data['job_tags'] = kwargs['job_tags']

    if kwargs.get('skip_tags'):
        data['skip_tags'] = kwargs['skip_tags']

    if kwargs.get('extra_vars'):
        # Validate JSON
        try:
            json.loads(kwargs['extra_vars'])
            data['extra_vars'] = kwargs['extra_vars']
        except json.JSONDecodeError as e:
            raise click.ClickException(f"Invalid JSON in extra_vars: {e}")

    # Boolean fields
    data['become_enabled'] = kwargs.get('enable_privileged_escalation', False)
    data['allow_simultaneous'] = kwargs.get('enable_concurrent_jobs', False)
    data['use_fact_cache'] = kwargs.get('enable_fact_storage', False)
    data['diff_mode'] = kwargs.get('enable_show_changes', False)
    data['prevent_instance_group_fallback'] = kwargs.get('prevent_instance_group_fallback', False)

    # Ask on launch fields
    ask_fields = [
        'ask_diff_mode_on_launch', 'ask_variables_on_launch', 'ask_limit_on_launch',
        'ask_tags_on_launch', 'ask_skip_tags_on_launch', 'ask_job_type_on_launch',
        'ask_verbosity_on_launch', 'ask_inventory_on_launch', 'ask_credential_on_launch',
        'ask_execution_environment_on_launch', 'ask_labels_on_launch', 'ask_forks_on_launch',
        'ask_job_slices_on_launch', 'ask_timeout_on_launch', 'ask_instance_groups_on_launch'
    ]

    for field in ask_fields:
        data[field] = kwargs.get(field, False)

    # Webhook fields
    if kwargs.get('enable_webhook'):
        data['webhook_service'] = kwargs['webhook_service']

        if kwargs.get('webhook_credential'):
            data['webhook_credential'] = resolve_credential_name(client, kwargs['webhook_credential'])

    return data


def _handle_template_associations(client, console, template_id: int, kwargs: Dict[str, Any]) -> None:
    """Handle template associations (credentials, instance groups)."""
    # Associate credentials
    if kwargs.get('credential'):
        for cred_name in kwargs['credential']:
            try:
                cred_id = resolve_credential_name(client, cred_name)
                assoc_response = client.post(
                    f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/credentials/",
                    json={'id': cred_id}
                )
                if assoc_response.status_code not in [HTTP_CREATED, HTTP_NO_CONTENT]:
                    show_error_message(console, f"Warning: Failed to associate credential '{cred_name}'")
            except Exception as e:
                show_error_message(console, f"Warning: Failed to resolve credential '{cred_name}': {e}")

    # Associate instance groups
    if kwargs.get('instance_group'):
        for ig_name in kwargs['instance_group']:
            try:
                ig_id = resolve_instance_group_name(client, ig_name)
                assoc_response = client.post(
                    f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/instance_groups/",
                    json={'id': ig_id}
                )
                if assoc_response.status_code not in [HTTP_CREATED, HTTP_NO_CONTENT]:
                    show_error_message(console, f"Warning: Failed to associate instance group '{ig_name}'")
            except Exception as e:
                show_error_message(console, f"Warning: Failed to resolve instance group '{ig_name}': {e}")


def _map_sort_field_to_api(sort_field: str) -> str:
    """Map user-friendly sort field names to API field names."""
    field_mapping = {
        'id': 'id',
        'name': 'name',
        'organization': 'organization__name',
        'project': 'project__name',
        'created': 'created',
        'modified': 'modified',
        'last_job_run': 'last_job_run'
    }
    return field_mapping.get(sort_field, 'id')


def _sort_templates_client_side(templates: List[Dict[str, Any]], sort_by: str, reverse: bool) -> List[Dict[str, Any]]:
    """
    Client-side sorting fallback for when server-side sorting is not available.

    Args:
        templates: List of template dictionaries
        sort_by: Field to sort by
        reverse: Whether to reverse sort order

    Returns:
        Sorted list of templates
    """
    def get_sort_key(template):
        if sort_by == 'id':
            return template.get('id', 0)
        elif sort_by == 'name':
            return template.get('name', '').lower()
        elif sort_by == 'organization':
            return template.get('summary_fields', {}).get('organization', {}).get('name', '').lower()
        elif sort_by == 'project':
            return template.get('summary_fields', {}).get('project', {}).get('name', '').lower()
        elif sort_by == 'created':
            return template.get('created', '')
        elif sort_by == 'modified':
            return template.get('modified', '')
        elif sort_by == 'last_job_run':
            # Handle None values for last_job_run
            last_run = template.get('last_job_run')
            return last_run if last_run else '1900-01-01'  # Put null values at beginning
        else:
            return template.get('id', 0)

    return sorted(templates, key=get_sort_key, reverse=reverse)


def _format_template_data(template: Dict[str, Any], use_utc: bool = False, client=None, output_format: str = 'table') -> Dict[str, Any]:
    """Format template data for rich display."""
    data = {}

    # Basic fields
    data['ID'] = str(template['id'])
    data['Name'] = template['name']
    data['Description'] = template.get('description', '')
    data['Job Type'] = template.get('job_type', 'N/A').title()

    # Organization
    org = template.get('summary_fields', {}).get('organization', {})
    data['Organization'] = org.get('name', 'N/A')

    # Project and inventory
    project = template.get('summary_fields', {}).get('project', {})
    data['Project'] = project.get('name', 'N/A')

    inventory = template.get('summary_fields', {}).get('inventory', {})
    data['Inventory'] = inventory.get('name', 'N/A')

    data['Playbook'] = template.get('playbook', 'N/A')

    # Execution environment
    ee = template.get('summary_fields', {}).get('execution_environment', {})
    data['Execution Environment'] = ee.get('name', 'Default')

    # Credentials
    creds = template.get('summary_fields', {}).get('credentials', [])
    if creds:
        data['Credentials'] = ', '.join([c['name'] for c in creds])
    else:
        data['Credentials'] = ''

    # Instance groups
    igs = template.get('summary_fields', {}).get('instance_groups', [])
    if igs:
        data['Instance Groups'] = ', '.join([ig['name'] for ig in igs])
    else:
        data['Instance Groups'] = ''

    # Labels
    labels = template.get('summary_fields', {}).get('labels', {})
    labels_list = []
    if isinstance(labels, dict) and 'results' in labels:
        for label in labels['results']:
            if isinstance(label, dict):
                labels_list.append(label.get('name', f"ID {label.get('id', 'Unknown')}"))
    data['Labels'] = ', '.join(labels_list) if labels_list else ''

    # Job configuration
    data['Forks'] = str(template.get('forks', 0))
    data['Verbosity'] = str(template.get('verbosity', 0))
    data['Job Slices'] = str(template.get('job_slice_count', 1))
    data['Job Timeout'] = str(template.get('timeout', 0))
    data['Job Tags'] = template.get('job_tags', '')
    data['Skip Tags'] = template.get('skip_tags', '')
    data['Limit'] = template.get('limit', '')

    # Boolean flags
    data['Diff Mode'] = 'Yes' if template.get('diff_mode') else 'No'
    data['Privileged Escalation'] = 'Yes' if template.get('become_enabled') else 'No'
    data['Concurrent Jobs'] = 'Yes' if template.get('allow_simultaneous') else 'No'
    data['Enable Fact Storage'] = 'Yes' if template.get('use_fact_cache') else 'No'
    data['Prevent Instance Group Fallback'] = 'Yes' if template.get('prevent_instance_group_fallback') else 'No'

    # Survey - determine state based on existence and enabled status
    survey_enabled = template.get('survey_enabled', False)
    summary_fields = template.get('summary_fields', {})
    survey_info = summary_fields.get('survey', None)

    if survey_info is None:
        survey_status = 'No'
    elif survey_enabled:
        survey_status = 'Yes (Enabled)'
    else:
        survey_status = 'Yes (Disabled)'

    data['Survey Attached'] = survey_status

    # Extra variables
    extra_vars = template.get('extra_vars', '')
    if extra_vars:
        data['Extra Variables'] = format_variables_display(extra_vars, 'template')
    else:
        data['Extra Variables'] = ''

    # Webhook fields
    webhook_service = template.get('webhook_service', '')
    data['Webhook Service'] = webhook_service

    # Webhook credential
    webhook_credential_display = ''
    webhook_credential_id = template.get('webhook_credential')
    if webhook_credential_id:
        webhook_cred_info = template.get('summary_fields', {}).get('webhook_credential', {})
        if webhook_cred_info and isinstance(webhook_cred_info, dict):
            webhook_credential_display = webhook_cred_info.get('name', f"ID {webhook_credential_id}")
        else:
            webhook_credential_display = f"ID {webhook_credential_id}"
    data['Webhook Credential'] = webhook_credential_display

    # Webhook URL - construct from related webhook_receiver path
    webhook_url = ''
    if webhook_service:
        related = template.get('related', {})
        webhook_receiver_path = related.get('webhook_receiver')
        if webhook_receiver_path:
            try:
                from aapclient.common.clientmanager import AAPClientManager
                client_manager = AAPClientManager()
                base_url = client_manager.config.base_url
                webhook_url = base_url.rstrip('/') + webhook_receiver_path
            except Exception:
                pass
    data['Webhook URL'] = webhook_url

    # Webhook Key - fetch from API if client available and webhook service enabled
    webhook_key = ''
    if webhook_service and client:
        related = template.get('related', {})
        webhook_key_url = related.get('webhook_key')
        if webhook_key_url:
            try:
                response = client.get(webhook_key_url)
                if response.status_code == 200:
                    key_data = response.json()
                    webhook_key = key_data.get('webhook_key', '')
            except Exception:
                pass
    data['Webhook Key'] = webhook_key

    # Last job info
    data['Last Job Run'] = format_datetime_rich(template.get('last_job_run'), use_utc, output_format)
    # Use last_job from summary_fields like legacy version
    last_job_info = template.get('summary_fields', {}).get('last_job', {})
    if last_job_info:
        last_job_status = f"{last_job_info.get('status', 'Unknown')} (ID: {last_job_info.get('id', 'Unknown')})"
    else:
        last_job_status = 'None'
    data['Last Job Status'] = last_job_status

    # Timestamps
    data['Created'] = format_datetime_rich(template.get('created'), use_utc, output_format)
    created_by = template.get('summary_fields', {}).get('created_by', {})
    data['Created By'] = created_by.get('username', 'N/A')

    data['Modified'] = format_datetime_rich(template.get('modified'), use_utc, output_format)
    modified_by = template.get('summary_fields', {}).get('modified_by', {})
    data['Modified By'] = modified_by.get('username', 'N/A')

    return data


@template.command('delete')
@click.argument('template_name', metavar='<template>')
@click.option('--id', type=int, help='Job template ID (overrides positional parameter)')
@delete_command()
def delete_template(console, template_name, id):
    """Delete a job template."""
    from aapclient.common.functions import resolve_job_template_name

    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Determine how to resolve the job template
        if id:
            # Use explicit ID (ignores positional parameter)
            job_template_id = id
            template_identifier = str(id)
        elif template_name:
            # Use positional parameter - name first, then ID fallback if numeric
            job_template_id = resolve_job_template_name(client, template_name)
            template_identifier = template_name
        else:
            show_error_message(console, "Job template identifier is required")
            click.get_current_context().exit(1)

        # Get job template details first for confirmation
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
        response = client.get(endpoint)

        if response.status_code == HTTP_OK:
            job_template_data = response.json()
            template_name = job_template_data.get('name', template_identifier)

            # Delete job template
            delete_response = client.delete(endpoint)

            if delete_response.status_code == HTTP_NO_CONTENT:
                show_success_message(console, f"Job template '{template_name}' deleted")
            else:
                show_error_message(console, f"Job template deletion failed with status {delete_response.status_code}")
                click.get_current_context().exit(1)
        else:
            show_error_message(console, f"Failed to get job template details with status {response.status_code}")
            click.get_current_context().exit(1)

    except Exception as e:
        show_error_message(console, f"Failed to delete job template: {e}")
        click.get_current_context().exit(1)


@template.command('set')
@click.argument('template_name', metavar='<template>')
@click.option('--id', type=int, help='Job template ID (overrides positional parameter)')
@click.option('--set-name', help='Set job template name')
@click.option('--job-type', type=click.Choice(['check', 'run']), help='Job type')
@click.option('--inventory', help='Inventory name or ID')
@click.option('--project', help='Project name or ID')
@click.option('--playbook', help='Playbook path within the project')
@click.option('--description', help='Job template description')
@click.option('--execution-environment', help='Execution environment name or ID')
@click.option('--credential', multiple=True, help='Credential name or ID (can be specified multiple times)')
@click.option('--forks', type=int, help='Number of parallel processes to use')
@click.option('--limit', 'job_limit', help='Limit execution to specific hosts')
@click.option('--verbosity', type=click.Choice(['0', '1', '2', '3', '4', '5']), help='Verbosity level')
@click.option('--job-slices', type=int, help='Number of job slices')
@click.option('--job-timeout', type=int, help='Job timeout in seconds')
@click.option('--job-tags', help='Job tags')
@click.option('--skip-tags', help='Skip tags')
@click.option('--extra-vars', help='Extra variables as JSON')
@click.option('--instance-group', multiple=True, help='Instance group name or ID (can be specified multiple times)')
# Mutually exclusive boolean flag groups
@optgroup.group('Privileged Escalation', cls=MutuallyExclusiveOptionGroup,
                help='Control privileged escalation setting')
@optgroup.option('--enable-privileged-escalation', is_flag=True, help='Enable privileged escalation')
@optgroup.option('--disable-privileged-escalation', is_flag=True, help='Disable privileged escalation')

@optgroup.group('Concurrent Jobs', cls=MutuallyExclusiveOptionGroup,
                help='Control concurrent jobs setting')
@optgroup.option('--enable-concurrent-jobs', is_flag=True, help='Enable concurrent jobs')
@optgroup.option('--disable-concurrent-jobs', is_flag=True, help='Disable concurrent jobs')

@optgroup.group('Fact Storage', cls=MutuallyExclusiveOptionGroup,
                help='Control fact storage setting')
@optgroup.option('--enable-fact-storage', is_flag=True, help='Enable fact storage')
@optgroup.option('--disable-fact-storage', is_flag=True, help='Disable fact storage')

@optgroup.group('Show Changes', cls=MutuallyExclusiveOptionGroup,
                help='Control diff mode changes display')
@optgroup.option('--enable-show-changes', is_flag=True, help='Show changes in diff mode')
@optgroup.option('--disable-show-changes', is_flag=True, help='Disable showing changes in diff mode')

@optgroup.group('Instance Group Fallback', cls=MutuallyExclusiveOptionGroup,
                help='Control instance group fallback behavior')
@optgroup.option('--prevent-instance-group-fallback', is_flag=True, help='Prevent instance group fallback')
@optgroup.option('--allow-instance-group-fallback', is_flag=True, help='Allow instance group fallback')
# Ask on launch flags
@click.option('--ask-diff-mode-on-launch', is_flag=True, help='Ask for diff mode on launch')
@click.option('--ask-variables-on-launch', is_flag=True, help='Ask for variables on launch')
@click.option('--ask-limit-on-launch', is_flag=True, help='Ask for limit on launch')
@click.option('--ask-tags-on-launch', is_flag=True, help='Ask for tags on launch')
@click.option('--ask-skip-tags-on-launch', is_flag=True, help='Ask for skip tags on launch')
@click.option('--ask-job-type-on-launch', is_flag=True, help='Ask for job type on launch')
@click.option('--ask-verbosity-on-launch', is_flag=True, help='Ask for verbosity on launch')
@click.option('--ask-inventory-on-launch', is_flag=True, help='Ask for inventory on launch')
@click.option('--ask-credential-on-launch', is_flag=True, help='Ask for credential on launch')
@click.option('--ask-execution-environment-on-launch', is_flag=True, help='Ask for execution environment on launch')
@click.option('--ask-labels-on-launch', is_flag=True, help='Ask for labels on launch')
@click.option('--ask-forks-on-launch', is_flag=True, help='Ask for forks on launch')
@click.option('--ask-job-slices-on-launch', is_flag=True, help='Ask for job slices on launch')
@click.option('--ask-timeout-on-launch', is_flag=True, help='Ask for timeout on launch')
@click.option('--ask-instance-groups-on-launch', is_flag=True, help='Ask for instance groups on launch')
# Webhook mutually exclusive group
@optgroup.group('Webhook', cls=MutuallyExclusiveOptionGroup,
                help='Control webhook setting')
@optgroup.option('--enable-webhook', is_flag=True, help='Enable webhook')
@optgroup.option('--disable-webhook', is_flag=True, help='Disable webhook')

# Webhook configuration options
@click.option('--webhook-service', type=click.Choice(['gitlab', 'github', 'bitbucket_dc']), help='Webhook service')
@click.option('--webhook-credential', help='Webhook credential name or ID')
@update_command
def set_template(console, template_name, id, set_name, **kwargs):
    """Update a job template."""
    from aapclient.common.functions import (
        resolve_job_template_name,
        resolve_inventory_name,
        resolve_project_name,
        resolve_execution_environment_name,
        resolve_credential_name,
        resolve_instance_group_name
    )

    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Determine how to resolve the job template
        if id:
            job_template_id = id
            template_identifier = str(id)
        elif template_name:
            job_template_id = resolve_job_template_name(client, template_name)
            template_identifier = template_name
        else:
            show_error_message(console, "Job template identifier is required")
            click.get_current_context().exit(1)

        # Build update data
        update_data = {}

        if set_name:
            update_data['name'] = set_name
        if kwargs.get('job_type'):
            update_data['job_type'] = kwargs['job_type']
        if kwargs.get('inventory'):
            inventory_id = resolve_inventory_name(client, kwargs['inventory'])
            update_data['inventory'] = inventory_id
        if kwargs.get('project'):
            project_id = resolve_project_name(client, kwargs['project'])
            update_data['project'] = project_id
        if kwargs.get('playbook'):
            update_data['playbook'] = kwargs['playbook']
        if kwargs.get('description') is not None:
            update_data['description'] = kwargs['description']
        if kwargs.get('execution_environment'):
            ee_id = resolve_execution_environment_name(client, kwargs['execution_environment'])
            update_data['execution_environment'] = ee_id
        if kwargs.get('forks') is not None:
            update_data['forks'] = kwargs['forks']
        if kwargs.get('job_limit') is not None:
            update_data['limit'] = kwargs['job_limit']
        if kwargs.get('verbosity'):
            update_data['verbosity'] = int(kwargs['verbosity'])
        if kwargs.get('job_slices') is not None:
            update_data['job_slices'] = kwargs['job_slices']
        if kwargs.get('job_timeout') is not None:
            update_data['job_timeout'] = kwargs['job_timeout']
        if kwargs.get('job_tags') is not None:
            update_data['job_tags'] = kwargs['job_tags']
        if kwargs.get('skip_tags') is not None:
            update_data['skip_tags'] = kwargs['skip_tags']
        if kwargs.get('extra_vars') is not None:
            update_data['extra_vars'] = kwargs['extra_vars']

        # Handle boolean flags with enable/disable pairs
        if kwargs.get('enable_privileged_escalation'):
            update_data['become_enabled'] = True
        elif kwargs.get('disable_privileged_escalation'):
            update_data['become_enabled'] = False

        if kwargs.get('enable_concurrent_jobs'):
            update_data['allow_simultaneous'] = True
        elif kwargs.get('disable_concurrent_jobs'):
            update_data['allow_simultaneous'] = False

        if kwargs.get('enable_fact_storage'):
            update_data['use_fact_cache'] = True
        elif kwargs.get('disable_fact_storage'):
            update_data['use_fact_cache'] = False

        if kwargs.get('enable_show_changes'):
            update_data['diff_mode'] = True
        elif kwargs.get('disable_show_changes'):
            update_data['diff_mode'] = False

        if kwargs.get('prevent_instance_group_fallback'):
            update_data['prevent_instance_group_fallback'] = True
        elif kwargs.get('allow_instance_group_fallback'):
            update_data['prevent_instance_group_fallback'] = False

        # Handle ask-on-launch flags
        ask_flags = [
            'ask_diff_mode_on_launch', 'ask_variables_on_launch', 'ask_limit_on_launch',
            'ask_tags_on_launch', 'ask_skip_tags_on_launch', 'ask_job_type_on_launch',
            'ask_verbosity_on_launch', 'ask_inventory_on_launch', 'ask_credential_on_launch',
            'ask_execution_environment_on_launch', 'ask_labels_on_launch', 'ask_forks_on_launch',
            'ask_job_slices_on_launch', 'ask_timeout_on_launch', 'ask_instance_groups_on_launch'
        ]
        for flag in ask_flags:
            if kwargs.get(flag):
                update_data[flag] = True

        # Handle webhook flags
        if kwargs.get('enable_webhook'):
            update_data['webhook_service'] = kwargs.get('webhook_service', '')
            if kwargs.get('webhook_credential'):
                cred_id = resolve_credential_name(client, kwargs['webhook_credential'])
                update_data['webhook_credential'] = cred_id
        elif kwargs.get('disable_webhook'):
            update_data['webhook_service'] = ''
            update_data['webhook_credential'] = None

        if not update_data:
            show_error_message(console, "No changes specified")
            click.get_current_context().exit(1)

        # Update the job template
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
        response = client.patch(endpoint, json=update_data)

        if response.status_code == HTTP_OK:
            template_data = response.json()
            data = _format_template_data(template_data, use_utc=False, client=client, output_format='table')
            show_details_table(console, data)
        else:
            show_error_message(console, f"Failed to update job template: HTTP {response.status_code}")
            click.get_current_context().exit(1)

    except Exception as e:
        show_error_message(console, f"Failed to update job template: {e}")
        click.get_current_context().exit(1)


@template.group('variables')
def template_variables():
    """Manage job template variables."""
    pass


@template_variables.command('show')
@click.argument('template_name', metavar='<template>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Job template ID (overrides positional parameter)')
@show_command
def show_template_variables(console, output_format, template_name, id, utc):
    """Show job template variables."""
    from aapclient.common.functions import resolve_job_template_name

    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Determine how to resolve the job template
        if id:
            job_template_id = id
        else:
            job_template_id = resolve_job_template_name(client, template_name)

        # Get job template data
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
        response = client.get(endpoint)
        template_data = response.json()
        variables_raw = template_data.get('extra_vars', {})

        # Parse variables for JSON/YAML output
        from aapclient.common.functions import parse_variables_for_output
        variables_parsed = parse_variables_for_output(variables_raw)

        if output_format == 'json':
            show_raw_json(variables_parsed)
        elif output_format == 'yaml':
            show_raw_yaml(variables_parsed)
        else:
            # Table format showing template name and variables in YAML
            from aapclient.common.functions import format_variables_yaml_display
            variables_yaml = format_variables_yaml_display(variables_raw)

            # Create a simple key-value display
            data = {
                'Job Template': template_data.get('name', 'Unknown'),
                'Variables': variables_yaml if variables_yaml.strip() else 'No variables defined'
            }
            show_details_table(console, data)

    except Exception as e:
        show_error_message(console, f"Failed to show job template variables: {e}")
        click.get_current_context().exit(1)


# Add the template group to the main CLI
def register_template_commands(main_group: click.Group) -> None:
    """Register template commands with the main CLI group."""
    # Register survey commands as a subgroup of template
    from aapclient.cli.controller.v2.template_surveys import register_survey_commands
    register_survey_commands(template)

    main_group.add_command(template)
