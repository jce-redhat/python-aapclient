"""Instance Group commands."""
from aapclient.common.basecommands import AAPShowCommand, AAPListCommand, AAPCommand
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST,
    HTTP_ACCEPTED
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import (
    resolve_credential_name,
    resolve_instance_group_name,
    format_datetime
)





def _format_instance_group_data(instance_group_data, use_utc=False):
    """
    Format instance group data consistently

    Args:
        instance_group_data (dict): Instance group data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract instance group details
    id_value = instance_group_data.get('id', '')
    name = instance_group_data.get('name', '')
    is_container_group = instance_group_data.get('is_container_group', False)
    # Handle instances field - can be either a list or an integer count
    instances_value = instance_group_data.get('instances', [])
    if isinstance(instances_value, list):
        instances_count = len(instances_value)
    else:
        # API returned count as integer
        instances_count = instances_value
    jobs_running = instance_group_data.get('jobs_running', 0)
    jobs_total = instance_group_data.get('jobs_total', 0)
    capacity_remaining = instance_group_data.get('percent_capacity_remaining', 0)

    # Determine type based on is_container_group
    group_type = "Container" if is_container_group else "Instance"

    # Display credential if it's a container group
    credential_name = ''
    if is_container_group and 'summary_fields' in instance_group_data and 'credential' in instance_group_data['summary_fields']:
        if instance_group_data['summary_fields']['credential']:
            credential_name = instance_group_data['summary_fields']['credential'].get('name', '')
        else:
            # If no credential in summary_fields but there's a credential ID, show the ID
            credential_id = instance_group_data.get('credential')
            if credential_id:
                credential_name = str(credential_id)

    created = format_datetime(instance_group_data.get('created', ''), use_utc)
    modified = format_datetime(instance_group_data.get('modified', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Type',
        'Running Jobs',
        'Total Jobs',
        'Instances',
        'Capacity Remaining'
    ]

    values = [
        id_value,
        name,
        group_type,
        jobs_running,
        jobs_total,
        instances_count,
        f"{capacity_remaining}%"
    ]

    # Add credential field if it's a container group
    if is_container_group:
        columns.append('Credential')
        values.append(credential_name)

    columns.extend(['Created', 'Modified'])
    values.extend([created, modified])

    return (columns, values)


class InstanceGroupListCommand(AAPListCommand):
    """List instance groups."""

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
        """Execute the instance group list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query instance groups endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "instance_groups endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                instance_groups = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Type', 'Running Jobs', 'Total Jobs', 'Instances', 'Capacity Remaining']
                rows = []

                for instance_group in instance_groups:
                    # Determine type based on is_container_group
                    is_container_group = instance_group.get('is_container_group', False)
                    group_type = "Container" if is_container_group else "Instance"

                    # Calculate instances count - handle both list and integer from API
                    instances_value = instance_group.get('instances', [])
                    if isinstance(instances_value, list):
                        instances_count = len(instances_value)
                    else:
                        # API returned count as integer
                        instances_count = instances_value

                    row = [
                        instance_group.get('id', ''),
                        instance_group.get('name', ''),
                        group_type,
                        instance_group.get('jobs_running', 0),
                        instance_group.get('jobs_total', 0),
                        instances_count,
                        f"{instance_group.get('percent_capacity_remaining', 0)}%"
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


class InstanceGroupShowCommand(AAPShowCommand):
    """Show details of a specific instance group."""

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
            metavar='<instance_group>',
            help='Instance Group name or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the instance group show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the instance group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                instance_group_id = parsed_args.id
            elif parsed_args.instance_group:
                # Use positional parameter - name first, then ID fallback if numeric
                instance_group_id = resolve_instance_group_name(client, parsed_args.instance_group, api="controller")
            else:
                raise AAPClientError("Instance Group identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                instance_group_data = response.json()
                return _format_instance_group_data(instance_group_data, use_utc=parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get instance group: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class InstanceGroupCreateCommand(AAPShowCommand):
    """Create a new instance group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Instance Group name'
        )
        parser.add_argument(
            '--is-container-group',
            action='store_true',
            dest='is_container_group',
            help='Create a container group'
        )

        # Container-specific arguments
        parser.add_argument(
            '--credential',
            help='Container Registry credential name or ID (container groups only)'
        )
        parser.add_argument(
            '--pod-spec-override',
            dest='pod_spec_override',
            help='Pod spec override for container groups (JSON format)'
        )

        # Instance-specific arguments
        parser.add_argument(
            '--policy-instance-minimum',
            type=int,
            dest='policy_instance_minimum',
            help='Minimum number of instances (instance groups only)'
        )
        parser.add_argument(
            '--policy-instance-percentage',
            type=int,
            dest='policy_instance_percentage',
            help='Percentage of instances to maintain (instance groups only)'
        )

        # Common arguments
        parser.add_argument(
            '--max-forks',
            type=int,
            dest='max_forks',
            help='Maximum number of forks'
        )
        parser.add_argument(
            '--max-concurrent-jobs',
            type=int,
            dest='max_concurrent_jobs',
            help='Maximum number of concurrent jobs'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the instance group create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap instance-group create')

            # Validate argument combinations based on type
            if parsed_args.is_container_group:
                # Container group - deny instance-specific arguments
                if parsed_args.policy_instance_minimum is not None:
                    parser.error("--policy-instance-minimum cannot be used with container groups")
                if parsed_args.policy_instance_percentage is not None:
                    parser.error("--policy-instance-percentage cannot be used with container groups")
            else:
                # Instance group - deny container-specific arguments
                if parsed_args.credential:
                    parser.error("--credential can only be used with container groups (use --is-container-group)")
                if parsed_args.pod_spec_override:
                    parser.error("--pod-spec-override can only be used with container groups (use --is-container-group)")

            instance_group_data = {
                'name': parsed_args.name,
                'is_container_group': parsed_args.is_container_group
            }

            # Add common fields
            if parsed_args.max_forks is not None:
                instance_group_data['max_forks'] = parsed_args.max_forks
            if parsed_args.max_concurrent_jobs is not None:
                instance_group_data['max_concurrent_jobs'] = parsed_args.max_concurrent_jobs

            # Add container-specific fields
            if parsed_args.is_container_group:
                if parsed_args.credential:
                    credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
                    instance_group_data['credential'] = credential_id
                if parsed_args.pod_spec_override:
                    try:
                        import json
                        instance_group_data['pod_spec_override'] = json.loads(parsed_args.pod_spec_override)
                    except json.JSONDecodeError:
                        parser.error("argument --pod-spec-override: must be valid JSON")
            else:
                # Add instance-specific fields
                if parsed_args.policy_instance_minimum is not None:
                    instance_group_data['policy_instance_minimum'] = parsed_args.policy_instance_minimum
                if parsed_args.policy_instance_percentage is not None:
                    instance_group_data['policy_instance_percentage'] = parsed_args.policy_instance_percentage

            # Create instance group
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/"
            try:
                response = client.post(endpoint, json=instance_group_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.name)

            if response.status_code == HTTP_CREATED:
                instance_group_data = response.json()
                print(f"Instance Group '{instance_group_data.get('name', '')}' created successfully")

                return _format_instance_group_data(instance_group_data)
            else:
                raise AAPClientError(f"Instance Group creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class InstanceGroupSetCommand(AAPShowCommand):
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
            metavar='<instance_group>',
            help='Instance Group name or ID to update'
        )

        # Container-specific arguments
        parser.add_argument(
            '--credential',
            help='Container Registry credential name or ID (container groups only)'
        )
        parser.add_argument(
            '--pod-spec-override',
            dest='pod_spec_override',
            help='Pod spec override for container groups (JSON format)'
        )

        # Instance-specific arguments
        parser.add_argument(
            '--policy-instance-minimum',
            type=int,
            dest='policy_instance_minimum',
            help='Minimum number of instances (instance groups only)'
        )
        parser.add_argument(
            '--policy-instance-percentage',
            type=int,
            dest='policy_instance_percentage',
            help='Percentage of instances to maintain (instance groups only)'
        )

        # Common arguments
        parser.add_argument(
            '--max-forks',
            type=int,
            dest='max_forks',
            help='Maximum number of forks'
        )
        parser.add_argument(
            '--max-concurrent-jobs',
            type=int,
            dest='max_concurrent_jobs',
            help='Maximum number of concurrent jobs'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the instance group set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap instance-group set')

            # Resolve instance group - handle both ID and name
            instance_group_id = resolve_instance_group_name(client, parsed_args.instance_group, api="controller")

            # Get current instance group details to check is_container_group
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
            response = client.get(endpoint)

            if response.status_code != HTTP_OK:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group)

            current_data = response.json()
            is_container_group = current_data.get('is_container_group', False)

            # Validate argument combinations based on current type
            if is_container_group:
                # Container group - deny instance-specific arguments
                if parsed_args.policy_instance_minimum is not None:
                    parser.error("--policy-instance-minimum cannot be used with container groups")
                if parsed_args.policy_instance_percentage is not None:
                    parser.error("--policy-instance-percentage cannot be used with container groups")
            else:
                # Instance group - deny container-specific arguments
                if parsed_args.credential:
                    parser.error("--credential can only be used with container groups")
                if parsed_args.pod_spec_override:
                    parser.error("--pod-spec-override can only be used with container groups")

            # Prepare instance group update data
            instance_group_data = {}

            # Add common fields
            if parsed_args.max_forks is not None:
                instance_group_data['max_forks'] = parsed_args.max_forks
            if parsed_args.max_concurrent_jobs is not None:
                instance_group_data['max_concurrent_jobs'] = parsed_args.max_concurrent_jobs

            # Add container-specific fields
            if is_container_group:
                # Include is_container_group in PATCH for container-specific fields
                if parsed_args.credential or parsed_args.pod_spec_override:
                    instance_group_data['is_container_group'] = True

                if parsed_args.credential:
                    credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
                    instance_group_data['credential'] = credential_id
                if parsed_args.pod_spec_override:
                    try:
                        import json
                        instance_group_data['pod_spec_override'] = json.loads(parsed_args.pod_spec_override)
                    except json.JSONDecodeError:
                        parser.error("argument --pod-spec-override: must be valid JSON")
            else:
                # Add instance-specific fields
                if parsed_args.policy_instance_minimum is not None:
                    instance_group_data['policy_instance_minimum'] = parsed_args.policy_instance_minimum
                if parsed_args.policy_instance_percentage is not None:
                    instance_group_data['policy_instance_percentage'] = parsed_args.policy_instance_percentage

            if not instance_group_data:
                parser.error("No update fields provided")

            # Update instance group
            try:
                response = client.patch(endpoint, json=instance_group_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.instance_group)

            if response.status_code == HTTP_OK:
                instance_group_data = response.json()
                print(f"Instance Group '{instance_group_data.get('name', '')}' updated successfully")

                return _format_instance_group_data(instance_group_data)
            else:
                raise AAPClientError(f"Instance Group update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class InstanceGroupDeleteCommand(AAPCommand):
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
            metavar='<instance_group>',
            help='Instance Group name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the instance group delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the instance group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                instance_group_id = parsed_args.id
            elif parsed_args.instance_group:
                # Use positional parameter - name first, then ID fallback if numeric
                instance_group_id = resolve_instance_group_name(client, parsed_args.instance_group, api="controller")
            else:
                raise AAPClientError("Instance Group identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}instance_groups/{instance_group_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Instance Group '{parsed_args.instance_group or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Instance Group", parsed_args.instance_group or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete instance group: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
