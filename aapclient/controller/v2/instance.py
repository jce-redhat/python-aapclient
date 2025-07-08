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

"""Instance commands for AAP Controller v2 API"""

import logging

from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common import utils
from aapclient.common.utils import CommandError, get_dict_properties, format_datetime


LOG = logging.getLogger(__name__)


class ListInstance(Lister):
    """List instances"""

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

        data = client.list_instances(**params)

        # Standard columns: ID, Name, Status, Node Type, Capacity, Percent Capacity Remaining, Enabled
        columns = ('ID', 'Name', 'Status', 'Node Type', 'Capacity', 'Percent Capacity Remaining', 'Enabled')
        column_headers = columns

        if parsed_args.long:
            # Long format adds Version, Heartbeat, Created, Modified
            columns = ('ID', 'Name', 'Status', 'Node Type', 'Capacity', 'Percent Capacity Remaining', 'Enabled', 'Version', 'Heartbeat', 'Created', 'Modified')
            column_headers = columns

        instances = []
        for instance in data.get('results', []):
            # Calculate percent capacity remaining
            capacity = instance.get('capacity', 0)
            consumed_capacity = instance.get('consumed_capacity', 0)
            if capacity > 0:
                percent_remaining = ((capacity - consumed_capacity) / capacity) * 100
                percent_capacity_remaining = f"{percent_remaining:.1f}%"
            else:
                percent_capacity_remaining = "N/A"

            instance_info = [
                instance['id'],
                instance.get('hostname', ''),
                instance.get('status', ''),
                instance.get('node_type', ''),
                f"{capacity} forks",
                percent_capacity_remaining,
                'Yes' if instance.get('enabled', True) else 'No',
            ]

            if parsed_args.long:
                instance_info.extend([
                    instance.get('version', ''),
                    format_datetime(instance.get('heartbeat')),
                    format_datetime(instance.get('created')),
                    format_datetime(instance.get('modified')),
                ])

            instances.append(instance_info)

        return (column_headers, instances)


class ShowInstance(ShowOne):
    """Display instance details"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'instance',
            help='Instance name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        client = self.app.client_manager.controller

        # Find instance by name or ID
        if parsed_args.instance.isdigit():
            instance_id = int(parsed_args.instance)
            try:
                data = client.get_instance(instance_id)
            except Exception as e:
                raise CommandError(f"Instance with ID {instance_id} not found")
        else:
            instances = client.list_instances()
            # Custom lookup for instances since they use 'hostname' instead of 'name'
            instance = None
            results = instances.get('results', [])

            # Try to find by hostname
            matches = [r for r in results if r.get('hostname') == parsed_args.instance]
            if len(matches) == 1:
                instance = matches[0]
            elif len(matches) > 1:
                raise CommandError(f"Multiple instances found with hostname '{parsed_args.instance}'")
            else:
                raise CommandError(f"Instance '{parsed_args.instance}' not found")

            data = client.get_instance(instance['id'])

        # Use the actual percent_capacity_remaining from the API
        percent_remaining = data.get('percent_capacity_remaining', 0.0)
        data['percent_capacity_remaining'] = f"{percent_remaining:.1f}%"

        # Format capacity with units
        capacity = data.get('capacity', 0)
        consumed_capacity = data.get('consumed_capacity', 0)
        data['capacity_formatted'] = f"{capacity} forks"
        data['consumed_capacity_formatted'] = f"{consumed_capacity} forks"

        # Format additional fields for display
        data['memory_formatted'] = f"{data.get('memory', 0) / (1024**3):.1f} GB" if data.get('memory') else 'N/A'
        data['cpu_formatted'] = str(data.get('cpu', ''))
        data['node_state_formatted'] = data.get('node_state', '').title()
        data['jobs_running_formatted'] = str(data.get('jobs_running', 0))
        data['jobs_total_formatted'] = str(data.get('jobs_total', 0))
        data['managed_formatted'] = 'Yes' if data.get('managed', False) else 'No'
        data['managed_by_policy_formatted'] = 'Yes' if data.get('managed_by_policy', False) else 'No'
        data['health_check_pending_formatted'] = 'Yes' if data.get('health_check_pending', False) else 'No'
        data['enabled_formatted'] = 'Yes' if data.get('enabled', True) else 'No'
        data['peers_from_control_nodes_formatted'] = 'Yes' if data.get('peers_from_control_nodes', False) else 'No'

        # Format the data for display
        display_data = []

        fields = [
            ('id', 'ID'),
            ('hostname', 'Name'),
            ('type', 'Type'),
            ('uuid', 'UUID'),
            ('node_type', 'Node Type'),
            ('node_state_formatted', 'Node State'),
            ('enabled_formatted', 'Enabled'),
            ('capacity_formatted', 'Capacity'),
            ('consumed_capacity_formatted', 'Consumed Capacity'),
            ('percent_capacity_remaining', 'Percent Capacity Remaining'),
            ('cpu_formatted', 'CPU'),
            ('cpu_capacity', 'CPU Capacity'),
            ('memory_formatted', 'Memory'),
            ('mem_capacity', 'Memory Capacity'),
            ('capacity_adjustment', 'Capacity Adjustment'),
            ('jobs_running_formatted', 'Jobs Running'),
            ('jobs_total_formatted', 'Jobs Total'),
            ('version', 'Version'),
            ('ip_address', 'IP Address'),
            ('listener_port', 'Listener Port'),
            ('protocol', 'Protocol'),
            ('peers_from_control_nodes_formatted', 'Peers From Control Nodes'),
            ('managed_formatted', 'Managed'),
            ('managed_by_policy_formatted', 'Managed By Policy'),
            ('health_check_pending_formatted', 'Health Check Pending'),
            ('last_health_check', 'Last Health Check'),
            ('last_seen', 'Last Seen'),
            ('errors', 'Errors'),
            ('created', 'Created'),
            ('modified', 'Modified'),
        ]

        for field, label in fields:
            value = data.get(field, '')
            if field in ['created', 'modified', 'last_health_check', 'last_seen']:
                value = format_datetime(value)
            elif isinstance(value, bool):
                value = 'Yes' if value else 'No'
            elif value is None:
                value = ''

            display_data.append((label, value))

        return zip(*display_data) if display_data else ((), ())
