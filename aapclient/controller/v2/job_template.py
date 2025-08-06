"""Job template commands."""
import json
import yaml
from aapclient.common.basecommands import AAPListCommand, AAPShowCommand, AAPCommand
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import (
    format_datetime,
    resolve_job_template_name,
    format_variables_display,
    format_variables_yaml_display
)


def _format_job_template_data(template_data, use_utc=False):
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

    last_job_run = template_data.get('last_job_run', 'Never')
    if last_job_run and last_job_run != 'Never':
        last_job_run = format_datetime(last_job_run, use_utc)

    # Determine execution environment
    execution_environment = 'Default'
    if template_data.get('execution_environment'):
        if ee_info:
            execution_environment = ee_info.get('name', f"ID {template_data.get('execution_environment')}")
        else:
            execution_environment = f"ID {template_data.get('execution_environment')}"

    # Determine last job status
    last_job_status = 'Never'
    if last_job_info:
        last_job_status = f"{last_job_info.get('status', 'Unknown')} (ID: {last_job_info.get('id', 'Unknown')})"

    # Determine credentials
    credentials_list = []
    credentials = summary_fields.get('credentials', [])
    for cred in credentials:
        if isinstance(cred, dict):
            cred_name = cred.get('name', f"ID {cred.get('id', 'Unknown')}")
            credentials_list.append(cred_name)
    credentials_display = ', '.join(credentials_list) if credentials_list else 'None'

    # Determine labels
    labels_list = []
    labels = summary_fields.get('labels', {})
    if isinstance(labels, dict) and 'results' in labels:
        for label in labels['results']:
            if isinstance(label, dict):
                label_name = label.get('name', f"ID {label.get('id', 'Unknown')}")
                labels_list.append(label_name)
    labels_display = ', '.join(labels_list) if labels_list else 'None'

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

    # Build field data for display
    field_data = {
        'ID': template_data.get('id', ''),
        'Name': template_data.get('name', ''),
        'Description': template_data.get('description', ''),
        'Job Type': template_data.get('job_type', ''),
        'Organization': org_info.get('name', 'Unknown'),
        'Project': project_info.get('name', f"ID {template_data.get('project', 'Unknown')}"),
        'Inventory': inventory_info.get('name', f"ID {template_data.get('inventory', 'Unknown')}"),
        'Playbook': template_data.get('playbook', ''),
        'Execution Environment': execution_environment,
        'Credentials': credentials_display,
        'Labels': labels_display,
        'Forks': template_data.get('forks', 0),
        'Verbosity': template_data.get('verbosity', 0),
        'Job Timeout': template_data.get('timeout', 0),
        'Job Tags': template_data.get('job_tags', ''),
        'Skip Tags': template_data.get('skip_tags', ''),
        'Limit': template_data.get('limit', ''),
        'Become Enabled': 'Yes' if template_data.get('become_enabled', False) else 'No',
        'Diff Mode': 'Yes' if template_data.get('diff_mode', False) else 'No',
        'Force Handlers': 'Yes' if template_data.get('force_handlers', False) else 'No',
        'Allow Simultaneous': 'Yes' if template_data.get('allow_simultaneous', False) else 'No',
        'Survey Attached': survey_status,
        'Use Fact Cache': 'Yes' if template_data.get('use_fact_cache', False) else 'No',
        'Extra Variables': extra_vars_display,
        'Last Job Run': last_job_run,
        'Last Job Status': last_job_status,
        'Created': created,
        'Modified': modified,
        'Created By': created_by.get('username', 'Unknown'),
        'Modified By': modified_by.get('username', 'Unknown')
    }

    # Add conditional fields only if they have meaningful values

    # Job Slice Count - only if > 1
    job_slice_count = template_data.get('job_slice_count', 1)
    if job_slice_count and job_slice_count > 1:
        field_data['Job Slice Count'] = job_slice_count

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
                return _format_job_template_data(template_data, parsed_args.utc)
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
