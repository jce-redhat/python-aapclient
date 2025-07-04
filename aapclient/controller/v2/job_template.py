# Copyright (c) 2025 Chris Edillon
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AAP Controller v2 Job Template action implementations"""

import logging
import json

from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.utils import CommandError, get_dict_properties, format_name, format_datetime


LOG = logging.getLogger(__name__)


class ListJobTemplate(Lister):
    """List job templates"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            type=int,
            help='Filter by organization ID',
        )
        parser.add_argument(
            '--project',
            metavar='<project>',
            type=int,
            help='Filter by project ID',
        )
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of results (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        params = {}
        if parsed_args.organization:
            params['organization'] = parsed_args.organization
        if parsed_args.project:
            params['project'] = parsed_args.project

        # Set consistent default limit of 20 (same as job list)
        if parsed_args.limit:
            params['page_size'] = parsed_args.limit
        else:
            params['page_size'] = 20

        # Sort by ID for consistency with other list commands
        params['order_by'] = 'id'

        data = client.list_job_templates(**params)

        # Process the data to extract organization, labels, and format data
        for template in data['results']:
            # Extract organization name from summary_fields
            if 'summary_fields' in template and 'organization' in template['summary_fields']:
                template['organization_name'] = template['summary_fields']['organization']['name']
            else:
                template['organization_name'] = ''

            # Extract labels from job_tags
            labels = ''
            if template.get('job_tags'):
                labels = template.get('job_tags', '')
            template['labels'] = labels

            # Format last job run time
            template['last_job_run_formatted'] = format_datetime(template.get('last_job_run'))

        if parsed_args.long:
            columns = ('ID', 'Name', 'Type', 'Labels', 'Organization', 'Last Run', 'Description', 'Project', 'Created')
            display_columns = ['id', 'name', 'job_type', 'labels', 'organization_name', 'last_job_run_formatted', 'description', 'playbook', 'created']
        else:
            columns = ('ID', 'Name', 'Type', 'Labels', 'Organization', 'Last Run')
            display_columns = ['id', 'name', 'job_type', 'labels', 'organization_name', 'last_job_run_formatted']

        return (
            columns,
            (
                get_dict_properties(s, display_columns)
                for s in data['results']
            ),
        )


class ShowJobTemplate(ShowOne):
    """Display job template details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'job_template',
            metavar='<job-template>',
            nargs='?',
            help='Job template to display (name or ID)',
        )

        # Create mutually exclusive group for --id and --name
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--id',
            metavar='<id>',
            type=int,
            help='Job template ID to display',
        )
        group.add_argument(
            '--name',
            metavar='<name>',
            help='Job template name to display',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Validate arguments
        if not any([parsed_args.job_template, parsed_args.id, parsed_args.name]):
            raise CommandError("Must specify a job template (by positional argument, --id, or --name)")

        # Check for redundant --name with positional argument
        if parsed_args.name and parsed_args.job_template:
            raise CommandError("Cannot use positional argument with --name (redundant)")

        # Determine lookup method
        template = None

        if parsed_args.id and parsed_args.job_template:
            # ID flag with positional argument - search by ID and validate name matches
            try:
                template = client.get_job_template(parsed_args.id)
            except Exception as e:
                raise CommandError(f"Job template with ID {parsed_args.id} not found")

            # Validate that the template found has the expected name
            if template['name'] != parsed_args.job_template:
                raise CommandError(
                    f"ID {parsed_args.id} and name '{parsed_args.job_template}' refer to different job templates: "
                    f"ID {parsed_args.id} is '{template['name']}', not '{parsed_args.job_template}'"
                )

        elif parsed_args.id:
            # Explicit ID lookup only
            try:
                template = client.get_job_template(parsed_args.id)
            except Exception as e:
                raise CommandError(f"Job template with ID {parsed_args.id} not found")

        else:
            # Name lookup (either explicit --name or positional argument)
            search_name = parsed_args.name or parsed_args.job_template
            templates = client.list_job_templates(name=search_name)
            if templates['count'] == 0:
                raise CommandError(f"Job template with name '{search_name}' not found")
            elif templates['count'] > 1:
                raise CommandError(f"Multiple job templates found with name '{search_name}'")
            template = templates['results'][0]

        # Add project and inventory names from summary_fields
        if 'summary_fields' in template and 'project' in template['summary_fields']:
            template['project_name'] = template['summary_fields']['project']['name']
        else:
            template['project_name'] = str(template.get('project', ''))

        if 'summary_fields' in template and 'inventory' in template['summary_fields']:
            template['inventory_name'] = template['summary_fields']['inventory']['name']
        else:
            template['inventory_name'] = str(template.get('inventory', ''))

        display_columns = [
            'id', 'name', 'description', 'job_type', 'inventory_name', 'project_name',
            'playbook', 'scm_branch', 'forks', 'limit', 'verbosity', 'extra_vars',
            'job_tags', 'force_handlers', 'skip_tags', 'start_at_task',
            'timeout', 'use_fact_cache', 'survey_enabled', 'ask_scm_branch_on_launch',
            'ask_diff_mode_on_launch', 'ask_variables_on_launch', 'ask_limit_on_launch',
            'ask_tags_on_launch', 'ask_skip_tags_on_launch', 'ask_job_type_on_launch',
            'ask_verbosity_on_launch', 'ask_inventory_on_launch', 'ask_credential_on_launch',
            'created', 'modified', 'last_job_run', 'last_job_failed', 'next_job_run',
            'status'
        ]

        return (
            display_columns,
            get_dict_properties(template, display_columns)
        )


class LaunchJobTemplate(ShowOne):
    """Launch a job template"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'job_template',
            metavar='<job-template>',
            help='Job template to launch (name or ID)',
        )
        parser.add_argument(
            '--extra-vars',
            metavar='<key=value>',
            action='append',
            help='Extra variables (can be used multiple times)',
        )
        parser.add_argument(
            '--extra-vars-file',
            metavar='<file>',
            help='JSON/YAML file containing extra variables',
        )
        parser.add_argument(
            '--inventory',
            metavar='<inventory>',
            type=int,
            help='Inventory ID to use for the job',
        )
        parser.add_argument(
            '--limit',
            metavar='<limit>',
            help='Limit job to specific hosts',
        )
        parser.add_argument(
            '--job-tags',
            metavar='<tags>',
            help='Comma-separated list of tags to run',
        )
        parser.add_argument(
            '--skip-tags',
            metavar='<tags>',
            help='Comma-separated list of tags to skip',
        )
        parser.add_argument(
            '--scm-branch',
            metavar='<branch>',
            help='SCM branch/tag/commit to use',
        )
        parser.add_argument(
            '--verbosity',
            metavar='<level>',
            type=int,
            choices=[0, 1, 2, 3, 4, 5],
            help='Verbosity level (0-5)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find the job template
        try:
            template_id = int(parsed_args.job_template)
        except ValueError:
            # Not an integer, search by name
            templates = client.list_job_templates(name=parsed_args.job_template)
            if templates['count'] == 0:
                raise CommandError(f"Job template '{parsed_args.job_template}' not found")
            elif templates['count'] > 1:
                raise CommandError(f"Multiple job templates found with name '{parsed_args.job_template}'")
            template_id = templates['results'][0]['id']

        # Build launch data
        launch_data = {}

        # Handle extra vars
        extra_vars = {}
        if parsed_args.extra_vars:
            for var in parsed_args.extra_vars:
                if '=' in var:
                    key, value = var.split('=', 1)
                    extra_vars[key] = value
                else:
                    raise CommandError(f"Invalid extra var format: {var}. Use key=value")

        if parsed_args.extra_vars_file:
            try:
                with open(parsed_args.extra_vars_file, 'r') as f:
                    file_vars = json.load(f)
                    extra_vars.update(file_vars)
            except Exception as e:
                raise CommandError(f"Error reading extra vars file: {e}")

        if extra_vars:
            launch_data['extra_vars'] = extra_vars

        # Handle other launch options
        if parsed_args.inventory:
            launch_data['inventory'] = parsed_args.inventory
        if parsed_args.limit:
            launch_data['limit'] = parsed_args.limit
        if parsed_args.job_tags:
            launch_data['job_tags'] = parsed_args.job_tags
        if parsed_args.skip_tags:
            launch_data['skip_tags'] = parsed_args.skip_tags
        if parsed_args.scm_branch:
            launch_data['scm_branch'] = parsed_args.scm_branch
        if parsed_args.verbosity is not None:
            launch_data['verbosity'] = parsed_args.verbosity

        # Launch the job
        job = client.launch_job_template(template_id, launch_data)

        display_columns = [
            'id', 'name', 'description', 'status', 'started', 'finished',
            'elapsed', 'job_template', 'inventory', 'project', 'playbook',
            'created', 'modified'
        ]

        return (
            display_columns,
            get_dict_properties(job, display_columns)
        )
