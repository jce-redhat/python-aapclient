"""Team commands."""
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
from aapclient.common.functions import resolve_organization_name, resolve_team_name




class TeamListCommand(Lister):
    """List teams."""

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
        """Execute the team list command."""
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

            # Query teams endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Team", "teams endpoint")
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                data = response.json()

                # Extract teams from results (already sorted by API)
                teams = data.get('results', [])

                # Define columns for table display
                columns = [
                    'ID',
                    'Name',
                    'Organization'
                ]

                # Build rows data
                rows = []
                for team in teams:
                    # Get organization name from summary_fields
                    org_name = ''
                    if 'summary_fields' in team and 'organization' in team['summary_fields']:
                        org_name = team['summary_fields']['organization'].get('name', '')

                    row = [
                        team.get('id', ''),
                        team.get('name', ''),
                        org_name
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


class TeamShowCommand(ShowOne):
    """Show details of a specific team."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Team ID (overrides positional parameter)'
        )

        # Positional parameter for team name lookup with ID fallback
        parser.add_argument(
            'team',
            nargs='?',
            help='Team name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the team show command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the team
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                team_id = parsed_args.id
            elif parsed_args.team:
                # Use positional parameter - team name first, then ID fallback if numeric
                team_id = resolve_team_name(client, parsed_args.team)
            else:
                raise AAPClientError("Team identifier is required")

            # Get specific team
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
            try:
                response = client.get(endpoint)
                team_data = response.json()

                # Prepare data using dictionary for cleaner code
                org_info = team_data.get('summary_fields', {}).get('organization', {})
                created_by = team_data.get('summary_fields', {}).get('created_by', {})
                modified_by = team_data.get('summary_fields', {}).get('modified_by', {})

                # Define field mappings as ordered dictionary
                field_data = {
                    'ID': str(team_data.get('id', '')),
                    'Name': team_data.get('name', ''),
                    'Description': team_data.get('description', ''),
                    'Organization': org_info.get('name', '') or str(team_data.get('organization', '')),
                    'Created': team_data.get('created', ''),
                    'Created By': created_by.get('username', '') if created_by else '',
                    'Modified': team_data.get('modified', ''),
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
                    identifier = str(parsed_args.id) if parsed_args.id else parsed_args.team
                    raise AAPResourceNotFoundError("Team", identifier)
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


class TeamCreateCommand(ShowOne):
    """Create a team."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        parser.add_argument(
            'name',
            help='Team name'
        )
        parser.add_argument(
            '--description',
            help='Team description'
        )
        parser.add_argument(
            '--organization',
            required=True,
            help='Organization name or ID'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the team create command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Prepare team data
            team_data = {
                'name': parsed_args.name
            }

            if parsed_args.description:
                team_data['description'] = parsed_args.description

            # Resolve organization name/ID to ID (organization is required)
            org_id = resolve_organization_name(client, parsed_args.organization)
            team_data['organization'] = org_id

            # Create team
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/"
            try:
                response = client.post(endpoint, json=team_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Team", parsed_args.name)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_CREATED:
                team_data = response.json()

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # Basic information
                columns.append('ID')
                values.append(str(team_data.get('id', '')))

                columns.append('Name')
                values.append(team_data.get('name', ''))

                columns.append('Description')
                values.append(team_data.get('description', ''))

                # Organization information
                columns.append('Organization')
                org_info = team_data.get('summary_fields', {}).get('organization', {})
                values.append(org_info.get('name', '') or str(team_data.get('organization', '')))

                columns.append('Created')
                values.append(team_data.get('created', ''))

                columns.append('Created By')
                created_by = team_data.get('summary_fields', {}).get('created_by', {})
                values.append(created_by.get('username', '') if created_by else '')

                return (columns, values)
            else:
                error_msg = f"Failed to create team: HTTP {response.status_code}"
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


class TeamSetCommand(ShowOne):
    """Set team properties."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Team ID (overrides positional parameter)'
        )

        # Positional parameter for team name lookup with ID fallback
        parser.add_argument(
            'team',
            nargs='?',
            help='Team name or ID'
        )

        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='Set team name'
        )
        parser.add_argument(
            '--description',
            help='Set team description (use empty string to clear)'
        )
        parser.add_argument(
            '--organization',
            help='Set organization name or ID'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the team set command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the team
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                team_id = parsed_args.id
            elif parsed_args.team:
                # Use positional parameter - team name first, then ID fallback if numeric
                team_id = resolve_team_name(client, parsed_args.team)
            else:
                raise AAPClientError("Team identifier is required")

            # Prepare data to set
            set_data = {}
            if parsed_args.set_name:
                set_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:  # Allow empty string to clear description
                set_data['description'] = parsed_args.description
            if parsed_args.organization:
                # Resolve organization name/ID to ID
                org_id = resolve_organization_name(client, parsed_args.organization)
                set_data['organization'] = org_id

            if not set_data:
                raise AAPClientError("At least one field must be specified to set")

            # Update team
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
            try:
                response = client.patch(endpoint, json=set_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    identifier = str(parsed_args.id) if parsed_args.id else parsed_args.team
                    raise AAPResourceNotFoundError("Team", identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                team_data = response.json()

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # Basic information
                columns.append('ID')
                values.append(str(team_data.get('id', '')))

                columns.append('Name')
                values.append(team_data.get('name', ''))

                columns.append('Description')
                values.append(team_data.get('description', ''))

                # Organization information
                columns.append('Organization')
                org_info = team_data.get('summary_fields', {}).get('organization', {})
                values.append(org_info.get('name', '') or str(team_data.get('organization', '')))

                columns.append('Created')
                values.append(team_data.get('created', ''))

                columns.append('Created By')
                created_by = team_data.get('summary_fields', {}).get('created_by', {})
                values.append(created_by.get('username', '') if created_by else '')

                columns.append('Modified')
                values.append(team_data.get('modified', ''))

                columns.append('Modified By')
                modified_by = team_data.get('summary_fields', {}).get('modified_by', {})
                values.append(modified_by.get('username', '') if modified_by else '')

                return (columns, values)
            else:
                error_msg = f"Failed to set team: HTTP {response.status_code}"
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


class TeamDeleteCommand(Command):
    """Delete a team."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Team ID (overrides positional parameter)'
        )

        # Positional parameter for team name lookup with ID fallback
        parser.add_argument(
            'team',
            nargs='?',
            help='Team name or ID'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the team delete command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the team
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                team_id = parsed_args.id
            elif parsed_args.team:
                # Use positional parameter - team name first, then ID fallback if numeric
                team_id = resolve_team_name(client, parsed_args.team)
            else:
                raise AAPClientError("Team identifier is required")

            # Get team info first to confirm it exists and get the name
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    identifier = str(parsed_args.id) if parsed_args.id else parsed_args.team
                    raise AAPResourceNotFoundError("Team", identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                team_data = response.json()
                team_name = team_data.get('name', str(team_id))

                # Delete team
                try:
                    response = client.delete(endpoint)
                except AAPAPIError as api_error:
                    if api_error.status_code == HTTP_NOT_FOUND:
                        # Handle 404 error with proper message
                        identifier = str(parsed_args.id) if parsed_args.id else parsed_args.team
                        raise AAPResourceNotFoundError("Team", identifier)
                    elif api_error.status_code == HTTP_BAD_REQUEST:
                        # Pass through 400 status messages directly to user
                        raise SystemExit(str(api_error))
                    else:
                        # Re-raise other errors
                        raise

                if response.status_code == HTTP_NO_CONTENT:
                    print(f"Team '{team_name}' deleted successfully.")
                else:
                    error_msg = f"Failed to delete team: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'detail' in error_data:
                            error_msg += f" - {error_data['detail']}"
                    except:
                        pass
                    raise AAPClientError(error_msg)
            else:
                raise AAPResourceNotFoundError("Team", parsed_args.team or str(parsed_args.id))

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
