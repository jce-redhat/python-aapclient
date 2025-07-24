"""Team commands."""
from aapclient.common.basecommands import AAPShowCommand, AAPListCommand, AAPCommand
from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST,
    HTTP_ACCEPTED
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import resolve_organization_name, resolve_team_name




def _format_team_data(team_data):
    """
    Format team data consistently

    Args:
        team_data (dict): Team data from API response

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract team details
    id_value = team_data.get('id', '')
    name = team_data.get('name', '')
    description = team_data.get('description', '')
    organization_name = ''

    # Resolve organization name if available
    if 'summary_fields' in team_data and 'organization' in team_data['summary_fields']:
        if team_data['summary_fields']['organization']:
            organization_name = team_data['summary_fields']['organization'].get('name', '')

    created = team_data.get('created', '')
    modified = team_data.get('modified', '')

    # Format fields for display
    columns = [
        'ID',
        'Name',
        'Description',
        'Organization',
        'Created',
        'Modified'
    ]

    values = [
        id_value,
        name,
        description,
        organization_name,
        created,
        modified
    ]

    return (columns, values)


class TeamListCommand(AAPListCommand):
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
            # Get client from centralized client manager
            client = self.gateway_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query teams endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", "teams endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                teams = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Name', 'Description', 'Organization']
                rows = []

                for team in teams:
                    # Get organization name from summary_fields if available
                    org_name = ''
                    if 'summary_fields' in team and 'organization' in team['summary_fields']:
                        if team['summary_fields']['organization']:
                            org_name = team['summary_fields']['organization'].get('name', '')

                    row = [
                        team.get('id', ''),
                        team.get('name', ''),
                        team.get('description', ''),
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


class TeamShowCommand(AAPShowCommand):
    """Show details of a specific team."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Team ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'team',
            nargs='?',
            metavar='<team>',
            help='Team name or ID to display'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the team show command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine how to resolve the team
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                team_id = parsed_args.id
            elif parsed_args.team:
                # Use positional parameter - name first, then ID fallback if numeric
                team_id = resolve_team_name(client, parsed_args.team, api="gateway")
            else:
                raise AAPClientError("Team identifier is required")

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                team_data = response.json()
                return _format_team_data(team_data)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Team", parsed_args.team or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get team: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class TeamCreateCommand(AAPShowCommand):
    """Create a new team."""

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
            # Get client from centralized client manager
            client = self.gateway_client

            # Get parser for usage message
            parser = self.get_parser('aap team create')

            # Resolve organization
            org_id = resolve_organization_name(client, parsed_args.organization, api="gateway")

            team_data = {
                'name': parsed_args.name,
                'organization': org_id
            }

            # Add optional fields
            if parsed_args.description:
                team_data['description'] = parsed_args.description

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
                print(f"Team '{team_data.get('name', '')}' created successfully")

                return _format_team_data(team_data)
            else:
                raise AAPClientError(f"Team creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class TeamSetCommand(AAPShowCommand):
    """Update an existing team."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Team ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'team',
            nargs='?',
            metavar='<team>',
            help='Team name or ID to update'
        )

        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='New team name'
        )
        parser.add_argument(
            '--description',
            help='Team description'
        )
        parser.add_argument(
            '--organization',
            help='Organization name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the team set command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Get parser for usage message
            parser = self.get_parser('aap team set')

            # Resolve team - handle both ID and name
            team_id = resolve_team_name(client, parsed_args.team, api="gateway")

            # Resolve organization if provided
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="gateway")
            else:
                org_id = None

            # Prepare team update data
            team_data = {}

            if parsed_args.set_name:
                team_data['name'] = parsed_args.set_name
            if parsed_args.description is not None:  # Allow empty string
                team_data['description'] = parsed_args.description
            if org_id is not None:
                team_data['organization'] = org_id

            if not team_data:
                parser.error("No update fields provided")

            # Update team
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
            try:
                response = client.patch(endpoint, json=team_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Team", parsed_args.team)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                team_data = response.json()
                print(f"Team '{team_data.get('name', '')}' updated successfully")

                return _format_team_data(team_data)
            else:
                raise AAPClientError(f"Team update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class TeamDeleteCommand(AAPCommand):
    """Delete a team."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Team ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'team',
            nargs='?',
            metavar='<team>',
            help='Team name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the team delete command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine how to resolve the team
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                team_id = parsed_args.id
            elif parsed_args.team:
                # Use positional parameter - name first, then ID fallback if numeric
                team_id = resolve_team_name(client, parsed_args.team, api="gateway")
            else:
                raise AAPClientError("Team identifier is required")

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}teams/{team_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"Team '{parsed_args.team or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("Team", parsed_args.team or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete team: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
