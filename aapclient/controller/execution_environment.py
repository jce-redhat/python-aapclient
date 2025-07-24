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
from aapclient.common.functions import resolve_organization_name, resolve_credential_name, resolve_execution_environment_name




def _format_execution_environment_data(ee_data):
    """
    Format execution environment data consistently

    Args:
        ee_data (dict): Execution environment data from API response

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
    created = ee_data.get('created', '')
    modified = ee_data.get('modified', '')

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
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Execution Environment", "execution_environments endpoint")
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

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
                return _format_execution_environment_data(ee_data)
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


class ExecutionEnvironmentCreateCommand(AAPShowCommand):
    """Create a new execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Execution Environment name'
        )
        parser.add_argument(
            '--image',
            required=True,
            help='Container image for this execution environment'
        )
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
        return parser

    def take_action(self, parsed_args):
        """Execute the execution environment create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap execution-environment create')

            # Resolve organization if provided
            org_id = None
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")

            # Resolve credential if provided
            credential_id = None
            if getattr(parsed_args, 'credential', None):
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")

            ee_data = {
                'name': parsed_args.name,
                'image': parsed_args.image
            }

            # Add optional fields
            if org_id is not None:
                ee_data['organization'] = org_id
            if credential_id is not None:
                ee_data['credential'] = credential_id
            if parsed_args.description:
                ee_data['description'] = parsed_args.description
            if getattr(parsed_args, 'pull', None):
                ee_data['pull'] = parsed_args.pull

            # Create execution environment
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/"
            try:
                response = client.post(endpoint, json=ee_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Execution Environment", parsed_args.name)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Format 400 errors properly using parser.error
                    parser = self.get_parser('aap execution-environment create')
                    parser.error(f"Bad request: {api_error}")
                else:
                    # Re-raise other errors
                    raise

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


class ExecutionEnvironmentSetCommand(AAPShowCommand):
    """Update an existing execution environment."""

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
        return parser

    def take_action(self, parsed_args):
        """Execute the execution environment set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap execution-environment set')

            # Resolve execution environment - handle both ID and name
            ee_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")

            # Resolve organization if provided
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")
            else:
                org_id = None

            # Resolve credential if provided
            if getattr(parsed_args, 'credential', None):
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
            else:
                credential_id = None

            # Prepare execution environment update data
            ee_data = {}

            if parsed_args.set_name:
                ee_data['name'] = parsed_args.set_name
            if getattr(parsed_args, 'image', None):
                ee_data['image'] = parsed_args.image
            if parsed_args.description is not None:  # Allow empty string
                ee_data['description'] = parsed_args.description
            if org_id is not None:
                ee_data['organization'] = org_id
            if credential_id is not None:
                ee_data['credential'] = credential_id
            if getattr(parsed_args, 'pull', None):
                ee_data['pull'] = parsed_args.pull

            if not ee_data:
                parser.error("No update fields provided")

            # Update execution environment
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{ee_id}/"
            try:
                response = client.patch(endpoint, json=ee_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Format 400 errors properly using parser.error
                    parser = self.get_parser('aap execution-environment set')
                    parser.error(f"Bad request: {api_error}")
                else:
                    # Re-raise other errors
                    raise

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
