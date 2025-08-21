"""User commands for AAP CLI using Click and Rich."""

import sys
from typing import Dict, Any, Optional
from collections import OrderedDict

import click
from rich.console import Console
from rich.table import Table
from click_option_group import optgroup, MutuallyExclusiveOptionGroup

from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
)
from aapclient.common.functions import resolve_user_name
from aapclient.decorators import (
    list_command,
    show_command,
    create_command,
    update_command,
    delete_command,
    common_options,
    get_client_from_context,
    validate_resource_identifier,
)
from aapclient.output import (
    show_success_message,
    show_error_message,
    show_raw_json,
    show_raw_yaml,
    format_datetime_rich,
    format_value_for_output,
)


@click.group()
def user():
    """Manage AAP users."""


def _format_user_data(user_data: Dict[str, Any], use_utc: bool = False, output_format: str = "table") -> Dict[str, Any]:
    """Format user data for display."""
    # Use OrderedDict to maintain field order
    data = OrderedDict()

    # Basic information
    data["ID"] = str(user_data.get("id", ""))
    data["Username"] = user_data.get("username", "")
    data["User Type"] = user_data.get("user_type", "")
    data["Email"] = user_data.get("email", "")
    data["First Name"] = user_data.get("first_name", "")
    data["Last Name"] = user_data.get("last_name", "")
    data["Last Login"] = format_datetime_rich(user_data.get("last_login", ""), use_utc, output_format)
    data["Is Superuser"] = format_value_for_output(user_data.get("is_superuser", False), "is_superuser", output_format)
    data["Is Platform Auditor"] = format_value_for_output(
        user_data.get("is_platform_auditor", False), "is_platform_auditor", output_format
    )

    # Timestamps
    data["Created"] = format_datetime_rich(user_data.get("created", ""), use_utc, output_format)
    data["Modified"] = format_datetime_rich(user_data.get("modified", ""), use_utc, output_format)

    # Created/Modified by
    summary_fields = user_data.get("summary_fields", {})
    created_by = summary_fields.get("created_by", {})
    data["Created By"] = created_by.get("username", "") if created_by else ""

    modified_by = summary_fields.get("modified_by", {})
    data["Modified By"] = modified_by.get("username", "") if modified_by else ""

    # Remove empty fields for cleaner display, but keep certain fields always visible
    always_show = ["ID", "Username", "User Type", "Email", "First Name", "Last Name"]
    data = {k: v for k, v in data.items() if v not in ["", None, "N/A"] or k in always_show}

    return data


@user.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(
    default_limit=20,
    sort_fields=[
        "id",
        "username",
        "user_type",
        "email",
        "first_name",
        "last_name",
        "last_login",
        "created",
        "modified",
    ],
    default_sort="id",
)
def list_users(
    console: Console,
    output_format: str,
    utc: bool,
    sort_by: str,
    reverse: bool,
    limit: int,
    offset: int,
    show_all: bool,
) -> None:
    """List users."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Build query parameters
    params = {}

    # Pagination
    if not show_all:
        params["page_size"] = limit
        params["page"] = (offset // limit) + 1

    # Sorting
    sort_field = sort_by if sort_by else "id"
    if reverse:
        params["order_by"] = f"-{sort_field}"
    else:
        params["order_by"] = sort_field

    # Fetch data
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/"
    response = client.get(endpoint, params=params)
    data = response.json()
    users = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for user in users:
            processed_data.append(
                {
                    "ID": user.get("id"),
                    "Username": user.get("username", ""),
                    "User Type": user.get("user_type", ""),
                    "Email": user.get("email", ""),
                    "First Name": user.get("first_name", ""),
                    "Last Name": user.get("last_name", ""),
                    "Last Login": format_datetime_rich(user.get("last_login", ""), utc, output_format),
                }
            )

        if output_format == "json":
            show_raw_json(processed_data)
        else:
            show_raw_yaml(processed_data)
        return

    # Table format
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Username", style="white")
    table.add_column("User Type", style="yellow")
    table.add_column("Email", style="white")
    table.add_column("First Name", style="white")
    table.add_column("Last Name", style="white")
    table.add_column("Last Login", style="green")

    for user in users:
        table.add_row(
            str(user.get("id", "")),
            user.get("username", ""),
            user.get("user_type", ""),
            user.get("email", ""),
            user.get("first_name", ""),
            user.get("last_name", ""),
            format_datetime_rich(user.get("last_login", ""), utc, output_format),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(users))
    if not show_all and len(users) < total_count:
        console.print(f"\nShowing {len(users)} of {total_count} total users")


@user.command("show")
@click.argument("username", metavar="<username>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="User ID (overrides name argument)")
@show_command
def show_user(console: Console, output_format: str, utc: bool, username: Optional[str], id: Optional[int]) -> None:
    """Show details of a specific user."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve user identifier
    if id:
        user_id = id
        f"ID {id}"
    elif username:
        try:
            user_id = resolve_user_name(client, username)
        except Exception:
            raise  # Let the decorator handle the error
    else:
        raise click.UsageError("Either username or --id must be provided.")

    # Fetch user details
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
    response = client.get(endpoint)
    user_data = response.json()

    # Format data for display
    formatted_data = _format_user_data(user_data, utc, output_format)

    if output_format == "json":
        show_raw_json(formatted_data)
    elif output_format == "yaml":
        show_raw_yaml(formatted_data)
    else:
        # Create table
        table = Table()
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")

        for field, value in formatted_data.items():
            table.add_row(field, str(value))

        console.print(table)


@user.command("create")
@click.argument("username", metavar="<username>")
@optgroup.group("Password", cls=MutuallyExclusiveOptionGroup, help="Password specification (one required)")
@optgroup.option("--password", help="User password")
@optgroup.option("--password-prompt", is_flag=True, help="Prompt for password interactively")
@click.option("--first-name", help="User first name")
@click.option("--last-name", help="User last name")
@click.option("--email", help="User email address")
@click.option("--is-superuser", is_flag=True, help="Grant superuser privileges")
@click.option("--is-platform-auditor", is_flag=True, help="Grant platform auditor privileges")
@create_command
def create_user(
    console, username, password, password_prompt, first_name, last_name, email, is_superuser, is_platform_auditor
):
    """Create a new user."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Handle password input
    if password_prompt:
        import getpass

        while True:
            password = getpass.getpass("Password: ")
            if not password:
                show_error_message(console, "Password cannot be empty")
                continue
            confirm_password = getpass.getpass("Confirm password: ")
            if password == confirm_password:
                break
            else:
                show_error_message(console, "Passwords do not match. Please try again.")
    elif not password:
        raise click.UsageError("Either --password or --password-prompt must be provided.")

    # Build user data
    user_data = {"username": username, "password": password}

    if first_name:
        user_data["first_name"] = first_name
    if last_name:
        user_data["last_name"] = last_name
    if email:
        user_data["email"] = email
    if is_superuser:
        user_data["is_superuser"] = True
    if is_platform_auditor:
        user_data["is_platform_auditor"] = True

    # Create user
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/"
    response = client.post(endpoint, json=user_data)

    if response.status_code == HTTP_CREATED:
        response.json()
        show_success_message(console, f"User '{username}' created successfully")
    else:
        show_error_message(console, f"Failed to create user: HTTP {response.status_code}")
        sys.exit(1)


@user.command("set")
@click.argument("username", metavar="<username>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="User ID (overrides name argument)")
@click.option("--name", "new_username", help="New username")
@click.option("--first-name", help="New first name")
@click.option("--last-name", help="New last name")
@click.option("--email", help="New email address")
@optgroup.group("Superuser Status", cls=MutuallyExclusiveOptionGroup, help="Superuser privilege control")
@optgroup.option("--is-superuser", is_flag=True, help="Grant superuser privileges")
@optgroup.option("--no-superuser", is_flag=True, help="Remove superuser privileges")
@optgroup.group("Platform Auditor Status", cls=MutuallyExclusiveOptionGroup, help="Platform auditor privilege control")
@optgroup.option("--is-platform-auditor", is_flag=True, help="Grant platform auditor privileges")
@optgroup.option("--no-platform-auditor", is_flag=True, help="Remove platform auditor privileges")
@common_options
@update_command
def set_user(
    console,
    output_format,
    utc,
    username,
    id,
    new_username,
    first_name,
    last_name,
    email,
    is_superuser,
    no_superuser,
    is_platform_auditor,
    no_platform_auditor,
):
    """Update user settings."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve user identifier
    if id:
        user_id = id
        user_identifier = f"ID {id}"
    elif username:
        try:
            user_id = resolve_user_name(client, username)
            user_identifier = username
        except Exception:
            raise  # Let the decorator handle the error
    else:
        raise click.UsageError("Either username or --id must be provided.")

    # Build update data
    update_data = {}

    if new_username:
        update_data["username"] = new_username
    if first_name:
        update_data["first_name"] = first_name
    if last_name:
        update_data["last_name"] = last_name
    if email:
        update_data["email"] = email
    if is_superuser:
        update_data["is_superuser"] = True
    elif no_superuser:
        update_data["is_superuser"] = False
    if is_platform_auditor:
        update_data["is_platform_auditor"] = True
    elif no_platform_auditor:
        update_data["is_platform_auditor"] = False

    if not update_data:
        show_error_message(console, "No updates specified")
        sys.exit(1)

    # Update user
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        show_success_message(console, f"User '{user_identifier}' updated successfully")

        # Show updated user details
        updated_user = response.json()
        formatted_data = _format_user_data(updated_user, utc, output_format)

        if output_format == "json":
            show_raw_json(formatted_data)
        elif output_format == "yaml":
            show_raw_yaml(formatted_data)
        else:
            table = Table()
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")
            for field, value in formatted_data.items():
                table.add_row(field, str(value))
            console.print(table)
    else:
        show_error_message(console, f"Failed to update user: HTTP {response.status_code}")
        sys.exit(1)


@user.command("delete")
@click.argument("username", metavar="<username>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="User ID (overrides name argument)")
@delete_command("Are you sure you want to delete this user?")
def delete_user(console, username, id):
    """Delete a user."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve user identifier
    if id:
        user_id = id
        user_identifier = f"ID {id}"
    elif username:
        try:
            user_id = resolve_user_name(client, username)
            user_identifier = username
        except Exception:
            raise  # Let the decorator handle the error
    else:
        raise click.UsageError("Either username or --id must be provided.")

    # Delete user
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}users/{user_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"User '{user_identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete user: HTTP {response.status_code}")
        sys.exit(1)


def register_user_commands(main_group: click.Group) -> None:
    """Register user commands with the main CLI group."""
    main_group.add_command(user)
