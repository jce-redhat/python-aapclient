"""Execution Environment commands."""
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
    resolve_credential_name,
    resolve_execution_environment_name,
    format_datetime
)




def _format_execution_environment_data(ee_data, use_utc=False):
    """
    Format execution environment data consistently

    Args:
        ee_data (dict): Execution environment data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract execution environment details
    id_value = ee_data.get('id', '')
    name = ee_data.get('name', '')
    description = ee_data.get('description', '')
    image = ee_data.get('image', '')
    organization_name = ''
    credential_name = ''

    # Resolve organization name if available
    if 'summary_fields' in ee_data and 'organization' in ee_data['summary_fields']:
        if ee_data['summary_fields']['organization']:
            organization_name = ee_data['summary_fields']['organization'].get('name', '')

    # Resolve credential name if available
    if 'summary_fields' in ee_data and 'credential' in ee_data['summary_fields']:
        if ee_data['summary_fields']['credential']:
            credential_name = ee_data['summary_fields']['credential'].get('name', '')

    pull = ee_data.get('pull', '')
    created = format_datetime(ee_data.get('created', ''), use_utc)
    modified = format_datetime(ee_data.get('modified', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Image',
        'Organization',
        'Credential',
        'Pull',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        name,
        description,
        image,
        organization_name,
        credential_name,
        pull,
        created,
        modified
    ]

    return (columns, values)


class ExecutionEnvironmentListCommand(AAPListCommand):
    """List execution environments."""

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
        """Execute the execution environment list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query execution environments endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "execution_environments endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                execution_environments = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Image', 'Organization']
                rows = []

                for ee in execution_environments:
                    # Get organization name from summary_fields if available
                    org_name = ''
                    if 'summary_fields' in ee and 'organization' in ee['summary_fields']:
                        if ee['summary_fields']['organization']:
                            org_name = ee['summary_fields']['organization'].get('name', '')

                    row = [
                        ee.get('id', ''),
                        ee.get('name', ''),
                        ee.get('image', ''),
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


class ExecutionEnvironmentShowCommand(AAPShowCommand):
    """Show details of a specific execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Execution Environment ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'execution_environment',
            nargs='?',
            metavar='<execution_environment>',
            help='Execution Environment name or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the execution environment show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the execution environment
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                ee_id = parsed_args.id
            elif parsed_args.execution_environment:
                # Use positional parameter - name first, then ID fallback if numeric
                ee_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")
            else:
                raise AAPClientError("Execution Environment identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                ee_data = response.json()
                return _format_execution_environment_data(ee_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get execution environment: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class ExecutionEnvironmentBaseCommand(AAPShowCommand):
    """Base class for execution environment create and set commands."""

    def add_common_arguments(self, parser, required_args=True):
        """Add common arguments for execution environment commands."""
        if required_args:
            # For create command
            parser.add_argument(
                'name',
                help='Execution Environment name'
            )
            parser.add_argument(
                '--image',
                required=True,
                help='Container image for this execution environment'
            )
        else:
            # For set command
            parser.add_argument(
                '--id',
                type=int,
                help='Execution Environment ID (overrides positional parameter)'
            )
            parser.add_argument(
                'execution_environment',
                nargs='?',
                metavar='<execution_environment>',
                help='Execution Environment name or ID to update'
            )
            parser.add_argument(
                '--set-name',
                dest='set_name',
                help='New execution environment name'
            )
            parser.add_argument(
                '--image',
                help='Container image for this execution environment'
            )

        # Common arguments for both commands
        parser.add_argument(
            '--description',
            help='Execution Environment description'
        )
        parser.add_argument(
            '--organization',
            help='Organization name or ID'
        )
        parser.add_argument(
            '--credential',
            help='Container Registry credential name or ID'
        )
        parser.add_argument(
            '--pull',
            choices=['always', 'missing', 'never'],
            help='Pull policy for execution environment image'
        )

    def resolve_resources(self, client, parsed_args, for_create=True):
        """Resolve resource names to IDs."""
        resolved_resources = {}

        if for_create:
            # For create command, resolve optional organization and credential
            if getattr(parsed_args, 'organization', None):
                resolved_resources['organization_id'] = resolve_organization_name(
                    client, parsed_args.organization, api="controller"
                )

            if getattr(parsed_args, 'credential', None):
                resolved_resources['credential_id'] = resolve_credential_name(
                    client, parsed_args.credential, api="controller"
                )
        else:
            # For set command, resolve execution environment
            ee_identifier = getattr(parsed_args, 'id', None) or parsed_args.execution_environment
            if not ee_identifier:
                parser = self.get_parser('aap execution-environment set')
                parser.error("Execution Environment name/ID is required")

            resolved_resources['ee_id'] = resolve_execution_environment_name(
                client, ee_identifier, api="controller"
            )

            # Resolve optional organization and credential for set
            if getattr(parsed_args, 'organization', None):
                resolved_resources['organization_id'] = resolve_organization_name(
                    client, parsed_args.organization, api="controller"
                )

            if getattr(parsed_args, 'credential', None):
                resolved_resources['credential_id'] = resolve_credential_name(
                    client, parsed_args.credential, api="controller"
                )

        return resolved_resources

    def build_ee_data(self, parsed_args, resolved_resources, for_create=True):
        """Build execution environment data dictionary for API requests."""
        ee_data = {}

        if for_create:
            # Required fields for create
            ee_data['name'] = parsed_args.name
            ee_data['image'] = parsed_args.image
        else:
            # Optional name and image update for set
            if getattr(parsed_args, 'set_name', None):
                ee_data['name'] = parsed_args.set_name
            if getattr(parsed_args, 'image', None):
                ee_data['image'] = parsed_args.image

        # Common optional fields
        for field in ['description']:
            value = getattr(parsed_args, field, None)
            if value is not None:
                ee_data[field] = value

        # Handle pull policy
        if getattr(parsed_args, 'pull', None):
            ee_data['pull'] = parsed_args.pull

        # Handle resolved resources
        if 'organization_id' in resolved_resources:
            ee_data['organization'] = resolved_resources['organization_id']

        if 'credential_id' in resolved_resources:
            ee_data['credential'] = resolved_resources['credential_id']

        return ee_data


class ExecutionEnvironmentCreateCommand(ExecutionEnvironmentBaseCommand):
    """Create a new execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=True)
        return parser

    def take_action(self, parsed_args):
        """Execute the execution environment create command."""
        try:
            client = self.controller_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=True)

            # Build execution environment data
            ee_data = self.build_ee_data(parsed_args, resolved_resources, for_create=True)

            # Create execution environment
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/"
            try:
                response = client.post(endpoint, json=ee_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.name)

            if response.status_code == HTTP_CREATED:
                ee_data = response.json()
                print(f"Execution Environment '{ee_data.get('name', '')}' created successfully")

                return _format_execution_environment_data(ee_data)
            else:
                raise AAPClientError(f"Execution Environment creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ExecutionEnvironmentSetCommand(ExecutionEnvironmentBaseCommand):
    """Update an existing execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=False)
        return parser

    def take_action(self, parsed_args):
        """Execute the execution environment set command."""
        try:
            client = self.controller_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=False)
            ee_id = resolved_resources['ee_id']

            # Build execution environment data
            ee_data = self.build_ee_data(parsed_args, resolved_resources, for_create=False)

            if not ee_data:
                parser = self.get_parser('aap execution-environment set')
                parser.error("No update fields provided")

            # Update execution environment
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/"
            try:
                response = client.patch(endpoint, json=ee_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.execution_environment)

            if response.status_code == HTTP_OK:
                ee_data = response.json()
                print(f"Execution Environment '{ee_data.get('name', '')}' updated successfully")

                return _format_execution_environment_data(ee_data)
            else:
                raise AAPClientError(f"Execution Environment update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ExecutionEnvironmentDeleteCommand(AAPCommand):
    """Delete an execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Execution Environment ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'execution_environment',
            nargs='?',
            metavar='<execution_environment>',
            help='Execution Environment name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the execution environment delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the execution environment
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                ee_id = parsed_args.id
            elif parsed_args.execution_environment:
                # Use positional parameter - name first, then ID fallback if numeric
                ee_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")
            else:
                raise AAPClientError("Execution Environment identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Execution Environment '{parsed_args.execution_environment or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete execution environment: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
