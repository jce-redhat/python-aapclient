"""Job template commands."""
import json
import yaml
from aapclient.common.basecommands import AAPListCommand, AAPShowCommand, AAPCommand
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import (
    format_datetime,
    resolve_job_template_name,
    resolve_inventory_name,
    resolve_project_name,
    resolve_execution_environment_name,
    resolve_credential_name,
    resolve_instance_group_name,
    format_variables_display,
    format_variables_yaml_display
)



def _format_job_template_data(template_data, use_utc=False, client=None):
    """
    Format job template data consistently for ShowOne display.

    Args:
        template_data (dict): Job template data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract helper variables from summary_fields
    summary_fields = template_data.get('summary_fields', {})
    org_info = summary_fields.get('organization', {})
    project_info = summary_fields.get('project', {})
    inventory_info = summary_fields.get('inventory', {})
    ee_info = summary_fields.get('execution_environment', {})
    last_job_info = summary_fields.get('last_job', {})
    created_by = summary_fields.get('created_by', {})
    modified_by = summary_fields.get('modified_by', {})

    # Format datetime fields using common function
    created = template_data.get('created', 'Unknown')
    if created and created != 'Unknown':
        created = format_datetime(created, use_utc)

    modified = template_data.get('modified', 'Unknown')
    if modified and modified != 'Unknown':
        modified = format_datetime(modified, use_utc)

    last_job_run = template_data.get('last_job_run')
    if last_job_run:
        last_job_run = format_datetime(last_job_run, use_utc)
    else:
        last_job_run = 'Never'

    # Determine execution environment
    execution_environment = 'Default'
    if template_data.get('execution_environment'):
        if ee_info:
            execution_environment = ee_info.get('name', f"ID {template_data.get('execution_environment')}")
        else:
            execution_environment = f"ID {template_data.get('execution_environment')}"

    # Determine last job status
    last_job_status = 'None'
    if last_job_info:
        last_job_status = f"{last_job_info.get('status', 'Unknown')} (ID: {last_job_info.get('id', 'Unknown')})"

    # Determine credentials
    credentials_list = []
    credentials = summary_fields.get('credentials', [])
    for cred in credentials:
        if isinstance(cred, dict):
            cred_name = cred.get('name', f"ID {cred.get('id', 'Unknown')}")
            credentials_list.append(cred_name)
    credentials_display = ', '.join(credentials_list) if credentials_list else ''

    # Determine labels
    labels_list = []
    labels = summary_fields.get('labels', {})
    if isinstance(labels, dict) and 'results' in labels:
        for label in labels['results']:
            if isinstance(label, dict):
                label_name = label.get('name', f"ID {label.get('id', 'Unknown')}")
                labels_list.append(label_name)
    labels_display = ', '.join(labels_list) if labels_list else ''

    # Determine instance groups
    instance_groups_list = []

    # Try to fetch instance groups from dedicated endpoint if client is available
    if client and template_data.get('id'):
        try:
            ig_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_data['id']}/instance_groups/"
            ig_response = client.get(ig_endpoint)
            if ig_response.status_code == 200:
                ig_data = ig_response.json()
                instance_groups = ig_data.get('results', [])
                for ig in instance_groups:
                    if isinstance(ig, dict):
                        ig_name = ig.get('name', f"ID {ig.get('id', 'Unknown')}")
                        instance_groups_list.append(ig_name)
        except Exception:
            # Fall back to summary_fields if endpoint fetch fails
            instance_groups = summary_fields.get('instance_groups', [])
            for ig in instance_groups:
                if isinstance(ig, dict):
                    ig_name = ig.get('name', f"ID {ig.get('id', 'Unknown')}")
                    instance_groups_list.append(ig_name)
    else:
        # Fall back to summary_fields if no client available
        instance_groups = summary_fields.get('instance_groups', [])
        for ig in instance_groups:
            if isinstance(ig, dict):
                ig_name = ig.get('name', f"ID {ig.get('id', 'Unknown')}")
                instance_groups_list.append(ig_name)

    instance_groups_display = ', '.join(instance_groups_list) if instance_groups_list else ''

    # Determine survey state (more detailed than just enabled/disabled)
    survey_enabled = template_data.get('survey_enabled', False)
    survey_info = summary_fields.get('survey', None)

    if survey_info is None:
        survey_status = 'No'
    elif survey_enabled:
        survey_status = 'Yes (Enabled)'
    else:
        survey_status = 'Yes (Disabled)'

    # Handle extra variables using unified function
    extra_vars = template_data.get('extra_vars', '')
    extra_vars_display = format_variables_display(extra_vars, "template")

    # Helper function to add ask-on-launch indicator
    def add_ask_on_launch_indicator(value, ask_field_name):
        if template_data.get(ask_field_name, False):
            if value and str(value).strip():
                return f"{value} (ask on launch)"
            else:
                return "(ask on launch)"
        return value

    # Build field data for display with ask-on-launch indicators
    job_type_display = add_ask_on_launch_indicator(template_data.get('job_type', ''), 'ask_job_type_on_launch')
    inventory_display = add_ask_on_launch_indicator(
        inventory_info.get('name', f"ID {template_data.get('inventory', 'Unknown')}"),
        'ask_inventory_on_launch'
    )
    execution_environment_display = add_ask_on_launch_indicator(execution_environment, 'ask_execution_environment_on_launch')
    credentials_display_with_ask = add_ask_on_launch_indicator(credentials_display, 'ask_credential_on_launch')
    instance_groups_display_with_ask = add_ask_on_launch_indicator(instance_groups_display, 'ask_instance_groups_on_launch')
    labels_display_with_ask = add_ask_on_launch_indicator(labels_display, 'ask_labels_on_launch')
    forks_display = add_ask_on_launch_indicator(template_data.get('forks', 0), 'ask_forks_on_launch')
    verbosity_display = add_ask_on_launch_indicator(template_data.get('verbosity', 0), 'ask_verbosity_on_launch')
    job_slices_display = add_ask_on_launch_indicator(template_data.get('job_slice_count', 0), 'ask_job_slice_count_on_launch')
    timeout_display = add_ask_on_launch_indicator(template_data.get('timeout', 0), 'ask_timeout_on_launch')
    job_tags_display = add_ask_on_launch_indicator(template_data.get('job_tags', ''), 'ask_tags_on_launch')
    skip_tags_display = add_ask_on_launch_indicator(template_data.get('skip_tags', ''), 'ask_skip_tags_on_launch')
    limit_display = add_ask_on_launch_indicator(template_data.get('limit', ''), 'ask_limit_on_launch')
    diff_mode_display = add_ask_on_launch_indicator(
        'Yes' if template_data.get('diff_mode', False) else 'No',
        'ask_diff_mode_on_launch'
    )
    extra_vars_display_with_ask = add_ask_on_launch_indicator(extra_vars_display, 'ask_variables_on_launch')

    # Get webhook key, URL, and credential if webhook service is configured
    webhook_key = ''
    webhook_url = ''
    webhook_credential_display = ''
    if template_data.get('webhook_service'):
        related = template_data.get('related', {})

        # Get webhook key
        if client:
            webhook_key_url = related.get('webhook_key')
            if webhook_key_url:
                try:
                    response = client.get(webhook_key_url)
                    if response.status_code == 200:
                        key_data = response.json()
                        webhook_key = key_data.get('webhook_key', '')
                except Exception:
                    pass

        # Get webhook URL from webhook_receiver endpoint
        webhook_receiver_path = related.get('webhook_receiver')
        if webhook_receiver_path:
            try:
                # Get base URL from client manager config
                from aapclient.common.clientmanager import AAPClientManager
                client_manager = AAPClientManager()
                base_url = client_manager.config.base_url
                webhook_url = base_url.rstrip('/') + webhook_receiver_path
            except Exception:
                pass

        # Get webhook credential display
        webhook_credential_id = template_data.get('webhook_credential')
        if webhook_credential_id:
            summary_fields = template_data.get('summary_fields', {})
            webhook_cred_info = summary_fields.get('webhook_credential', {})
            if webhook_cred_info and isinstance(webhook_cred_info, dict):
                webhook_credential_display = webhook_cred_info.get('name', f"ID {webhook_credential_id}")
            else:
                webhook_credential_display = f"ID {webhook_credential_id}"

    field_data = {
        'ID': template_data.get('id', ''),
        'Name': template_data.get('name', ''),
        'Description': template_data.get('description', ''),
        'Job Type': job_type_display,
        'Organization': org_info.get('name', 'Unknown'),
        'Project': project_info.get('name', f"ID {template_data.get('project', 'Unknown')}"),
        'Inventory': inventory_display,
        'Playbook': template_data.get('playbook', ''),
        'Execution Environment': execution_environment_display,
        'Credentials': credentials_display_with_ask,
        'Instance Groups': instance_groups_display_with_ask,
        'Labels': labels_display_with_ask,
        'Forks': forks_display,
        'Verbosity': verbosity_display,
        'Job Slices': job_slices_display,
        'Job Timeout': timeout_display,
        'Job Tags': job_tags_display,
        'Skip Tags': skip_tags_display,
        'Limit': limit_display,
        'Diff Mode': diff_mode_display,
        'Survey Attached': survey_status,
        'Privileged Escalation': 'Yes' if template_data.get('become_enabled', False) else 'No',
        'Concurrent Jobs': 'Yes' if template_data.get('allow_simultaneous', False) else 'No',
        'Enable Fact Storage': 'Yes' if template_data.get('use_fact_cache', False) else 'No',
        'Prevent Instance Group Fallback': 'Yes' if template_data.get('prevent_instance_group_fallback', False) else 'No',
        'Extra Variables': extra_vars_display_with_ask,
        'Webhook Service': template_data.get('webhook_service', ''),
        'Webhook Credential': webhook_credential_display,
        'Webhook URL': webhook_url,
        'Webhook Key': webhook_key,
        'Last Job Run': last_job_run,
        'Last Job Status': last_job_status,
        'Created': created,
        'Created By': created_by.get('username', 'Unknown'),
        'Modified': modified,
        'Modified By': modified_by.get('username', 'Unknown')
    }

    # Add conditional fields only if they have meaningful values

    # SCM Branch - only if specified
    scm_branch = template_data.get('scm_branch', '')
    if scm_branch and scm_branch.strip():
        field_data['SCM Branch'] = scm_branch

    # Start At Task - only if specified
    start_at_task = template_data.get('start_at_task', '')
    if start_at_task and start_at_task.strip():
        field_data['Start At Task'] = start_at_task

    return (list(field_data.keys()), list(field_data.values()))


class JobTemplateListCommand(AAPListCommand):
    """List job templates."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--limit',
            type=int,
            metavar='N',
            help='Limit the number of results returned (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the job template list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query job_templates endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "job_templates endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()

                # Extract job templates from results (already sorted by API)
                job_templates = data.get('results', [])

                # Define columns for table display
                columns = [
                    'ID',
                    'Name',
                    'Organization',
                    'Last Ran'
                ]

                # Build rows data
                rows = []
                for template in job_templates:
                    # Get organization name from summary_fields
                    org_name = 'Unknown'
                    if template.get('summary_fields', {}).get('organization'):
                        org_name = template['summary_fields']['organization'].get('name', 'Unknown')

                    # Get last job run time, format if available
                    last_ran = 'Never'
                    last_job_run = template.get('last_job_run')
                    if last_job_run:
                        # Format as relative time (e.g., "2 hours ago") for better UX
                        last_ran = format_datetime(last_job_run, use_utc=False)

                    row = [
                        template.get('id', ''),
                        template.get('name', ''),
                        org_name,
                        last_ran
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


class JobTemplateShowCommand(AAPShowCommand):
    """Show details of a specific job template."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            metavar='<template>',
            help='Job template name or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the job template show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                template_id = parsed_args.id
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                template_id = resolve_job_template_name(client, parsed_args.template, api="controller")
            else:
                raise AAPClientError("Job template identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                template_data = response.json()
                return _format_job_template_data(template_data, use_utc=parsed_args.utc, client=client)
            else:
                raise AAPClientError(f"Failed to get job template: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class JobTemplateVariablesShowCommand(AAPShowCommand):
    """Show job template variables in YAML format."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            metavar='<template>',
            help='Job template name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the job template variables show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                template_id = parsed_args.id
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                template_id = resolve_job_template_name(client, parsed_args.template, api="controller")
            else:
                raise AAPClientError("Job template identifier is required")

            # Get job template details
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                template_data = response.json()

                # Extract variables and format using unified function
                variables = template_data.get('extra_vars', '')
                variables_yaml = format_variables_yaml_display(variables)

                # Format for display
                columns = ['Template', 'Extra Variables']
                values = [
                    parsed_args.template or parsed_args.id,
                    variables_yaml
                ]

                return (columns, values)
            else:
                raise AAPClientError(f"Failed to get job template: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class JobTemplateSurveyShowCommand(AAPListCommand):
    """Show job template survey specification."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            metavar='<template>',
            help='Job template name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the job template survey show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                template_id = parsed_args.id
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                template_id = resolve_job_template_name(client, parsed_args.template, api="controller")
            else:
                raise AAPClientError("Job template identifier is required")

            # Get survey specification from the survey_spec endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/survey_spec/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", f"job_templates/{template_id}/survey_spec")

            if response.status_code == HTTP_OK:
                survey_data = response.json()

                # Check if survey data contains questions
                if not survey_data or not survey_data.get('spec'):
                    raise AAPClientError("No survey specification found for this job template")

                # Extract survey questions
                survey_spec = survey_data.get('spec', [])

                if not survey_spec:
                    raise AAPClientError("No survey questions found for this job template")

                                # Format survey data for display - create one row per question
                columns = [
                    'Index',
                    'Question',
                    'Type',
                    'Required',
                    'Variable',
                    'Default',
                    'Min Length',
                    'Max Length',
                    'Choices'
                ]

                rows = []
                for index, question in enumerate(survey_spec, start=1):
                    question_var = question.get('variable', '')
                    question_text = question.get('question_name', '')
                    question_type = question.get('type', '')
                    question_min = question.get('min', '')
                    question_max = question.get('max', '')
                    required = 'Yes' if question.get('required', False) else 'No'
                    default_value = question.get('default', '')

                    # Handle choices for multiple choice questions
                    choices = question.get('choices', '')
                    if isinstance(choices, list):
                        choices = ', '.join(str(choice) for choice in choices)
                    elif not choices:
                        choices = ''

                    # Convert default value to string
                    if default_value is None:
                        default_value = ''
                    else:
                        default_value = str(default_value)

                    row = [
                        str(index),
                        question_text,
                        question_type,
                        required,
                        question_var,
                        default_value,
                        question_min,
                        question_max,
                        choices
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                # Handle specific error cases
                if response.status_code == 404:
                    raise AAPResourceNotFoundError("Job Template", template_id)
                else:
                    raise AAPClientError(f"Failed to get survey specification: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class JobTemplateSurveyQuestionAddCommand(AAPCommand):
    """Add a new question to a job template survey specification."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            metavar='<template>',
            help='Job template name or ID'
        )

        # Required arguments
        parser.add_argument(
            '--question',
            required=True,
            help='Question text to display to the user'
        )

        parser.add_argument(
            '--type',
            required=True,
            choices=['text', 'password', 'integer', 'float', 'multiplechoice', 'multiselect'],
            help='Question type'
        )

        parser.add_argument(
            '--variable',
            required=True,
            help='Variable name to store the answer'
        )

        # Optional arguments
        parser.add_argument(
            '--is-required',
            action='store_true',
            help='Make this question required'
        )

        parser.add_argument(
            '--default-value',
            help='Default value for the question'
        )

        parser.add_argument(
            '--min-length',
            type=int,
            help='Minimum length for text inputs'
        )

        parser.add_argument(
            '--max-length',
            type=int,
            help='Maximum length for text inputs'
        )

        parser.add_argument(
            '--choices',
            help='Comma-separated list of choices for multiplechoice/multiselect questions'
        )

        # Index control argument
        parser.add_argument(
            '--index',
            type=int,
            help='Index where to insert the question (1-based, optional - defaults to end)'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the job template survey add command."""
        try:
            # Validate arguments
            self._validate_arguments(parsed_args)

            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                template_id = parsed_args.id
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                template_id = resolve_job_template_name(client, parsed_args.template, api="controller")
            else:
                raise AAPClientError("Job template identifier is required")

            # Get current survey specification
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/survey_spec/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", f"job_templates/{template_id}/survey_spec")

            if response.status_code == HTTP_OK:
                current_survey = response.json()

                # Handle empty survey
                if not current_survey:
                    current_survey = {
                        "name": "Survey",
                        "description": "Job Template Survey",
                        "spec": []
                    }

                # Create new question
                new_question = self._build_question(parsed_args)

                # Check for variable name conflicts
                existing_variables = [q.get('variable') for q in current_survey.get('spec', [])]
                if new_question['variable'] in existing_variables:
                    raise AAPClientError(f"Variable '{new_question['variable']}' already exists in the survey")

                # Insert new question at specified index or append to end
                current_spec = current_survey.get('spec', [])
                new_spec = self._insert_question_at_index(current_spec, new_question, parsed_args)

                modified_survey = {
                    "name": current_survey.get('name', 'Survey'),
                    "description": current_survey.get('description', 'Job Template Survey'),
                    "spec": new_spec
                }

                # POST the modified survey
                try:
                    response = client.post(endpoint, json=modified_survey)
                except AAPAPIError as api_error:
                    self.handle_api_error(api_error, "Controller API", f"job_templates/{template_id}/survey_spec")

                if response.status_code == HTTP_OK:
                    question_count = len(modified_survey['spec'])
                    print(f"Added question '{parsed_args.question}' to survey.")
                else:
                    raise AAPClientError(f"Failed to update survey: {response.status_code}")
            else:
                # Handle specific error cases
                if response.status_code == 404:
                    raise AAPResourceNotFoundError("Job Template", template_id)
                else:
                    raise AAPClientError(f"Failed to get survey specification: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")

    def _validate_arguments(self, parsed_args):
        """Validate command arguments."""
        # If --is-required is used, --default-value is required
        if parsed_args.is_required and not parsed_args.default_value:
            raise AAPClientError("--default-value is required when --is-required is specified")

        # If type is multiplechoice or multiselect, --choices is required
        if parsed_args.type in ['multiplechoice', 'multiselect']:
            if not parsed_args.choices:
                raise AAPClientError("--choices is required for multiplechoice and multiselect question types")

        # Validate min/max length
        if parsed_args.min_length is not None and parsed_args.min_length < 0:
            raise AAPClientError("--min-length must be a positive integer")

        if parsed_args.max_length is not None and parsed_args.max_length < 0:
            raise AAPClientError("--max-length must be a positive integer")

        if (parsed_args.min_length is not None and parsed_args.max_length is not None
            and parsed_args.min_length > parsed_args.max_length):
            raise AAPClientError("--min-length cannot be greater than --max-length")

        # Validate index argument
        if parsed_args.index is not None and parsed_args.index < 1:
            raise AAPClientError("--index must be 1 or greater")

    def _build_question(self, parsed_args):
        """Build the question dictionary from parsed arguments."""
        question = {
            "variable": parsed_args.variable,
            "question_name": parsed_args.question,
            "type": parsed_args.type,
            "required": parsed_args.is_required
        }

        # Add optional fields if provided
        if parsed_args.default_value is not None:
            # Convert default value based on question type
            if parsed_args.type == 'integer':
                try:
                    question["default"] = int(parsed_args.default_value)
                except ValueError:
                    raise AAPClientError(f"Default value '{parsed_args.default_value}' is not a valid integer")
            elif parsed_args.type == 'float':
                try:
                    question["default"] = float(parsed_args.default_value)
                except ValueError:
                    raise AAPClientError(f"Default value '{parsed_args.default_value}' is not a valid float")
            else:
                # For multiselect, check if default value contains multiple choices
                if parsed_args.type == 'multiselect' and ',' in parsed_args.default_value:
                    # Split comma-separated defaults and join with newlines
                    default_choices = [choice.strip() for choice in parsed_args.default_value.split(',')]
                    question["default"] = '\n'.join(default_choices)
                else:
                    question["default"] = parsed_args.default_value

        if parsed_args.min_length is not None:
            question["min"] = parsed_args.min_length

        if parsed_args.max_length is not None:
            question["max"] = parsed_args.max_length

        if parsed_args.choices:
            # Split choices by comma and strip whitespace
            choices_list = [choice.strip() for choice in parsed_args.choices.split(',')]
            question["choices"] = choices_list

        return question

    def _insert_question_at_index(self, current_spec, new_question, parsed_args):
        """Insert new question at the specified index or append to end."""
        if parsed_args.index is not None:
            # Insert at specified index (1-based)
            index = parsed_args.index - 1  # Convert to 0-based
            if parsed_args.index > len(current_spec) + 1:
                raise AAPClientError(f"--index {parsed_args.index} is beyond the allowed range. Survey has {len(current_spec)} question(s), maximum index is {len(current_spec) + 1}")
            return current_spec[:index] + [new_question] + current_spec[index:]
        else:
            # No index specified, append to end
            return current_spec + [new_question]


class JobTemplateSurveyQuestionDeleteCommand(AAPCommand):
    """Delete a question from a job template survey specification."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        parser.add_argument(
            'template',
            nargs='?',
            help='Job template name or ID'
        )

        parser.add_argument(
            '--index',
            type=int,
            required=True,
            help='Index of the question to delete'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the job template survey delete command."""
        try:
            # Validate arguments
            self._validate_arguments(parsed_args)

            # Get client from centralized client manager
            client = self.controller_client
            job_template_id = resolve_job_template_name(
                client, parsed_args.template if parsed_args.template else parsed_args.id
            )

            # Fetch current survey
            endpoint = f'{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/'
            try:
                response = client.get(endpoint)
                current_survey = response.json()
            except AAPAPIError as api_error:
                raise AAPClientError(f"Failed to fetch survey: {api_error}")

            # Check if survey exists and has questions
            if not current_survey or current_survey == {}:
                raise AAPClientError("No survey specification found for this job template")

            current_spec = current_survey.get('spec', [])
            if not current_spec:
                raise AAPClientError("No questions found in the survey specification")

            # Validate index bounds
            if parsed_args.index < 1 or parsed_args.index > len(current_spec):
                raise AAPClientError(f"Index {parsed_args.index} is invalid. Survey has {len(current_spec)} question(s)")

            # Get the question to be deleted for confirmation message
            question_to_delete = current_spec[parsed_args.index - 1]
            question_name = question_to_delete.get('question_name', 'Unknown')
            variable_name = question_to_delete.get('variable', 'unknown')

            # Remove the question at the specified index
            new_spec = current_spec[:parsed_args.index - 1] + current_spec[parsed_args.index:]

            modified_survey = {
                "name": current_survey.get('name', 'Survey'),
                "description": current_survey.get('description', 'Job Template Survey'),
                "spec": new_spec
            }

            # POST the modified survey
            try:
                response = client.post(endpoint, json=modified_survey)
                if response.status_code == HTTP_OK:
                    remaining_count = len(new_spec)
                    print(f"Deleted question {parsed_args.index}. ")
                else:
                    raise AAPClientError(f"Failed to update survey: HTTP {response.status_code}")
            except AAPAPIError as api_error:
                if hasattr(api_error, 'response') and api_error.response:
                    try:
                        error_data = api_error.response.json()
                        if isinstance(error_data, dict) and 'error' in error_data:
                            raise AAPClientError(f"Bad request: {error_data['error']}")
                    except:
                        pass
                raise AAPClientError(f"API error: {api_error}")

        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")

    def _validate_arguments(self, parsed_args):
        """Validate command arguments."""
        if not parsed_args.template and not parsed_args.id:
            raise AAPClientError("Either template name/ID or --id must be provided")

        if parsed_args.index < 1:
            raise AAPClientError("Index is invalid, must be 1 or greater")


class JobTemplateDeleteCommand(AAPCommand):
    """Delete a job template."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            help='Job template name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the job template delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                job_template_id = parsed_args.id
                template_identifier = str(parsed_args.id)
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                job_template_id = resolve_job_template_name(client, parsed_args.template)
                template_identifier = parsed_args.template
            else:
                raise AAPClientError("Job template identifier is required")

            # Get job template details first for confirmation
            try:
                endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Job template", template_identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                job_template_data = response.json()
                template_name = job_template_data.get('name', template_identifier)

                # Delete job template
                try:
                    delete_response = client.delete(endpoint)
                except AAPAPIError as api_error:
                    if api_error.status_code == HTTP_NOT_FOUND:
                        # Handle 404 error with proper message
                        raise AAPResourceNotFoundError("Job template", template_identifier)
                    elif api_error.status_code == HTTP_BAD_REQUEST:
                        # Pass through 400 status messages directly to user
                        raise SystemExit(str(api_error))
                    else:
                        # Re-raise other errors
                        raise

                if delete_response.status_code == HTTP_NO_CONTENT:
                    print(f"Job template '{template_name}' deleted")
                else:
                    raise AAPClientError(f"Job template deletion failed with status {delete_response.status_code}")
            else:
                raise AAPClientError(f"Failed to get job template details with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")



class JobTemplateSurveyCreateCommand(AAPCommand):
    """Create a survey by adding the first question (redirects to 'survey question add')."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            help='Job template name or ID'
        )

        # Required arguments for the first question
        parser.add_argument(
            '--question',
            required=True,
            help='Question text to display to the user'
        )

        parser.add_argument(
            '--type',
            required=True,
            choices=['text', 'password', 'integer', 'float', 'multiplechoice', 'multiselect'],
            help='Question type'
        )

        parser.add_argument(
            '--variable',
            required=True,
            help='Variable name to store the answer'
        )

        parser.add_argument(
            '--is-required',
            action='store_true',
            help='Make this question required'
        )

        parser.add_argument(
            '--default-value',
            help='Default value for the question'
        )

        parser.add_argument(
            '--min-length',
            type=int,
            help='Minimum length for text inputs'
        )

        parser.add_argument(
            '--max-length',
            type=int,
            help='Maximum length for text inputs'
        )

        parser.add_argument(
            '--choices',
            help='Comma-separated list of choices for multiplechoice/multiselect questions'
        )

        parser.add_argument(
            '--index',
            type=int,
            help='Index where to insert the question (1-based, optional - defaults to end)'
        )

        # Survey metadata arguments
        parser.add_argument(
            '--name',
            help='Survey name (will be set after question is added)'
        )

        parser.add_argument(
            '--description',
            help='Survey description (will be set after question is added)'
        )

        parser.add_argument(
            '--enabled',
            action='store_true',
            help='Enable the survey on the job template after creation'
        )

        return parser

    def take_action(self, parsed_args):
        """
        Execute the job template survey create command.

        Surveys are created by adding questions to a template survey spec, so this
        command calls the existing 'template survey question add' code to create the
        initial question, and 'template survey set' to update metadata such as the
        survey name, description, or enabled/disabled status.

        """
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                job_template_id = parsed_args.id
                template_identifier = str(parsed_args.id)
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                job_template_id = resolve_job_template_name(client, parsed_args.template)
                template_identifier = parsed_args.template
            else:
                raise AAPClientError("Job template identifier is required")

            # Check if survey already exists
            survey_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/"
            try:
                response = client.get(survey_endpoint)
                if response.status_code == HTTP_OK:
                    survey_data = response.json()
                    if survey_data.get('spec') and len(survey_data['spec']) > 0:
                        print(f"Survey already exists for job template {template_identifier} with {len(survey_data['spec'])} question(s).")
                        print("Use 'aap template survey question add' to add more questions or 'aap template survey show' to view existing questions.")
                        return
            except AAPAPIError:
                # Survey doesn't exist, which is what we want for create
                pass

            # Create an instance of the question add command and execute it
            question_add_command = JobTemplateSurveyQuestionAddCommand(self.app, self.app_args)
            question_add_command.take_action(parsed_args)

            # If we have survey metadata or enable flag, also run the set command
            if parsed_args.name or parsed_args.description or parsed_args.enabled:
                # Create args for the set command
                class SetArgs:
                    def __init__(self):
                        self.id = parsed_args.id
                        self.template = parsed_args.template
                        self.name = parsed_args.name
                        self.description = parsed_args.description
                        self.enabled = parsed_args.enabled
                        self.disabled = False

                set_args = SetArgs()
                set_command = JobTemplateSurveySetCommand(self.app, self.app_args)
                set_command.take_action(set_args)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class JobTemplateSurveySetCommand(AAPCommand):
    """Update survey settings for a job template."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            help='Job template name or ID'
        )

        # Survey metadata arguments
        parser.add_argument(
            '--name',
            help='Survey name'
        )

        parser.add_argument(
            '--description',
            help='Survey description'
        )

        # Mutually exclusive enabled/disabled arguments
        enabled_group = parser.add_mutually_exclusive_group()
        enabled_group.add_argument(
            '--enabled',
            action='store_true',
            help='Enable the survey on the job template'
        )

        enabled_group.add_argument(
            '--disabled',
            action='store_true',
            help='Disable the survey on the job template'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the job template survey set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                job_template_id = parsed_args.id
                template_identifier = str(parsed_args.id)
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                job_template_id = resolve_job_template_name(client, parsed_args.template)
                template_identifier = parsed_args.template
            else:
                raise AAPClientError("Job template identifier is required")

            # Check if any survey metadata needs to be updated
            if parsed_args.name is not None or parsed_args.description is not None:
                # Get current survey specification
                survey_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/"
                try:
                    response = client.get(survey_endpoint)
                    current_survey = response.json()
                except AAPAPIError as api_error:
                    if api_error.status_code == HTTP_NOT_FOUND:
                        raise AAPClientError("No survey found for this job template. Use 'survey create' first.")
                    raise AAPClientError(f"Failed to fetch survey: {api_error}")

                # Check if survey exists and has data
                if not current_survey or current_survey == {}:
                    raise AAPClientError("No survey found for this job template. Use 'survey create' first.")

                # Update survey metadata
                updated_survey = current_survey.copy()
                if parsed_args.name is not None:
                    updated_survey["name"] = parsed_args.name
                if parsed_args.description is not None:
                    updated_survey["description"] = parsed_args.description

                # Update the survey
                try:
                    response = client.post(survey_endpoint, json=updated_survey)
                    if response.status_code != HTTP_OK:
                        raise AAPClientError(f"Failed to update survey: HTTP {response.status_code}")
                except AAPAPIError as api_error:
                    if hasattr(api_error, 'response') and api_error.response:
                        try:
                            error_data = api_error.response.json()
                            if isinstance(error_data, dict) and 'error' in error_data:
                                raise AAPClientError(f"Bad request: {error_data['error']}")
                        except:
                            pass
                    raise AAPClientError(f"API error: {api_error}")

            # Update job template enabled status if requested
            if parsed_args.enabled or parsed_args.disabled:
                template_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
                survey_enabled = parsed_args.enabled  # True for --enabled, False for --disabled
                try:
                    template_response = client.patch(template_endpoint, json={"survey_enabled": survey_enabled})
                    if template_response.status_code != HTTP_OK:
                        raise AAPClientError(f"Failed to update survey enabled status: HTTP {template_response.status_code}")
                except AAPAPIError as api_error:
                    raise AAPClientError(f"Failed to update survey enabled status: {api_error}")

            # Success message
            changes = False
            if parsed_args.name is not None:
                changes = True
            if parsed_args.description is not None:
                changes = True
            if parsed_args.enabled:
                changes = True
            if parsed_args.disabled:
                changes = True

            if changes:
                print(f"Survey updated for job template {template_identifier}.")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class JobTemplateSurveyDeleteCommand(AAPCommand):
    """Delete the survey from a job template."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Job template ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'template',
            nargs='?',
            help='Job template name or ID'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the job template survey delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the job template
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                job_template_id = parsed_args.id
                template_identifier = str(parsed_args.id)
            elif parsed_args.template:
                # Use positional parameter - name first, then ID fallback if numeric
                job_template_id = resolve_job_template_name(client, parsed_args.template)
                template_identifier = parsed_args.template
            else:
                raise AAPClientError("Job template identifier is required")

            # Delete the survey specification
            survey_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/"
            try:
                response = client.delete(survey_endpoint)
                if response.status_code not in [HTTP_NO_CONTENT, HTTP_OK]:
                    raise AAPClientError(f"Failed to delete survey: HTTP {response.status_code}")
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    raise AAPClientError("No survey found for this job template")
                raise AAPClientError(f"Failed to delete survey: {api_error}")

            # Disable survey on the job template
            template_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
            try:
                template_response = client.patch(template_endpoint, json={"survey_enabled": False})
                if template_response.status_code != HTTP_OK:
                    print(f"Warning: Survey deleted but failed to disable it on the job template")
            except AAPAPIError as api_error:
                print(f"Warning: Survey deleted but failed to disable it on the job template: {api_error}")

            print(f"Survey deleted from job template {template_identifier}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class JobTemplateCreateCommand(AAPShowCommand):
    """Create a job template."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Required arguments
        parser.add_argument(
            'name',
            help='Job template name'
        )

        parser.add_argument(
            '--job-type',
            required=True,
            choices=['check', 'run'],
            help='Job type (check or run)'
        )

        parser.add_argument(
            '--inventory',
            required=True,
            help='Inventory name or ID'
        )

        parser.add_argument(
            '--project',
            required=True,
            help='Project name or ID'
        )

        parser.add_argument(
            '--playbook',
            required=True,
            help='Playbook path within the project'
        )

        # Optional arguments
        parser.add_argument(
            '--description',
            help='Job template description'
        )

        parser.add_argument(
            '--execution-environment',
            help='Execution environment name or ID'
        )

        parser.add_argument(
            '--credential',
            action='append',
            dest='credentials',
            help='Credential name or ID (can be specified multiple times)'
        )

        parser.add_argument(
            '--forks',
            type=int,
            help='Number of parallel processes to use'
        )

        parser.add_argument(
            '--limit',
            help='Limit execution to specific hosts or groups'
        )

        parser.add_argument(
            '--verbosity',
            type=int,
            choices=[0, 1, 2, 3, 4, 5],
            help='Verbosity level (0-5)'
        )

        parser.add_argument(
            '--job-slices',
            type=int,
            help='Number of job slices'
        )

        parser.add_argument(
            '--job-timeout',
            type=int,
            help='Number of seconds to run before the task is canceled'
        )

        parser.add_argument(
            '--enable-diff-mode',
            action='store_true',
            dest='diff_mode',
            help='Enable diff mode'
        )

        parser.add_argument(
            '--instance-group',
            action='append',
            dest='instance_groups',
            help='Instance group name or ID (can be specified multiple times)'
        )

        parser.add_argument(
            '--job-tags',
            help='Job tags (comma-separated)'
        )

        parser.add_argument(
            '--skip-tags',
            help='Skip tags (comma-separated)'
        )

        parser.add_argument(
            '--extra-vars',
            help='Extra variables as JSON string'
        )

        parser.add_argument(
            '--enable-privileged-escalation',
            action='store_true',
            dest='become_enabled',
            help='Enable privilege escalation (become)'
        )

        parser.add_argument(
            '--enable-concurrent-jobs',
            action='store_true',
            dest='allow_simultaneous',
            help='Allow multiple jobs to run simultaneously'
        )

        parser.add_argument(
            '--enable-fact-storage',
            action='store_true',
            dest='use_fact_cache',
            help='Enable fact storage/caching'
        )

        parser.add_argument(
            '--prevent-instance-group-fallback',
            action='store_true',
            dest='prevent_instance_group_fallback',
            help='Prevent fallback to other instance groups'
        )

        # Ask on launch arguments
        parser.add_argument(
            '--ask-credential-on-launch',
            action='store_true',
            dest='ask_credential_on_launch',
            help='Prompt for credential when launching'
        )

        parser.add_argument(
            '--ask-diff-mode-on-launch',
            action='store_true',
            dest='ask_diff_mode_on_launch',
            help='Prompt for diff mode when launching'
        )

        parser.add_argument(
            '--ask-execution-environment-on-launch',
            action='store_true',
            dest='ask_execution_environment_on_launch',
            help='Prompt for execution environment when launching'
        )

        parser.add_argument(
            '--ask-forks-on-launch',
            action='store_true',
            dest='ask_forks_on_launch',
            help='Prompt for forks when launching'
        )

        parser.add_argument(
            '--ask-instance-groups-on-launch',
            action='store_true',
            dest='ask_instance_groups_on_launch',
            help='Prompt for instance groups when launching'
        )

        parser.add_argument(
            '--ask-inventory-on-launch',
            action='store_true',
            dest='ask_inventory_on_launch',
            help='Prompt for inventory when launching'
        )

        parser.add_argument(
            '--ask-job-slice-count-on-launch',
            action='store_true',
            dest='ask_job_slice_count_on_launch',
            help='Prompt for job slice count when launching'
        )

        parser.add_argument(
            '--ask-job-type-on-launch',
            action='store_true',
            dest='ask_job_type_on_launch',
            help='Prompt for job type when launching'
        )

        parser.add_argument(
            '--ask-labels-on-launch',
            action='store_true',
            dest='ask_labels_on_launch',
            help='Prompt for labels when launching'
        )

        parser.add_argument(
            '--ask-limit-on-launch',
            action='store_true',
            dest='ask_limit_on_launch',
            help='Prompt for limit when launching'
        )

        parser.add_argument(
            '--ask-skip-tags-on-launch',
            action='store_true',
            dest='ask_skip_tags_on_launch',
            help='Prompt for skip tags when launching'
        )

        parser.add_argument(
            '--ask-tags-on-launch',
            action='store_true',
            dest='ask_tags_on_launch',
            help='Prompt for tags when launching'
        )

        parser.add_argument(
            '--ask-timeout-on-launch',
            action='store_true',
            dest='ask_timeout_on_launch',
            help='Prompt for timeout when launching'
        )

        parser.add_argument(
            '--ask-variables-on-launch',
            action='store_true',
            dest='ask_variables_on_launch',
            help='Prompt for variables when launching'
        )

        parser.add_argument(
            '--ask-verbosity-on-launch',
            action='store_true',
            dest='ask_verbosity_on_launch',
            help='Prompt for verbosity when launching'
        )

        # Webhook arguments
        parser.add_argument(
            '--enable-webhook',
            action='store_true',
            dest='enable_webhook',
            help='Enable webhook functionality for this job template'
        )

        parser.add_argument(
            '--webhook-service',
            choices=['gitlab', 'github', 'bitbucket_dc'],
            dest='webhook_service',
            help='Webhook service type (required when --enable-webhook is used)'
        )
        parser.add_argument(
            '--webhook-credential',
            dest='webhook_credential',
            help='Credential to use for webhook authentication (optional)'
        )



        return parser

    def take_action(self, parsed_args):
        """Execute the job template create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Validate webhook arguments
            if parsed_args.enable_webhook and not parsed_args.webhook_service:
                raise AAPClientError("--webhook-service is required when --enable-webhook is used")

            # Resolve inventory name to ID
            inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")

            # Resolve project name to ID
            project_id = resolve_project_name(client, parsed_args.project, api="controller")

            # Build job template data
            template_data = {
                "name": parsed_args.name,
                "job_type": parsed_args.job_type,
                "inventory": inventory_id,
                "project": project_id,
                "playbook": parsed_args.playbook
            }

            # Add optional description
            if parsed_args.description:
                template_data["description"] = parsed_args.description

            # Resolve execution environment if provided
            if parsed_args.execution_environment:
                ee_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")
                template_data["execution_environment"] = ee_id

            # Add optional numeric fields
            if parsed_args.forks is not None:
                template_data["forks"] = parsed_args.forks
            if parsed_args.verbosity is not None:
                template_data["verbosity"] = parsed_args.verbosity
            if parsed_args.job_slices is not None:
                template_data["job_slice_count"] = parsed_args.job_slices
            if parsed_args.job_timeout is not None:
                template_data["timeout"] = parsed_args.job_timeout

            # Add optional string fields
            if parsed_args.limit:
                template_data["limit"] = parsed_args.limit
            if parsed_args.job_tags:
                template_data["job_tags"] = parsed_args.job_tags
            if parsed_args.skip_tags:
                template_data["skip_tags"] = parsed_args.skip_tags

            # Add boolean fields
            if parsed_args.diff_mode:
                template_data["diff_mode"] = True
            if parsed_args.become_enabled:
                template_data["become_enabled"] = True
            if parsed_args.allow_simultaneous:
                template_data["allow_simultaneous"] = True
            if parsed_args.use_fact_cache:
                template_data["use_fact_cache"] = True
            if parsed_args.prevent_instance_group_fallback:
                template_data["prevent_instance_group_fallback"] = True

            # Add ask_*_on_launch boolean fields
            if parsed_args.ask_credential_on_launch:
                template_data["ask_credential_on_launch"] = True
            if parsed_args.ask_diff_mode_on_launch:
                template_data["ask_diff_mode_on_launch"] = True
            if parsed_args.ask_execution_environment_on_launch:
                template_data["ask_execution_environment_on_launch"] = True
            if parsed_args.ask_forks_on_launch:
                template_data["ask_forks_on_launch"] = True
            if parsed_args.ask_instance_groups_on_launch:
                template_data["ask_instance_groups_on_launch"] = True
            if parsed_args.ask_inventory_on_launch:
                template_data["ask_inventory_on_launch"] = True
            if parsed_args.ask_job_slice_count_on_launch:
                template_data["ask_job_slice_count_on_launch"] = True
            if parsed_args.ask_job_type_on_launch:
                template_data["ask_job_type_on_launch"] = True
            if parsed_args.ask_labels_on_launch:
                template_data["ask_labels_on_launch"] = True
            if parsed_args.ask_limit_on_launch:
                template_data["ask_limit_on_launch"] = True
            if parsed_args.ask_skip_tags_on_launch:
                template_data["ask_skip_tags_on_launch"] = True
            if parsed_args.ask_tags_on_launch:
                template_data["ask_tags_on_launch"] = True
            if parsed_args.ask_timeout_on_launch:
                template_data["ask_timeout_on_launch"] = True
            if parsed_args.ask_variables_on_launch:
                template_data["ask_variables_on_launch"] = True
            if parsed_args.ask_verbosity_on_launch:
                template_data["ask_verbosity_on_launch"] = True

            # Add webhook fields if enabled
            if parsed_args.enable_webhook:
                template_data["webhook_service"] = parsed_args.webhook_service
                # Add webhook credential if provided
                if parsed_args.webhook_credential:
                    webhook_credential_id = resolve_credential_name(client, parsed_args.webhook_credential, api="controller")
                    template_data["webhook_credential"] = webhook_credential_id

            # Validate and add extra vars JSON as string
            if parsed_args.extra_vars:
                try:
                    # Validate that it's valid JSON by parsing it
                    json.loads(parsed_args.extra_vars)
                    # But send the original string to the API
                    template_data["extra_vars"] = parsed_args.extra_vars
                except json.JSONDecodeError as e:
                    raise AAPClientError(f"Invalid JSON in --extra-vars: {e}")

            # Instance groups will be associated after template creation

            # Create the job template
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/"
            try:
                response = client.post(endpoint, json=template_data)
                if response.status_code == HTTP_CREATED:
                    created_template = response.json()
                    template_id = created_template['id']

                    # Collect association failures to determine if we should rollback
                    association_errors = []

                    # Associate credentials if provided
                    if parsed_args.credentials:
                        for credential in parsed_args.credentials:
                            try:
                                credential_id = resolve_credential_name(client, credential, api="controller")
                                # Associate credential with job template
                                credential_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/credentials/"
                                credential_response = client.post(credential_endpoint, json={"id": credential_id})
                                if credential_response.status_code not in [HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT]:
                                    association_errors.append(f"Failed to associate credential '{credential}' with job template")
                            except Exception as e:
                                association_errors.append(f"Failed to associate credential '{credential}': {e}")

                    # Associate instance groups if provided
                    if parsed_args.instance_groups:
                        for instance_group in parsed_args.instance_groups:
                            try:
                                ig_id = resolve_instance_group_name(client, instance_group, api="controller")
                                # Associate instance group with job template
                                ig_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/instance_groups/"
                                ig_response = client.post(ig_endpoint, json={"id": ig_id})
                                if ig_response.status_code not in [HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT]:
                                    association_errors.append(f"Failed to associate instance group '{instance_group}' with job template")
                            except Exception as e:
                                association_errors.append(f"Failed to associate instance group '{instance_group}': {e}")

                    # If any associations failed, delete the created template and raise error
                    if association_errors:
                        # Delete the created template to clean up
                        try:
                            delete_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/"
                            client.delete(delete_endpoint)
                        except Exception:
                            pass  # Don't fail if cleanup fails

                        # Raise error with all association failures
                        error_message = "Job template creation failed due to association errors:\n" + "\n".join(association_errors)
                        raise AAPClientError(error_message)

                    # Re-fetch the template to get updated associations
                    updated_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/")
                    if updated_response.status_code == HTTP_OK:
                        updated_template = updated_response.json()

                        field_names, field_values = _format_job_template_data(updated_template, use_utc=False, client=client)
                        return field_names, field_values
                    else:
                        # Fallback to original data if re-fetch fails
                        field_names, field_values = _format_job_template_data(created_template, use_utc=False, client=client)
                        return field_names, field_values
                else:
                    raise AAPClientError(f"Failed to create job template: HTTP {response.status_code}")
            except AAPAPIError as api_error:
                if hasattr(api_error, 'response') and api_error.response:
                    try:
                        error_data = api_error.response.json()
                        if isinstance(error_data, dict):
                            # Display API error messages directly
                            error_messages = []
                            for field, messages in error_data.items():
                                if isinstance(messages, list):
                                    for message in messages:
                                        error_messages.append(f"{field}: {message}")
                                elif isinstance(messages, str):
                                    error_messages.append(f"{field}: {messages}")
                                else:
                                    error_messages.append(f"{field}: {messages}")
                            raise AAPClientError(f"API error: {'; '.join(error_messages)}")
                    except (ValueError, KeyError):
                        pass
                raise AAPClientError(f"API error: {api_error}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class JobTemplateSetCommand(AAPShowCommand):
    """Update a job template."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Positional argument for template name/ID
        parser.add_argument(
            'template',
            help='Job template name or ID to update'
        )

        # Optional fields that can be updated
        parser.add_argument(
            '--description',
            help='Job template description'
        )
        parser.add_argument(
            '--job-type',
            choices=['check', 'run'],
            dest='job_type',
            help='Job type'
        )
        parser.add_argument(
            '--inventory',
            help='Inventory name or ID'
        )
        parser.add_argument(
            '--project',
            help='Project name or ID'
        )
        parser.add_argument(
            '--playbook',
            help='Playbook name'
        )
        parser.add_argument(
            '--execution-environment',
            dest='execution_environment',
            help='Execution environment name or ID'
        )
        parser.add_argument(
            '--credential',
            action='append',
            dest='credentials',
            help='Credential name or ID (can be used multiple times)'
        )
        parser.add_argument(
            '--forks',
            type=int,
            help='Number of parallel processes'
        )
        parser.add_argument(
            '--limit',
            help='Host pattern to limit job execution'
        )
        parser.add_argument(
            '--verbosity',
            type=int,
            choices=[0, 1, 2, 3, 4, 5],
            help='Verbosity level'
        )
        parser.add_argument(
            '--job-slices',
            type=int,
            dest='job_slices',
            help='Number of job slices'
        )
        parser.add_argument(
            '--job-timeout',
            type=int,
            dest='job_timeout',
            help='Job timeout in seconds'
        )
        parser.add_argument(
            '--instance-group',
            action='append',
            dest='instance_groups',
            help='Instance group name or ID (can be used multiple times)'
        )
        parser.add_argument(
            '--job-tags',
            dest='job_tags',
            help='Job tags'
        )
        parser.add_argument(
            '--skip-tags',
            dest='skip_tags',
            help='Skip tags'
        )
        parser.add_argument(
            '--extra-vars',
            dest='extra_vars',
            help='Extra variables as JSON'
        )

        # Mutually exclusive boolean arguments for diff mode
        diff_group = parser.add_mutually_exclusive_group()
        diff_group.add_argument(
            '--enable-diff-mode',
            action='store_true',
            dest='enable_diff_mode',
            help='Enable diff mode'
        )
        diff_group.add_argument(
            '--disable-diff-mode',
            action='store_true',
            dest='disable_diff_mode',
            help='Disable diff mode'
        )

        # Mutually exclusive boolean arguments for privileged escalation
        escalation_group = parser.add_mutually_exclusive_group()
        escalation_group.add_argument(
            '--enable-privileged-escalation',
            action='store_true',
            dest='enable_privileged_escalation',
            help='Enable privileged escalation'
        )
        escalation_group.add_argument(
            '--disable-privileged-escalation',
            action='store_true',
            dest='disable_privileged_escalation',
            help='Disable privileged escalation'
        )

        # Mutually exclusive boolean arguments for concurrent jobs
        concurrent_group = parser.add_mutually_exclusive_group()
        concurrent_group.add_argument(
            '--enable-concurrent-jobs',
            action='store_true',
            dest='enable_concurrent_jobs',
            help='Enable concurrent jobs'
        )
        concurrent_group.add_argument(
            '--disable-concurrent-jobs',
            action='store_true',
            dest='disable_concurrent_jobs',
            help='Disable concurrent jobs'
        )

        # Mutually exclusive boolean arguments for fact storage
        fact_storage_group = parser.add_mutually_exclusive_group()
        fact_storage_group.add_argument(
            '--enable-fact-storage',
            action='store_true',
            dest='enable_fact_storage',
            help='Enable fact storage'
        )
        fact_storage_group.add_argument(
            '--disable-fact-storage',
            action='store_true',
            dest='disable_fact_storage',
            help='Disable fact storage'
        )

        # Mutually exclusive boolean arguments for instance group fallback
        fallback_group = parser.add_mutually_exclusive_group()
        fallback_group.add_argument(
            '--enable-instance-group-fallback',
            action='store_true',
            dest='enable_instance_group_fallback',
            help='Enable instance group fallback'
        )
        fallback_group.add_argument(
            '--disable-instance-group-fallback',
            action='store_true',
            dest='disable_instance_group_fallback',
            help='Disable instance group fallback'
        )

        # Add ask-on-launch boolean arguments
        ask_credential_group = parser.add_mutually_exclusive_group()
        ask_credential_group.add_argument(
            '--enable-ask-credential-on-launch',
            action='store_true',
            dest='enable_ask_credential_on_launch',
            help='Enable ask credential on launch'
        )
        ask_credential_group.add_argument(
            '--disable-ask-credential-on-launch',
            action='store_true',
            dest='disable_ask_credential_on_launch',
            help='Disable ask credential on launch'
        )

        ask_diff_mode_group = parser.add_mutually_exclusive_group()
        ask_diff_mode_group.add_argument(
            '--enable-ask-diff-mode-on-launch',
            action='store_true',
            dest='enable_ask_diff_mode_on_launch',
            help='Enable ask diff mode on launch'
        )
        ask_diff_mode_group.add_argument(
            '--disable-ask-diff-mode-on-launch',
            action='store_true',
            dest='disable_ask_diff_mode_on_launch',
            help='Disable ask diff mode on launch'
        )

        ask_execution_environment_group = parser.add_mutually_exclusive_group()
        ask_execution_environment_group.add_argument(
            '--enable-ask-execution-environment-on-launch',
            action='store_true',
            dest='enable_ask_execution_environment_on_launch',
            help='Enable ask execution environment on launch'
        )
        ask_execution_environment_group.add_argument(
            '--disable-ask-execution-environment-on-launch',
            action='store_true',
            dest='disable_ask_execution_environment_on_launch',
            help='Disable ask execution environment on launch'
        )

        ask_forks_group = parser.add_mutually_exclusive_group()
        ask_forks_group.add_argument(
            '--enable-ask-forks-on-launch',
            action='store_true',
            dest='enable_ask_forks_on_launch',
            help='Enable ask forks on launch'
        )
        ask_forks_group.add_argument(
            '--disable-ask-forks-on-launch',
            action='store_true',
            dest='disable_ask_forks_on_launch',
            help='Disable ask forks on launch'
        )

        ask_instance_groups_group = parser.add_mutually_exclusive_group()
        ask_instance_groups_group.add_argument(
            '--enable-ask-instance-groups-on-launch',
            action='store_true',
            dest='enable_ask_instance_groups_on_launch',
            help='Enable ask instance groups on launch'
        )
        ask_instance_groups_group.add_argument(
            '--disable-ask-instance-groups-on-launch',
            action='store_true',
            dest='disable_ask_instance_groups_on_launch',
            help='Disable ask instance groups on launch'
        )

        ask_inventory_group = parser.add_mutually_exclusive_group()
        ask_inventory_group.add_argument(
            '--enable-ask-inventory-on-launch',
            action='store_true',
            dest='enable_ask_inventory_on_launch',
            help='Enable ask inventory on launch'
        )
        ask_inventory_group.add_argument(
            '--disable-ask-inventory-on-launch',
            action='store_true',
            dest='disable_ask_inventory_on_launch',
            help='Disable ask inventory on launch'
        )

        ask_job_slice_count_group = parser.add_mutually_exclusive_group()
        ask_job_slice_count_group.add_argument(
            '--enable-ask-job-slice-count-on-launch',
            action='store_true',
            dest='enable_ask_job_slice_count_on_launch',
            help='Enable ask job slice count on launch'
        )
        ask_job_slice_count_group.add_argument(
            '--disable-ask-job-slice-count-on-launch',
            action='store_true',
            dest='disable_ask_job_slice_count_on_launch',
            help='Disable ask job slice count on launch'
        )

        ask_job_type_group = parser.add_mutually_exclusive_group()
        ask_job_type_group.add_argument(
            '--enable-ask-job-type-on-launch',
            action='store_true',
            dest='enable_ask_job_type_on_launch',
            help='Enable ask job type on launch'
        )
        ask_job_type_group.add_argument(
            '--disable-ask-job-type-on-launch',
            action='store_true',
            dest='disable_ask_job_type_on_launch',
            help='Disable ask job type on launch'
        )

        ask_labels_group = parser.add_mutually_exclusive_group()
        ask_labels_group.add_argument(
            '--enable-ask-labels-on-launch',
            action='store_true',
            dest='enable_ask_labels_on_launch',
            help='Enable ask labels on launch'
        )
        ask_labels_group.add_argument(
            '--disable-ask-labels-on-launch',
            action='store_true',
            dest='disable_ask_labels_on_launch',
            help='Disable ask labels on launch'
        )

        ask_limit_group = parser.add_mutually_exclusive_group()
        ask_limit_group.add_argument(
            '--enable-ask-limit-on-launch',
            action='store_true',
            dest='enable_ask_limit_on_launch',
            help='Enable ask limit on launch'
        )
        ask_limit_group.add_argument(
            '--disable-ask-limit-on-launch',
            action='store_true',
            dest='disable_ask_limit_on_launch',
            help='Disable ask limit on launch'
        )

        ask_skip_tags_group = parser.add_mutually_exclusive_group()
        ask_skip_tags_group.add_argument(
            '--enable-ask-skip-tags-on-launch',
            action='store_true',
            dest='enable_ask_skip_tags_on_launch',
            help='Enable ask skip tags on launch'
        )
        ask_skip_tags_group.add_argument(
            '--disable-ask-skip-tags-on-launch',
            action='store_true',
            dest='disable_ask_skip_tags_on_launch',
            help='Disable ask skip tags on launch'
        )

        ask_tags_group = parser.add_mutually_exclusive_group()
        ask_tags_group.add_argument(
            '--enable-ask-tags-on-launch',
            action='store_true',
            dest='enable_ask_tags_on_launch',
            help='Enable ask tags on launch'
        )
        ask_tags_group.add_argument(
            '--disable-ask-tags-on-launch',
            action='store_true',
            dest='disable_ask_tags_on_launch',
            help='Disable ask tags on launch'
        )

        ask_timeout_group = parser.add_mutually_exclusive_group()
        ask_timeout_group.add_argument(
            '--enable-ask-timeout-on-launch',
            action='store_true',
            dest='enable_ask_timeout_on_launch',
            help='Enable ask timeout on launch'
        )
        ask_timeout_group.add_argument(
            '--disable-ask-timeout-on-launch',
            action='store_true',
            dest='disable_ask_timeout_on_launch',
            help='Disable ask timeout on launch'
        )

        ask_variables_group = parser.add_mutually_exclusive_group()
        ask_variables_group.add_argument(
            '--enable-ask-variables-on-launch',
            action='store_true',
            dest='enable_ask_variables_on_launch',
            help='Enable ask variables on launch'
        )
        ask_variables_group.add_argument(
            '--disable-ask-variables-on-launch',
            action='store_true',
            dest='disable_ask_variables_on_launch',
            help='Disable ask variables on launch'
        )

        ask_verbosity_group = parser.add_mutually_exclusive_group()
        ask_verbosity_group.add_argument(
            '--enable-ask-verbosity-on-launch',
            action='store_true',
            dest='enable_ask_verbosity_on_launch',
            help='Enable ask verbosity on launch'
        )
        ask_verbosity_group.add_argument(
            '--disable-ask-verbosity-on-launch',
            action='store_true',
            dest='disable_ask_verbosity_on_launch',
            help='Disable ask verbosity on launch'
        )

        # Webhook arguments
        webhook_group = parser.add_mutually_exclusive_group()
        webhook_group.add_argument(
            '--enable-webhook',
            action='store_true',
            dest='enable_webhook',
            help='Enable webhook functionality'
        )
        webhook_group.add_argument(
            '--disable-webhook',
            action='store_true',
            dest='disable_webhook',
            help='Disable webhook functionality'
        )

        parser.add_argument(
            '--webhook-service',
            choices=['gitlab', 'github', 'bitbucket_dc'],
            dest='webhook_service',
            help='Webhook service type'
        )
        parser.add_argument(
            '--webhook-credential',
            dest='webhook_credential',
            help='Credential to use for webhook authentication'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the job template update command."""
        client = self.controller_client

        try:
            # Resolve template name to ID
            template_id = resolve_job_template_name(client, parsed_args.template, api="controller")

            # Build update data only for provided arguments
            update_data = {}

            # Handle simple field updates
            if parsed_args.description is not None:
                update_data["description"] = parsed_args.description
            if parsed_args.job_type:
                update_data["job_type"] = parsed_args.job_type
            if parsed_args.playbook:
                update_data["playbook"] = parsed_args.playbook

            # Handle resource ID resolution
            if parsed_args.inventory:
                inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")
                update_data["inventory"] = inventory_id
            if parsed_args.project:
                project_id = resolve_project_name(client, parsed_args.project, api="controller")
                update_data["project"] = project_id
            if parsed_args.execution_environment:
                ee_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")
                update_data["execution_environment"] = ee_id

            # Handle numeric fields
            if parsed_args.forks is not None:
                update_data["forks"] = parsed_args.forks
            if parsed_args.verbosity is not None:
                update_data["verbosity"] = parsed_args.verbosity
            if parsed_args.job_slices is not None:
                update_data["job_slice_count"] = parsed_args.job_slices
            if parsed_args.job_timeout is not None:
                update_data["timeout"] = parsed_args.job_timeout

            # Handle string fields
            if parsed_args.limit is not None:
                update_data["limit"] = parsed_args.limit
            if parsed_args.job_tags is not None:
                update_data["job_tags"] = parsed_args.job_tags
            if parsed_args.skip_tags is not None:
                update_data["skip_tags"] = parsed_args.skip_tags

            # Handle boolean fields with enable/disable options
            if parsed_args.enable_diff_mode:
                update_data["diff_mode"] = True
            elif parsed_args.disable_diff_mode:
                update_data["diff_mode"] = False

            if parsed_args.enable_privileged_escalation:
                update_data["become_enabled"] = True
            elif parsed_args.disable_privileged_escalation:
                update_data["become_enabled"] = False

            if parsed_args.enable_concurrent_jobs:
                update_data["allow_simultaneous"] = True
            elif parsed_args.disable_concurrent_jobs:
                update_data["allow_simultaneous"] = False

            if parsed_args.enable_fact_storage:
                update_data["use_fact_cache"] = True
            elif parsed_args.disable_fact_storage:
                update_data["use_fact_cache"] = False

            if parsed_args.enable_instance_group_fallback:
                update_data["prevent_instance_group_fallback"] = False
            elif parsed_args.disable_instance_group_fallback:
                update_data["prevent_instance_group_fallback"] = True

            # Handle ask-on-launch fields
            if parsed_args.enable_ask_credential_on_launch:
                update_data["ask_credential_on_launch"] = True
            elif parsed_args.disable_ask_credential_on_launch:
                update_data["ask_credential_on_launch"] = False

            if parsed_args.enable_ask_diff_mode_on_launch:
                update_data["ask_diff_mode_on_launch"] = True
            elif parsed_args.disable_ask_diff_mode_on_launch:
                update_data["ask_diff_mode_on_launch"] = False

            if parsed_args.enable_ask_execution_environment_on_launch:
                update_data["ask_execution_environment_on_launch"] = True
            elif parsed_args.disable_ask_execution_environment_on_launch:
                update_data["ask_execution_environment_on_launch"] = False

            if parsed_args.enable_ask_forks_on_launch:
                update_data["ask_forks_on_launch"] = True
            elif parsed_args.disable_ask_forks_on_launch:
                update_data["ask_forks_on_launch"] = False

            if parsed_args.enable_ask_instance_groups_on_launch:
                update_data["ask_instance_groups_on_launch"] = True
            elif parsed_args.disable_ask_instance_groups_on_launch:
                update_data["ask_instance_groups_on_launch"] = False

            if parsed_args.enable_ask_inventory_on_launch:
                update_data["ask_inventory_on_launch"] = True
            elif parsed_args.disable_ask_inventory_on_launch:
                update_data["ask_inventory_on_launch"] = False

            if parsed_args.enable_ask_job_slice_count_on_launch:
                update_data["ask_job_slice_count_on_launch"] = True
            elif parsed_args.disable_ask_job_slice_count_on_launch:
                update_data["ask_job_slice_count_on_launch"] = False

            if parsed_args.enable_ask_job_type_on_launch:
                update_data["ask_job_type_on_launch"] = True
            elif parsed_args.disable_ask_job_type_on_launch:
                update_data["ask_job_type_on_launch"] = False

            if parsed_args.enable_ask_labels_on_launch:
                update_data["ask_labels_on_launch"] = True
            elif parsed_args.disable_ask_labels_on_launch:
                update_data["ask_labels_on_launch"] = False

            if parsed_args.enable_ask_limit_on_launch:
                update_data["ask_limit_on_launch"] = True
            elif parsed_args.disable_ask_limit_on_launch:
                update_data["ask_limit_on_launch"] = False

            if parsed_args.enable_ask_skip_tags_on_launch:
                update_data["ask_skip_tags_on_launch"] = True
            elif parsed_args.disable_ask_skip_tags_on_launch:
                update_data["ask_skip_tags_on_launch"] = False

            if parsed_args.enable_ask_tags_on_launch:
                update_data["ask_tags_on_launch"] = True
            elif parsed_args.disable_ask_tags_on_launch:
                update_data["ask_tags_on_launch"] = False

            if parsed_args.enable_ask_timeout_on_launch:
                update_data["ask_timeout_on_launch"] = True
            elif parsed_args.disable_ask_timeout_on_launch:
                update_data["ask_timeout_on_launch"] = False

            if parsed_args.enable_ask_variables_on_launch:
                update_data["ask_variables_on_launch"] = True
            elif parsed_args.disable_ask_variables_on_launch:
                update_data["ask_variables_on_launch"] = False

            if parsed_args.enable_ask_verbosity_on_launch:
                update_data["ask_verbosity_on_launch"] = True
            elif parsed_args.disable_ask_verbosity_on_launch:
                update_data["ask_verbosity_on_launch"] = False

            # Handle webhook fields
            if parsed_args.enable_webhook:
                if not parsed_args.webhook_service:
                    raise AAPClientError("--webhook-service is required when --enable-webhook is used")
                update_data["webhook_service"] = parsed_args.webhook_service
                if parsed_args.webhook_credential:
                    webhook_credential_id = resolve_credential_name(client, parsed_args.webhook_credential, api="controller")
                    update_data["webhook_credential"] = webhook_credential_id
            elif parsed_args.disable_webhook:
                update_data["webhook_service"] = ""
                update_data["webhook_credential"] = None
            else:
                # Handle webhook fields when not explicitly enabling/disabling
                if parsed_args.webhook_service:
                    update_data["webhook_service"] = parsed_args.webhook_service
                if parsed_args.webhook_credential:
                    webhook_credential_id = resolve_credential_name(client, parsed_args.webhook_credential, api="controller")
                    update_data["webhook_credential"] = webhook_credential_id

            # Handle extra vars
            if parsed_args.extra_vars is not None:
                try:
                    # Validate that it's valid JSON by parsing it
                    json.loads(parsed_args.extra_vars)
                    # But send the original string to the API
                    update_data["extra_vars"] = parsed_args.extra_vars
                except json.JSONDecodeError as e:
                    raise AAPClientError(f"Invalid JSON in --extra-vars: {e}")

            # Update the job template
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/"
            try:
                response = client.patch(endpoint, json=update_data)
                if response.status_code == HTTP_OK:
                    updated_template = response.json()

                    # Handle credentials and instance groups associations if provided
                    association_errors = []

                    # Handle credentials
                    if parsed_args.credentials:
                        # Clear existing credentials first
                        try:
                            clear_response = client.post(f"{endpoint}credentials/", json=[])
                            if clear_response.status_code not in [HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT]:
                                association_errors.append(f"Failed to clear existing credentials: HTTP {clear_response.status_code}")
                        except Exception as e:
                            association_errors.append(f"Error clearing credentials: {str(e)}")

                        # Add new credentials
                        for credential in parsed_args.credentials:
                            try:
                                credential_id = resolve_credential_name(client, credential, api="controller")
                                cred_response = client.post(f"{endpoint}credentials/", json={"id": credential_id})
                                if cred_response.status_code not in [HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT]:
                                    association_errors.append(f"Failed to associate credential '{credential}': HTTP {cred_response.status_code}")
                            except Exception as e:
                                association_errors.append(f"Error associating credential '{credential}': {str(e)}")

                    # Handle instance groups
                    if parsed_args.instance_groups:
                        # Clear existing instance groups first
                        try:
                            clear_response = client.post(f"{endpoint}instance_groups/", json=[])
                            if clear_response.status_code not in [HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT]:
                                association_errors.append(f"Failed to clear existing instance groups: HTTP {clear_response.status_code}")
                        except Exception as e:
                            association_errors.append(f"Error clearing instance groups: {str(e)}")

                        # Add new instance groups
                        for instance_group in parsed_args.instance_groups:
                            try:
                                ig_id = resolve_instance_group_name(client, instance_group, api="controller")
                                ig_response = client.post(f"{endpoint}instance_groups/", json={"id": ig_id})
                                if ig_response.status_code not in [HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT]:
                                    association_errors.append(f"Failed to associate instance group '{instance_group}': HTTP {ig_response.status_code}")
                            except Exception as e:
                                association_errors.append(f"Error associating instance group '{instance_group}': {str(e)}")

                    # Display warnings for association errors but don't fail
                    if association_errors:
                        for error in association_errors:
                            print(f"Warning: {error}", file=sys.stderr)

                    # Re-fetch the template to get updated associations
                    updated_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/")
                    if updated_response.status_code == HTTP_OK:
                        updated_template = updated_response.json()
                        field_names, field_values = _format_job_template_data(updated_template, use_utc=False, client=client)
                        return field_names, field_values
                    else:
                        # Fallback to original data if re-fetch fails
                        field_names, field_values = _format_job_template_data(updated_template, use_utc=False, client=client)
                        return field_names, field_values
                else:
                    raise AAPClientError(f"Failed to update job template: HTTP {response.status_code}")
            except AAPAPIError as api_error:
                if hasattr(api_error, 'response') and api_error.response:
                    try:
                        error_data = api_error.response.json()
                        if isinstance(error_data, dict):
                            error_messages = []
                            for field, messages in error_data.items():
                                if isinstance(messages, list):
                                    for message in messages:
                                        error_messages.append(f"{field}: {message}")
                                else:
                                    error_messages.append(f"{field}: {messages}")
                            raise AAPClientError("API error: " + "; ".join(error_messages))
                    except (ValueError, KeyError):
                        pass
                raise AAPClientError(f"API error: {api_error}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
