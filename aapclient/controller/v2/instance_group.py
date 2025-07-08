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

"""Instance Group commands for AAP Controller v2 API"""

import json
import logging

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common import utils
from aapclient.common.utils import CommandError, get_dict_properties, format_datetime


LOG = logging.getLogger(__name__)


class ListInstanceGroup(Lister):
    """List instance groups"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output'
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

        # Set consistent default limit of 20 (same as other list commands)
        if parsed_args.limit:
            params['page_size'] = parsed_args.limit
        else:
            params['page_size'] = 20

        # Sort by ID for consistency with other list commands
        params['order_by'] = 'id'

        data = client.list_instance_groups(**params)

        # Standard columns: ID, Name, Type, Running Jobs, Total Jobs, Instances, Capacity Remaining
        columns = ('ID', 'Name', 'Type', 'Running Jobs', 'Total Jobs', 'Instances', 'Capacity Remaining')
        column_headers = columns

        if parsed_args.long:
            # Long format adds Policy Instance Minimum, Max Concurrent Jobs, Created, Modified
            columns = ('ID', 'Name', 'Type', 'Running Jobs', 'Total Jobs', 'Instances', 'Capacity Remaining', 'Policy Instance Minimum', 'Max Concurrent Jobs', 'Created', 'Modified')
            column_headers = columns

        instance_groups = []
        for instance_group in data.get('results', []):
            # Use the capacity remaining percentage directly from the API
            percent_remaining = instance_group.get('percent_capacity_remaining', 100.0)
            capacity_remaining_str = f"{percent_remaining:.1f}%"

            # Handle instances field - it might be a count (int) or list
            instances = instance_group.get('instances', 0)
            if isinstance(instances, list):
                instance_count = len(instances)
            else:
                instance_count = instances  # Assume it's already a count

            instance_group_info = [
                instance_group['id'],
                instance_group.get('name', ''),
                instance_group.get('type', ''),  # Use the actual type field from API
                instance_group.get('jobs_running', 0),
                instance_group.get('jobs_total', 0),
                instance_count,
                capacity_remaining_str,
            ]

            if parsed_args.long:
                instance_group_info.extend([
                    instance_group.get('policy_instance_minimum', 0),
                    instance_group.get('max_concurrent_jobs', 0),
                    format_datetime(instance_group.get('created')),
                    format_datetime(instance_group.get('modified')),
                ])

            instance_groups.append(instance_group_info)

        return (column_headers, instance_groups)


class ShowInstanceGroup(ShowOne):
    """Display instance group details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'instance_group',
            help='Instance group name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find instance group by name or ID
        if parsed_args.instance_group.isdigit():
            instance_group_id = int(parsed_args.instance_group)
            try:
                data = client.get_instance_group(instance_group_id)
            except Exception as e:
                raise CommandError(f"Instance group with ID {instance_group_id} not found")
        else:
            instance_groups = client.list_instance_groups()
            instance_group = utils.find_resource(instance_groups, parsed_args.instance_group)
            data = client.get_instance_group(instance_group['id'])

        # Use the capacity remaining percentage directly from the API
        percent_remaining = data.get('percent_capacity_remaining', 100.0)
        data['capacity_remaining'] = f"{percent_remaining:.1f}%"

        # Add instance count - handle both list and integer formats
        instances = data.get('instances', 0)
        if isinstance(instances, list):
            data['instance_count'] = len(instances)
        else:
            data['instance_count'] = instances  # Assume it's already a count



        # Format the data for display
        display_data = []

        fields = [
            ('id', 'ID'),
            ('name', 'Name'),
            ('type', 'Type'),
            ('capacity', 'Capacity'),
            ('consumed_capacity', 'Consumed Capacity'),
            ('capacity_remaining', 'Capacity Remaining'),
            ('jobs_running', 'Running Jobs'),
            ('jobs_total', 'Total Jobs'),
            ('instance_count', 'Instances'),
            ('policy_instance_percentage', 'Policy Instance Percentage'),
            ('policy_instance_minimum', 'Policy Instance Minimum'),
            ('max_concurrent_jobs', 'Max Concurrent Jobs'),
            ('max_forks', 'Max Forks'),
            ('is_container_group', 'Is Container Group'),
            ('created', 'Created'),
            ('modified', 'Modified'),
        ]

        for field, label in fields:
            value = data.get(field, '')
            if field in ['created', 'modified']:
                value = format_datetime(value)
            elif isinstance(value, bool):
                value = 'Yes' if value else 'No'
            elif field == 'policy_instance_percentage':
                # Format as percentage
                value = f"{value}%" if value else "0%"
            elif value is None:
                value = ''

            display_data.append((label, value))

        return zip(*display_data) if display_data else ((), ())


class CreateInstanceGroup(Command):
    """Create a new instance group"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Name of the instance group'
        )
        parser.add_argument(
            '--policy-instance-percentage',
            type=int,
            default=0,
            help='Policy instance percentage (default: 0)'
        )
        parser.add_argument(
            '--policy-instance-minimum',
            type=int,
            default=0,
            help='Policy instance minimum (default: 0)'
        )
        parser.add_argument(
            '--max-concurrent-jobs',
            type=int,
            default=0,
            help='Maximum concurrent jobs (default: 0)'
        )
        parser.add_argument(
            '--max-forks',
            type=int,
            default=0,
            help='Maximum forks (default: 0)'
        )
        parser.add_argument(
            '--is-container-group',
            action='store_true',
            default=False,
            help='Set as container group'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Build the data dictionary
        data = {
            'name': parsed_args.name,
            'policy_instance_percentage': parsed_args.policy_instance_percentage,
            'policy_instance_minimum': parsed_args.policy_instance_minimum,
            'max_concurrent_jobs': parsed_args.max_concurrent_jobs,
            'max_forks': parsed_args.max_forks,
            'is_container_group': parsed_args.is_container_group,
        }

        try:
            result = client.create_instance_group(data)
            print(f"Instance group '{parsed_args.name}' created successfully")
        except Exception as e:
            # Check for duplicate name on 400 errors
            if "400" in str(e) or "Bad Request" in str(e):
                try:
                    existing = client.list_instance_groups(name=parsed_args.name)
                    if existing.get('results'):
                        existing_group = existing['results'][0]
                        raise CommandError(f"Instance group '{parsed_args.name} (ID: {existing_group['id']})' already exists")
                except:
                    pass
            raise CommandError(f"Failed to create instance group: {e}")


class SetInstanceGroup(Command):
    """Update an existing instance group"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'instance_group',
            help='Instance group name or ID to update'
        )
        parser.add_argument(
            '--name',
            help='New name for the instance group'
        )
        parser.add_argument(
            '--policy-instance-percentage',
            type=int,
            help='Policy instance percentage'
        )
        parser.add_argument(
            '--policy-instance-minimum',
            type=int,
            help='Policy instance minimum'
        )
        parser.add_argument(
            '--max-concurrent-jobs',
            type=int,
            help='Maximum concurrent jobs'
        )
        parser.add_argument(
            '--max-forks',
            type=int,
            help='Maximum forks'
        )
        parser.add_argument(
            '--is-container-group',
            action='store_true',
            help='Set as container group'
        )
        parser.add_argument(
            '--not-container-group',
            action='store_true',
            help='Unset as container group'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find instance group by name or ID
        if parsed_args.instance_group.isdigit():
            instance_group_id = int(parsed_args.instance_group)
            try:
                instance_group = client.get_instance_group(instance_group_id)
                instance_group_name = instance_group.get('name', f'ID {instance_group_id}')
            except Exception as e:
                raise CommandError(f"Instance group with ID {instance_group_id} not found")
        else:
            instance_groups = client.list_instance_groups()
            instance_group = utils.find_resource(instance_groups, parsed_args.instance_group)
            instance_group_id = instance_group['id']
            instance_group_name = parsed_args.instance_group

        # Build the data dictionary with only the fields to update
        data = {}
        if parsed_args.name:
            data['name'] = parsed_args.name
        if parsed_args.policy_instance_percentage is not None:
            data['policy_instance_percentage'] = parsed_args.policy_instance_percentage
        if parsed_args.policy_instance_minimum is not None:
            data['policy_instance_minimum'] = parsed_args.policy_instance_minimum
        if parsed_args.max_concurrent_jobs is not None:
            data['max_concurrent_jobs'] = parsed_args.max_concurrent_jobs
        if parsed_args.max_forks is not None:
            data['max_forks'] = parsed_args.max_forks
        if parsed_args.is_container_group:
            data['is_container_group'] = True
        elif parsed_args.not_container_group:
            data['is_container_group'] = False

        if not data:
            raise CommandError("No fields to update specified")

        try:
            client.update_instance_group(instance_group_id, data)
            # Use the final name (updated name if changed, otherwise original)
            final_name = data.get('name', instance_group_name)
            print(f"Instance group '{final_name}' updated successfully")
        except Exception as e:
            raise CommandError(f"Failed to update instance group: {e}")


class DeleteInstanceGroup(Command):
    """Delete instance groups"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'instance_groups',
            nargs='+',
            help='Instance group names or IDs to delete'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        for instance_group_ref in parsed_args.instance_groups:
            try:
                # Find instance group by name or ID
                if instance_group_ref.isdigit():
                    instance_group_id = int(instance_group_ref)
                    try:
                        instance_group = client.get_instance_group(instance_group_id)
                        instance_group_name = instance_group.get('name', f'ID {instance_group_id}')
                    except Exception as e:
                        raise CommandError(f"Instance group with ID {instance_group_id} not found")
                else:
                    instance_groups = client.list_instance_groups()
                    instance_group = utils.find_resource(instance_groups, instance_group_ref)
                    instance_group_id = instance_group['id']
                    instance_group_name = instance_group_ref

                # Delete the instance group
                client.delete_instance_group(instance_group_id)
                print(f"Instance group '{instance_group_name}' deleted successfully")

            except CommandError:
                # Re-raise CommandError as-is
                raise
            except Exception as e:
                raise CommandError(f"Failed to delete instance group '{instance_group_ref}': {e}")
