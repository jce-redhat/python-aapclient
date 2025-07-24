"""Instance Group commands."""

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.config import AAPConfig
from aapclient.common.client import AAPHTTPClient
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import (
    AAPClientError,
    AAPResourceNotFoundError,
    AAPAPIError
)
from aapclient.common.functions import (
    resolve_organization_name,
    resolve_credential_name,
    resolve_instance_group_name
)


def _format_instance_group_data(instance_group_data):
    """Format instance group data for display."""
    # Determine type based on is_container_group
    is_container_group = instance_group_data.get('is_container_group', False)
    group_type = "Container group" if is_container_group else "Instance group"

    # Format capacity remaining as percentage
    capacity_remaining = instance_group_data.get('percent_capacity_remaining', 0)
    capacity_display = f"{capacity_remaining}%"

    # Common fields for both types
    columns = [
        'Name',
        'Type',
        'Created',
        'Modified',
        'Max Concurrent Jobs',
        'Max Forks',
        'Jobs Running',
        'Jobs Total',
    ]

    values = [
        instance_group_data.get('name', ''),
        group_type,
        instance_group_data.get('created', ''),
        instance_group_data.get('modified', ''),
        instance_group_data.get('max_concurrent_jobs', 0),
        instance_group_data.get('max_forks', 0),
        instance_group_data.get('jobs_running', 0),
        instance_group_data.get('jobs_total', 0),
    ]

    # Add type-specific fields
    if is_container_group:
        # Container group specific fields
        columns.extend(['Credential', 'Pod Spec Override'])

        # Resolve credential name from summary_fields if available, otherwise use ID
        credential_value = instance_group_data.get('credential')
        if credential_value:
            summary_fields = instance_group_data.get('summary_fields', {})
            credential_summary = summary_fields.get('credential', {})
            credential_name = credential_summary.get('name', str(credential_value))
        else:
            credential_name = ''

        values.extend([
            credential_name,
            instance_group_data.get('pod_spec_override', '')
        ])
    else:
        # Instance group specific fields
        columns.extend([
            'Policy Instance Minimum',
            'Policy Instance Percentage',
            'Capacity',
            'Consumed Capacity',
            'Capacity Remaining',
        ])
        values.extend([
            instance_group_data.get('policy_instance_minimum', 0),
            instance_group_data.get('policy_instance_percentage', 0),
            instance_group_data.get('capacity', 0),
            instance_group_data.get('consumed_capacity', 0),
            capacity_display,
        ])

    return (columns, values)





class InstanceGroupListCommand(Lister):
    """List instance groups."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Enable server-side sorting on ID
            params = {'order_by': 'id'}
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/"
            response = client.get(endpoint, params=params)

            if response.status_code == HTTP_OK:
                data = response.json()
                instance_groups = data.get('results', [])

                columns = ['ID', 'Name', 'Type', 'Running Jobs', 'Total Jobs', 'Instances', 'Capacity Remaining']
                rows = []

                for group in instance_groups:
                    group_type = "Container group" if group.get('is_container_group', False) else "Instance group"
                    capacity_remaining = f"{group.get('percent_capacity_remaining', 0)}%"

                    row = [
                        group.get('id', ''),
                        group.get('name', ''),
                        group_type,
                        group.get('jobs_running', 0),
                        group.get('jobs_total', 0),
                        group.get('instances', 0),
                        capacity_remaining
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                raise AAPClientError(f"Failed to list instance groups: {response.status_code}")

        except AAPAPIError as api_error:
            raise AAPClientError(f"API error: {api_error}")


class InstanceGroupShowCommand(ShowOne):
    """Show instance group details."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Instance Group ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'instance_group',
            nargs='?',
            metavar='<instance-group>',
            help='Instance group name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Determine how to resolve the instance group
            if parsed_args.id:
                instance_group_id = parsed_args.id
            elif parsed_args.instance_group:
                instance_group_id = resolve_instance_group_name(client, parsed_args.instance_group, api="controller")
            else:
                raise AAPClientError("Instance group identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                instance_group_data = response.json()
                return _format_instance_group_data(instance_group_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get instance group: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {api_error}")


class InstanceGroupCreateCommand(ShowOne):
    """Create a new instance group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Required positional argument
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Name for the new instance group'
        )

        # Optional arguments
        parser.add_argument(
            '--is-container-group',
            action='store_true',
            help='Set as container group'
        )
        parser.add_argument(
            '--max-forks',
            type=int,
            help='Maximum forks'
        )
        parser.add_argument(
            '--max-concurrent-jobs',
            type=int,
            help='Maximum concurrent jobs'
        )
        parser.add_argument(
            '--credential',
            help='Credential for container groups'
        )
        parser.add_argument(
            '--policy-instance-minimum',
            type=int,
            help='Policy instance minimum for instance groups'
        )
        parser.add_argument(
            '--policy-instance-percentage',
            type=int,
            help='Policy instance percentage for instance groups'
        )
        parser.add_argument(
            '--pod-spec-override',
            help='Pod spec override for container groups'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Get parser for usage message
            parser = self.get_parser('aap instance-group create')

            # Validate arguments based on instance group type
            if parsed_args.is_container_group:
                # Container groups should not have policy arguments
                if parsed_args.policy_instance_minimum is not None:
                    parser.error("argument --policy-instance-minimum: not allowed when --is-container-group is specified")
                if parsed_args.policy_instance_percentage is not None:
                    parser.error("argument --policy-instance-percentage: not allowed when --is-container-group is specified")
            else:
                # Regular instance groups should not have container-specific arguments
                if parsed_args.credential:
                    parser.error("argument --credential: not allowed when --is-container-group is not specified")
                if parsed_args.pod_spec_override is not None:
                    parser.error("argument --pod-spec-override: not allowed when --is-container-group is not specified")

            instance_group_data = {
                'name': parsed_args.name,
                'is_container_group': parsed_args.is_container_group,
            }

            # Add optional fields
            if parsed_args.max_concurrent_jobs is not None:
                instance_group_data['max_concurrent_jobs'] = parsed_args.max_concurrent_jobs
            if parsed_args.max_forks is not None:
                instance_group_data['max_forks'] = parsed_args.max_forks
            if parsed_args.credential:
                try:
                    credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
                    instance_group_data['credential'] = credential_id
                except AAPResourceNotFoundError:
                    parser.error(f"Credential '{parsed_args.credential}' not found")
            if parsed_args.policy_instance_percentage is not None:
                instance_group_data['policy_instance_percentage'] = parsed_args.policy_instance_percentage
            if parsed_args.policy_instance_minimum is not None:
                instance_group_data['policy_instance_minimum'] = parsed_args.policy_instance_minimum
            if parsed_args.pod_spec_override is not None:
                instance_group_data['pod_spec_override'] = parsed_args.pod_spec_override

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/"
            response = client.post(endpoint, json=instance_group_data)

            if response.status_code == HTTP_CREATED:
                instance_group_data = response.json()
                print(f"Instance Group '{parsed_args.name}' created successfully")
                return _format_instance_group_data(instance_group_data)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                parser.error(f"Bad request: {error_data}")
            else:
                raise AAPClientError(f"Failed to create instance group: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                parser = self.get_parser('aap instance-group create')
                parser.error(f"Bad request: {api_error}")
            else:
                raise AAPClientError(f"API error: {api_error}")


class InstanceGroupSetCommand(ShowOne):
    """Update an existing instance group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Instance Group ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'instance_group',
            nargs='?',
            metavar='<instance-group>',
            help='Instance group name or ID to update'
        )

        # Update fields
        parser.add_argument(
            '--max-forks',
            type=int,
            help='Maximum forks'
        )
        parser.add_argument(
            '--max-concurrent-jobs',
            type=int,
            help='Maximum concurrent jobs'
        )
        parser.add_argument(
            '--credential',
            help='Credential for container groups'
        )
        parser.add_argument(
            '--policy-instance-minimum',
            type=int,
            help='Policy instance minimum for instance groups'
        )
        parser.add_argument(
            '--policy-instance-percentage',
            type=int,
            help='Policy instance percentage for instance groups'
        )
        parser.add_argument(
            '--pod-spec-override',
            help='Pod spec override for container groups'
        )

        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap instance-group set')

            # Determine how to resolve the instance group
            if parsed_args.id:
                instance_group_id = parsed_args.id
            elif parsed_args.instance_group:
                instance_group_id = resolve_instance_group_name(client, parsed_args.instance_group, api="controller")
            else:
                parser.error("Instance group identifier is required")

            # Fetch current instance group to check its type
            fetch_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
            fetch_response = client.get(fetch_endpoint)

            if fetch_response.status_code != HTTP_OK:
                if fetch_response.status_code == HTTP_NOT_FOUND:
                    raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
                else:
                    raise AAPClientError(f"Failed to fetch instance group: {fetch_response.status_code}")

            current_instance_group = fetch_response.json()
            is_container_group = current_instance_group.get('is_container_group', False)

            # Validate arguments based on instance group type
            if is_container_group:
                # Container groups should not have policy arguments
                if parsed_args.policy_instance_minimum is not None:
                    parser.error("argument --policy-instance-minimum: not allowed for container groups")
                if parsed_args.policy_instance_percentage is not None:
                    parser.error("argument --policy-instance-percentage: not allowed for container groups")
            else:
                # Regular instance groups should not have container-specific arguments
                if parsed_args.credential is not None:
                    parser.error("argument --credential: not allowed for instance groups (only for container groups)")
                if parsed_args.pod_spec_override is not None:
                    parser.error("argument --pod-spec-override: not allowed for instance groups (only for container groups)")

            instance_group_data = {}

            # Update fields if provided
            if parsed_args.max_concurrent_jobs is not None:
                instance_group_data['max_concurrent_jobs'] = parsed_args.max_concurrent_jobs
            if parsed_args.max_forks is not None:
                instance_group_data['max_forks'] = parsed_args.max_forks
            if parsed_args.credential is not None:
                try:
                    credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
                    instance_group_data['credential'] = credential_id
                    # API requires is_container_group to be explicitly set when setting credential
                    instance_group_data['is_container_group'] = True
                except AAPResourceNotFoundError:
                    parser.error(f"Credential '{parsed_args.credential}' not found")
            if parsed_args.policy_instance_percentage is not None:
                instance_group_data['policy_instance_percentage'] = parsed_args.policy_instance_percentage
            if parsed_args.policy_instance_minimum is not None:
                instance_group_data['policy_instance_minimum'] = parsed_args.policy_instance_minimum
            if parsed_args.pod_spec_override is not None:
                instance_group_data['pod_spec_override'] = parsed_args.pod_spec_override
                # API requires is_container_group to be explicitly set when setting container-specific fields
                instance_group_data['is_container_group'] = True

            if not instance_group_data:
                parser.error("At least one field must be specified to update")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
            response = client.patch(endpoint, json=instance_group_data)

            if response.status_code == HTTP_OK:
                instance_group_data = response.json()
                print(f"Instance Group '{parsed_args.instance_group or parsed_args.id}' updated successfully")
                return _format_instance_group_data(instance_group_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                parser.error(f"Bad request: {error_data}")
            else:
                raise AAPClientError(f"Failed to update instance group: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            elif api_error.status_code == HTTP_BAD_REQUEST:
                parser = self.get_parser('aap instance-group set')
                parser.error(f"Bad request: {api_error}")
            else:
                raise AAPClientError(f"API error: {api_error}")


class InstanceGroupDeleteCommand(Command):
    """Delete an instance group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Instance Group ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'instance_group',
            nargs='?',
            metavar='<instance-group>',
            help='Instance group name or ID to delete'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            parser = self.get_parser('aap instance-group delete')

            # Determine how to resolve the instance group
            if parsed_args.id:
                instance_group_id = parsed_args.id
            elif parsed_args.instance_group:
                instance_group_id = resolve_instance_group_name(client, parsed_args.instance_group, api="controller")
            else:
                parser.error("Instance group identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
            response = client.delete(endpoint)

            if response.status_code == HTTP_NO_CONTENT:
                print(f"Instance Group '{parsed_args.instance_group or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete instance group: {response.status_code}")

        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {api_error}")
