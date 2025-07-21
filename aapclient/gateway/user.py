"""User commands for AAP Gateway API."""
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
from aapclient.common.functions import resolve_user_name


class UserListCommand(Lister):
    """List users from AAP Gateway API."""

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
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query users endpoint
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("User", "users endpoint")
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                data = response.json()

                # Extract users from results (already sorted by API)
                users = data.get('results', [])

                # Define columns for table display
                columns = [
                    'ID',
                    'Username',
                    'User Type',
                    'Email',
                    'First Name',
                    'Last Name',
                    'Last Login'
                ]

                # Build rows data
                rows = []
                for user in users:
                    # Determine user type based on permissions
                    user_type = 'Normal User'
                    if user.get('is_superuser', False):
                        user_type = 'Superuser'
                    elif user.get('is_platform_auditor', False):
                        user_type = 'Platform Auditor'

                    row = [
                        user.get('id', ''),
                        user.get('username', ''),
                        user_type,
                        user.get('email', ''),
                        user.get('first_name', ''),
                        user.get('last_name', ''),
                        user.get('last_login', '') or ''
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


class UserShowCommand(ShowOne):
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
            help='Username or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the user show command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the user
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                user_id = parsed_args.id
            elif parsed_args.user:
                # Use positional parameter - username first, then ID fallback if numeric
                user_id = resolve_user_name(client, parsed_args.user)
            else:
                raise AAPClientError("User identifier is required")

            # Get specific user
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
            try:
                response = client.get(endpoint)
                user_data = response.json()

                # Prepare data using dictionary for cleaner code
                created_by = user_data.get('summary_fields', {}).get('created_by', {})
                modified_by = user_data.get('summary_fields', {}).get('modified_by', {})

                # Define field mappings as ordered dictionary
                field_data = {
                    'ID': str(user_data.get('id', '')),
                    'Username': user_data.get('username', ''),
                    'Email': user_data.get('email', ''),
                    'First Name': user_data.get('first_name', '').strip(),
                    'Last Name': user_data.get('last_name', '').strip(),
                    'Superuser': 'Yes' if user_data.get('is_superuser', False) else 'No',
                    'Platform Auditor': 'Yes' if user_data.get('is_platform_auditor', False) else 'No',
                    'Managed Account': 'Yes' if user_data.get('managed', False) else 'No',
                    'Last Login': user_data.get('last_login', ''),
                    'Created': user_data.get('created', ''),
                    'Created By': created_by.get('username', '') if created_by else '',
                    'Modified': user_data.get('modified', ''),
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
                    identifier = str(parsed_args.id) if parsed_args.id else parsed_args.user
                    raise AAPResourceNotFoundError("User", identifier)
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


class UserCreateCommand(ShowOne):
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
            help='First name'
        )
        parser.add_argument(
            '--last-name',
            help='Last name'
        )
        parser.add_argument(
            '--password',
            help='Password'
        )
        parser.add_argument(
            '--is-superuser',
            action='store_true',
            help='Make user a superuser'
        )
        parser.add_argument(
            '--is-platform-auditor',
            action='store_true',
            help='Make user a platform auditor'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the user create command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Prepare user data
            user_data = {
                'username': parsed_args.username
            }

            if parsed_args.email:
                user_data['email'] = parsed_args.email
            if parsed_args.first_name:
                user_data['first_name'] = parsed_args.first_name
            if parsed_args.last_name:
                user_data['last_name'] = parsed_args.last_name
            if parsed_args.password:
                user_data['password'] = parsed_args.password
            if parsed_args.is_superuser:
                user_data['is_superuser'] = True
            if parsed_args.is_platform_auditor:
                user_data['is_platform_auditor'] = True

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

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # Basic information
                columns.append('ID')
                values.append(str(user_data.get('id', '')))

                columns.append('Username')
                values.append(user_data.get('username', ''))

                columns.append('Email')
                values.append(user_data.get('email', ''))

                # Name fields (always show)
                columns.append('First Name')
                values.append(user_data.get('first_name', '').strip())

                columns.append('Last Name')
                values.append(user_data.get('last_name', '').strip())

                # Permission flags
                columns.append('Superuser')
                values.append('Yes' if user_data.get('is_superuser', False) else 'No')

                columns.append('Platform Auditor')
                values.append('Yes' if user_data.get('is_platform_auditor', False) else 'No')

                # Creation info
                columns.append('Created')
                values.append(user_data.get('created', ''))

                columns.append('Created By')
                created_by = user_data.get('summary_fields', {}).get('created_by', {})
                values.append(created_by.get('username', '') if created_by else '')

                return (columns, values)
            else:
                error_msg = f"Failed to create user: HTTP {response.status_code}"
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


class UserSetCommand(ShowOne):
    """Set/update an existing user."""

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
            help='Username or ID'
        )

        # Set fields
        parser.add_argument(
            '--username',
            help='Set username'
        )
        parser.add_argument(
            '--email',
            help='Set email address'
        )
        parser.add_argument(
            '--first-name',
            help='Set first name'
        )
        parser.add_argument(
            '--last-name',
            help='Set last name'
        )
        parser.add_argument(
            '--password',
            help='Set password'
        )
        parser.add_argument(
            '--is-superuser',
            action='store_true',
            help='Make user a superuser'
        )
        parser.add_argument(
            '--no-is-superuser',
            action='store_true',
            help='Remove superuser privileges'
        )
        parser.add_argument(
            '--is-platform-auditor',
            action='store_true',
            help='Make user a platform auditor'
        )
        parser.add_argument(
            '--no-is-platform-auditor',
            action='store_true',
            help='Remove platform auditor privileges'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the user set command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the user
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                user_id = parsed_args.id
            elif parsed_args.user:
                # Use positional parameter - username first, then ID fallback if numeric
                user_id = resolve_user_name(client, parsed_args.user)
            else:
                raise AAPClientError("User identifier is required")

            # Prepare data to set
            set_data = {}
            if parsed_args.username:
                set_data['username'] = parsed_args.username
            if parsed_args.email is not None:  # Allow empty string to clear email
                set_data['email'] = parsed_args.email
            if parsed_args.first_name is not None:  # Allow empty string to clear first name
                set_data['first_name'] = parsed_args.first_name
            if parsed_args.last_name is not None:  # Allow empty string to clear last name
                set_data['last_name'] = parsed_args.last_name
            if parsed_args.password:
                set_data['password'] = parsed_args.password
            if parsed_args.is_superuser:
                set_data['is_superuser'] = True
            if parsed_args.no_is_superuser:
                set_data['is_superuser'] = False
            if parsed_args.is_platform_auditor:
                set_data['is_platform_auditor'] = True
            if parsed_args.no_is_platform_auditor:
                set_data['is_platform_auditor'] = False

            if not set_data:
                raise AAPClientError("At least one field must be specified to set")

            # Update user
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
            try:
                response = client.patch(endpoint, json=set_data)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    identifier = str(parsed_args.id) if parsed_args.id else parsed_args.user
                    raise AAPResourceNotFoundError("User", identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                user_data = response.json()

                # Prepare columns and data for Cliff formatting
                columns = []
                values = []

                # Basic information
                columns.append('ID')
                values.append(str(user_data.get('id', '')))

                columns.append('Username')
                values.append(user_data.get('username', ''))

                columns.append('Email')
                values.append(user_data.get('email', ''))

                # Name fields (always show)
                columns.append('First Name')
                values.append(user_data.get('first_name', '').strip())

                columns.append('Last Name')
                values.append(user_data.get('last_name', '').strip())

                # Permission flags
                columns.append('Superuser')
                values.append('Yes' if user_data.get('is_superuser', False) else 'No')

                columns.append('Platform Auditor')
                values.append('Yes' if user_data.get('is_platform_auditor', False) else 'No')

                columns.append('Managed Account')
                values.append('Yes' if user_data.get('managed', False) else 'No')

                # Timestamps
                columns.append('Last Login')
                values.append(user_data.get('last_login', ''))

                columns.append('Created')
                values.append(user_data.get('created', ''))

                columns.append('Created By')
                created_by = user_data.get('summary_fields', {}).get('created_by', {})
                values.append(created_by.get('username', '') if created_by else '')

                # Modifier info
                columns.append('Modified')
                values.append(user_data.get('modified', ''))

                columns.append('Modified By')
                modified_by = user_data.get('summary_fields', {}).get('modified_by', {})
                values.append(modified_by.get('username', '') if modified_by else '')

                return (columns, values)
            else:
                error_msg = f"Failed to set user: HTTP {response.status_code}"
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


class UserDeleteCommand(Command):
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
            help='Username or ID'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the user delete command."""
        try:
            # Initialize configuration and validate
            config = AAPConfig()
            config.validate()

            # Create HTTP client
            client = AAPHTTPClient(config)

            # Determine how to resolve the user
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                user_id = parsed_args.id
            elif parsed_args.user:
                # Use positional parameter - username first, then ID fallback if numeric
                user_id = resolve_user_name(client, parsed_args.user)
            else:
                raise AAPClientError("User identifier is required")

            # Get user details first for confirmation
            endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
            try:
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    identifier = str(parsed_args.id) if parsed_args.id else parsed_args.user
                    raise AAPResourceNotFoundError("User", identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                user_data = response.json()
                username = user_data.get('username', str(user_id))

                # Check if user is managed
                if user_data.get('managed', False):
                    raise AAPClientError(f"Cannot delete managed user '{username}'")

                # Delete user
                try:
                    response = client.delete(endpoint)
                except AAPAPIError as api_error:
                    if api_error.status_code == HTTP_NOT_FOUND:
                        # Handle 404 error with proper message
                        identifier = str(parsed_args.id) if parsed_args.id else parsed_args.user
                        raise AAPResourceNotFoundError("User", identifier)
                    elif api_error.status_code == HTTP_BAD_REQUEST:
                        # Pass through 400 status messages directly to user
                        raise SystemExit(str(api_error))
                    else:
                        # Re-raise other errors
                        raise

                if response.status_code == HTTP_NO_CONTENT:
                    print(f"User '{username}' deleted successfully.")
                else:
                    error_msg = f"Failed to delete user: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'detail' in error_data:
                            error_msg += f" - {error_data['detail']}"
                    except:
                        pass
                    raise AAPClientError(error_msg)
            else:
                raise AAPResourceNotFoundError("User", parsed_args.user or str(parsed_args.id))

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
