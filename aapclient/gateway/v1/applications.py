"""Application commands for AAP CLI using Click and Rich."""

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
from aapclient.common.functions import resolve_organization_name, resolve_application_name
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
def application():
    """Manage AAP OAuth applications."""


def _format_application_data(
    application_data: Dict[str, Any], use_utc: bool = False, output_format: str = "table"
) -> Dict[str, Any]:
    """Format application data for display."""
    # Use OrderedDict to maintain field order
    data = OrderedDict()

    # Basic information
    data["ID"] = str(application_data.get("id", ""))
    data["Name"] = application_data.get("name", "")
    data["Description"] = application_data.get("description", "")

    # Organization
    organization_info = application_data.get("summary_fields", {}).get("organization", {})
    data["Organization"] = organization_info.get("name", "") if organization_info else ""

    # OAuth details
    data["Client ID"] = application_data.get("client_id", "")
    data["Client Secret"] = application_data.get("client_secret", "")
    data["Client Type"] = application_data.get("client_type", "")
    data["Authorization Grant Type"] = application_data.get("authorization_grant_type", "")
    data["Redirect URIs"] = application_data.get("redirect_uris", "")
    data["Skip Authorization"] = format_value_for_output(
        application_data.get("skip_authorization", False), "skip_authorization", output_format
    )

    # Token count
    tokens_info = application_data.get("summary_fields", {}).get("tokens", {})
    data["Tokens"] = tokens_info.get("count", 0) if tokens_info else 0

    # Timestamps
    data["Created"] = format_datetime_rich(application_data.get("created", ""), use_utc, output_format)
    data["Modified"] = format_datetime_rich(application_data.get("modified", ""), use_utc, output_format)

    # Created/Modified by
    summary_fields = application_data.get("summary_fields", {})
    created_by = summary_fields.get("created_by", {})
    data["Created By"] = created_by.get("username", "") if created_by else ""

    modified_by = summary_fields.get("modified_by", {})
    data["Modified By"] = modified_by.get("username", "") if modified_by else ""

    # Remove empty fields for cleaner display, but keep certain fields always visible
    always_show = ["ID", "Name", "Description", "Organization", "Client ID", "Client Type"]
    data = {k: v for k, v in data.items() if v not in ["", None, "N/A"] or k in always_show}

    return data


@application.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(default_limit=20, sort_fields=["id", "name", "organization", "created", "modified"], default_sort="id")
def list_applications(console, output_format, utc, sort_by, reverse, limit, offset, show_all):
    """List OAuth applications."""
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
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/"
    response = client.get(endpoint, params=params)
    data = response.json()
    applications = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for app in applications:
            org_info = app.get("summary_fields", {}).get("organization", {})
            org_name = org_info.get("name", "") if org_info else ""

            tokens_info = app.get("summary_fields", {}).get("tokens", {})
            tokens_count = tokens_info.get("count", 0) if tokens_info else 0

            processed_data.append(
                {
                    "ID": app.get("id"),
                    "Name": app.get("name", ""),
                    "Organization": org_name,
                    "Description": app.get("description", ""),
                    "Tokens": tokens_count,
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
    table.add_column("Name", style="white")
    table.add_column("Organization", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("Tokens", style="green")

    for app in applications:
        org_info = app.get("summary_fields", {}).get("organization", {})
        org_name = org_info.get("name", "") if org_info else ""

        tokens_info = app.get("summary_fields", {}).get("tokens", {})
        tokens_count = tokens_info.get("count", 0) if tokens_info else 0

        # Truncate description for table display
        description = app.get("description", "")
        description_display = description[:50] + ("..." if len(description) > 50 else "")

        table.add_row(str(app.get("id", "")), app.get("name", ""), org_name, description_display, str(tokens_count))

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(applications))
    if not show_all and len(applications) < total_count:
        console.print(f"\nShowing {len(applications)} of {total_count} total applications")


@application.command("show")
@click.argument("application_name", metavar="<application>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Application ID (overrides name argument)")
@show_command
def show_application(console, output_format, utc, application_name, id):
    """Show details of a specific application."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve application identifier
    if id:
        app_id = id
        f"ID {id}"
    elif application_name:
        try:
            app_id = resolve_application_name(client, application_name)
        except Exception:
            raise  # Let the decorator handle the error
    else:
        raise click.UsageError("Either application name or --id must be provided.")

    # Fetch application details
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/{app_id}/"
    response = client.get(endpoint)
    app_data = response.json()

    # Format data for display
    formatted_data = _format_application_data(app_data, utc, output_format)

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


@application.command("create")
@click.argument("name", metavar="<name>")
@click.option("--organization", required=True, help="Organization name or ID")
@click.option("--client-type", type=click.Choice(["public", "confidential"]), required=True, help="OAuth client type")
@click.option(
    "--grant-type",
    type=click.Choice(["authorization-code", "password"]),
    required=True,
    help="OAuth authorization grant type",
)
@click.option("--description", help="Application description")
@click.option("--redirect-uris", help="Redirect URIs (space-separated URLs)")
@click.option("--skip-authorization", is_flag=True, help="Skip authorization step")
@create_command
def create_application(
    console, name, organization, client_type, grant_type, description, redirect_uris, skip_authorization
):
    """Create a new OAuth application."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve organization ID
    try:
        org_id = resolve_organization_name(client, organization)
    except Exception as e:
        show_error_message(console, f"Error resolving organization '{organization}': {e}")
        sys.exit(1)

    # Build application data
    app_data = {
        "name": name,
        "organization": org_id,
        "client_type": client_type,
        "authorization_grant_type": grant_type,
    }

    if description:
        app_data["description"] = description
    if redirect_uris:
        app_data["redirect_uris"] = redirect_uris
    if skip_authorization:
        app_data["skip_authorization"] = True

    # Create application
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/"
    response = client.post(endpoint, json=app_data)

    if response.status_code == HTTP_CREATED:
        response.json()
        show_success_message(console, f"Application '{name}' created successfully")
    else:
        show_error_message(console, f"Failed to create application: HTTP {response.status_code}")
        sys.exit(1)


@application.command("set")
@click.argument("application_name", metavar="<application>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Application ID (overrides name argument)")
@click.option("--name", "new_name", help="New application name")
@click.option("--description", help="New application description")
@click.option("--organization", help="New organization name or ID")
@click.option("--client-type", type=click.Choice(["public", "confidential"]), help="New OAuth client type")
@click.option(
    "--grant-type", type=click.Choice(["authorization-code", "password"]), help="New OAuth authorization grant type"
)
@click.option("--redirect-uris", help="New redirect URIs (space-separated URLs)")
@click.option("--skip-authorization/--no-skip-authorization", default=None, help="Enable/disable skip authorization")
@common_options
@update_command
def set_application(
    console,
    output_format,
    utc,
    application_name,
    id,
    new_name,
    description,
    organization,
    client_type,
    grant_type,
    redirect_uris,
    skip_authorization,
):
    """Update application settings."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve application identifier
    if id:
        app_id = id
        app_identifier = f"ID {id}"
    elif application_name:
        try:
            app_id = resolve_application_name(client, application_name)
            app_identifier = application_name
        except Exception:
            raise  # Let the decorator handle the error
    else:
        raise click.UsageError("Either application name or --id must be provided.")

    # Build update data
    update_data = {}

    if new_name:
        update_data["name"] = new_name
    if description is not None:  # Allow empty string
        update_data["description"] = description
    if organization:
        try:
            org_id = resolve_organization_name(client, organization)
            update_data["organization"] = org_id
        except Exception as e:
            show_error_message(console, f"Error resolving organization '{organization}': {e}")
            sys.exit(1)
    if client_type:
        update_data["client_type"] = client_type
    if grant_type:
        update_data["authorization_grant_type"] = grant_type
    if redirect_uris is not None:  # Allow empty string
        update_data["redirect_uris"] = redirect_uris
    if skip_authorization is not None:
        update_data["skip_authorization"] = skip_authorization

    if not update_data:
        show_error_message(console, "No updates specified")
        sys.exit(1)

    # Update application
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/{app_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        show_success_message(console, f"Application '{app_identifier}' updated successfully")

        # Show updated application details
        updated_app = response.json()
        formatted_data = _format_application_data(updated_app, utc, output_format)

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
        show_error_message(console, f"Failed to update application: HTTP {response.status_code}")
        sys.exit(1)


@application.command("delete")
@click.argument("application_name", metavar="<application>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Application ID (overrides name argument)")
@delete_command("Are you sure you want to delete this application?")
def delete_application(console, application_name, id):
    """Delete an application."""
    client_manager = get_client_from_context()
    client = client_manager.gateway

    # Resolve application identifier
    if id:
        app_id = id
        app_identifier = f"ID {id}"
    elif application_name:
        try:
            app_id = resolve_application_name(client, application_name)
            app_identifier = application_name
        except Exception:
            raise  # Let the decorator handle the error
    else:
        raise click.UsageError("Either application name or --id must be provided.")

    # Delete application
    endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/{app_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Application '{app_identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete application: HTTP {response.status_code}")
        sys.exit(1)


def register_application_commands(main_group: click.Group) -> None:
    """Register application commands with the main CLI group."""
    main_group.add_command(application)
