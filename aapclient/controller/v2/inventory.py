"""Inventory commands."""
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
from aapclient.common.functions import (
    resolve_organization_name,
    resolve_inventory_name,
    resolve_instance_group_name,
    format_datetime,
    format_variables_display,
    format_variables_yaml_display
)





def _get_inventory_type(inventory_data):
    """
    Get inventory type based on kind field, defaulting to 'inventory' if empty.

    Args:
        inventory_data (dict): Inventory data from API response

    Returns:
        str: Inventory type
    """
    kind = inventory_data.get('kind', '')
    return kind if kind else 'inventory'


def _format_inventory_data(inventory_data, use_utc=False, client=None):
    """
    Format inventory data consistently with comprehensive field display

    Args:
        inventory_data (dict): Inventory data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract basic inventory details
    id_value = inventory_data.get('id', '')
    name = inventory_data.get('name', '')
    description = inventory_data.get('description', '')
    inventory_type = _get_inventory_type(inventory_data)
    variables = inventory_data.get('variables', '')

    # Organization information
    organization_name = ''
    if 'summary_fields' in inventory_data and 'organization' in inventory_data['summary_fields']:
        org_info = inventory_data['summary_fields']['organization']
        if org_info:
            organization_name = org_info.get('name', '')

    # Statistics
    total_inventory_sources = inventory_data.get('total_inventory_sources', 0)
    inventory_sources_with_failures = inventory_data.get('inventory_sources_with_failures', 0)

    # Get dynamic counts from endpoint APIs if client is available
    total_hosts = 0
    total_groups = 0
    if client:
        inventory_id = inventory_data.get('id')
        if inventory_id:
            # Get host count
            try:
                hosts_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/hosts/")
                if hosts_response.status_code == HTTP_OK:
                    hosts_data = hosts_response.json()
                    total_hosts = hosts_data.get('count', 0)
            except Exception:
                total_hosts = 0

            # Get group count
            try:
                groups_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/groups/")
                if groups_response.status_code == HTTP_OK:
                    groups_data = groups_response.json()
                    total_groups = groups_data.get('count', 0)
            except Exception:
                total_groups = 0

    # Get instance groups assigned to inventory if client is available
    instance_groups_display = ""
    if client:
        inventory_id = inventory_data.get('id')
        if inventory_id:
            try:
                ig_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/instance_groups/")
                if ig_response.status_code == HTTP_OK:
                    ig_data = ig_response.json()
                    instance_groups = ig_data.get('results', [])
                    if instance_groups:
                        ig_names = [ig.get('name', '') for ig in instance_groups if ig.get('name')]
                        instance_groups_display = ', '.join(ig_names)
                    else:
                        instance_groups_display = ""
            except Exception:
                instance_groups_display = ""

    # Instance group settings
    prevent_instance_group_fallback = inventory_data.get('prevent_instance_group_fallback', False)

    # User information from summary fields
    created_by = ''
    modified_by = ''
    if 'summary_fields' in inventory_data:
        summary = inventory_data['summary_fields']
        if 'created_by' in summary and summary['created_by']:
            created_by = summary['created_by'].get('username', '')
        if 'modified_by' in summary and summary['modified_by']:
            modified_by = summary['modified_by'].get('username', '')

    # Get variables using unified function - prefer variable_data endpoint if client available
    variables_display = ""
    if client:
        inventory_id = inventory_data.get('id')
        if inventory_id:
            try:
                var_response = client.get(f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/variable_data/")
                if var_response.status_code == HTTP_OK:
                    var_data = var_response.json()
                    variables_display = format_variables_display(var_data, "inventory")
                else:
                    # Fallback to direct field if endpoint fails
                    variables_display = format_variables_display(variables, "inventory")
            except Exception:
                # Fallback to direct field if request fails
                variables_display = format_variables_display(variables, "inventory")
    else:
        # Use direct field if no client available
        variables_display = format_variables_display(variables, "inventory")

    # Format datetime fields
    created = format_datetime(inventory_data.get('created', ''), use_utc)
    modified = format_datetime(inventory_data.get('modified', ''), use_utc)

    # Format fields for comprehensive display
    columns = [
        'ID',
        'Name',
        'Description',
        'Type',
        'Organization',
        'Total Hosts',
        'Total Groups',
        'Total Inventory Sources',
        'Inventory Sources with Failures',
        'Instance Groups',
        'Prevent Instance Group Fallback',
        'Variables',
        'Created',
        'Created By',
        'Modified',
        'Modified By',
    ]

    values = [
        id_value,
        name,
        description or "",
        inventory_type,
        organization_name,
        total_hosts,
        total_groups,
        total_inventory_sources,
        inventory_sources_with_failures,
        instance_groups_display,
        prevent_instance_group_fallback,
        variables_display,
        created,
        created_by,
        modified,
        modified_by
    ]

    return (columns, values)


class InventoryListCommand(AAPListCommand):
    """List inventories."""

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
        """Execute the inventory list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query inventories endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "inventories endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                inventories = data.get('results', [])

                # Define columns for output: id, name, status, type, organization
                columns = ['ID', 'Name', 'Status', 'Type', 'Organization']
                rows = []

                for inventory in inventories:
                    # Get organization name from summary_fields if available
                    org_name = ''
                    if 'summary_fields' in inventory and 'organization' in inventory['summary_fields']:
                        if inventory['summary_fields']['organization']:
                            org_name = inventory['summary_fields']['organization'].get('name', '')

                    # Derive status and type
                    status = "failing" if inventory.get('inventory_sources_with_failures', 0) > 0 else "ok"
                    inventory_type = _get_inventory_type(inventory)

                    row = [
                        inventory.get('id', ''),
                        inventory.get('name', ''),
                        status,
                        inventory_type,
                        org_name
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


class InventoryShowCommand(AAPShowCommand):
    """Show details of a specific inventory."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Inventory ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'inventory',
            nargs='?',
            metavar='<inventory>',
            help='Inventory name or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the inventory show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the inventory
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                inventory_id = parsed_args.id
            elif parsed_args.inventory:
                # Use positional parameter - name first, then ID fallback if numeric
                inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")
            else:
                raise AAPClientError("Inventory identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                inventory_data = response.json()
                return _format_inventory_data(inventory_data, parsed_args.utc, client)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Inventory", parsed_args.inventory or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get inventory: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class InventoryVariablesShowCommand(AAPShowCommand):
    """Show inventory variables in YAML format."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Inventory ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'inventory',
            nargs='?',
            metavar='<inventory>',
            help='Inventory name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the inventory variables show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the inventory
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                inventory_id = parsed_args.id
            elif parsed_args.inventory:
                # Use positional parameter - name first, then ID fallback if numeric
                inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")
            else:
                raise AAPClientError("Inventory identifier is required")

            # Get inventory details
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.inventory or parsed_args.id)

            if response.status_code == HTTP_OK:
                inventory_data = response.json()

                # Extract variables and format using unified function
                variables = inventory_data.get('variables', {})
                variables_yaml = format_variables_yaml_display(variables)

                # Format for display
                columns = ['Inventory', 'Variables']
                values = [
                    parsed_args.inventory or parsed_args.id,
                    variables_yaml
                ]

                return (columns, values)
            else:
                raise AAPClientError(f"Failed to get inventory: {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class InventoryCreateCommand(AAPShowCommand):
    """Create a new inventory."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Inventory name'
        )
        parser.add_argument(
            '--description',
            help='Inventory description'
        )
        parser.add_argument(
            '--organization',
            required=True,
            help='Organization name or ID'
        )
        parser.add_argument(
            '--variables',
            help='Inventory variables as JSON string'
        )
        parser.add_argument(
            '--prevent-instance-group-fallback',
            action='store_true',
            dest='prevent_instance_group_fallback',
            help='Prevent instance group fallback'
        )
        parser.add_argument(
            '--instance-groups',
            nargs='+',
            dest='instance_groups',
            help='Instance group names or IDs to assign to inventory'
        )
        return parser

    def _assign_instance_groups(self, client, inventory_id, instance_groups):
        """Assign instance groups to the inventory."""
        for instance_group in instance_groups:
            try:
                # Resolve instance group name/ID to actual ID
                instance_group_id = resolve_instance_group_name(client, instance_group)

                # Associate instance group with inventory
                ig_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/instance_groups/"
                ig_data = {"id": instance_group_id}

                ig_response = client.post(ig_endpoint, json=ig_data)
                if ig_response.status_code not in [HTTP_CREATED, HTTP_NO_CONTENT]:
                    print(f"Warning: Failed to assign instance group '{instance_group}' to inventory")

            except (AAPResourceNotFoundError, AAPAPIError) as e:
                print(f"Warning: Failed to assign instance group '{instance_group}': {e}")

    def take_action(self, parsed_args):
        """Execute the inventory create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap inventory create')

            # Resolve organization
            org_id = resolve_organization_name(client, parsed_args.organization, api="controller")

            inventory_data = {
                'name': parsed_args.name,
                'organization': org_id
            }

            # Add optional fields
            if parsed_args.description:
                inventory_data['description'] = parsed_args.description

            if getattr(parsed_args, 'variables', None):
                try:
                    # Validate JSON format but store as string
                    json.loads(parsed_args.variables)
                    inventory_data['variables'] = parsed_args.variables
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

            # Handle instance group fallback flag
            if parsed_args.prevent_instance_group_fallback:
                inventory_data['prevent_instance_group_fallback'] = True

            # Create inventory
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/"
            try:
                response = client.post(endpoint, json=inventory_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.name)

            if response.status_code == HTTP_CREATED:
                inventory_data = response.json()
                inventory_id = inventory_data.get('id')

                # Assign instance groups if provided
                if getattr(parsed_args, 'instance_groups', None) and inventory_id:
                    self._assign_instance_groups(client, inventory_id, parsed_args.instance_groups)

                print(f"Inventory '{inventory_data.get('name', '')}' created successfully")

                return _format_inventory_data(inventory_data, False, client)
            else:
                raise AAPClientError(f"Inventory creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class InventorySetCommand(AAPShowCommand):
    """Update an existing inventory."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'inventory',
            metavar='<inventory>',
            help='Inventory name or ID to update'
        )

        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='New inventory name'
        )
        parser.add_argument(
            '--description',
            help='Inventory description'
        )
        parser.add_argument(
            '--organization',
            help='Organization name or ID'
        )

        parser.add_argument(
            '--variables',
            help='Inventory variables as JSON string'
        )

        # Enable/disable flags for instance group fallback
        fallback_group = parser.add_mutually_exclusive_group()
        fallback_group.add_argument(
            '--allow-instance-group-fallback',
            action='store_false',
            dest='prevent_instance_group_fallback',
            help='Allow instance group fallback'
        )
        fallback_group.add_argument(
            '--prevent-instance-group-fallback',
            action='store_true',
            dest='prevent_instance_group_fallback',
            help='Prevent instance group fallback'
        )

        parser.add_argument(
            '--add-instance-group',
            action='append',
            dest='add_instance_groups',
            help='Instance group name or ID to add to inventory (can be used multiple times)'
        )
        parser.add_argument(
            '--remove-instance-group',
            action='append',
            dest='remove_instance_groups',
            help='Instance group name or ID to remove from inventory (can be used multiple times)'
        )

        return parser

    def _manage_instance_groups(self, client, inventory_id, add_groups=None, remove_groups=None):
        """Add or remove instance groups from the inventory."""
        ig_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/instance_groups/"

        # Remove instance groups
        if remove_groups:
            for instance_group in remove_groups:
                try:
                    # Resolve instance group name/ID to actual ID
                    instance_group_id = resolve_instance_group_name(client, instance_group)

                    # Disassociate instance group from inventory using POST with disassociate=true
                    ig_data = {"id": instance_group_id, "disassociate": True}
                    ig_response = client.post(ig_endpoint, json=ig_data)
                    if ig_response.status_code not in [HTTP_CREATED, HTTP_NO_CONTENT, HTTP_OK]:
                        print(f"Warning: Failed to remove instance group '{instance_group}' from inventory")

                except (AAPResourceNotFoundError, AAPAPIError) as e:
                    print(f"Warning: Failed to remove instance group '{instance_group}': {e}")

        # Add instance groups
        if add_groups:
            for instance_group in add_groups:
                try:
                    # Resolve instance group name/ID to actual ID
                    instance_group_id = resolve_instance_group_name(client, instance_group)

                    # Associate instance group with inventory
                    ig_data = {"id": instance_group_id}
                    ig_response = client.post(ig_endpoint, json=ig_data)
                    if ig_response.status_code not in [HTTP_CREATED, HTTP_NO_CONTENT, HTTP_OK]:
                        print(f"Warning: Failed to add instance group '{instance_group}' to inventory")

                except (AAPResourceNotFoundError, AAPAPIError) as e:
                    print(f"Warning: Failed to add instance group '{instance_group}': {e}")

    def take_action(self, parsed_args):
        """Execute the inventory set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap inventory set')

            # Resolve inventory - handle both ID and name
            inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")

            # Resolve organization if provided
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")
            else:
                org_id = None

            # Prepare inventory update data
            inventory_data = {}

            if parsed_args.set_name:
                inventory_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:  # Allow empty string
                inventory_data['description'] = parsed_args.description
            if org_id is not None:
                inventory_data['organization'] = org_id

            if getattr(parsed_args, 'variables', None):
                try:
                    # Validate JSON format but store as string
                    json.loads(parsed_args.variables)
                    inventory_data['variables'] = parsed_args.variables
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

            # Handle instance group fallback flag
            if hasattr(parsed_args, 'prevent_instance_group_fallback') and parsed_args.prevent_instance_group_fallback is not None:
                inventory_data['prevent_instance_group_fallback'] = parsed_args.prevent_instance_group_fallback

            if not inventory_data:
                parser.error("No update fields provided")

            # Update inventory
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/"
            try:
                response = client.patch(endpoint, json=inventory_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.inventory)

            if response.status_code == HTTP_OK:
                inventory_data = response.json()
                inventory_id = inventory_data.get('id')

                # Manage instance groups if provided
                add_groups = getattr(parsed_args, 'add_instance_groups', None)
                remove_groups = getattr(parsed_args, 'remove_instance_groups', None)
                if (add_groups or remove_groups) and inventory_id:
                    self._manage_instance_groups(client, inventory_id, add_groups, remove_groups)

                print(f"Inventory '{inventory_data.get('name', '')}' updated successfully")

                return _format_inventory_data(inventory_data, False, client)
            else:
                raise AAPClientError(f"Inventory update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class InventoryDeleteCommand(AAPCommand):
    """Delete an inventory."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Inventory ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'inventory',
            nargs='?',
            metavar='<inventory>',
            help='Inventory name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the inventory delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the inventory
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                inventory_id = parsed_args.id
            elif parsed_args.inventory:
                # Use positional parameter - name first, then ID fallback if numeric
                inventory_id = resolve_inventory_name(client, parsed_args.inventory, api="controller")
            else:
                raise AAPClientError("Inventory identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Inventory '{parsed_args.inventory or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Inventory", parsed_args.inventory or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete inventory: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
