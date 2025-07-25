"""Job commands."""
from aapclient.common.basecommands import AAPShowCommand, AAPListCommand
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_NOT_FOUND
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import format_duration, format_datetime


def _format_job_data(job_data, use_utc=False):
    """
    Format unified job data consistently

    Args:
        job_data (dict): Job data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract job details
    id_value = job_data.get('id', '')
    name = job_data.get('name', '')
    description = job_data.get('description', '')
    status = job_data.get('status', '')
    job_type = job_data.get('job_type', '')
    launch_type = job_data.get('launch_type', '')
    failed = job_data.get('failed', False)

    # The 'type' field indicates the kind of job (job, project_update, etc.)
    unified_job_type = job_data.get('type', '')

    # Time and duration fields
    started = job_data.get('started', '')
    finished = job_data.get('finished', '')
    elapsed = job_data.get('elapsed', 0)
    created = job_data.get('created', '')
    modified = job_data.get('modified', '')

    # Format elapsed time using helper function
    duration_display = format_duration(elapsed)

    # Format datetime fields
    started_display = format_datetime(started, use_utc)
    finished_display = format_datetime(finished, use_utc)
    created_display = format_datetime(created, use_utc)
    modified_display = format_datetime(modified, use_utc)

    # Get related resource names from summary_fields
    organization_name = ''
    if 'summary_fields' in job_data and 'organization' in job_data['summary_fields']:
        if job_data['summary_fields']['organization']:
            organization_name = job_data['summary_fields']['organization'].get('name', '')

    inventory_name = ''
    if 'summary_fields' in job_data and 'inventory' in job_data['summary_fields']:
        if job_data['summary_fields']['inventory']:
            inventory_name = job_data['summary_fields']['inventory'].get('name', '')

    project_name = ''
    if 'summary_fields' in job_data and 'project' in job_data['summary_fields']:
        if job_data['summary_fields']['project']:
            project_name = job_data['summary_fields']['project'].get('name', '')

    # For regular jobs, get job_template. For other types, get unified_job_template
    template_name = ''
    if 'summary_fields' in job_data and 'job_template' in job_data['summary_fields']:
        if job_data['summary_fields']['job_template']:
            template_name = job_data['summary_fields']['job_template'].get('name', '')
    elif 'summary_fields' in job_data and 'unified_job_template' in job_data['summary_fields']:
        if job_data['summary_fields']['unified_job_template']:
            template_name = job_data['summary_fields']['unified_job_template'].get('name', '')

    execution_environment_name = ''
    if 'summary_fields' in job_data and 'execution_environment' in job_data['summary_fields']:
        if job_data['summary_fields']['execution_environment']:
            execution_environment_name = job_data['summary_fields']['execution_environment'].get('name', '')

    instance_group_name = ''
    if 'summary_fields' in job_data and 'instance_group' in job_data['summary_fields']:
        if job_data['summary_fields']['instance_group']:
            instance_group_name = job_data['summary_fields']['instance_group'].get('name', '')

    created_by_username = ''
    if 'summary_fields' in job_data and 'created_by' in job_data['summary_fields']:
        if job_data['summary_fields']['created_by']:
            created_by_username = job_data['summary_fields']['created_by'].get('username', '')

    # Fields specific to certain job types
    playbook = job_data.get('playbook', '')
    scm_branch = job_data.get('scm_branch', '')
    scm_revision = job_data.get('scm_revision', '')
    if scm_revision:
        scm_revision = scm_revision[:8]  # Show first 8 characters

    execution_node = job_data.get('execution_node', '')
    controller_node = job_data.get('controller_node', '')

    # Fields specific to inventory updates
    source = job_data.get('source', '')

    # Fields specific to system jobs
    system_job_template = job_data.get('system_job_template', '')

    # Fields specific to workflow jobs
    workflow_job_template = job_data.get('workflow_job_template', '')

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Type',
        'Status',
        'Job Type',
        'Launch Type',
        'Failed',
        'Duration',
        'Started',
        'Finished',
        'Organization',
        'Inventory',
        'Project',
        'Template',
        'Execution Environment',
        'Instance Group',
        'Created By',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        name,
        description,
        unified_job_type,
        status,
        job_type,
        launch_type,
        'Yes' if failed else 'No',
        duration_display,
        started_display,
        finished_display,
        organization_name,
        inventory_name,
        project_name,
        template_name,
        execution_environment_name,
        instance_group_name,
        created_by_username,
        created_display,
        modified_display
    ]

    # Add type-specific fields conditionally
    if playbook:
        columns.append('Playbook')
        values.append(playbook)

    if scm_branch:
        columns.append('SCM Branch')
        values.append(scm_branch)

    if scm_revision:
        columns.append('SCM Revision')
        values.append(scm_revision)

    if source:
        columns.append('Source')
        values.append(source)

    if execution_node:
        columns.append('Execution Node')
        values.append(execution_node)

    if controller_node:
        columns.append('Controller Node')
        values.append(controller_node)

    return (columns, values)


class JobListCommand(AAPListCommand):
    """List unified jobs."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Maximum number of jobs to display (default: 20)'
        )
        parser.add_argument(
            '--type',
            choices=['job', 'project_update', 'inventory_update', 'system_job', 'workflow_job'],
            help='Filter by job type'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )
        return parser

    def take_action(self, parsed_args):
        try:
            client = self.controller_client

            # Build query parameters for server-side sorting (newest to oldest)
            params = {
                'page_size': parsed_args.limit,
                'order_by': '-id'  # Negative for descending order (newest first)
            }

            # Add type filter if specified
            if parsed_args.type:
                params['type'] = parsed_args.type

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}unified_jobs/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "unified jobs")

            if response.status_code == HTTP_OK:
                data = response.json()
                jobs = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Type', 'Status', 'Duration', 'Start Time', 'Finish Time']
                rows = []

                for job in jobs:
                    # Format elapsed time using helper function
                    elapsed = job.get('elapsed', 0)
                    duration_display = format_duration(elapsed)

                    row = [
                        job.get('id', ''),
                        job.get('name', ''),
                        job.get('type', ''),
                        job.get('status', ''),
                        duration_display,
                        format_datetime(job.get('started', ''), parsed_args.utc),
                        format_datetime(job.get('finished', ''), parsed_args.utc)
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                raise AAPClientError(f"Controller API failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class JobShowCommand(AAPShowCommand):
    """Show unified job details."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument('job_id', metavar='<job_id>', help='Job ID (numeric)')
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )
        return parser

    def take_action(self, parsed_args):
        try:
            client = self.controller_client

            # Validate that job_id is numeric
            try:
                job_id = int(parsed_args.job_id)
            except ValueError:
                raise AAPClientError(f"Job ID must be numeric, got: '{parsed_args.job_id}'")

            # First, get the job from unified_jobs to determine its type
            # We need the type to know which specific endpoint to use
            unified_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}unified_jobs/"
            try:
                unified_response = client.get(unified_endpoint, params={'id': job_id})
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", job_id)

            if unified_response.status_code == HTTP_OK:
                unified_data = unified_response.json()
                results = unified_data.get('results', [])
                if not results:
                    raise AAPResourceNotFoundError("Job", job_id)

                job_preview = results[0]
                job_type = job_preview.get('type', '')

                # Map job type to specific endpoint
                type_endpoint_map = {
                    'job': 'jobs',
                    'project_update': 'project_updates',
                    'inventory_update': 'inventory_updates',
                    'system_job': 'system_jobs',
                    'workflow_job': 'workflow_jobs'
                }

                if job_type not in type_endpoint_map:
                    raise AAPClientError(f"Unknown job type: {job_type}")

                # Now get the full job details from the specific endpoint
                specific_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}{type_endpoint_map[job_type]}/{job_id}/"
                try:
                    response = client.get(specific_endpoint)
                except AAPAPIError as api_error:
                    self.handle_api_error(api_error, "Controller API", job_id)

                if response.status_code == HTTP_OK:
                    job_data = response.json()
                    return _format_job_data(job_data, parsed_args.utc)
                else:
                    raise AAPClientError(f"Failed to get job details: {response.status_code}")
            else:
                raise AAPClientError(f"Failed to find job: {unified_response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
