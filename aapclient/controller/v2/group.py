"""Group commands."""
import json
import yaml
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
from aapclient.common.functions import resolve_group_name, resolve_inventory_name, resolve_host_name, format_datetime, format_variables_display, format_variables_yaml_display


def _get_group_resource_count(client, group_id, resource_type):
    """
    Get the count of a specific resource type for a group.

    Args:
        client: AAPHTTPClient instance
        group_id: Group ID
        resource_type: Type of resource to count ('children' or 'hosts')

    Returns:
        int: Number of resources (0 if error or no resources)
    """
    try:
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/{resource_type}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            data = response.json()
            return data.get('count', 0)
    except:
        pass  # Return 0 on any error
    return 0


def _format_group_data(group_data, client=None, use_utc=False):
    """
    Format group data consistently

    Args:
        group_data (dict): Group data from API response
        client: AAPHTTPClient instance (optional, for getting child groups count)
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract group details
    id_value = group_data.get('id', '')
    name = group_data.get('name', '')
    description = group_data.get('description', '')

    # Get inventory name from summary_fields
    inventory_name = ''
    if 'summary_fields' in group_data and 'inventory' in group_data['summary_fields']:
        if group_data['summary_fields']['inventory']:
            inventory_name = group_data['summary_fields']['inventory'].get('name', '')

    variables = group_data.get('variables', '{}')
    created = format_datetime(group_data.get('created', ''), use_utc)
    modified = format_datetime(group_data.get('modified', ''), use_utc)

    # Get child groups count if client provided
    child_groups_count = 0
    if client and id_value:
        child_groups_count = _get_group_resource_count(client, id_value, 'children')

    # Get direct hosts count if client provided
    hosts_direct_count = 0
    if client and id_value:
        hosts_direct_count = _get_group_resource_count(client, id_value, 'hosts')

    # Get total hosts count (including from child groups) if client provided
    hosts_total_count = 0
    if client and id_value:
        hosts_total_count = _get_group_resource_count(client, id_value, 'all_hosts')

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Inventory',
        'Child Groups',
        'Hosts (direct)',
        'Hosts (total)',
        'Variables',
        'Created',
        'Modified'
    ]

    # Handle variables using unified function
    variables_display = format_variables_display(variables, "group")

    values = [
        id_value,
        name,
        description,
        inventory_name,
        child_groups_count,
        hosts_direct_count,
        hosts_total_count,
        variables_display,
        created,
        modified
    ]

    return (columns, values)


class GroupListCommand(AAPListCommand):
    """List groups."""

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
        """Execute the group list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query groups endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "groups endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                groups = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Description', 'Inventory']
                rows = []

                for group in groups:
                    # Get inventory name from summary_fields
                    inventory_name = ''
                    if 'summary_fields' in group and 'inventory' in group['summary_fields']:
                        if group['summary_fields']['inventory']:
                            inventory_name = group['summary_fields']['inventory'].get('name', '')

                    row = [
                        group.get('id', ''),
                        group.get('name', ''),
                        group.get('description', ''),
                        inventory_name
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


class GroupShowCommand(AAPShowCommand):
    """Show details of a specific group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Group ID'
        )
        parser.add_argument(
            'group',
            nargs='?',
            metavar='<group>',
            help='Group name or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                group_id = parsed_args.id
            elif parsed_args.group:
                # Use positional parameter - name first, then ID fallback if numeric
                group_id = resolve_group_name(client, parsed_args.group, api="controller")
            else:
                raise AAPClientError("Group identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                group_data = response.json()
                return _format_group_data(group_data, client, parsed_args.utc)
            else:
                raise AAPClientError(f"Failed to get group: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class GroupBaseCommand(AAPShowCommand):
    """Base class for group create and set commands."""

    def add_common_arguments(self, parser, required_args=True):
        """Add common arguments for group commands."""
        if required_args:
            # For create command
            parser.add_argument(
                'name',
                help='Group name'
            )
            parser.add_argument(
                '--inventory',
                required=True,
                help='Inventory name or ID that the group belongs to'
            )
        else:
            # For set command
            parser.add_argument(
                '--id',
                type=int,
                help='Group ID'
            )
            parser.add_argument(
                'group',
                nargs='?',
                metavar='<group>',
                help='Group name or ID to update'
            )
            parser.add_argument(
                '--set-name',
                dest='set_name',
                help='New group name'
            )

        # Common arguments for both commands
        parser.add_argument(
            '--description',
            help='Group description'
        )
        parser.add_argument(
            '--variables',
            help='Group variables in JSON format'
        )

    def resolve_resources(self, client, parsed_args, for_create=True):
        """Resolve resource names to IDs."""
        resolved_resources = {}

        if for_create:
            # For create command, resolve inventory
            resolved_resources['inventory_id'] = resolve_inventory_name(
                client, parsed_args.inventory, api="controller"
            )
        else:
            # For set command, resolve group
            group_identifier = getattr(parsed_args, 'id', None) or parsed_args.group
            if not group_identifier:
                parser = self.get_parser('aap group set')
                parser.error("Group name/ID is required")

            resolved_resources['group_id'] = resolve_group_name(
                client, group_identifier, api="controller"
            )

        return resolved_resources

    def build_group_data(self, parsed_args, resolved_resources, for_create=True):
        """Build group data dictionary for API requests."""
        group_data = {}

        if for_create:
            # Required fields for create
            group_data['name'] = parsed_args.name
            group_data['inventory'] = resolved_resources['inventory_id']
        else:
            # Optional name update for set
            if getattr(parsed_args, 'set_name', None):
                group_data['name'] = parsed_args.set_name

        # Common optional fields
        for field in ['description']:
            value = getattr(parsed_args, field, None)
            if value is not None:
                group_data[field] = value

        # Handle variables (JSON validation)
        if getattr(parsed_args, 'variables', None):
            try:
                # Validate JSON
                json.loads(parsed_args.variables)
                group_data['variables'] = parsed_args.variables
            except json.JSONDecodeError:
                parser = self.get_parser('aap group create' if for_create else 'aap group set')
                parser.error("argument --variables: must be valid JSON")

        return group_data


class GroupCreateCommand(GroupBaseCommand):
    """Create a new group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=True)
        return parser

    def take_action(self, parsed_args):
        """Execute the group create command."""
        try:
            client = self.controller_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=True)

            # Build group data
            group_data = self.build_group_data(parsed_args, resolved_resources, for_create=True)

            # Create group
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/"
            try:
                response = client.post(endpoint, json=group_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.name)

            if response.status_code == HTTP_CREATED:
                group_data = response.json()
                print(f"Group '{group_data.get('name', '')}' created successfully")

                return _format_group_data(group_data, client)
            else:
                raise AAPClientError(f"Group creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class GroupSetCommand(GroupBaseCommand):
    """Update an existing group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=False)
        return parser

    def take_action(self, parsed_args):
        """Execute the group set command."""
        try:
            client = self.controller_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=False)
            group_id = resolved_resources['group_id']

            # Build group data
            group_data = self.build_group_data(parsed_args, resolved_resources, for_create=False)

            if not group_data:
                parser = self.get_parser('aap group set')
                parser.error("No update fields provided")

            # Update group
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
            try:
                response = client.patch(endpoint, json=group_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.group or parsed_args.id)

            if response.status_code == HTTP_OK:
                group_data = response.json()
                print(f"Group '{group_data.get('name', '')}' updated successfully")

                return _format_group_data(group_data, client)
            else:
                raise AAPClientError(f"Group update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class GroupDeleteCommand(AAPCommand):
    """Delete a group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Group ID'
        )
        parser.add_argument(
            'group',
            nargs='?',
            metavar='<group>',
            help='Group name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                group_id = parsed_args.id
            elif parsed_args.group:
                # Use positional parameter - name first, then ID fallback if numeric
                group_id = resolve_group_name(client, parsed_args.group, api="controller")
            else:
                raise AAPClientError("Group identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Group '{parsed_args.group or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Group", parsed_args.group or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete group: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class GroupHostsListCommand(AAPListCommand):
    """List hosts in a group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Group ID'
        )
        parser.add_argument(
            'group',
            nargs='?',
            metavar='<group>',
            help='Group name or ID'
        )
        parser.add_argument(
            '--limit',
            type=int,
            metavar='N',
            help='Limit the number of results returned (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group hosts list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                group_id = parsed_args.id
            elif parsed_args.group:
                # Use positional parameter - name first, then ID fallback if numeric
                group_id = resolve_group_name(client, parsed_args.group, api="controller")
            else:
                raise AAPClientError("Group identifier is required")

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query group hosts endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/hosts/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", f"group {parsed_args.group or parsed_args.id} hosts endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                hosts = data.get('results', [])

                # Define columns for output (same as aap host list)
                columns = ['Host ID', 'Hostname', 'Description', 'Inventory', 'Enabled']
                rows = []

                for host in hosts:
                    # Get inventory name from summary_fields
                    inventory_name = ''
                    if 'summary_fields' in host and 'inventory' in host['summary_fields']:
                        if host['summary_fields']['inventory']:
                            inventory_name = host['summary_fields']['inventory'].get('name', '')

                    row = [
                        host.get('id', ''),
                        host.get('name', ''),
                        host.get('description', ''),
                        inventory_name,
                        'Yes' if host.get('enabled', False) else 'No'
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


class GroupChildrenListCommand(AAPListCommand):
    """List child groups of a group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Group ID'
        )
        parser.add_argument(
            'group',
            nargs='?',
            metavar='<group>',
            help='Group name or ID'
        )
        parser.add_argument(
            '--limit',
            type=int,
            metavar='N',
            help='Limit the number of results returned (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group children list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                group_id = parsed_args.id
            elif parsed_args.group:
                # Use positional parameter - name first, then ID fallback if numeric
                group_id = resolve_group_name(client, parsed_args.group, api="controller")
            else:
                raise AAPClientError("Group identifier is required")

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query group children endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/children/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", f"group {parsed_args.group or parsed_args.id} children endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                children = data.get('results', [])

                # Define columns for output (same as aap group list)
                columns = ['Group ID', 'Group Name', 'Description', 'Inventory']
                rows = []

                for child in children:
                    # Get inventory name from summary_fields
                    inventory_name = ''
                    if 'summary_fields' in child and 'inventory' in child['summary_fields']:
                        if child['summary_fields']['inventory']:
                            inventory_name = child['summary_fields']['inventory'].get('name', '')

                    row = [
                        child.get('id', ''),
                        child.get('name', ''),
                        child.get('description', ''),
                        inventory_name
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


class GroupHostsBaseCommand(AAPCommand):
    """Base class for group hosts add and remove commands."""

    def get_common_parser(self, prog_name, operation):
        """Get parser with common arguments for host operations."""
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Group ID (overrides group positional argument)'
        )
        parser.add_argument(
            'group',
            metavar='<group>',
            help='Group name or ID'
        )
        parser.add_argument(
            'hosts',
            nargs='+',
            metavar='<host>',
            help=f'Host name(s) or ID(s) to {operation} the group'
        )
        return parser

    def execute_host_operation(self, parsed_args, operation, payload_func, success_msg_func, duplicate_check_func):
        """Execute host operation with common logic."""
        try:
            client = self.controller_client

            # Resolve group
            if parsed_args.id:
                group_id = parsed_args.id
            else:
                group_id = resolve_group_name(client, parsed_args.group, api="controller")

            # Resolve all host identifiers to IDs
            host_ids = []
            for host_identifier in parsed_args.hosts:
                try:
                    host_id = resolve_host_name(client, host_identifier, api="controller")
                    host_ids.append(host_id)
                except Exception as e:
                    raise AAPClientError(f"Failed to resolve host '{host_identifier}': {e}")

            # Process each host
            successful_operations = []
            failed_operations = []

            for i, host_id in enumerate(host_ids):
                host_identifier = parsed_args.hosts[i]

                try:
                    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/hosts/"
                    payload = payload_func(host_id)

                    try:
                        response = client.post(endpoint, json=payload)
                    except AAPAPIError as api_error:
                        if api_error.status_code == HTTP_BAD_REQUEST:
                            error_msg = str(api_error).lower()
                            if duplicate_check_func(host_identifier, error_msg):
                                successful_operations.append(host_identifier)
                                continue
                        raise

                    if response.status_code == HTTP_NO_CONTENT:
                        successful_operations.append(host_identifier)
                        print(success_msg_func(host_identifier))
                    else:
                        failed_operations.append((host_identifier, f"Unexpected status code: {response.status_code}"))

                except Exception as e:
                    failed_operations.append((host_identifier, str(e)))

            # Summary
            if successful_operations:
                if operation == "add":
                    print(f"Successfully added {len(successful_operations)} host(s) to the group")
                else:
                    print(f"Successfully removed {len(successful_operations)} host(s) from the group")

            if failed_operations:
                print(f"Failed to {operation} {len(failed_operations)} host(s):")
                for host_identifier, error in failed_operations:
                    print(f"  - {host_identifier}: {error}")
                raise SystemExit(1)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class GroupHostsAddCommand(GroupHostsBaseCommand):
    """Add hosts to a group."""

    def get_parser(self, prog_name):
        return self.get_common_parser(prog_name, "add to")

    def take_action(self, parsed_args):
        """Execute the group hosts add command."""
        self.execute_host_operation(
            parsed_args,
            "add",
            payload_func=lambda host_id: {'id': host_id},
            success_msg_func=lambda host_identifier: f"Host '{host_identifier}' added to group successfully",
            duplicate_check_func=self._handle_add_duplicate_error
        )

    def _handle_add_duplicate_error(self, host_identifier, error_msg):
        """Handle duplicate error for add operation."""
        if 'already' in error_msg or 'duplicate' in error_msg:
            print(f"Host '{host_identifier}' is already in the group")
            return True
        return False



class GroupHostsRemoveCommand(GroupHostsBaseCommand):
    """Remove hosts from a group."""

    def get_parser(self, prog_name):
        return self.get_common_parser(prog_name, "remove from")

    def take_action(self, parsed_args):
        """Execute the group hosts remove command."""
        self.execute_host_operation(
            parsed_args,
            "remove",
            payload_func=lambda host_id: {'id': host_id, 'disassociate': True},
            success_msg_func=lambda host_identifier: f"Host '{host_identifier}' removed from group successfully",
            duplicate_check_func=self._handle_remove_duplicate_error
        )

    def _handle_remove_duplicate_error(self, host_identifier, error_msg):
        """Handle duplicate error for remove operation."""
        if 'not found' in error_msg or 'does not exist' in error_msg:
            print(f"Host '{host_identifier}' is not in the group")
            return True
        return False


class GroupChildrenBaseCommand(AAPCommand):
    """Base class for group children add and remove commands."""

    def get_common_parser(self, prog_name, operation):
        """Get parser with common arguments for child group operations."""
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Parent Group ID (overrides parent_group positional argument)'
        )
        parser.add_argument(
            'parent_group',
            metavar='<parent_group>',
            help='Parent group name or ID'
        )
        parser.add_argument(
            'child_groups',
            nargs='+',
            metavar='<child_group>',
            help=f'Child group name(s) or ID(s) to {operation} the parent group'
        )
        return parser

    def execute_children_operation(self, parsed_args, operation, payload_func, success_msg_func, duplicate_check_func):
        """Execute child group operation with common logic."""
        try:
            client = self.controller_client

            # Resolve parent group
            if parsed_args.id:
                parent_group_id = parsed_args.id
            else:
                parent_group_id = resolve_group_name(client, parsed_args.parent_group, api="controller")

            # Resolve all child group identifiers to IDs
            child_group_ids = []
            for child_identifier in parsed_args.child_groups:
                try:
                    child_group_id = resolve_group_name(client, child_identifier, api="controller")
                    child_group_ids.append(child_group_id)
                except Exception as e:
                    raise AAPClientError(f"Failed to resolve child group '{child_identifier}': {e}")

            # Process each child group
            successful_operations = []
            failed_operations = []

            for i, child_group_id in enumerate(child_group_ids):
                child_identifier = parsed_args.child_groups[i]

                try:
                    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{parent_group_id}/children/"
                    payload = payload_func(child_group_id)

                    try:
                        response = client.post(endpoint, json=payload)
                    except AAPAPIError as api_error:
                        if api_error.status_code == HTTP_BAD_REQUEST:
                            error_msg = str(api_error).lower()
                            if duplicate_check_func(child_identifier, error_msg):
                                successful_operations.append(child_identifier)
                                continue
                        raise

                    if response.status_code == HTTP_NO_CONTENT:
                        successful_operations.append(child_identifier)
                        print(success_msg_func(child_identifier))
                    else:
                        failed_operations.append((child_identifier, f"Unexpected status code: {response.status_code}"))

                except Exception as e:
                    failed_operations.append((child_identifier, str(e)))

            # Summary
            if successful_operations:
                if operation == "add":
                    print(f"Successfully added {len(successful_operations)} child group(s) to the parent group")
                else:
                    print(f"Successfully removed {len(successful_operations)} child group(s) from the parent group")

            if failed_operations:
                print(f"Failed to {operation} {len(failed_operations)} child group(s):")
                for child_identifier, error in failed_operations:
                    print(f"  - {child_identifier}: {error}")
                raise SystemExit(1)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class GroupChildrenAddCommand(GroupChildrenBaseCommand):
    """Add child groups to a parent group."""

    def get_parser(self, prog_name):
        return self.get_common_parser(prog_name, "add to")

    def take_action(self, parsed_args):
        """Execute the group children add command."""
        self.execute_children_operation(
            parsed_args,
            "add",
            payload_func=lambda child_group_id: {'id': child_group_id},
            success_msg_func=lambda child_identifier: f"Child group '{child_identifier}' added to parent group successfully",
            duplicate_check_func=self._handle_add_duplicate_error
        )

    def _handle_add_duplicate_error(self, child_identifier, error_msg):
        """Handle duplicate error for add operation."""
        if 'already' in error_msg or 'duplicate' in error_msg:
            print(f"Child group '{child_identifier}' is already in the parent group")
            return True
        return False


class GroupChildrenRemoveCommand(GroupChildrenBaseCommand):
    """Remove child groups from a parent group."""

    def get_parser(self, prog_name):
        return self.get_common_parser(prog_name, "remove from")

    def take_action(self, parsed_args):
        """Execute the group children remove command."""
        self.execute_children_operation(
            parsed_args,
            "remove",
            payload_func=lambda child_group_id: {'id': child_group_id, 'disassociate': True},
            success_msg_func=lambda child_identifier: f"Child group '{child_identifier}' removed from parent group successfully",
            duplicate_check_func=self._handle_remove_duplicate_error
        )

    def _handle_remove_duplicate_error(self, child_identifier, error_msg):
        """Handle duplicate error for remove operation."""
        if 'not found' in error_msg or 'does not exist' in error_msg:
            print(f"Child group '{child_identifier}' is not in the parent group")
            return True
        return False


class GroupVariablesShowCommand(AAPShowCommand):
    """Show group variables in YAML format."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Group ID'
        )
        parser.add_argument(
            'group',
            nargs='?',
            metavar='<group>',
            help='Group name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group variables show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                group_id = parsed_args.id
            elif parsed_args.group:
                # Use positional parameter - name first, then ID fallback if numeric
                group_id = resolve_group_name(client, parsed_args.group, api="controller")
            else:
                raise AAPClientError("Group identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                group_data = response.json()

                # Extract variables and format using unified function
                variables = group_data.get('variables', '{}')
                variables_yaml = format_variables_yaml_display(variables)

                # Format for display
                columns = ['Group', 'Variables']
                values = [
                    parsed_args.group or parsed_args.id,
                    variables_yaml
                ]

                return (columns, values)
            else:
                raise AAPClientError(f"Failed to get group: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
