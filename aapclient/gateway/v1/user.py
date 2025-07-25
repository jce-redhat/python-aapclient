"""User commands."""
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
from aapclient.common.functions import (
    resolve_user_name,
    format_datetime
)




def _format_user_data(user_data, use_utc=False):
    """
    Format user data consistently

    Args:
        user_data (dict): User data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract user details
    id_value = user_data.get('id', '')
    username = user_data.get('username', '')
    email = user_data.get('email', '')
    first_name = user_data.get('first_name', '')
    last_name = user_data.get('last_name', '')
    is_superuser = user_data.get('is_superuser', False)
    is_system_auditor = user_data.get('is_system_auditor', False)

    # Format datetime fields using common function
    date_joined = format_datetime(user_data.get('date_joined', ''), use_utc)
    last_login = format_datetime(user_data.get('last_login', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Username',
        'Email',
        'First Name',
        'Last Name',
        'Superuser',
        'System Auditor',
        'Date Joined',
        'Last Login'
    ]

    values = [
        id_value,
        username,
        email,
        first_name,
        last_name,
        "Yes" if is_superuser else "No",
        "Yes" if is_system_auditor else "No",
        date_joined,
        last_login
    ]

    return (columns, values)


class UserListCommand(AAPListCommand):
    """List users."""

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
        """Execute the user list command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query users endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", "users endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                users = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Username', 'Email', 'First Name', 'Last Name', 'Superuser']
                rows = []

                for user in users:
                    row = [
                        user.get('id', ''),
                        user.get('username', ''),
                        user.get('email', ''),
                        user.get('first_name', ''),
                        user.get('last_name', ''),
                        "Yes" if user.get('is_superuser', False) else "No"
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


class UserShowCommand(AAPShowCommand):
    """Show details of a specific user."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='User ID (overrides positional parameter)'
        )

        # Positional parameter for username lookup with ID fallback
        parser.add_argument(
            'user',
            nargs='?',
            metavar='<user>',
            help='Username or ID to display'
        )
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the user show command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine how to resolve the user
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                user_id = parsed_args.id
            elif parsed_args.user:
                # Use positional parameter - username first, then ID fallback if numeric
                user_id = resolve_user_name(client, parsed_args.user, api="gateway")
            else:
                raise AAPClientError("User identifier is required")

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
            response = client.get(endpoint)

            if response.status_code == HTTP_OK:
                user_data = response.json()
                return _format_user_data(user_data, parsed_args.utc)
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("User", parsed_args.user or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to get user: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")


class UserCreateCommand(AAPShowCommand):
    """Create a new user."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'username',
            help='Username'
        )
        parser.add_argument(
            '--email',
            help='Email address'
        )
        parser.add_argument(
            '--first-name',
            dest='first_name',
            help='First name'
        )
        parser.add_argument(
            '--last-name',
            dest='last_name',
            help='Last name'
        )
        parser.add_argument(
            '--password',
            help='Password'
        )
        parser.add_argument(
            '--superuser',
            action='store_true',
            help='Grant superuser privileges'
        )
        parser.add_argument(
            '--system-auditor',
            action='store_true',
            dest='system_auditor',
            help='Grant system auditor privileges'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the user create command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Get parser for usage message
            parser = self.get_parser('aap user create')

            user_data = {
                'username': parsed_args.username
            }

            # Add optional fields
            if getattr(parsed_args, 'email', None):
                user_data['email'] = parsed_args.email
            if getattr(parsed_args, 'first_name', None):
                user_data['first_name'] = parsed_args.first_name
            if getattr(parsed_args, 'last_name', None):
                user_data['last_name'] = parsed_args.last_name
            if getattr(parsed_args, 'password', None):
                user_data['password'] = parsed_args.password
            if parsed_args.superuser:
                user_data['is_superuser'] = True
            if parsed_args.system_auditor:
                user_data['is_system_auditor'] = True

            # Create user
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/"
            try:
                response = client.post(endpoint, json=user_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("User", parsed_args.username)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_CREATED:
                user_data = response.json()
                print(f"User '{user_data.get('username', '')}' created successfully")

                return _format_user_data(user_data)
            else:
                raise AAPClientError(f"User creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class UserSetCommand(AAPShowCommand):
    """Update an existing user."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='User ID (overrides positional parameter)'
        )

        # Positional parameter for username lookup with ID fallback
        parser.add_argument(
            'user',
            nargs='?',
            metavar='<user>',
            help='Username or ID to update'
        )

        parser.add_argument(
            '--username',
            help='New username'
        )
        parser.add_argument(
            '--email',
            help='Email address'
        )
        parser.add_argument(
            '--first-name',
            dest='first_name',
            help='First name'
        )
        parser.add_argument(
            '--last-name',
            dest='last_name',
            help='Last name'
        )
        parser.add_argument(
            '--password',
            help='New password'
        )

        # Enable/disable flags for privileges
        superuser_group = parser.add_mutually_exclusive_group()
        superuser_group.add_argument(
            '--enable-superuser',
            action='store_true',
            dest='enable_superuser',
            help='Grant superuser privileges'
        )
        superuser_group.add_argument(
            '--disable-superuser',
            action='store_true',
            dest='disable_superuser',
            help='Revoke superuser privileges'
        )

        auditor_group = parser.add_mutually_exclusive_group()
        auditor_group.add_argument(
            '--enable-system-auditor',
            action='store_true',
            dest='enable_auditor',
            help='Grant system auditor privileges'
        )
        auditor_group.add_argument(
            '--disable-system-auditor',
            action='store_true',
            dest='disable_auditor',
            help='Revoke system auditor privileges'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the user set command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Get parser for usage message
            parser = self.get_parser('aap user set')

            # Resolve user - handle both ID and username
            user_id = resolve_user_name(client, parsed_args.user, api="gateway")

            # Prepare user update data
            user_data = {}

            if getattr(parsed_args, 'username', None):
                user_data['username'] = parsed_args.username
            if getattr(parsed_args, 'email', None):
                user_data['email'] = parsed_args.email
            if getattr(parsed_args, 'first_name', None):
                user_data['first_name'] = parsed_args.first_name
            if getattr(parsed_args, 'last_name', None):
                user_data['last_name'] = parsed_args.last_name
            if getattr(parsed_args, 'password', None):
                user_data['password'] = parsed_args.password

            # Handle enable/disable flags
            if parsed_args.enable_superuser:
                user_data['is_superuser'] = True
            elif parsed_args.disable_superuser:
                user_data['is_superuser'] = False

            if parsed_args.enable_auditor:
                user_data['is_system_auditor'] = True
            elif parsed_args.disable_auditor:
                user_data['is_system_auditor'] = False

            if not user_data:
                parser.error("No update fields provided")

            # Update user
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
            try:
                response = client.patch(endpoint, json=user_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Gateway API", parsed_args.user)

            if response.status_code == HTTP_OK:
                user_data = response.json()
                print(f"User '{user_data.get('username', '')}' updated successfully")

                return _format_user_data(user_data)
            else:
                raise AAPClientError(f"User update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class UserDeleteCommand(AAPCommand):
    """Delete a user."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='User ID (overrides positional parameter)'
        )

        # Positional parameter for username lookup with ID fallback
        parser.add_argument(
            'user',
            nargs='?',
            metavar='<user>',
            help='Username or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the user delete command."""
        try:
            # Get client from centralized client manager
            client = self.gateway_client

            # Determine how to resolve the user
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                user_id = parsed_args.id
            elif parsed_args.user:
                # Use positional parameter - username first, then ID fallback if numeric
                user_id = resolve_user_name(client, parsed_args.user, api="gateway")
            else:
                raise AAPClientError("User identifier is required")

            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
            response = client.delete(endpoint)

            if response.status_code in (HTTP_NO_CONTENT, HTTP_ACCEPTED):
                print(f"User '{parsed_args.user or parsed_args.id}' deleted successfully")
            elif response.status_code == HTTP_NOT_FOUND:
                raise AAPResourceNotFoundError("User", parsed_args.user or parsed_args.id)
            else:
                raise AAPClientError(f"Failed to delete user: {response.status_code}")

        except AAPResourceNotFoundError:
            raise
        except AAPClientError:
            raise
        except Exception as e:
            raise AAPClientError(f"Unexpected error: {e}")
