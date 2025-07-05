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

"""AAP Controller v2 Workflow Job action implementations"""

import logging

from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.utils import CommandError, get_dict_properties


LOG = logging.getLogger(__name__)


class ListWorkflowJob(Lister):
    """List workflow jobs"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--status',
            metavar='<status>',
            choices=['pending', 'waiting', 'running', 'successful', 'failed', 'error', 'canceled'],
            help='Filter by workflow job status',
        )
        parser.add_argument(
            '--workflow-job-template',
            metavar='<template-id>',
            type=int,
            help='Filter by workflow job template ID',
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
        if parsed_args.status:
            params['status'] = parsed_args.status
        if parsed_args.workflow_job_template:
            params['workflow_job_template'] = parsed_args.workflow_job_template

        data = client.list_workflow_jobs(**params)
        
        if parsed_args.long:
            columns = ('ID', 'Name', 'Status', 'Created', 'Started', 'Finished', 'Elapsed', 'Launched By', 'Template')
            display_columns = ['id', 'name', 'status', 'created', 'started', 'finished', 'elapsed', 'launched_by', 'workflow_job_template']
        else:
            columns = ('ID', 'Name', 'Status', 'Created', 'Launched By')
            display_columns = ['id', 'name', 'status', 'created', 'launched_by']

        return (
            columns,
            (
                get_dict_properties(s, display_columns)
                for s in data['results']
            ),
        )


class ShowWorkflowJob(ShowOne):
    """Display workflow job details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'workflow_job',
            metavar='<workflow-job>',
            help='Workflow job to display (ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        try:
            job_id = int(parsed_args.workflow_job)
            workflow_job = client.get_workflow_job(job_id)
        except ValueError:
            raise CommandError(f"Workflow job ID must be an integer, got: {parsed_args.workflow_job}")
        except Exception as e:
            raise CommandError(f"Failed to get workflow job {parsed_args.workflow_job}: {e}")

        display_columns = [
            'id', 'name', 'description', 'status', 'failed', 'started', 'finished', 
            'canceled_on', 'elapsed', 'job_explanation', 'launched_by', 
            'workflow_job_template', 'extra_vars', 'allow_simultaneous',
            'job_template', 'inventory', 'limit', 'scm_branch', 'created', 'modified'
        ]
        
        return (
            display_columns,
            get_dict_properties(workflow_job, display_columns)
        )


class CancelWorkflowJob(ShowOne):
    """Cancel a workflow job"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'workflow_job',
            metavar='<workflow-job-id>',
            help='Workflow job to cancel (ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        try:
            job_id = int(parsed_args.workflow_job)
        except ValueError:
            raise CommandError(f"Workflow job ID must be an integer, got: {parsed_args.workflow_job}")

        try:
            result = client.cancel_workflow_job(job_id)
            
            # Get updated job info
            workflow_job = client.get_workflow_job(job_id)
            
            display_columns = [
                'id', 'name', 'status', 'created', 'started', 'finished',
                'elapsed', 'launched_by', 'workflow_job_template'
            ]
            
            return (
                display_columns,
                get_dict_properties(workflow_job, display_columns)
            )
        except Exception as e:
            raise CommandError(f"Failed to cancel workflow job {job_id}: {e}")


class RelaunchWorkflowJob(ShowOne):
    """Relaunch a workflow job"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'workflow_job',
            metavar='<workflow-job-id>',
            help='Workflow job to relaunch (ID)',
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        try:
            job_id = int(parsed_args.workflow_job)
        except ValueError:
            raise CommandError(f"Workflow job ID must be an integer, got: {parsed_args.workflow_job}")

        try:
            new_job = client.relaunch_workflow_job(job_id)
            
            display_columns = [
                'id', 'name', 'status', 'created', 'started', 'finished',
                'elapsed', 'launched_by', 'workflow_job_template'
            ]
            
            return (
                display_columns,
                get_dict_properties(new_job, display_columns)
            )
        except Exception as e:
            raise CommandError(f"Failed to relaunch workflow job {job_id}: {e}") 