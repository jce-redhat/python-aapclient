"""Credential commands for AAP Controller API."""
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
from aapclient.common.functions import resolve_organization_name


def resolve_credential_parameter(client, identifier):
    """
    Resolve credential identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Credential name or ID

    Returns:
        int: Credential ID

    Raises:
        AAPResourceNotFoundError: If credential not found by name or ID
    """
    # First try as credential name lookup
    try:
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for credential '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        credential_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return credential_id
        else:
            raise AAPResourceNotFoundError("Credential", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Credential", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Credential", identifier)


def _format_credential_data(credential_data):
    """
    Format credential data consistently

    Args:
        credential_data (dict): Credential data from API response

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract helper variables from summary_fields
    credential_type_info = credential_data.get('summary_fields', {}).get('credential_type', {})
    organization_info = credential_data.get('summary_fields', {}).get('organization', {})
    created_by = credential_data.get('summary_fields', {}).get('created_by', {})
    modified_by = credential_data.get('summary_fields', {}).get('modified_by', {})

    # Define comprehensive field mappings as ordered dictionary
    field_data = {
        'ID': str(credential_data.get('id', '')),
        'Name': credential_data.get('name', ''),
        'Description': credential_data.get('description', ''),
        'Organization': organization_info.get('name', '') or str(credential_data.get('organization', '')),
        'Credential Type': credential_type_info.get('name', '') or str(credential_data.get('credential_type', '')),
        'Kind': credential_data.get('kind', ''),
        'Cloud': str(credential_data.get('cloud')).lower(),
        'Kubernetes': str(credential_data.get('kubernetes')).lower(),
        'Inputs': str(credential_data.get('inputs', {})),
        'Created': credential_data.get('created', ''),
        'Created By': created_by.get('username', ''),
        'Modified': credential_data.get('modified', ''),
        'Modified By': modified_by.get('username', ''),
    }

    # Return all fields, displaying "None" for null values instead of filtering them out
    return list(field_data.keys()), list(field_data.values())


class CredentialListCommand(Lister):
    """List credentials from AAP Controller API."""

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
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query credentials endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Credential", "credentials endpoint")
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                data = response.json()

                # Extract credentials from results (already sorted by API)
                credentials = data.get('results', [])

                # Define columns for table display
                columns = [
                    'ID',
                    'Name',
                    'Credential Type'
                ]

                # Build rows data
                rows = []
                for credential in credentials:
                    # Get credential type name from summary_fields, fallback to ID
                    credential_type_info = credential.get('summary_fields', {}).get('credential_type', {})
                    credential_type_name = credential_type_info.get('name', credential.get('credential_type', ''))

                    row = [
                        credential.get('id', ''),
                        credential.get('name', ''),
                        credential_type_name,
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                raise AAPClientError(f"Controller API failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                # Pass through 400 status messages directly to user
                raise SystemExit(str(api_error))
            else:
                # Re-raise other API errors as client errors with context
                raise SystemExit(f"API Error: {api_error}")
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class CredentialShowCommand(ShowOne):
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
            help='Credential name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the credential show command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the credential
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                credential_id = parsed_args.id
            elif parsed_args.credential:
                # Use positional parameter - name first, then ID fallback if numeric
                credential_id = resolve_credential_parameter(client, parsed_args.credential)
            else:
                raise AAPClientError("Credential identifier is required")

            # Get specific credential
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/"
            try:
                response = client.get(endpoint)
                credential_data = response.json()

                return _format_credential_data(credential_data)

            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    raise AAPResourceNotFoundError("Credential", parsed_args.credential or parsed_args.id)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                # Pass through 400 status messages directly to user
                raise SystemExit(str(api_error))
            else:
                # Re-raise other API errors as client errors with context
                raise SystemExit(f"API Error: {api_error}")
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class CredentialCreateCommand(ShowOne):
    """Create a new credential."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Credential name'
        )
        parser.add_argument(
            '--description',
            help='Credential description'
        )
        parser.add_argument(
            '--organization',
            help='Organization'
        )
        parser.add_argument(
            '--credential-type',
            required=True,
            help='Credential type'
        )
        parser.add_argument(
            '--inputs',
            help='Credential inputs as JSON string'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the credential create command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Get parser for usage message
            parser = self.get_parser('aap credential create')

            # Resolve organization if provided
            org_id = None
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")

            credential_data = {
                'name': parsed_args.name,
                'credential_type': parsed_args.credential_type
            }

            # Add organization if provided
            if org_id is not None:
                credential_data['organization'] = org_id

            if parsed_args.description:
                credential_data['description'] = parsed_args.description
            if getattr(parsed_args, 'inputs', None):
                try:
                    import json
                    credential_data['inputs'] = json.loads(parsed_args.inputs)
                except json.JSONDecodeError:
                    parser.error("argument --inputs: must be valid JSON")

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
        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                # Pass through 400 status messages directly to user
                raise SystemExit(str(api_error))
            else:
                # Re-raise other API errors as client errors with context
                raise SystemExit(f"API Error: {api_error}")
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class CredentialSetCommand(ShowOne):
    """Update an existing credential."""

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
            help='Credential name or ID'
        )

        # Update fields
        parser.add_argument(
            '--name',
            help='Update credential name'
        )
        parser.add_argument(
            '--description',
            help='Update credential description'
        )
        parser.add_argument(
            '--organization',
            help='Update organization'
        )
        parser.add_argument(
            '--credential-type',
            help='Update credential type'
        )
        parser.add_argument(
            '--inputs',
            help='Update credential inputs as JSON string'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the credential set command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Get parser for usage message
            parser = self.get_parser('aap credential set')

            # Determine how to resolve the credential
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                credential_id = parsed_args.id
            elif parsed_args.credential:
                # Use positional parameter - name first, then ID fallback if numeric
                credential_id = resolve_credential_parameter(client, parsed_args.credential)
            else:
                raise AAPClientError("Credential identifier is required")

            # Resolve organization if provided
            org_id = None
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")

            # Prepare credential update data
            credential_data = {}

            if parsed_args.name:
                credential_data['name'] = parsed_args.name
            if parsed_args.description:
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
                raise AAPClientError("At least one field must be specified to update")

            # Update credential
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/"
            try:
                response = client.patch(endpoint, json=credential_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Credential", parsed_args.credential or parsed_args.id)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                credential_data = response.json()
                print(f"Credential '{credential_data.get('name', '')}' updated successfully")

                return _format_credential_data(credential_data)
            else:
                raise AAPClientError(f"Credential update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                # Pass through 400 status messages directly to user
                raise SystemExit(str(api_error))
            else:
                # Re-raise other API errors as client errors with context
                raise SystemExit(f"API Error: {api_error}")
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class CredentialDeleteCommand(Command):
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
            help='Credential name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the credential delete command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the credential
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                credential_id = parsed_args.id
                credential_identifier = str(parsed_args.id)
            elif parsed_args.credential:
                # Use positional parameter - name first, then ID fallback if numeric
                credential_id = resolve_credential_parameter(client, parsed_args.credential)
                credential_identifier = parsed_args.credential
            else:
                raise AAPClientError("Credential identifier is required")

            # Get credential details first for confirmation
            try:
                endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}credentials/{credential_id}/"
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Credential", credential_identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                credential_data = response.json()
                credential_name = credential_data.get('name', credential_identifier)

                # Delete credential
                try:
                    delete_response = client.delete(endpoint)
                except AAPAPIError as api_error:
                    if api_error.status_code == HTTP_NOT_FOUND:
                        # Handle 404 error with proper message
                        raise AAPResourceNotFoundError("Credential", credential_identifier)
                    elif api_error.status_code == HTTP_BAD_REQUEST:
                        # Pass through 400 status messages directly to user
                        raise SystemExit(str(api_error))
                    else:
                        # Re-raise other errors
                        raise

                if delete_response.status_code == HTTP_NO_CONTENT:
                    print(f"Credential '{credential_name}' deleted successfully")
                else:
                    raise AAPClientError(f"Credential deletion failed with status {delete_response.status_code}")
            else:
                raise AAPClientError(f"Failed to get credential details with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPAPIError as api_error:
            if api_error.status_code == HTTP_BAD_REQUEST:
                # Pass through 400 status messages directly to user
                raise SystemExit(str(api_error))
            else:
                # Re-raise other API errors as client errors with context
                raise SystemExit(f"API Error: {api_error}")
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
