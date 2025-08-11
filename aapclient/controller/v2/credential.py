"""Credential commands."""
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
    format_datetime
)





def _format_credential_data(credential_data, use_utc=False):
    """
    Format credential data consistently

    Args:
        credential_data (dict): Credential data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract credential details
    id_value = credential_data.get('id', '')
    name = credential_data.get('name', '')
    description = credential_data.get('description', '')
    credential_type = credential_data.get('credential_type_name', '')

    # Resolve organization name if available
    organization_name = ''
    if 'summary_fields' in credential_data and 'organization' in credential_data['summary_fields']:
        if credential_data['summary_fields']['organization']:
            organization_name = credential_data['summary_fields']['organization'].get('name', '')

    # Format datetime fields using common function
    created = format_datetime(credential_data.get('created', ''), use_utc)
    modified = format_datetime(credential_data.get('modified', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Credential Type',
        'Organization',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        name,
        description,
        credential_type,
        organization_name,
        created,
        modified
    ]

    return (columns, values)


class CredentialListCommand(AAPListCommand):
    """List credentials."""

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
        """Execute the credential list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query credentials endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "credentials endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                credentials = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Credential Type', 'Organization']
                rows = []

                for credential in credentials:
                    # Get organization name from summary_fields if available
                    org_name = ''
                    if 'summary_fields' in credential and 'organization' in credential['summary_fields']:
                        if credential['summary_fields']['organization']:
                            org_name = credential['summary_fields']['organization'].get('name', '')

                    row = [
                        credential.get('id', ''),
                        credential.get('name', ''),
                        credential.get('credential_type', ''),
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


class CredentialShowCommand(AAPShowCommand):
    """Show details of a specific credential."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Credential ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'credential',
            nargs='?',
            metavar='<credential>',
            help='Credential name or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the credential show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the credential
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                credential_id = parsed_args.id
            elif parsed_args.credential:
                # Use positional parameter - name first, then ID fallback if numeric
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
            else:
                raise AAPClientError("Credential identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                credential_data = response.json()
                return _format_credential_data(credential_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Credential", parsed_args.credential or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get credential: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class CredentialBaseCommand(AAPShowCommand):
    """Base class for credential create and set commands."""

    def add_common_arguments(self, parser, required_args=True):
        """Add common arguments for credential commands."""
        if required_args:
            # For create command
            parser.add_argument(
                'name',
                help='Credential name'
            )
            parser.add_argument(
                '--credential-type',
                required=True,
                type=int,
                help='Credential type ID'
            )
        else:
            # For set command
            parser.add_argument(
                '--id',
                type=int,
                help='Credential ID (overrides positional parameter)'
            )
            parser.add_argument(
                'credential',
                nargs='?',
                metavar='<credential>',
                help='Credential name or ID to update'
            )
            parser.add_argument(
                '--set-name',
                dest='set_name',
                help='New credential name'
            )
            parser.add_argument(
                '--credential-type',
                type=int,
                help='Credential type ID'
            )

        # Common arguments for both commands
        parser.add_argument(
            '--description',
            help='Credential description'
        )
        parser.add_argument(
            '--organization',
            help='Organization name or ID'
        )
        parser.add_argument(
            '--inputs',
            help='Credential inputs as JSON string'
        )

    def resolve_resources(self, client, parsed_args, for_create=True):
        """Resolve resource names to IDs."""
        resolved = {}

        if not for_create:
            # For set command - credential resolution
            if parsed_args.id:
                resolved['credential_id'] = parsed_args.id
            elif parsed_args.credential:
                resolved['credential_id'] = resolve_credential_name(client, parsed_args.credential, api="controller")
            else:
                raise AAPClientError("Credential identifier is required")

        # Organization resolution (optional for both commands)
        if getattr(parsed_args, 'organization', None):
            resolved['organization_id'] = resolve_organization_name(client, parsed_args.organization, api="controller")

        return resolved

    def build_credential_data(self, parsed_args, resolved_resources, for_create=True):
        """Build credential data for API requests."""
        credential_data = {}

        if for_create:
            credential_data['name'] = parsed_args.name
            credential_data['credential_type'] = parsed_args.credential_type
        else:
            # For set command
            if getattr(parsed_args, 'set_name', None):
                credential_data['name'] = parsed_args.set_name
            if hasattr(parsed_args, 'credential_type') and parsed_args.credential_type:
                credential_data['credential_type'] = parsed_args.credential_type

        # Common fields
        if hasattr(parsed_args, 'description') and parsed_args.description is not None:
            credential_data['description'] = parsed_args.description

        # Organization (optional)
        if 'organization_id' in resolved_resources:
            credential_data['organization'] = resolved_resources['organization_id']

        # Handle inputs with JSON validation
        if getattr(parsed_args, 'inputs', None):
            try:
                # Validate JSON format and parse it
                inputs = json.loads(parsed_args.inputs)
                credential_data['inputs'] = inputs
            except json.JSONDecodeError as e:
                raise AAPClientError(f"Invalid JSON in --inputs: {e}")

        return credential_data


class CredentialCreateCommand(CredentialBaseCommand):
    """Create a new credential."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=True)
        return parser

    def take_action(self, parsed_args):
        """Execute the credential create command."""
        try:
            client = self.controller_client

            # Resolve resources
            resolved_resources = self.resolve_resources(client, parsed_args, for_create=True)

            # Build credential data
            credential_data = self.build_credential_data(parsed_args, resolved_resources, for_create=True)

            # Create credential
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/"
            try:
                response = client.post(endpoint, json=credential_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Credential", parsed_args.name)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_CREATED:
                credential_data = response.json()
                print(f"Credential '{credential_data.get('name', '')}' created successfully")

                return _format_credential_data(credential_data)
            else:
                raise AAPClientError(f"Credential creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class CredentialSetCommand(CredentialBaseCommand):
    """Update an existing credential."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        self.add_common_arguments(parser, required_args=False)
        return parser

    def take_action(self, parsed_args):
        """Execute the credential set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap credential set')

            # Resolve credential - handle both ID and name
            credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")

            # Resolve organization if provided
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")
            else:
                org_id = None

            # Prepare credential update data
            credential_data = {}

            if parsed_args.set_name:
                credential_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:  # Allow empty string
                credential_data['description'] = parsed_args.description
            if org_id is not None:
                credential_data['organization'] = org_id
            if getattr(parsed_args, 'credential_type', None):
                credential_data['credential_type'] = parsed_args.credential_type
            if getattr(parsed_args, 'inputs', None):
                try:
                    import json
                    credential_data['inputs'] = json.loads(parsed_args.inputs)
                except json.JSONDecodeError:
                    parser.error("argument --inputs: must be valid JSON")

            if not credential_data:
                parser.error("No update fields provided")

            # Update credential
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/"
            try:
                response = client.patch(endpoint, json=credential_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.credential)

            if response.status_code == HTTP_OK:
                credential_data = response.json()
                print(f"Credential '{credential_data.get('name', '')}' updated successfully")

                return _format_credential_data(credential_data)
            else:
                raise AAPClientError(f"Credential update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class CredentialDeleteCommand(AAPCommand):
    """Delete a credential."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Credential ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'credential',
            nargs='?',
            metavar='<credential>',
            help='Credential name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the credential delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the credential
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                credential_id = parsed_args.id
            elif parsed_args.credential:
                # Use positional parameter - name first, then ID fallback if numeric
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
            else:
                raise AAPClientError("Credential identifier is required")

            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Credential '{parsed_args.credential or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Credential", parsed_args.credential or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete credential: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
