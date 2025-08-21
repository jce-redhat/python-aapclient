"""
Job template survey commands for AAP CLI using Click and Rich.

This module provides enhanced versions of job template survey management commands
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
    format_datetime,
    format_variables_display
)
from aapclient.decorators import (
    list_command,
    show_command,
    create_command,
    update_command,
    delete_command,
    get_client_from_context,
    get_console_from_context,
    validate_resource_identifier
)
from aapclient.output import (
    create_table,
    show_details_table,
    show_raw_json,
    show_raw_yaml,
    show_success_message,
    show_error_message,
    format_datetime_rich
)


@click.group()
def survey():
    """Manage job template surveys."""
    pass


@survey.command('show')
@click.argument('template_name', metavar='<template>', required=False, callback=validate_resource_identifier)
@click.option('--id', type=int, help='Job template ID (overrides template name)')
@show_command
def show_survey(console, output_format, utc, template_name, id):
    """Show job template survey specification."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve template ID
        if id:
            template_id = id
        else:
            template_id = resolve_job_template_name(client, template_name)

        # Get survey specification
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/survey_spec/"
        response = client.get(endpoint)

        if response.status_code != HTTP_OK:
            if response.status_code == 404:
                show_error_message(console, "No survey found for this job template")
            else:
                show_error_message(console, f"Failed to fetch survey: HTTP {response.status_code}")
            click.get_current_context().exit(1)

        survey_data = response.json()

        # Check if survey data contains questions
        if not survey_data or not survey_data.get('spec'):
            show_error_message(console, "No survey specification found for this job template")
            click.get_current_context().exit(1)

        # Extract survey questions
        survey_spec = survey_data.get('spec', [])

        if not survey_spec:
            show_error_message(console, "No survey questions found for this job template")
            click.get_current_context().exit(1)

        if output_format == 'json':
            show_raw_json(survey_data)
        elif output_format == 'yaml':
            show_raw_yaml(survey_data)
        else:
            # Format survey data for table display
            columns = ['Index', 'Question', 'Type', 'Required', 'Variable', 'Default', 'Min Length', 'Max Length', 'Choices']
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

                rows.append([
                    str(index),
                    question_text,
                    question_type,
                    required,
                    question_var,
                    str(default_value),
                    str(question_min),
                    str(question_max),
                    str(choices)
                ])

            table = create_table(columns, rows)
            console.print(table)

    except SystemExit:
        # Re-raise SystemExit to allow clean exit from click.get_current_context().exit()
        raise
    except Exception as e:
        show_error_message(console, f"Failed to show survey: {e}")
        click.get_current_context().exit(1)


@survey.command('create')
@click.argument('template_name', metavar='<template>')
@click.option('--id', type=int, help='Job template ID (overrides template name)')
@click.option('--question', required=True, help='Question text to display to the user')
@click.option('--type', 'question_type', required=True,
              type=click.Choice(['text', 'password', 'integer', 'float', 'multiplechoice', 'multiselect']),
              help='Question type')
@click.option('--variable', required=True, help='Variable name to store the answer')
@click.option('--is-required', is_flag=True, help='Make this question required')
@click.option('--default-value', help='Default value for the question')
@click.option('--min-length', type=int, help='Minimum length for text inputs')
@click.option('--max-length', type=int, help='Maximum length for text inputs')
@click.option('--choices', help='Comma-separated list of choices for multiplechoice/multiselect questions')
@click.option('--index', type=int, help='Position to insert the question (default: append to end)')
@click.option('--name', help='Survey name (will be set after question is added)')
@click.option('--description', help='Survey description (will be set after question is added)')
@click.option('--enabled', is_flag=True, help='Enable the survey on the job template after creation')
@create_command
def create_survey(console, template_name, id, question, question_type, variable, is_required,
                 default_value, min_length, max_length, choices, index, name, description, enabled):
    """Create a survey by adding the first question."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve template ID
        if id:
            job_template_id = id
        elif template_name:
            job_template_id = resolve_job_template_name(client, template_name)
        else:
            show_error_message(console, "Job template identifier is required")
            click.get_current_context().exit(1)

        # Check if survey already exists
        survey_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/"
        response = client.get(survey_endpoint)

        if response.status_code == HTTP_OK:
            existing_survey = response.json()
            if existing_survey.get('spec'):
                show_error_message(console, "Survey already exists for this job template. Use 'survey question add' to add more questions.")
                import sys
                sys.exit(1)

        # Build question data
        question_data = {
            'question_name': question,
            'type': question_type,
            'variable': variable,
            'required': is_required
        }

        if default_value is not None:
            # Convert default value to appropriate type
            if question_type in ['integer']:
                try:
                    question_data['default'] = int(default_value)
                except ValueError:
                    show_error_message(console, f"Invalid integer default value: {default_value}")
                    click.get_current_context().exit(1)
            elif question_type in ['float']:
                try:
                    question_data['default'] = float(default_value)
                except ValueError:
                    show_error_message(console, f"Invalid float default value: {default_value}")
                    click.get_current_context().exit(1)
            else:
                question_data['default'] = default_value

        if min_length is not None:
            question_data['min'] = min_length

        if max_length is not None:
            question_data['max'] = max_length

        if choices and question_type in ['multiplechoice', 'multiselect']:
            question_data['choices'] = [choice.strip() for choice in choices.split(',')]

        # Create new survey with the first question
        survey_data = {
            'name': name if name else '',
            'description': description if description else '',
            'spec': [question_data]
        }

        # Post the survey
        response = client.post(survey_endpoint, json=survey_data)

        if response.status_code == HTTP_OK:
            # Enable survey on the job template if requested
            if enabled:
                template_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
                template_response = client.patch(template_endpoint, json={"survey_enabled": True})
                if template_response.status_code != HTTP_OK:
                    show_error_message(console, f"Survey created but failed to enable it: HTTP {template_response.status_code}")
                    import sys
                    sys.exit(1)
                show_success_message(console, f"Survey created with 1 question and enabled for job template {job_template_id}")
            else:
                show_success_message(console, f"Survey created with 1 question for job template {job_template_id}")
        else:
            show_error_message(console, f"Failed to create survey: HTTP {response.status_code}")
            import sys
            sys.exit(1)

    except SystemExit:
        # Re-raise SystemExit to allow clean exit from click.get_current_context().exit()
        raise
    except Exception as e:
        show_error_message(console, f"Failed to create survey: {e}")
        click.get_current_context().exit(1)


@survey.command('delete')
@click.argument('template_name', metavar='<template>')
@click.option('--id', type=int, help='Job template ID (overrides template name)')
@delete_command()
def delete_survey(console, template_name, id):
    """Delete job template survey specification."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve template ID
        if id:
            job_template_id = id
        elif template_name:
            job_template_id = resolve_job_template_name(client, template_name)
        else:
            show_error_message(console, "Job template identifier is required")
            click.get_current_context().exit(1)

        # Delete the survey specification
        survey_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/"
        response = client.delete(survey_endpoint)

        if response.status_code in [HTTP_NO_CONTENT, HTTP_OK]:
            show_success_message(console, f"Survey deleted for job template {job_template_id}")
        else:
            show_error_message(console, f"Failed to delete survey: HTTP {response.status_code}")
            click.get_current_context().exit(1)

    except SystemExit:
        # Re-raise SystemExit to allow clean exit from click.get_current_context().exit()
        raise
    except Exception as e:
        show_error_message(console, f"Failed to delete survey: {e}")
        click.get_current_context().exit(1)


@survey.command('set')
@click.argument('template_name', metavar='<template>')
@click.option('--id', type=int, help='Job template ID (overrides template name)')
@click.option('--name', help='Survey name')
@click.option('--description', help='Survey description')
@optgroup.group('Survey State', cls=MutuallyExclusiveOptionGroup,
                help='Control survey enabled/disabled state')
@optgroup.option('--enabled', is_flag=True, help='Enable the survey on the job template')
@optgroup.option('--disabled', is_flag=True, help='Disable the survey on the job template')
@update_command
def set_survey(console, template_name, id, name, description, enabled, disabled):
    """Update survey metadata (name and description)."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve template ID
        if id:
            job_template_id = id
        elif template_name:
            job_template_id = resolve_job_template_name(client, template_name)
        else:
            show_error_message(console, "Job template identifier is required")
            click.get_current_context().exit(1)

        # Note: Mutually exclusive validation now handled by click-option-group

        # Check if any fields need to be updated
        if name is None and description is None and not enabled and not disabled:
            show_error_message(console, "At least one field must be specified to update")
            import sys
            sys.exit(1)

        # Get current survey specification
        survey_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/"
        response = client.get(survey_endpoint)

        if response.status_code != HTTP_OK:
            show_error_message(console, "No survey found for this job template")
            click.get_current_context().exit(1)

        current_survey = response.json()

        # Update the specified fields
        if name is not None:
            current_survey['name'] = name
        if description is not None:
            current_survey['description'] = description

        # Update the survey metadata if needed
        if name is not None or description is not None:
            response = client.post(survey_endpoint, json=current_survey)
            if response.status_code != HTTP_OK:
                show_error_message(console, f"Failed to update survey metadata: HTTP {response.status_code}")
                import sys
                sys.exit(1)

        # Update job template survey enabled status if requested
        if enabled or disabled:
            template_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/"
            survey_enabled = enabled  # True for --enabled, False for --disabled
            template_response = client.patch(template_endpoint, json={"survey_enabled": survey_enabled})
            if template_response.status_code != HTTP_OK:
                show_error_message(console, f"Failed to update survey enabled status: HTTP {template_response.status_code}")
                import sys
                sys.exit(1)

        show_success_message(console, f"Survey updated for job template {job_template_id}")

    except SystemExit:
        # Re-raise SystemExit to allow clean exit from click.get_current_context().exit()
        raise
    except Exception as e:
        show_error_message(console, f"Failed to update survey: {e}")
        click.get_current_context().exit(1)


@survey.group('question')
def survey_question():
    """Manage survey questions."""
    pass


@survey_question.command('add')
@click.argument('template_name', metavar='<template>')
@click.option('--id', type=int, help='Job template ID (overrides template name)')
@click.option('--question', required=True, help='Question text to display to the user')
@click.option('--type', 'question_type', required=True,
              type=click.Choice(['text', 'password', 'integer', 'float', 'multiplechoice', 'multiselect']),
              help='Question type')
@click.option('--variable', required=True, help='Variable name to store the answer')
@click.option('--is-required', is_flag=True, help='Make this question required')
@click.option('--default-value', help='Default value for the question')
@click.option('--min-length', type=int, help='Minimum length for text inputs')
@click.option('--max-length', type=int, help='Maximum length for text inputs')
@click.option('--choices', help='Comma-separated list of choices for multiplechoice/multiselect questions')
@click.option('--index', type=int, help='Position to insert the question (default: append to end)')
@create_command
def add_question(console, template_name, id, question, question_type, variable, is_required,
                default_value, min_length, max_length, choices, index):
    """Add a new question to a job template survey."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve template ID
        if id:
            template_id = id
        elif template_name:
            template_id = resolve_job_template_name(client, template_name)
        else:
            show_error_message(console, "Job template identifier is required")
            click.get_current_context().exit(1)

        # Get current survey specification
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{template_id}/survey_spec/"
        response = client.get(endpoint)

        if response.status_code == HTTP_OK:
            current_survey = response.json()
        else:
            # Create a new survey if one doesn't exist
            current_survey = {
                'name': '',
                'description': '',
                'spec': []
            }

        # Build new question data
        question_data = {
            'question_name': question,
            'type': question_type,
            'variable': variable,
            'required': is_required
        }

        if default_value is not None:
            # Convert default value to appropriate type
            if question_type in ['integer']:
                try:
                    question_data['default'] = int(default_value)
                except ValueError:
                    show_error_message(console, f"Invalid integer default value: {default_value}")
                    click.get_current_context().exit(1)
            elif question_type in ['float']:
                try:
                    question_data['default'] = float(default_value)
                except ValueError:
                    show_error_message(console, f"Invalid float default value: {default_value}")
                    click.get_current_context().exit(1)
            else:
                question_data['default'] = default_value

        if min_length is not None:
            question_data['min'] = min_length

        if max_length is not None:
            question_data['max'] = max_length

        if choices and question_type in ['multiplechoice', 'multiselect']:
            question_data['choices'] = [choice.strip() for choice in choices.split(',')]

        # Add question to survey spec
        survey_spec = current_survey.get('spec', [])

        if index is not None:
            # Insert at specific position
            survey_spec.insert(index - 1, question_data)  # Convert to 0-based index
        else:
            # Append to end
            survey_spec.append(question_data)

        current_survey['spec'] = survey_spec

        # Post the updated survey
        response = client.post(endpoint, json=current_survey)

        if response.status_code == HTTP_OK:
            question_count = len(current_survey['spec'])
            show_success_message(console, f"Question added to survey. Survey now has {question_count} question(s)")
        else:
            show_error_message(console, f"Failed to add question: HTTP {response.status_code}")
            click.get_current_context().exit(1)

    except SystemExit:
        # Re-raise SystemExit to allow clean exit from click.get_current_context().exit()
        raise
    except Exception as e:
        show_error_message(console, f"Failed to add question: {e}")
        click.get_current_context().exit(1)


@survey_question.command('delete')
@click.argument('template_name', metavar='<template>')
@click.argument('question_index', type=int, metavar='<index>')
@click.option('--id', type=int, help='Job template ID (overrides template name)')
@delete_command()
def delete_question(console, template_name, question_index, id):
    """Delete a question from a job template survey by index."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    try:
        # Resolve template ID
        if id:
            job_template_id = id
        elif template_name:
            job_template_id = resolve_job_template_name(client, template_name)
        else:
            show_error_message(console, "Job template identifier is required")
            click.get_current_context().exit(1)

        # Fetch current survey
        endpoint = f'{CONTROLLER_API_VERSION_ENDPOINT}job_templates/{job_template_id}/survey_spec/'
        response = client.get(endpoint)

        if response.status_code != HTTP_OK:
            show_error_message(console, "No survey found for this job template")
            click.get_current_context().exit(1)

        current_survey = response.json()
        survey_spec = current_survey.get('spec', [])

        if not survey_spec:
            show_error_message(console, "No questions found in survey")
            click.get_current_context().exit(1)

        # Validate question index
        if question_index < 1 or question_index > len(survey_spec):
            show_error_message(console, f"Invalid question index. Must be between 1 and {len(survey_spec)}")
            click.get_current_context().exit(1)

        # Remove the question (convert to 0-based index)
        removed_question = survey_spec.pop(question_index - 1)
        current_survey['spec'] = survey_spec

        # If no questions remain, delete the entire survey
        if not survey_spec:
            response = client.delete(endpoint)
            if response.status_code in [HTTP_NO_CONTENT, HTTP_OK]:
                show_success_message(console, "Last question removed. Survey deleted.")
            else:
                show_error_message(console, f"Failed to delete survey: HTTP {response.status_code}")
                click.get_current_context().exit(1)
        else:
            # Update the survey with remaining questions
            response = client.post(endpoint, json=current_survey)
            if response.status_code == HTTP_OK:
                show_success_message(console, f"Question {question_index} removed. Survey now has {len(survey_spec)} question(s)")
            else:
                show_error_message(console, f"Failed to update survey: HTTP {response.status_code}")
                click.get_current_context().exit(1)

    except SystemExit:
        # Re-raise SystemExit to allow clean exit from click.get_current_context().exit()
        raise
    except Exception as e:
        show_error_message(console, f"Failed to delete question: {e}")
        click.get_current_context().exit(1)


# Registration function
def register_survey_commands(template_group: click.Group) -> None:
    """Register survey commands with the template group."""
    template_group.add_command(survey)
