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

"""AAP Controller v2 Workflow Job Template action implementations"""

import logging
import json

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.utils import CommandError, get_dict_properties


LOG = logging.getLogger(__name__)


class CreateWorkflow(ShowOne):
    """Create new workflow job template"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<workflow-name>',
            help='New workflow job template name',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='Workflow job template description',
        )
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            type=int,
            required=True,
            help='Organization ID for the workflow job template',
        )
        parser.add_argument(
            '--inventory',
            metavar='<inventory>',
            type=int,
            help='Inventory ID to use for the workflow',
        )
        parser.add_argument(
            '--extra-vars',
            metavar='<extra-vars>',
            help='Extra variables as JSON string',
        )
        parser.add_argument(
            '--allow-simultaneous',
            action='store_true',
            default=False,
            help='Allow simultaneous runs of the workflow',
        )
        parser.add_argument(
            '--ask-variables-on-launch',
            action='store_true',
            default=False,
            help='Prompt for extra variables on launch',
        )
        parser.add_argument(
            '--ask-inventory-on-launch',
            action='store_true',
            default=False,
            help='Prompt for inventory on launch',
        )
        parser.add_argument(
            '--ask-limit-on-launch',
            action='store_true',
            default=False,
            help='Prompt for limit on launch',
        )
        parser.add_argument(
            '--ask-scm-branch-on-launch',
            action='store_true',
            default=False,
            help='Prompt for SCM branch on launch',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        data = {
            'name': parsed_args.name,
            'organization': parsed_args.organization,
        }
        
        if parsed_args.description:
            data['description'] = parsed_args.description
        if parsed_args.inventory:
            data['inventory'] = parsed_args.inventory
        if parsed_args.extra_vars:
            try:
                data['extra_vars'] = json.loads(parsed_args.extra_vars)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON for extra-vars: {e}")
        
        # Boolean flags
        if parsed_args.allow_simultaneous:
            data['allow_simultaneous'] = True
        if parsed_args.ask_variables_on_launch:
            data['ask_variables_on_launch'] = True  
        if parsed_args.ask_inventory_on_launch:
            data['ask_inventory_on_launch'] = True
        if parsed_args.ask_limit_on_launch:
            data['ask_limit_on_launch'] = True
        if parsed_args.ask_scm_branch_on_launch:
            data['ask_scm_branch_on_launch'] = True

        workflow = client.create_workflow_job_template(data)
        
        display_columns = [
            'id', 'name', 'description', 'organization', 'inventory', 
            'allow_simultaneous', 'ask_variables_on_launch', 'ask_inventory_on_launch',
            'created', 'modified', 'last_job_run', 'last_job_failed', 'status'
        ]
        
        return (
            display_columns,
            get_dict_properties(workflow, display_columns)
        )


class DeleteWorkflow(Command):
    """Delete workflow job template(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'workflows',
            metavar='<workflow>',
            nargs="+",
            help='Workflow job template(s) to delete (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        errors = 0
        for workflow in parsed_args.workflows:
            try:
                # Try to get by ID first, then by name
                try:
                    workflow_id = int(workflow)
                    workflow_obj = client.get_workflow_job_template(workflow_id)
                except ValueError:
                    # Not an integer, search by name
                    workflows = client.list_workflow_job_templates(name=workflow)
                    if workflows['count'] == 0:
                        raise CommandError(f"Workflow job template '{workflow}' not found")
                    elif workflows['count'] > 1:
                        raise CommandError(f"Multiple workflow job templates found with name '{workflow}'")
                    workflow_obj = workflows['results'][0]
                    workflow_id = workflow_obj['id']
                
                client.delete_workflow_job_template(workflow_id)
                print(f"Workflow job template '{workflow}' deleted successfully")
            except Exception as e:
                errors += 1
                LOG.error(f"Failed to delete workflow job template '{workflow}': {e}")

        if errors > 0:
            total = len(parsed_args.workflows)
            msg = f"{errors} of {total} workflow job templates failed to delete."
            raise CommandError(msg)


class ListWorkflow(Lister):
    """List workflow job templates"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--organization',
            metavar='<organization>',
            type=int,
            help='Filter by organization ID',
        )
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller
        
        params = {}
        if parsed_args.organization:
            params['organization'] = parsed_args.organization

        data = client.list_workflow_job_templates(**params)
        
        if parsed_args.long:
            columns = ('ID', 'Name', 'Description', 'Organization', 'Inventory', 'Allow Simultaneous', 'Status', 'Created')
            display_columns = ['id', 'name', 'description', 'organization', 'inventory', 'allow_simultaneous', 'status', 'created']
        else:
            columns = ('ID', 'Name', 'Description', 'Organization', 'Status')
            display_columns = ['id', 'name', 'description', 'organization', 'status']

        return (
            columns,
            (
                get_dict_properties(s, display_columns)
                for s in data['results']
            ),
        )


class ShowWorkflow(ShowOne):
    """Display workflow job template details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'workflow',
            metavar='<workflow>',
            help='Workflow job template to display (name or ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Try to get by ID first, then by name
        try:
            workflow_id = int(parsed_args.workflow)
            workflow = client.get_workflow_job_template(workflow_id)
        except ValueError:
            # Not an integer, search by name
            workflows = client.list_workflow_job_templates(name=parsed_args.workflow)
            if workflows['count'] == 0:
                raise CommandError(f"Workflow job template '{parsed_args.workflow}' not found")
            elif workflows['count'] > 1:
                raise CommandError(f"Multiple workflow job templates found with name '{parsed_args.workflow}'")
            workflow = workflows['results'][0]

        display_columns = [
            'id', 'name', 'description', 'organization', 'inventory', 'extra_vars',
            'allow_simultaneous', 'ask_variables_on_launch', 'ask_inventory_on_launch',
            'ask_limit_on_launch', 'ask_scm_branch_on_launch', 'survey_enabled',
            'created', 'modified', 'last_job_run', 'last_job_failed', 'next_job_run',
            'status'
        ]
        
        return (
            display_columns,
            get_dict_properties(workflow, display_columns)
        )


class SetWorkflow(Command):
    """Set workflow job template properties"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'workflow',
            metavar='<workflow>',
            help='Workflow job template to modify (name or ID)',
        )
        parser.add_argument(
            '--name',
            metavar='<name>',
            help='New workflow job template name',
        )
        parser.add_argument(
            '--description',
            metavar='<description>',
            help='New workflow job template description',
        )
        parser.add_argument(
            '--inventory',
            metavar='<inventory>',
            type=int,
            help='Inventory ID to use for the workflow',
        )
        parser.add_argument(
            '--extra-vars',
            metavar='<extra-vars>',
            help='Extra variables as JSON string',
        )
        parser.add_argument(
            '--allow-simultaneous',
            action='store_true',
            help='Allow simultaneous runs of the workflow',
        )
        parser.add_argument(
            '--no-allow-simultaneous',
            action='store_true',
            help='Disallow simultaneous runs of the workflow',
        )
        parser.add_argument(
            '--ask-variables-on-launch',
            action='store_true',
            help='Prompt for extra variables on launch',
        )
        parser.add_argument(
            '--no-ask-variables-on-launch',
            action='store_true',
            help='Do not prompt for extra variables on launch',
        )
        parser.add_argument(
            '--ask-inventory-on-launch',
            action='store_true',
            help='Prompt for inventory on launch',
        )
        parser.add_argument(
            '--no-ask-inventory-on-launch',
            action='store_true',
            help='Do not prompt for inventory on launch',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find the workflow job template
        try:
            workflow_id = int(parsed_args.workflow)
        except ValueError:
            # Not an integer, search by name
            workflows = client.list_workflow_job_templates(name=parsed_args.workflow)
            if workflows['count'] == 0:
                raise CommandError(f"Workflow job template '{parsed_args.workflow}' not found")
            elif workflows['count'] > 1:
                raise CommandError(f"Multiple workflow job templates found with name '{parsed_args.workflow}'")
            workflow_id = workflows['results'][0]['id']

        # Build update data
        data = {}
        
        if parsed_args.name:
            data['name'] = parsed_args.name
        if parsed_args.description:
            data['description'] = parsed_args.description
        if parsed_args.inventory:
            data['inventory'] = parsed_args.inventory
        if parsed_args.extra_vars:
            try:
                data['extra_vars'] = json.loads(parsed_args.extra_vars)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON for extra-vars: {e}")
        
        # Handle boolean flags
        if parsed_args.allow_simultaneous:
            data['allow_simultaneous'] = True
        if parsed_args.no_allow_simultaneous:
            data['allow_simultaneous'] = False
        if parsed_args.ask_variables_on_launch:
            data['ask_variables_on_launch'] = True
        if parsed_args.no_ask_variables_on_launch:
            data['ask_variables_on_launch'] = False
        if parsed_args.ask_inventory_on_launch:
            data['ask_inventory_on_launch'] = True
        if parsed_args.no_ask_inventory_on_launch:
            data['ask_inventory_on_launch'] = False

        if not data:
            raise CommandError("No properties specified to set")

        client.update_workflow_job_template(workflow_id, data)
        print(f"Workflow job template '{parsed_args.workflow}' updated successfully")


class LaunchWorkflow(ShowOne):
    """Launch a workflow job template"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'workflow',
            metavar='<workflow>',
            help='Workflow job template to launch (name or ID)',
        )
        parser.add_argument(
            '--extra-vars',
            metavar='<extra-vars>',
            help='Extra variables as JSON string',
        )
        parser.add_argument(
            '--inventory',
            metavar='<inventory>',
            type=int,
            help='Inventory ID to use for the workflow job',
        )
        parser.add_argument(
            '--limit',
            metavar='<limit>',
            help='Limit job to specific hosts',
        )
        parser.add_argument(
            '--scm-branch',
            metavar='<branch>',
            help='SCM branch/tag/commit to use',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find the workflow job template
        try:
            workflow_id = int(parsed_args.workflow)
        except ValueError:
            # Not an integer, search by name
            workflows = client.list_workflow_job_templates(name=parsed_args.workflow)
            if workflows['count'] == 0:
                raise CommandError(f"Workflow job template '{parsed_args.workflow}' not found")
            elif workflows['count'] > 1:
                raise CommandError(f"Multiple workflow job templates found with name '{parsed_args.workflow}'")
            workflow_id = workflows['results'][0]['id']

        # Build launch data
        launch_data = {}
        
        if parsed_args.extra_vars:
            try:
                launch_data['extra_vars'] = json.loads(parsed_args.extra_vars)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON for extra-vars: {e}")
        if parsed_args.inventory:
            launch_data['inventory'] = parsed_args.inventory
        if parsed_args.limit:
            launch_data['limit'] = parsed_args.limit
        if parsed_args.scm_branch:
            launch_data['scm_branch'] = parsed_args.scm_branch

        workflow_job = client.launch_workflow_job_template(workflow_id, launch_data)
        
        display_columns = [
            'id', 'name', 'status', 'created', 'started', 'finished',
            'elapsed', 'launched_by', 'workflow_job_template'
        ]
        
        return (
            display_columns,
            get_dict_properties(workflow_job, display_columns)
        ) 