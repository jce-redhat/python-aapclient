"""Execution Environment commands."""

from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne

from aapclient.common.client import AAPHTTPClient
from aapclient.common.config import AAPConfig
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import resolve_organization_name, resolve_execution_environment_name, resolve_credential_name





def _format_execution_environment_data(execution_environment_data):
    """Format execution environment data for display."""
    # Extract helper variables from summary_fields
    organization_info = execution_environment_data.get('summary_fields', {}).get('organization', {})
    created_by = execution_environment_data.get('summary_fields', {}).get('created_by', {})
    modified_by = execution_environment_data.get('summary_fields', {}).get('modified_by', {})

    # Handle organization display using summary_fields pattern
    org_display = organization_info.get('name', '')
    if not org_display:
        # Fall back to raw organization value, but handle None case
        org_value = execution_environment_data.get('organization')
        if org_value is not None:
            org_display = str(org_value)
        else:
            org_display = "Global"

    field_data = {
        'ID': execution_environment_data.get('id', ''),
        'Name': execution_environment_data.get('name', ''),
        'Description': execution_environment_data.get('description', ''),
        'Organization': org_display,
        'Image': execution_environment_data.get('image', ''),
        'Managed': "Yes" if execution_environment_data.get('managed', False) else "No",
        'Pull': execution_environment_data.get('pull', ''),
        'Credential': execution_environment_data.get('credential', ''),
        'Created': execution_environment_data.get('created', ''),
        'Created By': created_by.get('username', ''),
        'Modified': execution_environment_data.get('modified', ''),
        'Modified By': modified_by.get('username', ''),
    }

    return (field_data.keys(), field_data.values())


class ExecutionEnvironmentListCommand(Lister):
    """List execution environments."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--all',
            action='store_true',
            help='Show all execution environments (default behavior)'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/"
            params = {'order_by': 'id'}  # Sort by ID on server side
            response = client.get(endpoint, params=params)

            if response.status_code == HTTP_OK:
                data = response.json()
                results = data.get('results', [])

                columns = ('ID', 'Name', 'Image', 'Organization')
                execution_environment_data = []

                for execution_environment in results:
                    # Get organization name from summary_fields, same pattern as show command
                    organization_info = execution_environment.get('summary_fields', {}).get('organization', {})
                    org_display = organization_info.get('name', '')
                    if not org_display:
                        # Fall back to raw organization value, but handle None case
                        org_value = execution_environment.get('organization')
                        if org_value is not None:
                            org_display = str(org_value)
                        else:
                            org_display = "Global"

                    execution_environment_data.append((
                        execution_environment.get('id', ''),
                        execution_environment.get('name', ''),
                        execution_environment.get('image', ''),
                        org_display
                    ))

                return (columns, execution_environment_data)
            else:
                raise AAPClientError(f"Failed to list execution environments: {response.status_code}")

        except AAPAPIError as e:
            raise AAPClientError(f"API error: {e}")


class ExecutionEnvironmentShowCommand(ShowOne):
    """Show execution environment details."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Execution environment ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'execution_environment',
            nargs='?',
            metavar='<execution_environment>',
            help='Execution environment name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Determine how to resolve the execution environment
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                execution_environment_id = parsed_args.id
            elif parsed_args.execution_environment:
                # Use positional parameter - name first, then ID fallback if numeric
                execution_environment_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")
            else:
                raise AAPClientError("Execution environment identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{execution_environment_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                execution_environment_data = response.json()
                return _format_execution_environment_data(execution_environment_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get execution environment: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPAPIError as e:
            if e.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {e}")


class ExecutionEnvironmentCreateCommand(ShowOne):
    """Create execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            metavar='<name>',
            help='Name of the execution environment'
        )
        parser.add_argument(
            '--image',
            required=True,
            help='Container image for the execution environment'
        )
        parser.add_argument(
            '--description',
            help='Description of the execution environment'
        )
        parser.add_argument(
            '--organization',
            help='Organization name or ID for the execution environment'
        )
        parser.add_argument(
            '--credential',
            help='Credential name or ID for pulling the container image'
        )
        parser.add_argument(
            '--pull',
            choices=['always', 'missing', 'never'],
            default='missing',
            help='Pull policy for the container image (default: missing)'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Get parser for usage message
            parser = self.get_parser('aap execution-environment create')

            # Resolve organization if provided
            org_id = None
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")

            execution_environment_data = {
                'name': parsed_args.name,
                'image': parsed_args.image,
                'pull': parsed_args.pull
            }

            # Add optional fields
            if parsed_args.description:
                execution_environment_data['description'] = parsed_args.description
            if org_id is not None:
                execution_environment_data['organization'] = org_id
            if parsed_args.credential:
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
                execution_environment_data['credential'] = credential_id

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/"
            response = client.post(endpoint, json=execution_environment_data)

            if response.status_code == HTTP_CREATED:
                execution_environment_data = response.json()
                print(f"Execution environment '{parsed_args.name}' created successfully")
                return _format_execution_environment_data(execution_environment_data)
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
                parser.error("Execution environment creation failed due to validation errors")
            else:
                raise AAPClientError(f"Failed to create execution environment: {response.status_code}")

        except AAPResourceNotFoundError as e:
            parser.error(str(e))
        except AAPAPIError as e:
            if e.status_code == HTTP_BAD_REQUEST:
                parser.error(f"Bad request: {e}")
            else:
                raise AAPClientError(f"API error: {e}")


class ExecutionEnvironmentSetCommand(ShowOne):
    """Update execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'execution_environment',
            metavar='<execution_environment>',
            help='Execution environment name or ID to update'
        )
        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='New name for the execution environment'
        )
        parser.add_argument(
            '--image',
            help='New container image for the execution environment'
        )
        parser.add_argument(
            '--description',
            help='New description for the execution environment'
        )
        parser.add_argument(
            '--organization',
            help='New organization name or ID for the execution environment'
        )
        parser.add_argument(
            '--credential',
            help='New credential name or ID for pulling the container image'
        )
        parser.add_argument(
            '--pull',
            choices=['always', 'missing', 'never'],
            help='New pull policy for the container image'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Get parser for usage message
            parser = self.get_parser('aap execution-environment set')

            # Resolve execution environment - handle both ID and name
            execution_environment_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")

            # Resolve organization if provided
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")
            else:
                org_id = None

            # Prepare execution environment update data
            execution_environment_data = {}

            if parsed_args.set_name:
                execution_environment_data['name'] = parsed_args.set_name
            if parsed_args.image:
                execution_environment_data['image'] = parsed_args.image
            if parsed_args.description:
                execution_environment_data['description'] = parsed_args.description
            if org_id is not None:
                execution_environment_data['organization'] = org_id
            if parsed_args.credential:
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
                execution_environment_data['credential'] = credential_id
            if parsed_args.pull:
                execution_environment_data['pull'] = parsed_args.pull

            if not execution_environment_data:
                parser.error("At least one field must be specified to update")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{execution_environment_id}/"
            response = client.patch(endpoint, json=execution_environment_data)

            if response.status_code == HTTP_OK:
                execution_environment_data = response.json()
                print(f"Execution environment '{parsed_args.execution_environment}' updated successfully")
                return _format_execution_environment_data(execution_environment_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment)
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
                parser.error("Execution environment update failed due to validation errors")
            else:
                raise AAPClientError(f"Failed to update execution environment: {response.status_code}")

        except AAPResourceNotFoundError as e:
            parser.error(str(e))
        except AAPAPIError as e:
            if e.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment)
            elif e.status_code == HTTP_BAD_REQUEST:
                parser.error(f"Bad request: {e}")
            else:
                raise AAPClientError(f"API error: {e}")


class ExecutionEnvironmentDeleteCommand(Command):
    """Delete execution environment."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Execution environment ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'execution_environment',
            nargs='?',
            metavar='<execution_environment>',
            help='Execution environment name or ID to delete'
        )
        return parser

    def take_action(self, parsed_args):
        config = AAPConfig()
        config.validate()

        # Create HTTP client
        client = AAPHTTPClient(config)

        try:
            # Determine how to resolve the execution environment
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                execution_environment_id = parsed_args.id
            elif parsed_args.execution_environment:
                # Use positional parameter - name first, then ID fallback if numeric
                execution_environment_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")
            else:
                raise AAPClientError("Execution environment identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}execution_environments/{execution_environment_id}/"
            response = client.delete(endpoint)

            if response.status_code == HTTP_NO_CONTENT:
                print(f"Execution environment '{parsed_args.execution_environment or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete execution environment: {response.status_code}")

        except AAPResourceNotFoundError as e:
            parser = self.get_parser('aap execution-environment delete')
            parser.error(str(e))
        except AAPAPIError as e:
            if e.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Execution Environment", parsed_args.execution_environment or parsed_args.id)
            else:
                raise AAPClientError(f"API error: {e}")
