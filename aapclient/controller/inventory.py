"""Inventory commands."""

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.client import AAPHTTPClient
from aapclient.common.config import AAPConfig
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_ACCEPTED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import resolve_organization_name, resolve_inventory_name





def _format_inventory_data(inventory_data):
    """
    Format inventory data for display.

    Args:
        inventory_data (dict): Inventory data from API response

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract helper variables from summary_fields
    organization_info = inventory_data.get('summary_fields', {}).get('organization', {})
    created_by = inventory_data.get('summary_fields', {}).get('created_by', {})
    modified_by = inventory_data.get('summary_fields', {}).get('modified_by', {})

    # Handle organization display using summary_fields pattern
    org_display = organization_info.get('name', '')
    if not org_display:
        # Fall back to raw organization value, but handle None case
        org_value = inventory_data.get('organization')
        if org_value is not None:
            org_display = str(org_value)
        else:
            org_display = "None"

    # Handle inventory type (kind field)
    inventory_type = inventory_data.get('kind', '') or 'inventory'

    # Compute status based on failure indicators
    sources_with_failures = inventory_data.get('inventory_sources_with_failures', 0)

    if sources_with_failures > 0:
        status = "Error"
    else:
        status = "Ready"

    # Define comprehensive field mappings as ordered dictionary
    field_data = {
        'ID': str(inventory_data.get('id', '')),
        'Name': inventory_data.get('name', ''),
        'Description': inventory_data.get('description', ''),
        'Organization': org_display,
        'Type': inventory_type,
        'Status': status,
        'Variables': inventory_data.get('variables', ''),
        'Inventory Sources': str(inventory_data.get('total_inventory_sources', 0)),
        'Sources with Failures': str(inventory_data.get('inventory_sources_with_failures', 0)),
        'Prevent Instance Group Fallback': "Yes" if inventory_data.get('prevent_instance_group_fallback', False) else "No",
        'Created': inventory_data.get('created', ''),
        'Created By': created_by.get('username', ''),
        'Modified': inventory_data.get('modified', ''),
        'Modified By': modified_by.get('username', ''),
    }

    # Return all fields
    return list(field_data.keys()), list(field_data.values())


class InventoryListCommand(Lister):
    """List inventories."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/"
            params = {'order_by': 'id'}  # Sort by ID on server side
            response = client.get(endpoint, params=params)

            if response.status_code == HTTP_OK:
                data = response.json()
                results = data.get('results', [])

                columns = ('ID', 'Name', 'Status', 'Type', 'Organization')
                inventory_data = []

                for inventory in results:
                    # Get organization name from summary_fields, same pattern as other commands
                    organization_info = inventory.get('summary_fields', {}).get('organization', {})
                    org_display = organization_info.get('name', '')
                    if not org_display:
                        # Fall back to raw organization value, but handle None case
                        org_value = inventory.get('organization')
                        if org_value is not None:
                            org_display = str(org_value)
                        else:
                            org_display = "None"

                    # Handle inventory type (kind field)
                    inventory_type = inventory.get('kind', '') or 'inventory'

                    # Compute status based on failure indicators
                    sources_with_failures = inventory.get('inventory_sources_with_failures', 0)

                    if sources_with_failures > 0:
                        status = "Error"
                    else:
                        status = "Ready"

                    inventory_data.append((
                        inventory.get('id', ''),
                        inventory.get('name', ''),
                        status,
                        inventory_type,
                        org_display
                    ))

                return (columns, inventory_data)
            else:
                raise AAPClientError(f"Failed to list inventories: {response.status_code}")

        except AAPAPIError as e:
            raise AAPClientError(f"API error: {e}")


class InventoryShowCommand(ShowOne):
    """Show inventory details."""

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
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
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
        except AAPAPIError as e:
            if e.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Inventory", parsed_args.inventory or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {e}")


class InventoryCreateCommand(ShowOne):
    """Create a new static inventory in AAP"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Name of the inventory to create'
        )
        parser.add_argument(
            '--description',
            help='Description of the inventory'
        )
        parser.add_argument(
            '--organization',
            required=True,
            help='Organization name or ID for the inventory'
        )
        parser.add_argument(
            '--variables',
            help='Variables for the inventory in YAML/JSON format'
        )
        parser.add_argument(
            '--prevent-instance-group-fallback',
            action='store_true',
            dest='prevent_instance_group_fallback',
            help='Prevent instance group fallback'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Get parser for usage message
            parser = self.get_parser('aap inventory create')

            # Resolve organization
            org_id = resolve_organization_name(client, parsed_args.organization, api="controller")

            inventory_data = {
                'name': parsed_args.name,
                'organization': org_id,
                'kind': ''  # Empty string indicates a static inventory
            }

            # Add optional fields
            if parsed_args.description:
                inventory_data['description'] = parsed_args.description
            if parsed_args.variables:
                inventory_data['variables'] = parsed_args.variables

            # Handle instance group fallback boolean
            if parsed_args.prevent_instance_group_fallback:
                inventory_data['prevent_instance_group_fallback'] = True
            # If flag is not specified, let the API use its default

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/"
            response = client.post(endpoint, json=inventory_data)

            if response.status_code == HTTP_CREATED:
                inventory_data = response.json()
                print(f"Inventory '{parsed_args.name}' created successfully")
                return _format_inventory_data(inventory_data)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                if isinstance(error_data, dict):
                    for field, messages in error_data.items():
                        if isinstance(messages, list):
                            for message in messages:
                                print(f"{field}: {message}")
                        else:
                            print(f"{field}: {messages}")
                else:
                    print(f"Error: {error_data}")
                parser.error("Inventory creation failed due to validation errors")
            else:
                raise AAPClientError(f"Failed to create inventory: {response.status_code}")

        except AAPResourceNotFoundError as e:
            parser.error(str(e))
        except AAPAPIError as e:
            if e.status_code == HTTP_BAD_REQUEST:
                parser.error(f"Bad request: {e}")
            else:
                raise AAPClientError(f"API error: {e}")


class InventorySetCommand(ShowOne):
    """Update an existing inventory."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'inventory',
            metavar='<inventory>',
            help='Inventory name or ID to update'
        )
        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='New name for the inventory'
        )
        parser.add_argument(
            '--description',
            help='New description for the inventory'
        )
        parser.add_argument(
            '--organization',
            help='New organization name or ID for the inventory'
        )
        parser.add_argument(
            '--variables',
            help='New variables for the inventory in YAML/JSON format'
        )

        # Mutually exclusive group for instance group fallback settings
        fallback_group = parser.add_mutually_exclusive_group()
        fallback_group.add_argument(
            '--prevent-instance-group-fallback',
            action='store_true',
            dest='prevent_instance_group_fallback',
            help='Prevent instance group fallback'
        )
        fallback_group.add_argument(
            '--allow-instance-group-fallback',
            action='store_true',
            dest='allow_instance_group_fallback',
            help='Allow instance group fallback'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
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
            if parsed_args.variables is not None:  # Allow empty string
                inventory_data['variables'] = parsed_args.variables

            # Handle instance group fallback boolean
            if parsed_args.prevent_instance_group_fallback:
                inventory_data['prevent_instance_group_fallback'] = True
            elif parsed_args.allow_instance_group_fallback:
                inventory_data['prevent_instance_group_fallback'] = False

            if not inventory_data:
                parser.error("At least one field must be specified to update")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}inventories/{inventory_id}/"
            response = client.patch(endpoint, json=inventory_data)

            if response.status_code == HTTP_OK:
                inventory_data = response.json()
                print(f"Inventory '{parsed_args.inventory}' updated successfully")
                return _format_inventory_data(inventory_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Inventory", parsed_args.inventory)
            elif response.status_code == HTTP_BAD_REQUEST:
                error_data = response.json()
                if isinstance(error_data, dict):
                    for field, messages in error_data.items():
                        if isinstance(messages, list):
                            for message in messages:
                                print(f"{field}: {message}")
                        else:
                            print(f"{field}: {messages}")
                else:
                    print(f"Error: {error_data}")
                parser.error("Inventory update failed due to validation errors")
            else:
                raise AAPClientError(f"Failed to update inventory: {response.status_code}")

        except AAPResourceNotFoundError as e:
            parser.error(str(e))
        except AAPAPIError as e:
            if e.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Inventory", parsed_args.inventory)
            elif e.status_code == HTTP_BAD_REQUEST:
                parser.error(f"Bad request: {e}")
            else:
                raise AAPClientError(f"API error: {e}")


class InventoryDeleteCommand(Command):
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
            help='Inventory name or ID to delete'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
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

        except AAPResourceNotFoundError as e:
            parser = self.get_parser('aap inventory delete')
            parser.error(str(e))
        except AAPAPIError as e:
            if e.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Inventory", parsed_args.inventory or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {e}")
