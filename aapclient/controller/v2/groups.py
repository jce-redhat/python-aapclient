"""Group commands for AAP CLI using Click and Rich."""

import sys
from typing import Dict, Any

import click
from rich.table import Table

from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
)
from aapclient.common.functions import (
    resolve_group_name,
    resolve_inventory_name,
    resolve_host_name,
    format_variables_display,
    format_variables_yaml_display,
    parse_variables_for_output,
)
from aapclient.decorators import (
    list_command,
    show_command,
    create_command,
    update_command,
    delete_command,
    standard_command,
    get_client_from_context,
    validate_resource_identifier,
)
from aapclient.output import (
    show_details_table,
    show_raw_json,
    show_raw_yaml,
    show_success_message,
    show_error_message,
    format_datetime_rich,
    format_value_for_output,
)


@click.group()
def group():
    """Manage AAP groups."""


def _get_group_resource_count(client, group_id, resource_type):
    """
    Get the count of a specific resource type for a group.

    Args:
        client: AAPHTTPClient instance
        group_id: Group ID
        resource_type: Type of resource to count ('children' or 'hosts')

    Returns:
        int: Number of resources (0 if error or no resources)
    """
    try:
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/{resource_type}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            data = response.json()
            return data.get("count", 0)
    except:
        pass  # Return 0 on any error
    return 0


def _format_group_data(
    group_data: Dict[str, Any], client=None, use_utc: bool = False, output_format: str = "table"
) -> Dict[str, Any]:
    """Format group data for display."""
    data = {}

    # Basic information
    data["ID"] = str(group_data.get("id", ""))
    data["Name"] = group_data.get("name", "")
    data["Description"] = group_data.get("description", "")

    # Inventory
    inventory_info = group_data.get("summary_fields", {}).get("inventory", {})
    data["Inventory"] = inventory_info.get("name", "")

    # Resource counts (get from API if client provided)
    if client:
        group_id = group_data.get("id")
        if group_id:
            data["Total Hosts"] = str(_get_group_resource_count(client, group_id, "hosts"))
            data["Total Child Groups"] = str(_get_group_resource_count(client, group_id, "children"))
    else:
        data["Total Hosts"] = "0"
        data["Total Child Groups"] = "0"

    # Variables
    variables = group_data.get("variables", "")
    if variables:
        data["Variables"] = format_variables_display(variables, "group")
    else:
        data["Variables"] = ""

    # Timestamps
    data["Created"] = format_datetime_rich(group_data.get("created"), use_utc, output_format)
    data["Modified"] = format_datetime_rich(group_data.get("modified"), use_utc, output_format)

    # Created/Modified by
    created_by = group_data.get("summary_fields", {}).get("created_by", {})
    data["Created By"] = created_by.get("username", "") if created_by else ""

    modified_by = group_data.get("summary_fields", {}).get("modified_by", {})
    data["Modified By"] = modified_by.get("username", "") if modified_by else ""

    # Remove empty fields for cleaner display, but keep Description field
    data = {k: v for k, v in data.items() if v not in ["", None, "N/A"] or k == "Description"}

    return data


@group.command("list")
@click.option("--inventory", help="Filter by inventory name or ID")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(default_limit=20, sort_fields=["id", "name", "inventory", "created", "modified"], default_sort="id")
def list_groups(console, output_format, utc, sort_by, reverse, limit, offset, inventory, show_all):
    """List groups."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build API parameters
    params = {}

    # Handle inventory filter
    if inventory:
        try:
            inventory_id = resolve_inventory_name(client, inventory)
            params["inventory"] = inventory_id
        except Exception as e:
            show_error_message(console, f"Error resolving inventory '{inventory}': {e}")
            sys.exit(1)

    # Pagination
    if not show_all:
        params["page_size"] = limit
        params["page"] = (offset // limit) + 1

    # Sorting
    sort_field = sort_by if sort_by else "id"
    if reverse:
        if sort_field == "id":
            params["order_by"] = sort_field  # oldest first
        else:
            params["order_by"] = f"-{sort_field}"
    else:
        if sort_field == "id":
            params["order_by"] = f"-{sort_field}"  # newest first (default)
        else:
            params["order_by"] = sort_field

    # Fetch data
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/"
    response = client.get(endpoint, params=params)
    data = response.json()
    groups = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for group in groups:
            inventory_name = group.get("summary_fields", {}).get("inventory", {}).get("name", "")
            processed_data.append(
                {
                    "ID": group.get("id"),
                    "Name": group.get("name", ""),
                    "Inventory": inventory_name,
                    "Description": group.get("description", ""),
                    "Created": format_datetime_rich(
                        group.get("created", ""), use_utc=False, output_format=output_format
                    ),
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
    table.add_column("Inventory", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("Created", style="green")

    for group in groups:
        inventory_name = group.get("summary_fields", {}).get("inventory", {}).get("name", "")

        table.add_row(
            str(group.get("id", "")),
            group.get("name", ""),
            inventory_name,
            group.get("description", "")[:50] + ("..." if len(group.get("description", "")) > 50 else ""),
            format_datetime_rich(group.get("created", ""), utc, output_format),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(groups))
    if not show_all and len(groups) < total_count:
        console.print(f"\nShowing {len(groups)} of {total_count} total groups")


@group.command("show")
@click.argument("group_name", metavar="<group>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Group ID (overrides name argument)")
@show_command
def show_group(console, output_format, utc, group_name, id):
    """Show details of a specific group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if id:
        group_id = id
    elif group_name:
        group_id = resolve_group_name(client, group_name)
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Get group details
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
    response = client.get(endpoint)
    group_data = response.json()

    # Format group data for display
    formatted_data = _format_group_data(group_data, client, utc, output_format)

    if output_format == "json":
        show_raw_json(formatted_data)
    elif output_format == "yaml":
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


@group.command("create")
@click.argument("name", metavar="<name>")
@click.option("--inventory", required=True, help="Inventory name or ID")
@click.option("--description", help="Group description")
@click.option("--variables", help="Group variables in JSON or YAML format")
@create_command
def create_group(console, name, inventory, description, variables):
    """Create a new group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve inventory ID
    try:
        inventory_id = resolve_inventory_name(client, inventory)
    except Exception as e:
        show_error_message(console, f"Error resolving inventory '{inventory}': {e}")
        sys.exit(1)

    # Build group data
    group_data = {"name": name, "inventory": inventory_id}

    if description:
        group_data["description"] = description

    if variables:
        group_data["variables"] = variables

    # Create group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/"
    response = client.post(endpoint, json=group_data)

    if response.status_code == HTTP_CREATED:
        created_group = response.json()
        show_success_message(console, f"Group '{name}' created successfully")

        # Show the created group details
        formatted_data = _format_group_data(created_group, client, use_utc=False, output_format="table")
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Failed to create group: {response.status_code}")
        sys.exit(1)


@group.command("set")
@click.argument("group_name", metavar="<group>", required=False)
@click.option("--id", type=int, help="Group ID (overrides name argument)")
@click.option("--name", help="New group name")
@click.option("--description", help="New group description")
@click.option("--variables", help="Group variables in JSON or YAML format")
@update_command
def set_group(console, group_name, id, name, description, variables):
    """Update group settings."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if id:
        group_id = id
        identifier = str(id)
    elif group_name:
        group_id = resolve_group_name(client, group_name)
        identifier = group_name
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Build update data
    update_data = {}

    if name:
        update_data["name"] = name
    if description is not None:  # Allow empty string
        update_data["description"] = description
    if variables is not None:  # Allow empty string
        update_data["variables"] = variables

    if not update_data:
        show_error_message(console, "No updates specified")
        sys.exit(1)

    # Update group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        updated_group = response.json()
        show_success_message(console, f"Group '{identifier}' updated successfully")

        # Show the updated group details
        formatted_data = _format_group_data(updated_group, client, use_utc=False, output_format="table")
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Failed to update group: {response.status_code}")
        sys.exit(1)


@group.command("delete")
@click.argument("group_name", metavar="<group>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Group ID (overrides name argument)")
@delete_command("Are you sure you want to delete this group?")
def delete_group(console, group_name, id):
    """Delete a group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if id:
        group_id = id
        identifier = str(id)
    elif group_name:
        group_id = resolve_group_name(client, group_name)
        identifier = group_name
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Delete group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Group '{identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete group: {response.status_code}")
        sys.exit(1)


# Group hosts subcommands
@group.group("hosts")
def group_hosts():
    """Manage group hosts."""


@group_hosts.command("list")
@click.argument("group_name", metavar="<group>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Group ID (overrides name argument)")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(default_limit=20, sort_fields=["id", "name", "created", "modified"], default_sort="id")
def list_group_hosts(console, output_format, utc, sort_by, reverse, limit, offset, group_name, id, show_all):
    """List hosts in a group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if id:
        group_id = id
    elif group_name:
        group_id = resolve_group_name(client, group_name)
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Build API parameters
    params = {}

    # Pagination
    if not show_all:
        params["page_size"] = limit
        params["page"] = (offset // limit) + 1

    # Sorting
    sort_field = sort_by if sort_by else "id"
    if reverse:
        if sort_field == "id":
            params["order_by"] = sort_field  # oldest first
        else:
            params["order_by"] = f"-{sort_field}"
    else:
        if sort_field == "id":
            params["order_by"] = f"-{sort_field}"  # newest first (default)
        else:
            params["order_by"] = sort_field

    # Fetch data
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/hosts/"
    response = client.get(endpoint, params=params)
    data = response.json()
    hosts = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for host in hosts:
            processed_data.append(
                {
                    "ID": host.get("id"),
                    "Name": host.get("name", ""),
                    "Enabled": format_value_for_output(host.get("enabled", False), "enabled", output_format),
                    "Description": host.get("description", ""),
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
    table.add_column("Description", style="white")
    table.add_column("Created", style="green")

    for host in hosts:
        table.add_row(
            str(host.get("id", "")),
            host.get("name", ""),
            host.get("description", "")[:50] + ("..." if len(host.get("description", "")) > 50 else ""),
            format_datetime_rich(host.get("created", ""), utc, output_format),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(hosts))
    if not show_all and len(hosts) < total_count:
        console.print(f"\nShowing {len(hosts)} of {total_count} total hosts")


@group_hosts.command("add")
@click.argument("group_name", metavar="<group>", required=False)
@click.option("--group-id", type=int, help="Group ID (overrides name argument)")
@click.argument("host_name", metavar="<host>", required=False)
@click.option("--host-id", type=int, help="Host ID (overrides host name argument)")
@standard_command
def add_group_host(console, group_name, group_id, host_name, host_id):
    """Add a host to a group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if group_id:
        resolved_group_id = group_id
        group_identifier = str(group_id)
    elif group_name:
        resolved_group_id = resolve_group_name(client, group_name)
        group_identifier = group_name
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Resolve host ID
    if host_id:
        resolved_host_id = host_id
        host_identifier = str(host_id)
    elif host_name:
        resolved_host_id = resolve_host_name(client, host_name)
        host_identifier = host_name
    else:
        show_error_message(console, "Host identifier is required")
        sys.exit(1)

    # Add host to group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{resolved_group_id}/hosts/"
    host_data = {"id": resolved_host_id}
    response = client.post(endpoint, json=host_data)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Host '{host_identifier}' added to group '{group_identifier}'")
    else:
        show_error_message(console, f"Failed to add host to group: {response.status_code}")
        sys.exit(1)


@group_hosts.command("remove")
@click.argument("group_name", metavar="<group>", required=False)
@click.option("--group-id", type=int, help="Group ID (overrides name argument)")
@click.argument("host_name", metavar="<host>", required=False)
@click.option("--host-id", type=int, help="Host ID (overrides host name argument)")
@standard_command
def remove_group_host(console, group_name, group_id, host_name, host_id):
    """Remove a host from a group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if group_id:
        resolved_group_id = group_id
        group_identifier = str(group_id)
    elif group_name:
        resolved_group_id = resolve_group_name(client, group_name)
        group_identifier = group_name
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Resolve host ID
    if host_id:
        resolved_host_id = host_id
        host_identifier = str(host_id)
    elif host_name:
        resolved_host_id = resolve_host_name(client, host_name)
        host_identifier = host_name
    else:
        show_error_message(console, "Host identifier is required")
        sys.exit(1)

    # Remove host from group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{resolved_group_id}/hosts/"
    host_data = {"id": resolved_host_id, "disassociate": True}
    response = client.post(endpoint, json=host_data)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Host '{host_identifier}' removed from group '{group_identifier}'")
    else:
        show_error_message(console, f"Failed to remove host from group: {response.status_code}")
        sys.exit(1)


# Group children subcommands
@group.group("children")
def group_children():
    """Manage group children."""


@group_children.command("list")
@click.argument("group_name", metavar="<group>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Group ID (overrides name argument)")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(default_limit=20, sort_fields=["id", "name", "created", "modified"], default_sort="id")
def list_group_children(console, output_format, utc, sort_by, reverse, limit, offset, group_name, id, show_all):
    """List child groups of a group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if id:
        group_id = id
    elif group_name:
        group_id = resolve_group_name(client, group_name)
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Build API parameters
    params = {}

    # Pagination
    if not show_all:
        params["page_size"] = limit
        params["page"] = (offset // limit) + 1

    # Sorting
    sort_field = sort_by if sort_by else "id"
    if reverse:
        if sort_field == "id":
            params["order_by"] = sort_field  # oldest first
        else:
            params["order_by"] = f"-{sort_field}"
    else:
        if sort_field == "id":
            params["order_by"] = f"-{sort_field}"  # newest first (default)
        else:
            params["order_by"] = sort_field

    # Fetch data
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/children/"
    response = client.get(endpoint, params=params)
    data = response.json()
    children = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for child in children:
            processed_data.append(
                {"ID": child.get("id"), "Name": child.get("name", ""), "Description": child.get("description", "")}
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
    table.add_column("Description", style="white")
    table.add_column("Created", style="green")

    for child in children:
        table.add_row(
            str(child.get("id", "")),
            child.get("name", ""),
            child.get("description", "")[:50] + ("..." if len(child.get("description", "")) > 50 else ""),
            format_datetime_rich(child.get("created", ""), utc, output_format),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(children))
    if not show_all and len(children) < total_count:
        console.print(f"\nShowing {len(children)} of {total_count} total child groups")


@group_children.command("add")
@click.argument("parent_group_name", metavar="<parent_group>", required=False)
@click.option("--parent-group-id", type=int, help="Parent group ID (overrides name argument)")
@click.argument("child_group_name", metavar="<child_group>", required=False)
@click.option("--child-group-id", type=int, help="Child group ID (overrides name argument)")
@standard_command
def add_group_child(console, parent_group_name, parent_group_id, child_group_name, child_group_id):
    """Add a child group to a parent group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve parent group ID
    if parent_group_id:
        resolved_parent_id = parent_group_id
        parent_identifier = str(parent_group_id)
    elif parent_group_name:
        resolved_parent_id = resolve_group_name(client, parent_group_name)
        parent_identifier = parent_group_name
    else:
        show_error_message(console, "Parent group identifier is required")
        sys.exit(1)

    # Resolve child group ID
    if child_group_id:
        resolved_child_id = child_group_id
        child_identifier = str(child_group_id)
    elif child_group_name:
        resolved_child_id = resolve_group_name(client, child_group_name)
        child_identifier = child_group_name
    else:
        show_error_message(console, "Child group identifier is required")
        sys.exit(1)

    # Add child group to parent group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{resolved_parent_id}/children/"
    child_data = {"id": resolved_child_id}
    response = client.post(endpoint, json=child_data)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Group '{child_identifier}' added as child of group '{parent_identifier}'")
    else:
        show_error_message(console, f"Failed to add child group: {response.status_code}")
        sys.exit(1)


@group_children.command("remove")
@click.argument("parent_group_name", metavar="<parent_group>", required=False)
@click.option("--parent-group-id", type=int, help="Parent group ID (overrides name argument)")
@click.argument("child_group_name", metavar="<child_group>", required=False)
@click.option("--child-group-id", type=int, help="Child group ID (overrides name argument)")
@standard_command
def remove_group_child(console, parent_group_name, parent_group_id, child_group_name, child_group_id):
    """Remove a child group from a parent group."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve parent group ID
    if parent_group_id:
        resolved_parent_id = parent_group_id
        parent_identifier = str(parent_group_id)
    elif parent_group_name:
        resolved_parent_id = resolve_group_name(client, parent_group_name)
        parent_identifier = parent_group_name
    else:
        show_error_message(console, "Parent group identifier is required")
        sys.exit(1)

    # Resolve child group ID
    if child_group_id:
        resolved_child_id = child_group_id
        child_identifier = str(child_group_id)
    elif child_group_name:
        resolved_child_id = resolve_group_name(client, child_group_name)
        child_identifier = child_group_name
    else:
        show_error_message(console, "Child group identifier is required")
        sys.exit(1)

    # Remove child group from parent group
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{resolved_parent_id}/children/"
    child_data = {"id": resolved_child_id, "disassociate": True}
    response = client.post(endpoint, json=child_data)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Group '{child_identifier}' removed as child of group '{parent_identifier}'")
    else:
        show_error_message(console, f"Failed to remove child group: {response.status_code}")
        sys.exit(1)


# Group variables subcommands
@group.group("variables")
def group_variables():
    """Manage group variables."""


@group_variables.command("show")
@click.argument("group_name", metavar="<group>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Group ID (overrides name argument)")
@show_command
def show_group_variables(console, output_format, utc, group_name, id):
    """Show group variables in YAML format."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve group ID
    if id:
        group_id = id
        str(id)
    elif group_name:
        group_id = resolve_group_name(client, group_name)
    else:
        show_error_message(console, "Group identifier is required")
        sys.exit(1)

    # Get group details
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}groups/{group_id}/"
    response = client.get(endpoint)
    group_data = response.json()

    # Extract and parse variables for display
    variables_raw = group_data.get("variables", {})
    variables_parsed = parse_variables_for_output(variables_raw)

    if output_format == "json":
        show_raw_json(variables_parsed)
    elif output_format == "yaml":
        show_raw_yaml(variables_parsed)
    else:
        # Table format showing group name and variables in YAML
        variables_yaml = format_variables_yaml_display(variables_raw)

        # Create a simple key-value display
        data = {"Group": group_data["name"], "Variables": variables_yaml}
        show_details_table(console, data)


def register_group_commands(main_group: click.Group) -> None:
    """Register group commands with the main CLI group."""
    main_group.add_command(group)
