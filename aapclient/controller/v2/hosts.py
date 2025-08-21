"""Host commands for AAP CLI using Click and Rich."""

import sys
from typing import Dict, Any

import click
from click_option_group import optgroup, MutuallyExclusiveOptionGroup
from rich.table import Table

from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
)
from aapclient.common.functions import (
    resolve_host_name,
    resolve_inventory_name,
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
def host():
    """Manage AAP hosts."""


def _format_host_data(host_data: Dict[str, Any], use_utc: bool = False, output_format: str = "table") -> Dict[str, Any]:
    """Format host data for display."""
    data = {}

    # Basic information
    data["ID"] = str(host_data.get("id", ""))
    data["Name"] = host_data.get("name", "")
    data["Description"] = host_data.get("description", "")

    # Inventory
    inventory_info = host_data.get("summary_fields", {}).get("inventory", {})
    data["Inventory"] = inventory_info.get("name", "")

    # Status
    data["Enabled"] = format_value_for_output(host_data.get("enabled", False), "enabled", output_format)

    # Instance ID (if available)
    instance_id = host_data.get("instance_id", "")
    if instance_id:
        data["Instance ID"] = instance_id

    # Variables
    variables = host_data.get("variables", "")
    if variables:
        data["Variables"] = format_variables_display(variables, "host")
    else:
        data["Variables"] = ""

    # Last job information (if available)
    last_job = host_data.get("summary_fields", {}).get("last_job", {})
    if last_job:
        job_name = last_job.get("name", "")
        job_id = last_job.get("id", "")
        if job_name and job_id:
            data["Last Job"] = f"{job_name} (Job ID: {job_id})"

    # Timestamps
    data["Created"] = format_datetime_rich(host_data.get("created"), use_utc, output_format)
    data["Modified"] = format_datetime_rich(host_data.get("modified"), use_utc, output_format)

    # Created/Modified by
    created_by = host_data.get("summary_fields", {}).get("created_by", {})
    data["Created By"] = created_by.get("username", "") if created_by else ""

    modified_by = host_data.get("summary_fields", {}).get("modified_by", {})
    data["Modified By"] = modified_by.get("username", "") if modified_by else ""

    # Remove empty fields for cleaner display, but keep Description field
    data = {k: v for k, v in data.items() if v not in ["", None, "N/A"] or k == "Description"}

    return data


@host.command("list")
@click.option("--inventory", help="Filter by inventory name or ID")
@click.option("--enabled/--disabled", default=None, help="Filter by enabled status")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(
    default_limit=20, sort_fields=["id", "name", "inventory", "enabled", "created", "modified"], default_sort="id"
)
def list_hosts(console, output_format, utc, sort_by, reverse, limit, offset, inventory, enabled, show_all):
    """List hosts."""
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

    # Handle enabled filter
    if enabled is not None:
        params["enabled"] = enabled

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
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/"
    response = client.get(endpoint, params=params)
    data = response.json()
    hosts = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for host in hosts:
            inventory_name = host.get("summary_fields", {}).get("inventory", {}).get("name", "")
            processed_data.append(
                {
                    "ID": host.get("id"),
                    "Name": host.get("name", ""),
                    "Inventory": inventory_name,
                    "Enabled": format_value_for_output(host.get("enabled", False), "enabled", output_format),
                    "Description": host.get("description", ""),
                    "Created": format_datetime_rich(host.get("created", ""), utc, output_format),
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
    table.add_column("Enabled", style="green")
    table.add_column("Description", style="white")
    table.add_column("Created", style="green")

    for host in hosts:
        inventory_name = host.get("summary_fields", {}).get("inventory", {}).get("name", "")
        enabled_display = format_value_for_output(host.get("enabled", False), "enabled", output_format)

        table.add_row(
            str(host.get("id", "")),
            host.get("name", ""),
            inventory_name,
            enabled_display,
            host.get("description", "")[:50] + ("..." if len(host.get("description", "")) > 50 else ""),
            format_datetime_rich(host.get("created", ""), utc, output_format),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(hosts))
    if not show_all and len(hosts) < total_count:
        console.print(f"\nShowing {len(hosts)} of {total_count} total hosts")


@host.command("show")
@click.argument("host_name", metavar="<host>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Host ID (overrides name argument)")
@show_command
def show_host(console, output_format, utc, host_name, id):
    """Show details of a specific host."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve host ID
    if id:
        host_id = id
    elif host_name:
        host_id = resolve_host_name(client, host_name)
    else:
        show_error_message(console, "Host identifier is required")
        sys.exit(1)

    # Get host details
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
    response = client.get(endpoint)
    host_data = response.json()

    # Format host data for display
    formatted_data = _format_host_data(host_data, utc, output_format)

    if output_format == "json":
        show_raw_json(formatted_data)
    elif output_format == "yaml":
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


@host.command("create")
@click.argument("name", metavar="<name>")
@click.option("--inventory", required=True, help="Inventory name or ID")
@click.option("--description", help="Host description")
@click.option("--variables", help="Host variables in JSON or YAML format")
@create_command
def create_host(console, name, inventory, description, variables):
    """Create a new host."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve inventory ID
    try:
        inventory_id = resolve_inventory_name(client, inventory)
    except Exception as e:
        show_error_message(console, f"Error resolving inventory '{inventory}': {e}")
        sys.exit(1)

    # Build host data
    host_data = {"name": name, "inventory": inventory_id}

    if description:
        host_data["description"] = description

    if variables:
        host_data["variables"] = variables

    # Create host
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/"
    response = client.post(endpoint, json=host_data)

    if response.status_code == HTTP_CREATED:
        created_host = response.json()
        show_success_message(console, f"Host '{name}' created successfully")

        # Show the created host details
        formatted_data = _format_host_data(created_host, use_utc=False, output_format="table")
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Failed to create host: {response.status_code}")
        sys.exit(1)


@host.command("set")
@click.argument("host_name", metavar="<host>", required=False)
@click.option("--id", type=int, help="Host ID (overrides name argument)")
@click.option("--name", help="New host name")
@click.option("--description", help="New host description")
@optgroup.group("Host State", cls=MutuallyExclusiveOptionGroup, help="Control host enabled/disabled state")
@optgroup.option("--enabled", is_flag=True, help="Enable the host")
@optgroup.option("--disabled", is_flag=True, help="Disable the host")
@click.option("--variables", help="Host variables in JSON or YAML format")
@update_command
def set_host(console, host_name, id, name, description, enabled, disabled, variables):
    """Update host settings."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve host ID
    if id:
        host_id = id
        identifier = str(id)
    elif host_name:
        host_id = resolve_host_name(client, host_name)
        identifier = host_name
    else:
        show_error_message(console, "Host identifier is required")
        sys.exit(1)

    # Build update data
    update_data = {}

    if name:
        update_data["name"] = name
    if description is not None:  # Allow empty string
        update_data["description"] = description
    if enabled:
        update_data["enabled"] = True
    if disabled:
        update_data["enabled"] = False
    if variables is not None:  # Allow empty string
        update_data["variables"] = variables

    if not update_data:
        show_error_message(console, "No updates specified")
        sys.exit(1)

    # Update host
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
    response = client.patch(endpoint, json=update_data)

    if response.status_code == HTTP_OK:
        updated_host = response.json()
        show_success_message(console, f"Host '{identifier}' updated successfully")

        # Show the updated host details
        formatted_data = _format_host_data(updated_host, use_utc=False, output_format="table")
        show_details_table(console, formatted_data)
    else:
        show_error_message(console, f"Failed to update host: {response.status_code}")
        sys.exit(1)


@host.command("delete")
@click.argument("host_name", metavar="<host>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Host ID (overrides name argument)")
@delete_command("Are you sure you want to delete this host?")
def delete_host(console, host_name, id):
    """Delete a host."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve host ID
    if id:
        host_id = id
        identifier = str(id)
    elif host_name:
        host_id = resolve_host_name(client, host_name)
        identifier = host_name
    else:
        show_error_message(console, "Host identifier is required")
        sys.exit(1)

    # Delete host
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Host '{identifier}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete host: {response.status_code}")
        sys.exit(1)


# Host groups subcommands
@host.group("groups")
def host_groups():
    """Manage host groups."""


@host_groups.command("list")
@click.argument("host_name", metavar="<host>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Host ID (overrides name argument)")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(default_limit=20, sort_fields=["id", "name", "created", "modified"], default_sort="id")
def list_host_groups(console, output_format, utc, sort_by, reverse, limit, offset, host_name, id, show_all):
    """List groups that contain a host."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve host ID
    if id:
        host_id = id
    elif host_name:
        host_id = resolve_host_name(client, host_name)
    else:
        show_error_message(console, "Host identifier is required")
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
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/groups/"
    response = client.get(endpoint, params=params)
    data = response.json()
    groups = data.get("results", [])

    if output_format == "json":
        show_raw_json(groups)
        return
    elif output_format == "yaml":
        show_raw_yaml(groups)
        return

    # Table format
    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Description", style="white")
    table.add_column("Created", style="green")

    for group in groups:
        table.add_row(
            str(group.get("id", "")),
            group.get("name", ""),
            group.get("description", "")[:50] + ("..." if len(group.get("description", "")) > 50 else ""),
            format_datetime_rich(group.get("created", ""), utc, output_format),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(groups))
    if not show_all and len(groups) < total_count:
        console.print(f"\nShowing {len(groups)} of {total_count} total groups")


# Host metrics subcommands
@host.group("metrics")
def host_metrics():
    """Manage host metrics."""


@host_metrics.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(
    default_limit=20, sort_fields=["id", "hostname", "first_automation", "last_automation"], default_sort="id"
)
def list_host_metrics(console, output_format, utc, sort_by, reverse, limit, offset, show_all):
    """List all host metrics."""
    client_manager = get_client_from_context()
    client = client_manager.controller

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
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}host_metrics/"
    response = client.get(endpoint, params=params)
    data = response.json()
    metrics = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for metric in metrics:
            hostname = metric.get("hostname", "")
            processed_data.append(
                {
                    "ID": metric.get("id"),
                    "Hostname": hostname,
                    "First automation": format_datetime_rich(metric.get("first_automation", ""), utc, output_format),
                    "Last automation": format_datetime_rich(metric.get("last_automation", ""), utc, output_format),
                    "Last deleted": format_datetime_rich(metric.get("last_deleted", ""), utc, output_format),
                    "Automated counter": metric.get("automated_counter", 0),
                    "Deleted": format_value_for_output(metric.get("deleted", False), "deleted", output_format),
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
    table.add_column("Hostname", style="white")
    table.add_column("Automations", style="yellow")
    table.add_column("First Automation", style="green")
    table.add_column("Last Automation", style="green")
    table.add_column("Deleted", style="red")
    table.add_column("Deletions", style="yellow")

    for metric in metrics:
        table.add_row(
            str(metric.get("id", "")),
            metric.get("hostname", ""),
            str(metric.get("automated_counter", 0)),
            format_datetime_rich(metric.get("first_automation", ""), utc, output_format),
            format_datetime_rich(metric.get("last_automation", ""), utc, output_format),
            format_value_for_output(metric.get("deleted", False), "deleted", output_format),
            str(metric.get("deleted_counter", 0)),
        )

    console.print(table)

    # Show pagination info
    total_count = data.get("count", len(metrics))
    if not show_all and len(metrics) < total_count:
        console.print(f"\nShowing {len(metrics)} of {total_count} total metrics")


@host_metrics.command("show")
@click.argument("metric_id", metavar="<metric_id>", type=int)
@show_command
def show_host_metric(console, output_format, utc, metric_id):
    """Show details of a specific host metric."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Get metric details
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}host_metrics/{metric_id}/"
    response = client.get(endpoint)
    metric_data = response.json()

    # Format metric data for display
    data = {}
    data["ID"] = str(metric_data.get("id", ""))
    data["Hostname"] = metric_data.get("hostname", "")
    data["Automations"] = str(metric_data.get("automated_counter", 0))
    data["First Automation"] = format_datetime_rich(metric_data.get("first_automation", ""), utc, output_format)
    data["Last Automation"] = format_datetime_rich(metric_data.get("last_automation", ""), utc, output_format)
    data["Deleted"] = format_value_for_output(metric_data.get("deleted", False), "deleted", output_format)
    data["Deletions"] = str(metric_data.get("deleted_counter", 0))

    # Handle last_deleted field
    last_deleted = metric_data.get("last_deleted")
    if last_deleted:
        data["Last Deleted"] = format_datetime_rich(last_deleted, utc, output_format)

    # Used in inventories
    used_in_inventories = metric_data.get("used_in_inventories")
    if used_in_inventories:
        data["Used in Inventories"] = used_in_inventories

    # Host reference (if available)
    host_info = metric_data.get("summary_fields", {}).get("host", {})
    if host_info:
        data["Host"] = f"{host_info.get('name', '')} (ID: {host_info.get('id', '')})"

    # Remove empty fields
    data = {k: v for k, v in data.items() if v not in ["", None, "N/A"]}

    if output_format == "json":
        show_raw_json(data)
    elif output_format == "yaml":
        show_raw_yaml(data)
    else:
        show_details_table(console, data)


@host_metrics.command("delete")
@click.argument("metric_id", metavar="<metric_id>", type=int)
@delete_command("Are you sure you want to delete this host metric?")
def delete_host_metric(console, metric_id):
    """Delete a host metric."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Delete metric
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}host_metrics/{metric_id}/"
    response = client.delete(endpoint)

    if response.status_code == HTTP_NO_CONTENT:
        show_success_message(console, f"Host metric '{metric_id}' deleted successfully")
    else:
        show_error_message(console, f"Failed to delete host metric: {response.status_code}")
        sys.exit(1)


# Host variables subcommands
@host.group("variables")
def host_variables():
    """Manage host variables."""


# Host facts subcommands
@host.group("facts")
def host_facts():
    """Manage host facts."""


@host_facts.command("show")
@click.argument("host_name", metavar="<host>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Host ID (overrides name argument)")
@show_command
def show_host_facts(console, output_format, utc, host_name, id):
    """Show host facts in YAML format."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve host ID
    if id:
        host_id = id
        identifier = str(id)
    elif host_name:
        host_id = resolve_host_name(client, host_name)
        identifier = host_name
    else:
        show_error_message(console, "Host identifier is required")
        sys.exit(1)

    # Get host details first to get the host name for display
    host_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
    host_response = client.get(host_endpoint)
    host_data = host_response.json()
    host_name_display = host_data.get("name", identifier)

    # Get host facts
    facts_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/ansible_facts/"
    response = client.get(facts_endpoint)
    facts_data = response.json()

    if output_format == "json":
        show_raw_json(facts_data)
    elif output_format == "yaml":
        show_raw_yaml(facts_data)
    else:
        # Table format showing host name and facts in YAML
        from aapclient.common.functions import format_variables_yaml_display

        facts_yaml = format_variables_yaml_display(facts_data)

        # Create a simple key-value display similar to host variables show
        data = {"Host": host_name_display, "Facts": facts_yaml}
        show_details_table(console, data)


@host_variables.command("show")
@click.argument("host_name", metavar="<host>", required=False, callback=validate_resource_identifier)
@click.option("--id", type=int, help="Host ID (overrides name argument)")
@show_command
def show_host_variables(console, output_format, utc, host_name, id):
    """Show host variables in YAML format."""
    client_manager = get_client_from_context()
    client = client_manager.controller

    # Resolve host ID
    if id:
        host_id = id
        str(id)
    elif host_name:
        host_id = resolve_host_name(client, host_name)
    else:
        show_error_message(console, "Host identifier is required")
        sys.exit(1)

    # Get host details
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}hosts/{host_id}/"
    response = client.get(endpoint)
    host_data = response.json()

    # Extract and parse variables for display
    variables_raw = host_data.get("variables", {})
    variables_parsed = parse_variables_for_output(variables_raw)

    if output_format == "json":
        show_raw_json(variables_parsed)
    elif output_format == "yaml":
        show_raw_yaml(variables_parsed)
    else:
        # Table format showing host name and variables in YAML
        variables_yaml = format_variables_yaml_display(variables_raw)

        # Create a simple key-value display
        data = {"Host": host_data["name"], "Variables": variables_yaml}
        show_details_table(console, data)


def register_host_commands(main_group: click.Group) -> None:
    """Register host commands with the main CLI group."""
    main_group.add_command(host)
