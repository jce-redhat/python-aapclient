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
from aapclient.common.functions import resolve_group_name, resolve_inventory_name, resolve_host_name, format_datetime


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

    # Check if variables should be truncated
    variables_display = variables
    if len(variables) > 120:
        variables_display = "(Display with `group variables show` command)"

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


class GroupCreateCommand(AAPShowCommand):
    """Create a new group."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Group name'
        )
        parser.add_argument(
            '--description',
            help='Group description'
        )
        parser.add_argument(
            '--inventory',
            required=True,
            help='Inventory name or ID that the group belongs to'
        )
        parser.add_argument(
            '--variables',
            help='Group variables in JSON format'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap group create')

            # Resolve inventory name to ID
            inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")

            group_data = {
                'name': parsed_args.name,
                'inventory': inventory_id
            }

            # Add optional fields
            if parsed_args.description:
                group_data['description'] = parsed_args.description

            if parsed_args.variables:
                try:
                    # Validate JSON
                    json.loads(parsed_args.variables)
                    group_data['variables'] = parsed_args.variables
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

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


class GroupSetCommand(AAPShowCommand):
    """Update an existing group."""

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
            help='Group name or ID to update'
        )
        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='New group name'
        )
        parser.add_argument(
            '--description',
            help='Group description'
        )
        parser.add_argument(
            '--variables',
            help='Group variables in JSON format'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap group set')

            # Determine how to resolve the group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                group_id = parsed_args.id
            elif parsed_args.group:
                # Use positional parameter - name first, then ID fallback if numeric
                group_id = resolve_group_name(client, parsed_args.group, api="controller")
            else:
                raise AAPClientError("Group identifier is required")

            # Prepare group update data
            group_data = {}

            if parsed_args.set_name:
                group_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:
                group_data['description'] = parsed_args.description
            if parsed_args.variables:
                try:
                    # Validate JSON
                    json.loads(parsed_args.variables)
                    group_data['variables'] = parsed_args.variables
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

            if not group_data:
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


class GroupHostsModifyCommand(AAPCommand):
    """Base class for adding/removing hosts to/from groups."""

    def get_parser(self, prog_name):
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
            help='Host name(s) or ID(s) to modify in the group'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group hosts modify command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser(f'aap group hosts {self.get_operation_name()}')

            # Determine how to resolve the group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                group_id = parsed_args.id
            else:
                # Use positional parameter - name first, then ID fallback if numeric
                group_id = resolve_group_name(client, parsed_args.group, api="controller")

            # Resolve all host identifiers to IDs
            host_ids = []
            for host_identifier in parsed_args.hosts:
                try:
                    host_id = resolve_host_name(client, host_identifier, api="controller")
                    host_ids.append(host_id)
                except Exception as e:
                    raise AAPClientError(f"Failed to resolve host '{host_identifier}': {e}")

            # Modify each host in the group
            successful_operations = []
            failed_operations = []

            for i, host_id in enumerate(host_ids):
                host_identifier = parsed_args.hosts[i]

                try:
                    # POST to modify host relationship with group
                    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/hosts/"
                    payload = self.get_api_payload(host_id)

                    try:
                        response = client.post(endpoint, json=payload)
                    except AAPAPIError as api_error:
                        if api_error.status_code == HTTP_BAD_REQUEST:
                            # Check if it's a duplicate/not-found error specific to the operation
                            error_msg = str(api_error).lower()
                            if self.handle_duplicate_error(host_identifier, error_msg):
                                continue  # Skip this host
                        self.handle_api_error(api_error, "Controller API", f"group {parsed_args.group or parsed_args.id} hosts {self.get_operation_name()}")

                    if response.status_code in (HTTP_CREATED, HTTP_NO_CONTENT, HTTP_OK):
                        successful_operations.append(host_identifier)
                        print(self.get_success_message(host_identifier))
                    else:
                        failed_operations.append(host_identifier)
                        print(f"Failed to {self.get_operation_name()} host '{host_identifier}' {self.get_operation_preposition()} group: HTTP {response.status_code}")

                except Exception as e:
                    failed_operations.append(host_identifier)
                    print(f"Failed to {self.get_operation_name()} host '{host_identifier}' {self.get_operation_preposition()} group: {e}")

            # Summary
            if successful_operations:
                print(f"\nSuccessfully {self.get_operation_past_tense()} {len(successful_operations)} host(s) {self.get_operation_preposition()} group")
            if failed_operations:
                print(f"Failed to {self.get_operation_name()} {len(failed_operations)} host(s) {self.get_operation_preposition()} group")
                raise SystemExit(1)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")

    # Abstract methods to be implemented by subclasses
    def get_operation_name(self):
        """Return the operation name ('add' or 'remove')."""
        raise NotImplementedError("Subclass must implement get_operation_name")

    def get_operation_past_tense(self):
        """Return the operation past tense ('added' or 'removed')."""
        raise NotImplementedError("Subclass must implement get_operation_past_tense")

    def get_operation_preposition(self):
        """Return the operation preposition ('to' or 'from')."""
        raise NotImplementedError("Subclass must implement get_operation_preposition")

    def get_api_payload(self, host_id):
        """Return the API payload for the operation."""
        raise NotImplementedError("Subclass must implement get_api_payload")

    def get_success_message(self, host_identifier):
        """Return success message for the operation."""
        raise NotImplementedError("Subclass must implement get_success_message")

    def handle_duplicate_error(self, host_identifier, error_msg):
        """Handle operation-specific duplicate/not-found errors. Return True to skip host."""
        raise NotImplementedError("Subclass must implement handle_duplicate_error")


class GroupHostsAddCommand(GroupHostsModifyCommand):
    """Add hosts to a group."""

    def get_operation_name(self):
        return "add"

    def get_operation_past_tense(self):
        return "added"

    def get_operation_preposition(self):
        return "to"

    def get_api_payload(self, host_id):
        return {'id': host_id}

    def get_success_message(self, host_identifier):
        return f"Host '{host_identifier}' added to group successfully"

    def handle_duplicate_error(self, host_identifier, error_msg):
        if 'already' in error_msg or 'duplicate' in error_msg:
            print(f"Host '{host_identifier}' is already in the group")
            return True  # Skip this host
        return False


class GroupHostsRemoveCommand(GroupHostsModifyCommand):
    """Remove hosts from a group."""

    def get_operation_name(self):
        return "remove"

    def get_operation_past_tense(self):
        return "removed"

    def get_operation_preposition(self):
        return "from"

    def get_api_payload(self, host_id):
        return {'id': host_id, 'disassociate': True}

    def get_success_message(self, host_identifier):
        return f"Host '{host_identifier}' removed from group successfully"

    def handle_duplicate_error(self, host_identifier, error_msg):
        if 'not found' in error_msg or 'does not exist' in error_msg:
            print(f"Host '{host_identifier}' is not in the group")
            return True  # Skip this host
        return False


class GroupChildrenModifyCommand(AAPCommand):
    """Base class for adding/removing child groups to/from parent groups."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--id',
            type=int,
            help='Parent group ID (overrides parent group positional argument)'
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
            help='Child group name(s) or ID(s) to modify in the parent group'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the group children modify command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser(f'aap group children {self.get_operation_name()}')

            # Determine how to resolve the parent group
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                parent_group_id = parsed_args.id
            else:
                # Use positional parameter - name first, then ID fallback if numeric
                parent_group_id = resolve_group_name(client, parsed_args.parent_group, api="controller")

            # Resolve all child group identifiers to IDs
            child_group_ids = []
            for child_identifier in parsed_args.child_groups:
                try:
                    child_group_id = resolve_group_name(client, child_identifier, api="controller")
                    child_group_ids.append(child_group_id)
                except Exception as e:
                    raise AAPClientError(f"Failed to resolve child group '{child_identifier}': {e}")

            # Modify each child group relationship with the parent group
            successful_operations = []
            failed_operations = []

            for i, child_group_id in enumerate(child_group_ids):
                child_identifier = parsed_args.child_groups[i]

                try:
                    # POST to modify child group relationship with parent group
                    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{parent_group_id}/children/"
                    payload = self.get_api_payload(child_group_id)

                    try:
                        response = client.post(endpoint, json=payload)
                    except AAPAPIError as api_error:
                        if api_error.status_code == HTTP_BAD_REQUEST:
                            # Check if it's a duplicate/not-found error specific to the operation
                            error_msg = str(api_error).lower()
                            if self.handle_duplicate_error(child_identifier, error_msg):
                                continue  # Skip this child group
                        self.handle_api_error(api_error, "Controller API", f"group {parsed_args.parent_group or parsed_args.id} children {self.get_operation_name()}")

                    if response.status_code in (HTTP_CREATED, HTTP_NO_CONTENT, HTTP_OK):
                        successful_operations.append(child_identifier)
                        print(self.get_success_message(child_identifier))
                    else:
                        failed_operations.append(child_identifier)
                        print(f"Failed to {self.get_operation_name()} child group '{child_identifier}' {self.get_operation_preposition()} parent group: HTTP {response.status_code}")

                except Exception as e:
                    failed_operations.append(child_identifier)
                    print(f"Failed to {self.get_operation_name()} child group '{child_identifier}' {self.get_operation_preposition()} parent group: {e}")

            # Summary
            if successful_operations:
                print(f"\nSuccessfully {self.get_operation_past_tense()} {len(successful_operations)} child group(s) {self.get_operation_preposition()} parent group")
            if failed_operations:
                print(f"Failed to {self.get_operation_name()} {len(failed_operations)} child group(s) {self.get_operation_preposition()} parent group")
                raise SystemExit(1)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")

    # Abstract methods to be implemented by subclasses
    def get_operation_name(self):
        """Return the operation name ('add' or 'remove')."""
        raise NotImplementedError("Subclass must implement get_operation_name")

    def get_operation_past_tense(self):
        """Return the operation past tense ('added' or 'removed')."""
        raise NotImplementedError("Subclass must implement get_operation_past_tense")

    def get_operation_preposition(self):
        """Return the operation preposition ('to' or 'from')."""
        raise NotImplementedError("Subclass must implement get_operation_preposition")

    def get_api_payload(self, child_group_id):
        """Return the API payload for the operation."""
        raise NotImplementedError("Subclass must implement get_api_payload")

    def get_success_message(self, child_identifier):
        """Return success message for the operation."""
        raise NotImplementedError("Subclass must implement get_success_message")

    def handle_duplicate_error(self, child_identifier, error_msg):
        """Handle operation-specific duplicate/not-found errors. Return True to skip child group."""
        raise NotImplementedError("Subclass must implement handle_duplicate_error")


class GroupChildrenAddCommand(GroupChildrenModifyCommand):
    """Add child groups to a parent group."""

    def get_operation_name(self):
        return "add"

    def get_operation_past_tense(self):
        return "added"

    def get_operation_preposition(self):
        return "to"

    def get_api_payload(self, child_group_id):
        return {'id': child_group_id}

    def get_success_message(self, child_identifier):
        return f"Child group '{child_identifier}' added to parent group successfully"

    def handle_duplicate_error(self, child_identifier, error_msg):
        if 'already' in error_msg or 'duplicate' in error_msg:
            print(f"Child group '{child_identifier}' is already in the parent group")
            return True  # Skip this child group
        return False


class GroupChildrenRemoveCommand(GroupChildrenModifyCommand):
    """Remove child groups from a parent group."""

    def get_operation_name(self):
        return "remove"

    def get_operation_past_tense(self):
        return "removed"

    def get_operation_preposition(self):
        return "from"

    def get_api_payload(self, child_group_id):
        return {'id': child_group_id, 'disassociate': True}

    def get_success_message(self, child_identifier):
        return f"Child group '{child_identifier}' removed from parent group successfully"

    def handle_duplicate_error(self, child_identifier, error_msg):
        if 'not found' in error_msg or 'does not exist' in error_msg:
            print(f"Child group '{child_identifier}' is not in the parent group")
            return True  # Skip this child group
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
                variables_str = group_data.get('variables', '{}')

                try:
                    # Parse JSON and convert to YAML
                    variables_dict = json.loads(variables_str)
                    yaml_output = yaml.dump(variables_dict, default_flow_style=False)

                    # Return as ShowOne format
                    return (['Variables'], [yaml_output.strip()])
                except json.JSONDecodeError:
                    # If variables aren't valid JSON, return as-is
                    return (['Variables'], [variables_str])
            else:
                raise AAPClientError(f"Failed to get group: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
