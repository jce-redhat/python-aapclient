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
from aapclient.common.functions import resolve_organization_name, resolve_inventory_name





def _format_inventory_data(inventory_data):
    """
    Format inventory data consistently

    Args:
        inventory_data (dict): Inventory data from API response

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract inventory details
    id_value = inventory_data.get('id', '')
    name = inventory_data.get('name', '')
    description = inventory_data.get('description', '')
    organization_name = ''
    kind = inventory_data.get('kind', '')
    host_filter = inventory_data.get('host_filter', '')
    variables = inventory_data.get('variables', '')

    # Resolve organization name if available
    if 'summary_fields' in inventory_data and 'organization' in inventory_data['summary_fields']:
        if inventory_data['summary_fields']['organization']:
            organization_name = inventory_data['summary_fields']['organization'].get('name', '')

    # Handle variables with length check
    if len(str(variables)) > 120:
        variables_display = "(Display with `inventory variables show` command)"
    else:
        variables_display = str(variables)

    created = inventory_data.get('created', '')
    modified = inventory_data.get('modified', '')

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Organization',
        'Kind',
        'Host Filter',
        'Variables',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        name,
        description,
        organization_name,
        kind,
        host_filter,
        variables_display,
        created,
        modified
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

                # Define columns for output
                columns = ['ID', 'Name', 'Description', 'Organization', 'Kind']
                rows = []

                for inventory in inventories:
                    # Get organization name from summary_fields if available
                    org_name = ''
                    if 'summary_fields' in inventory and 'organization' in inventory['summary_fields']:
                        if inventory['summary_fields']['organization']:
                            org_name = inventory['summary_fields']['organization'].get('name', '')

                    row = [
                        inventory.get('id', ''),
                        inventory.get('name', ''),
                        inventory.get('description', ''),
                        org_name,
                        inventory.get('kind', '')
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
                return _format_inventory_data(inventory_data)
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

                # Extract variables
                variables = inventory_data.get('variables', {})

                # Always convert to YAML format
                if variables:
                    try:
                        # If variables is a string, try to parse it as JSON first
                        if isinstance(variables, str):
                            variables = json.loads(variables)
                        # Convert to YAML
                        variables_yaml = yaml.dump(variables, default_flow_style=False)
                    except (json.JSONDecodeError, yaml.YAMLError):
                        # If conversion fails, display as string
                        variables_yaml = str(variables)
                else:
                    variables_yaml = "{}"

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
            '--kind',
            choices=['', 'smart'],
            default='',
            help='Inventory kind (default: regular inventory)'
        )
        parser.add_argument(
            '--host-filter',
            dest='host_filter',
            help='Host filter query for smart inventories'
        )
        parser.add_argument(
            '--variables',
            help='Inventory variables as JSON string'
        )
        parser.add_argument(
            '--enable-instance-group-fallback',
            action='store_true',
            dest='instance_group_fallback',
            help='Allow instance group fallback'
        )
        parser.add_argument(
            '--disable-instance-group-fallback',
            action='store_true',
            dest='disable_instance_group_fallback',
            help='Disable instance group fallback'
        )
        return parser

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
            if getattr(parsed_args, 'kind', None):
                inventory_data['kind'] = parsed_args.kind
            if getattr(parsed_args, 'host_filter', None):
                inventory_data['host_filter'] = parsed_args.host_filter
            if getattr(parsed_args, 'variables', None):
                try:
                    # Validate JSON format but store as string
                    json.loads(parsed_args.variables)
                    inventory_data['variables'] = parsed_args.variables
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

            # Handle instance group fallback flags
            if parsed_args.instance_group_fallback:
                inventory_data['instance_group_fallback'] = True
            elif parsed_args.disable_instance_group_fallback:
                inventory_data['instance_group_fallback'] = False

            # Create inventory
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/"
            try:
                response = client.post(endpoint, json=inventory_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.name)

            if response.status_code == HTTP_CREATED:
                inventory_data = response.json()
                print(f"Inventory '{inventory_data.get('name', '')}' created successfully")

                return _format_inventory_data(inventory_data)
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
            '--host-filter',
            dest='host_filter',
            help='Host filter query for smart inventories'
        )
        parser.add_argument(
            '--variables',
            help='Inventory variables as JSON string'
        )

        # Enable/disable flags for instance group fallback
        fallback_group = parser.add_mutually_exclusive_group()
        fallback_group.add_argument(
            '--enable-instance-group-fallback',
            action='store_true',
            dest='enable_fallback',
            help='Allow instance group fallback'
        )
        fallback_group.add_argument(
            '--disable-instance-group-fallback',
            action='store_true',
            dest='disable_fallback',
            help='Disable instance group fallback'
        )

        return parser

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
            if getattr(parsed_args, 'host_filter', None):
                inventory_data['host_filter'] = parsed_args.host_filter
            if getattr(parsed_args, 'variables', None):
                try:
                    # Validate JSON format but store as string
                    json.loads(parsed_args.variables)
                    inventory_data['variables'] = parsed_args.variables
                except json.JSONDecodeError:
                    parser.error("argument --variables: must be valid JSON")

            # Handle enable/disable flags
            if parsed_args.enable_fallback:
                inventory_data['instance_group_fallback'] = True
            elif parsed_args.disable_fallback:
                inventory_data['instance_group_fallback'] = False

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
                print(f"Inventory '{inventory_data.get('name', '')}' updated successfully")

                return _format_inventory_data(inventory_data)
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
