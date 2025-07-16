"""Organization commands for AAP Gateway API."""
from cliff.command import Command
from cliff.lister import Lister
from cliff.show import ShowOne
from aapclient.common.client import AAPHTTPClient
from aapclient.common.config import AAPConfig
from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError


class OrganizationListCommand(Lister):
    """List organizations from AAP Gateway API."""

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
        """Execute the organization list command."""
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

            # Query organizations endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                data = response.json()

                # Extract organizations from results (already sorted by API)
                organizations = data.get('results', [])

                # Define columns for table display
                columns = [
                    'ID',
                    'Name',
                    'Description',
                    'Managed',
                    'Users',
                    'Teams'
                ]

                # Build rows data
                rows = []
                for org in organizations:
                    row = [
                        org.get('id', ''),
                        org.get('name', ''),
                        org.get('description', ''),
                        'Yes' if org.get('managed', False) else 'No',
                        org.get('summary_fields', {}).get('related_field_counts', {}).get('users', 0),
                        org.get('summary_fields', {}).get('related_field_counts', {}).get('teams', 0)
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                raise AAPClientError(f"Gateway API failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class OrganizationShowCommand(ShowOne):
    """Show details of a specific organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Organization ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'organization',
            nargs='?',
            help='Organization name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the organization show command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the organization
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                organization_id = parsed_args.id
            elif parsed_args.organization:
                # Use positional parameter - name first, then ID fallback if numeric
                organization_id = self._resolve_organization_positional(client, parsed_args.organization)
            else:
                raise AAPClientError("Organization identifier is required")

            # Get specific organization
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
            try:
                response = client.get(endpoint)
                org_data = response.json()

                # Prepare data using dictionary for cleaner code
                related_counts = org_data.get('summary_fields', {}).get('related_field_counts', {})
                created_by = org_data.get('summary_fields', {}).get('created_by', {})
                modified_by = org_data.get('summary_fields', {}).get('modified_by', {})

                # Define field mappings as ordered dictionary
                field_data = {
                    'ID': str(org_data.get('id', '')),
                    'Name': org_data.get('name', ''),
                    'Description': org_data.get('description', ''),
                    'Managed': 'Yes' if org_data.get('managed', False) else 'No',
                    'Users': str(related_counts.get('users', 0)),
                    'Teams': str(related_counts.get('teams', 0)),
                    'Created': org_data.get('created', ''),
                    'Created By': created_by.get('username', '') if created_by else '',
                    'Modified': org_data.get('modified', ''),
                    'Modified By': modified_by.get('username', '') if modified_by else ''
                }

                # Convert to columns and values for Cliff formatting
                columns = []
                values = []
                for column_name, value in field_data.items():
                    columns.append(column_name)
                    values.append(value)

                return (columns, values)
            except AAPAPIError as api_error:
                # Check if it's a 404 error from the API
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Use consistent error message for both --id and positional parameter
                    identifier = str(parsed_args.id) if parsed_args.id else parsed_args.organization
                    raise AAPResourceNotFoundError("Organization", identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")

    def _resolve_organization_positional(self, client, identifier):
        """Resolve positional parameter - try name first, then ID fallback if numeric."""
        # First try as name lookup
        try:
            return self._resolve_organization_by_name(client, identifier)
        except AAPClientError:
            # If name lookup fails and identifier is numeric, try as ID
            try:
                org_id = int(identifier)
                # Verify the ID exists by trying to get it
                endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{org_id}/"
                response = client.get(endpoint)
                if response.status_code == HTTP_OK:
                    return org_id
                else:
                    raise AAPResourceNotFoundError("Organization", identifier)
            except ValueError:
                # Not a valid integer, and name lookup already failed
                raise AAPResourceNotFoundError("Organization", identifier)
            except Exception:
                # Catch any other errors (like API errors) during ID lookup
                raise AAPResourceNotFoundError("Organization", identifier)

    def _resolve_organization_by_name(self, client, name):
        """Resolve organization name to ID."""
        endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
        params = {'name': name}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                raise AAPResourceNotFoundError("Organization", name)
        else:
            raise AAPClientError(f"Failed to search for organization '{name}'")


class OrganizationCreateCommand(ShowOne):
    """Create a new organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Organization name'
        )
        parser.add_argument(
            '--description',
            help='Organization description'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the organization create command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Prepare organization data
            org_data = {
                'name': parsed_args.name
            }

            if parsed_args.description:
                org_data['description'] = parsed_args.description

            # Create organization
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
            try:
                response = client.post(endpoint, json=org_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_CREATED:
                org_data = response.json()

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # Basic information
                columns.append('ID')
                values.append(str(org_data.get('id', '')))

                columns.append('Name')
                values.append(org_data.get('name', ''))

                columns.append('Description')
                values.append(org_data.get('description', ''))

                columns.append('Managed')
                values.append('Yes' if org_data.get('managed', False) else 'No')

                # Creation info
                columns.append('Created')
                values.append(org_data.get('created', ''))

                columns.append('Created By')
                created_by = org_data.get('summary_fields', {}).get('created_by', {})
                values.append(created_by.get('username', '') if created_by else '')

                return (columns, values)
            else:
                error_msg = f"Failed to create organization: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        error_msg += f" - {error_data['detail']}"
                    elif isinstance(error_data, dict):
                        # Handle field-specific errors
                        for field, errors in error_data.items():
                            if isinstance(errors, list):
                                error_msg += f" - {field}: {', '.join(errors)}"
                            else:
                                error_msg += f" - {field}: {errors}"
                except:
                    pass
                raise AAPClientError(error_msg)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class OrganizationSetCommand(ShowOne):
    """Set/update an existing organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Organization ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'organization',
            nargs='?',
            help='Organization name or ID'
        )

        # Set fields
        parser.add_argument(
            '--name',
            help='Set organization name'
        )
        parser.add_argument(
            '--description',
            help='Set organization description'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the organization set command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the organization
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                organization_id = parsed_args.id
            elif parsed_args.organization:
                # Use positional parameter - name first, then ID fallback if numeric
                organization_id = self._resolve_organization_positional(client, parsed_args.organization)
            else:
                raise AAPClientError("Organization identifier is required")

            # Prepare data to set
            set_data = {}
            if parsed_args.name:
                set_data['name'] = parsed_args.name
            if parsed_args.description is not None:  # Allow empty string to clear description
                set_data['description'] = parsed_args.description

            if not set_data:
                raise AAPClientError("At least one field must be specified to set")

            # Update organization
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
            try:
                response = client.patch(endpoint, json=set_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                org_data = response.json()

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # Basic information
                columns.append('ID')
                values.append(str(org_data.get('id', '')))

                columns.append('Name')
                values.append(org_data.get('name', ''))

                columns.append('Description')
                values.append(org_data.get('description', ''))

                columns.append('Managed')
                values.append('Yes' if org_data.get('managed', False) else 'No')

                # User and team counts
                related_counts = org_data.get('summary_fields', {}).get('related_field_counts', {})
                columns.append('Users')
                values.append(str(related_counts.get('users', 0)))

                columns.append('Teams')
                values.append(str(related_counts.get('teams', 0)))

                # Creation info
                columns.append('Created')
                values.append(org_data.get('created', ''))

                columns.append('Created By')
                created_by = org_data.get('summary_fields', {}).get('created_by', {})
                values.append(created_by.get('username', '') if created_by else '')

                # Modifier info
                columns.append('Modified')
                values.append(org_data.get('modified', ''))

                columns.append('Modified By')
                modified_by = org_data.get('summary_fields', {}).get('modified_by', {})
                values.append(modified_by.get('username', '') if modified_by else '')

                return (columns, values)
            else:
                error_msg = f"Failed to set organization: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        error_msg += f" - {error_data['detail']}"
                    elif isinstance(error_data, dict):
                        # Handle field-specific errors
                        for field, errors in error_data.items():
                            if isinstance(errors, list):
                                error_msg += f" - {field}: {', '.join(errors)}"
                            else:
                                error_msg += f" - {field}: {errors}"
                except:
                    pass
                raise AAPClientError(error_msg)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")

    def _resolve_organization_positional(self, client, identifier):
        """Resolve positional parameter - try name first, then ID fallback if numeric."""
        # First try as name lookup
        try:
            return self._resolve_organization_by_name(client, identifier)
        except AAPClientError:
            # If name lookup fails and identifier is numeric, try as ID
            try:
                org_id = int(identifier)
                # Verify the ID exists by trying to get it
                endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{org_id}/"
                response = client.get(endpoint)
                if response.status_code == HTTP_OK:
                    return org_id
                else:
                    raise AAPResourceNotFoundError("Organization", identifier)
            except ValueError:
                # Not a valid integer, and name lookup already failed
                raise AAPResourceNotFoundError("Organization", identifier)
            except Exception:
                # Catch any other errors (like API errors) during ID lookup
                raise AAPResourceNotFoundError("Organization", identifier)

    def _resolve_organization_by_name(self, client, name):
        """Resolve organization name to ID."""
        endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
        params = {'name': name}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                raise AAPResourceNotFoundError("Organization", name)
        else:
            raise AAPClientError(f"Failed to search for organization '{name}'")


class OrganizationDeleteCommand(Command):
    """Delete an organization."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Organization ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'organization',
            nargs='?',
            help='Organization name or ID'
        )


        return parser

    def take_action(self, parsed_args):
        """Execute the organization delete command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the organization
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                organization_id = parsed_args.id
            elif parsed_args.organization:
                # Use positional parameter - name first, then ID fallback if numeric
                organization_id = self._resolve_organization_positional(client, parsed_args.organization)
            else:
                raise AAPClientError("Organization identifier is required")

            # Get organization details first for confirmation
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{organization_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                org_data = response.json()
                org_name = org_data.get('name', str(organization_id))

                # Check if organization is managed
                if org_data.get('managed', False):
                    raise AAPClientError(f"Cannot delete managed organization '{org_name}'")

                # Delete organization
                try:
                    response = client.delete(endpoint)
                except AAPAPIError as api_error:
                    if api_error.status_code == HTTP_BAD_REQUEST:
                        # Pass through 400 status messages directly to user
                        raise SystemExit(str(api_error))
                    else:
                        # Re-raise other errors
                        raise

                if response.status_code == HTTP_NO_CONTENT:
                    print(f"Organization '{org_name}' deleted successfully.")
                else:
                    error_msg = f"Failed to delete organization: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'detail' in error_data:
                            error_msg += f" - {error_data['detail']}"
                    except:
                        pass
                    raise AAPClientError(error_msg)
            else:
                raise AAPResourceNotFoundError("Organization", parsed_args.organization or str(parsed_args.id))

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")

    def _resolve_organization_positional(self, client, identifier):
        """Resolve positional parameter - try name first, then ID fallback if numeric."""
        # First try as name lookup
        try:
            return self._resolve_organization_by_name(client, identifier)
        except AAPClientError:
            # If name lookup fails and identifier is numeric, try as ID
            try:
                org_id = int(identifier)
                # Verify the ID exists by trying to get it
                endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/{org_id}/"
                response = client.get(endpoint)
                if response.status_code == HTTP_OK:
                    return org_id
                else:
                    raise AAPResourceNotFoundError("Organization", identifier)
            except ValueError:
                # Not a valid integer, and name lookup already failed
                raise AAPResourceNotFoundError("Organization", identifier)
            except Exception:
                # Catch any other errors (like API errors) during ID lookup
                raise AAPResourceNotFoundError("Organization", identifier)

    def _resolve_organization_by_name(self, client, name):
        """Resolve organization name to ID."""
        endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}organizations/"
        params = {'name': name}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                raise AAPResourceNotFoundError("Organization", name)
        else:
            raise AAPClientError(f"Failed to search for organization '{name}'")
