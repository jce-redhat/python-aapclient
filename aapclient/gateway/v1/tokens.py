"""Token commands for AAP CLI using Click and Rich."""

import sys
from typing import Dict, Any
from collections import OrderedDict

import click
from rich.table import Table

from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
)
from aapclient.common.functions import resolve_application_name
from aapclient.decorators import (
    list_command,
    show_command,
    create_command,
    update_command,
    delete_command,
    common_options,
    get_client_from_context,
)
from aapclient.output import (
    show_success_message,
    show_error_message,
    show_raw_json,
    show_raw_yaml,
    format_datetime_rich,
)


@click.group()
def token():
    """Manage AAP personal access tokens."""


def _format_token_data(
    token_data: Dict[str, Any], output_format: str = "table", use_utc: bool = False
) -> Dict[str, Any]:
    """Format token data for display."""
    # Use OrderedDict to maintain field order
    data = OrderedDict()

    # Basic information
    data["ID"] = str(token_data.get("id", ""))

    # User
    user_info = token_data.get("summary_fields", {}).get("user", {})
    data["User"] = user_info.get("username", "") if user_info else ""

    # Token value
    data["Token"] = token_data.get("token", "")

    # Scope and description
    data["Scope"] = token_data.get("scope", "")
    data["Description"] = token_data.get("description", "")

    # OAuth application
    app_info = token_data.get("summary_fields", {}).get("application", {})
    data["OAuth Application"] = app_info.get("name", "Personal access token") if app_info else "Personal access token"

    # Timestamps
    data["Expires"] = format_datetime_rich(token_data.get("expires", ""), use_utc, output_format)
    data["Created"] = format_datetime_rich(token_data.get("created", ""), use_utc, output_format)
    data["Modified"] = format_datetime_rich(token_data.get("modified", ""), use_utc, output_format)
    data["Last Used"] = format_datetime_rich(token_data.get("last_used", ""), use_utc, output_format)

    # Created/Modified by
    summary_fields = token_data.get("summary_fields", {})
    created_by = summary_fields.get("created_by", {})
    data["Created By"] = created_by.get("username", "") if created_by else ""

    modified_by = summary_fields.get("modified_by", {})
    data["Modified By"] = modified_by.get("username", "") if modified_by else ""

    # Remove empty fields for cleaner display, but keep certain fields always visible
    always_show = ["ID", "User", "Token", "Scope", "Description", "OAuth Application"]
    data = {k: v for k, v in data.items() if v not in ["", None, "N/A"] or k in always_show}

    return data


@token.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(
    default_limit=20,
    sort_fields=["id", "user", "scope", "description", "expires", "created", "modified"],
    default_sort="id",
)
def list_tokens(console, output_format, utc, sort_by, reverse, limit, offset, show_all):
    """List tokens for the currently authenticated user."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Build API parameters
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
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/"
    response = client.get(endpoint, params=params)
    data = response.json()
    tokens = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for token in tokens:
            user_info = token.get("summary_fields", {}).get("user", {})
            username = user_info.get("username", "") if user_info else ""

            app_info = token.get("summary_fields", {}).get("application", {})
            oauth_app_name = app_info.get("name", "Personal access token") if app_info else "Personal access token"

            processed_data.append(
                {
                    "ID": token.get("id"),
                    "User": username,
                    "OAuth Application": oauth_app_name,
                    "Scope": token.get("scope", ""),
                    "Description": token.get("description", ""),
                    "Expiration": format_datetime_rich(token.get("expires", ""), utc, output_format),
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
    table.add_column("User", style="white")
    table.add_column("OAuth Application", style="yellow")
    table.add_column("Scope", style="green")
    table.add_column("Description", style="white")
    table.add_column("Expiration", style="magenta")

    for token in tokens:
        user_info = token.get("summary_fields", {}).get("user", {})
        username = user_info.get("username", "") if user_info else ""

        app_info = token.get("summary_fields", {}).get("application", {})
        oauth_app_name = app_info.get("name", "Personal access token") if app_info else "Personal access token"

        # Truncate description for table display
        description = token.get("description", "")
        description_display = description[:30] + ("..." if len(description) > 30 else "")

        table.add_row(
            str(token.get("id", "")),
            username,
            oauth_app_name,
            token.get("scope", ""),
            description_display,
            format_datetime_rich(token.get("expires", ""), utc, output_format),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(tokens))
    if not show_all and len(tokens) < total_count:
        console.print(f"\nShowing {len(tokens)} of {total_count} total tokens")


@token.command("show")
@click.argument("token_id", type=int, metavar="<token_id>")
@show_command
def show_token(console, output_format, utc, token_id):
    """Show details of a specific token."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Fetch token details
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/{token_id}/"
    response = client.get(endpoint)
    token_data = response.json()

    # Format data for display
    formatted_data = _format_token_data(token_data, output_format, utc)

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


@token.command("create")
@click.option("--scope", type=click.Choice(["read", "write"]), required=True, help="Token scope")
@click.option("--description", help="Token description")
@click.option(
    "--oauth-application",
    help="OAuth application name or ID (creates application token instead of personal access token)",
)
@common_options
@create_command
def create_token(console, output_format, utc, scope, description, oauth_application):
    """Create a new token for the currently authenticated user."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Build token data
    token_data = {"scope": scope}

    if description:
        token_data["description"] = description

    if oauth_application:
        try:
            app_id = resolve_application_name(client, oauth_application)
            token_data["application"] = app_id
        except Exception as e:
            show_error_message(console, f"Error resolving OAuth application '{oauth_application}': {e}")
            sys.exit(1)

    # Create token
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/"
    response = client.post(endpoint, json=token_data)

    if response.status_code == HTTP_CREATED:
        token_response = response.json()
        show_success_message(console, "Token created successfully")

        # Show the created token value prominently
        token_value = token_response.get("token", "")
        if token_value:
            console.print(f"\n[bold red]Token value:[/bold red] {token_value}")
            console.print("[dim]Save this token value - it will not be shown again![/dim]\n")

        # Format and display the token details using the same format as show command
        formatted_data = _format_token_data(token_response, output_format, utc)

        if output_format == "json":
            show_raw_json(formatted_data)
        elif output_format == "yaml":
            show_raw_yaml(formatted_data)
        else:
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Field", style="white")
            table.add_column("Value", style="white")

            for field, value in formatted_data.items():
                table.add_row(field, str(value))

            console.print(table)
    else:
        show_error_message(console, f"Failed to create token: HTTP {response.status_code}")
        sys.exit(1)


@token.command("set")
@click.argument("token_id", type=int, metavar="<token_id>")
@click.option("--description", help="New token description")
@click.option("--scope", type=click.Choice(["read", "write"]), help="New token scope")
@common_options
@update_command
def set_token(console, output_format, utc, token_id, description, scope):
    """Update token settings."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Build update data
    update_data = {}

    if description is not None:  # Allow empty string
        update_data["description"] = description
    if scope:
        update_data["scope"] = scope

    if not update_data:
        show_error_message(console, "No updates specified")
        sys.exit(1)

    # Update token
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/{token_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        show_success_message(console, f"Token '{token_id}' updated successfully")

        # Show updated token details
        updated_token = response.json()
        formatted_data = _format_token_data(updated_token, output_format, utc)

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
        show_error_message(console, f"Failed to update token: HTTP {response.status_code}")
        sys.exit(1)


@token.command("delete")
@click.argument("token_id", type=int, metavar="<token_id>")
@delete_command("Are you sure you want to delete this token?")
def delete_token(console, token_id):
    """Delete a token."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Delete token
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}tokens/{token_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Token '{token_id}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete token: HTTP {response.status_code}")
        sys.exit(1)


def register_token_commands(main_group: click.Group) -> None:
    """Register token commands with the main CLI group."""
    main_group.add_command(token)
