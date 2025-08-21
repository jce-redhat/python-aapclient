"""Job management commands for AAP CLI."""

import sys
import click
from aapclient.decorators import (
    list_command,
    show_command,
    standard_command,
)
from aapclient.output import (
    show_raw_json,
    show_raw_yaml,
    show_details_table,
    create_table,
    format_datetime_rich,
    format_duration_rich,
    format_value_for_output,
)
from aapclient.common.constants import CONTROLLER_API_VERSION_ENDPOINT, HTTP_OK


@click.group()
def job():
    """Manage AAP jobs."""


@job.command("list")
@click.option(
    "--type",
    "job_type",
    type=click.Choice(["job", "project_update", "inventory_update", "system_job", "workflow_job"]),
    help="Filter by job type",
)
@click.option("--all", "show_all", is_flag=True, help="Show all results (no pagination)")
@list_command(
    default_limit=20,
    sort_fields=["id", "name", "type", "status", "started", "finished", "elapsed"],
    default_sort="id",  # Will be reversed to newest first
)
def list_jobs(console, output_format, utc, offset, limit, sort_by, reverse, show_all, job_type):
    """List jobs."""
    from aapclient.decorators import get_client_from_context

    client_manager = get_client_from_context()
    client = client_manager.controller

    # Build query parameters
    params = {}

    # Add server-side sorting
    # Default to ID sorting if no sort field specified
    sort_field = sort_by if sort_by else "id"

    # For jobs, we want newest first by default when sorting by ID
    if sort_field == "id":
        # Reverse the logic for ID: default to newest first, reverse gives oldest first
        if reverse:
            order_field = sort_field  # oldest first
        else:
            order_field = f"-{sort_field}"  # newest first (default)
    else:
        # For other fields, normal logic: default ascending, reverse for descending
        if reverse:
            order_field = f"-{sort_field}"
        else:
            order_field = sort_field

    params["order_by"] = order_field

    # Add type filter if specified
    if job_type:
        params["type"] = job_type

    # Fetch jobs with proper pagination handling
    endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}unified_jobs/"

    if show_all:
        # Fetch all results by paginating through all pages
        jobs = []
        page = 1
        params["page_size"] = 200  # Use large page size for efficiency

        while True:
            params["page"] = page
            response = client.get(endpoint, params=params)
            page_data = response.json()
            page_jobs = page_data.get("results", [])

            if not page_jobs:
                break

            jobs.extend(page_jobs)

            # Check if we have more pages
            if not page_data.get("next"):
                break

            page += 1

        # Create a mock data structure for consistency
        data = {"count": len(jobs), "results": jobs}
    else:
        # Regular pagination
        params["page_size"] = limit
        params["page"] = (offset // limit) + 1

        response = client.get(endpoint, params=params)
        data = response.json()
        jobs = data.get("results", [])

    if output_format in ["json", "yaml"]:
        # Process data into the format that matches table columns
        processed_data = []
        for job in jobs:
            # Format duration
            elapsed = job.get("elapsed", 0)
            duration_display = format_duration_rich(elapsed, output_format) if elapsed else ""

            processed_data.append(
                {
                    "ID": job.get("id"),
                    "Name": job.get("name", ""),
                    "Type": job.get("type", ""),
                    "Status": job.get("status", ""),
                    "Duration": duration_display,
                    "Started": format_datetime_rich(job.get("started", ""), utc, output_format),
                    "Finished": format_datetime_rich(job.get("finished", ""), utc, output_format),
                }
            )

        if output_format == "json":
            show_raw_json(processed_data)
        else:
            show_raw_yaml(processed_data)
        return

    # Prepare output for table format
    else:
        # Table format
        columns = ["ID", "Name", "Type", "Status", "Duration", "Started", "Finished"]
        rows = []

        for job in jobs:
            # Format duration
            elapsed = job.get("elapsed", 0)
            duration_display = format_duration_rich(elapsed, output_format) if elapsed else ""

            # Format status with rich colors
            status = job.get("status", "")
            status_display = format_value_for_output(status, "status", output_format)

            row = [
                str(job.get("id", "")),
                job.get("name", ""),
                job.get("type", ""),
                status_display,
                duration_display,
                format_datetime_rich(job.get("started", ""), utc, output_format),
                format_datetime_rich(job.get("finished", ""), utc, output_format),
            ]
            rows.append(row)

        table = create_table(columns, rows)
        console.print(table)

        # Show pagination info
        total_count = data.get("count", len(jobs))
        if not show_all and len(jobs) < total_count:
            console.print(f"\nShowing {len(jobs)} of {total_count} total jobs")


@job.command("output")
@click.argument("job_id", metavar="<job_id>")
@standard_command
def show_job_output(console, job_id):
    """Show job output/stdout."""
    from aapclient.decorators import get_client_from_context

    client_manager = get_client_from_context()
    client = client_manager.controller

    # Validate that job_id is numeric
    try:
        job_id = int(job_id)
    except ValueError:
        show_error_message(console, f"Job ID must be numeric, got: '{job_id}'")
        sys.exit(1)

    # First, get the job from unified_jobs to determine its type
    unified_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}unified_jobs/"
    response = client.get(unified_endpoint, params={"id": job_id})
    unified_data = response.json()
    results = unified_data.get("results", [])

    if not results:
        show_error_message(console, f"Job {job_id} not found")
        sys.exit(1)

    job_preview = results[0]
    job_type = job_preview.get("type", "")

    # Handle different job types
    if job_type == "job":
        # Regular jobs have stdout endpoint
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}jobs/{job_id}/stdout/"
        response = client.get(endpoint, params={"format": "txt"})

        if response.status_code == HTTP_OK:
            output = response.text
            if output:
                console.print(output, highlight=False)
            else:
                console.print("No output available for this job.")
        elif response.status_code == 404:
            console.print(f"No output available for {job_type} {job_id}.")
        else:
            show_error_message(console, f"Failed to get job output: HTTP {response.status_code}")
            sys.exit(1)

    elif job_type in ["project_update", "inventory_update"]:
        # Project and inventory updates have stdout endpoints
        type_endpoint_map = {
            "project_update": f"project_updates/{job_id}/stdout/",
            "inventory_update": f"inventory_updates/{job_id}/stdout/",
        }

        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}{type_endpoint_map[job_type]}"
        response = client.get(endpoint, params={"format": "txt"})

        if response.status_code == HTTP_OK:
            output = response.text
            if output:
                console.print(output, highlight=False)
            else:
                console.print("No output available for this job.")
        elif response.status_code == 404:
            console.print(f"No output available for {job_type} {job_id}.")
        else:
            show_error_message(console, f"Failed to get job output: HTTP {response.status_code}")
            sys.exit(1)

    elif job_type == "system_job":
        # System jobs store output in result_stdout field
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}system_jobs/{job_id}/"
        response = client.get(endpoint)

        if response.status_code == HTTP_OK:
            job_data = response.json()
            result_stdout = job_data.get("result_stdout", "")
            if result_stdout:
                console.print(result_stdout, highlight=False)
            else:
                console.print("No output available for this system job.")
        else:
            show_error_message(console, f"Failed to get system job details: HTTP {response.status_code}")
            sys.exit(1)

    elif job_type == "workflow_job":
        # Workflow jobs show nodes and execution status in a table
        endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}workflow_jobs/{job_id}/workflow_nodes/"
        response = client.get(endpoint)

        if response.status_code == HTTP_OK:
            nodes_data = response.json()
            nodes = nodes_data.get("results", [])

            if nodes:
                # Create rich table for workflow nodes
                from rich.table import Table

                table = Table()
                table.add_column("Node", style="cyan")
                table.add_column("Execution Status", style="white")

                for node in nodes:
                    # Left column: Node ID + name (prefer identifier, fallback to template name)
                    node_id = node.get("id", "")

                    # Prefer identifier field when set, as it's more descriptive for workflow nodes
                    identifier = node.get("identifier", "")
                    if identifier:
                        node_name = identifier
                    else:
                        # Fallback to unified_job_template name
                        template_info = node.get("summary_fields", {}).get("unified_job_template", {})
                        node_name = template_info.get("name", "Unknown Template")

                    node_column = f"{node_id}: {node_name}"

                    # Right column: Status + job info + duration with visual indicators
                    job_info = node.get("summary_fields", {}).get("job", {})
                    do_not_run = node.get("do_not_run", False)

                    if do_not_run:
                        # Node was skipped
                        status_column = "[dim]⊘ skipped • No Job[/dim]"
                    elif job_info:
                        # Node was executed
                        job_id_inner = job_info.get("id", "-")
                        status = job_info.get("status", "unknown")
                        job_elapsed = job_info.get("elapsed", 0)

                        # Visual status indicators with colors
                        if status == "successful":
                            status_icon = "[green]✓[/green]"
                        elif status == "failed":
                            status_icon = "[red]✗[/red]"
                        elif status in ["pending", "waiting", "running"]:
                            status_icon = "[yellow]⋯[/yellow]"
                        else:
                            status_icon = "[dim]?[/dim]"

                        # Format duration
                        if job_elapsed:
                            duration = format_duration_rich(job_elapsed)
                        else:
                            duration = "-"

                        status_column = f"{status_icon} {status} • Job {job_id_inner} • {duration}"
                    else:
                        # Node exists but no job info
                        status_column = "[dim]? no job info[/dim]"

                    table.add_row(node_column, status_column)

                console.print(table)
            else:
                console.print("No workflow nodes found for this workflow job.")
        else:
            show_error_message(console, f"Failed to get workflow job nodes: HTTP {response.status_code}")
            sys.exit(1)

    else:
        # Unknown job type
        show_error_message(
            console,
            f"Unsupported job type: {job_type}. Supported types: job, project_update, inventory_update, system_job, workflow_job",
        )
        sys.exit(1)


@job.command("show")
@click.argument("job_id", metavar="<job_id>")
@show_command
def show_job(console, output_format, utc, job_id):
    """Show details of a specific job."""
    from aapclient.decorators import get_client_from_context

    client_manager = get_client_from_context()
    client = client_manager.controller

    # Validate that job_id is numeric
    try:
        job_id = int(job_id)
    except ValueError:
        show_error_message(console, f"Job ID must be numeric, got: '{job_id}'")
        sys.exit(1)

    # First, get the job from unified_jobs to determine its type
    unified_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}unified_jobs/"
    response = client.get(unified_endpoint, params={"id": job_id})
    unified_data = response.json()
    results = unified_data.get("results", [])

    if not results:
        show_error_message(console, f"Job {job_id} not found")
        sys.exit(1)

    job_preview = results[0]
    job_type = job_preview.get("type", "")

    # Map job type to specific endpoint
    type_endpoint_map = {
        "job": "jobs",
        "project_update": "project_updates",
        "inventory_update": "inventory_updates",
        "system_job": "system_jobs",
        "workflow_job": "workflow_jobs",
    }

    if job_type not in type_endpoint_map:
        show_error_message(console, f"Unknown job type: {job_type}")
        sys.exit(1)

    # Get the full job details from the specific endpoint
    specific_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}{type_endpoint_map[job_type]}/{job_id}/"
    response = client.get(specific_endpoint)
    job_data = response.json()

    # Format job data for display
    formatted_data = _format_job_data(job_data, utc, output_format)

    if output_format == "json":
        show_raw_json(formatted_data)
    elif output_format == "yaml":
        show_raw_yaml(formatted_data)
    else:
        show_details_table(console, formatted_data)


def _format_job_data(job_data: dict, use_utc: bool = False, output_format: str = "table") -> dict:
    """Format job data for display with comprehensive fields based on job type."""
    from aapclient.common.functions import format_variables_display

    data = {}
    summary_fields = job_data.get("summary_fields", {})
    job_type = job_data.get("type", "")

    # Common fields for all job types (in specified order)
    data["ID"] = str(job_data.get("id", ""))
    data["Name"] = job_data.get("name", "")
    data["Status"] = format_value_for_output(job_data.get("status", ""), "status", output_format)
    data["Type"] = job_data.get("type", "")

    # Duration
    elapsed = job_data.get("elapsed", 0)
    data["Duration"] = format_duration_rich(elapsed, output_format) if elapsed else "N/A"

    # Timing
    data["Started"] = format_datetime_rich(job_data.get("started", ""), use_utc, output_format)
    data["Finished"] = format_datetime_rich(job_data.get("finished", ""), use_utc, output_format)

    # Launched by information
    launched_by = job_data.get("launched_by", {})
    if launched_by:
        data["Launched By"] = f"{launched_by.get('name', '')} ({launched_by.get('type', '')})"
    else:
        data["Launched By"] = ""

    # Launch type
    data["Launch Type"] = job_data.get("launch_type", "")

    # Job type specific fields
    if job_type == "workflow_job":
        # Workflow job template name
        workflow_template = summary_fields.get("workflow_job_template", {})
        data["Workflow Job Template"] = workflow_template.get("name", "")

        # Job slice parent
        data["Job Slice Parent"] = str(job_data.get("job_slice_parent", "")) if job_data.get("job_slice_parent") else ""

    elif job_type == "job":
        # Job template name
        job_template = summary_fields.get("job_template", {})
        data["Job Template"] = job_template.get("name", "")

        # Inventory
        inventory = summary_fields.get("inventory", {})
        data["Inventory"] = inventory.get("name", "")

        # Project
        project = summary_fields.get("project", {})
        data["Project"] = project.get("name", "")

        # Execution environment
        execution_env = summary_fields.get("execution_environment", {})
        data["Execution Environment"] = execution_env.get("name", "")

        # Credentials
        credentials = summary_fields.get("credentials", [])
        if credentials:
            cred_names = [cred.get("name", "") for cred in credentials if cred.get("name")]
            data["Credentials"] = ", ".join(cred_names)
        else:
            data["Credentials"] = ""

        # Job slice info
        job_slice_count = job_data.get("job_slice_count", 0)
        job_slice_number = job_data.get("job_slice_number", 0)
        if job_slice_count > 1:
            data["Job Slice"] = f"{job_slice_number + 1}/{job_slice_count}"
        else:
            data["Job Slice"] = ""

        data["Job Slice Parent"] = str(job_data.get("job_slice_parent", "")) if job_data.get("job_slice_parent") else ""

        # Playbook
        data["Playbook"] = job_data.get("playbook", "")

        # Project update status (from related project)
        project_status = project.get("status", "") if project else ""
        data["Project Update Status"] = project_status

        # Revision
        data["Revision"] = job_data.get("scm_revision", "")

        # Controller node
        data["Controller Node"] = job_data.get("controller_node", "")

        # Instance group
        instance_group = summary_fields.get("instance_group", {})
        data["Instance Group"] = instance_group.get("name", "")

        # Container group (if different from instance group)
        container_group_name = ""
        if instance_group.get("is_container_group", False):
            container_group_name = instance_group.get("name", "")
        data["Container Group"] = container_group_name

        # Forks
        forks = job_data.get("forks", 0)
        data["Forks"] = str(forks) if forks else ""

        # Timeout
        timeout = job_data.get("timeout", 0)
        data["Timeout"] = str(timeout) if timeout else "None"

    elif job_type == "project_update":
        # Project
        project = summary_fields.get("project", {})
        data["Project"] = project.get("name", "")

        # Execution environment
        execution_env = summary_fields.get("execution_environment", {})
        data["Execution Environment"] = execution_env.get("name", "")

        # Job slice parent
        data["Job Slice Parent"] = str(job_data.get("job_slice_parent", "")) if job_data.get("job_slice_parent") else ""

        # Revision
        data["Revision"] = job_data.get("scm_revision", "")

        # Execution node
        data["Execution Node"] = job_data.get("execution_node", "")

        # Timeout
        timeout = job_data.get("timeout", 0)
        data["Timeout"] = str(timeout) if timeout else "None"

        # Job tags
        data["Job Tags"] = job_data.get("job_tags", "")

    elif job_type == "inventory_update":
        # Inventory
        inventory = summary_fields.get("inventory", {})
        data["Inventory"] = inventory.get("name", "")

        # Execution environment
        execution_env = summary_fields.get("execution_environment", {})
        data["Execution Environment"] = execution_env.get("name", "")

        # Credentials
        credentials = summary_fields.get("credentials", [])
        if credentials:
            cred_names = [cred.get("name", "") for cred in credentials if cred.get("name")]
            data["Credentials"] = ", ".join(cred_names)
        else:
            data["Credentials"] = ""

        # Job slice parent
        data["Job Slice Parent"] = str(job_data.get("job_slice_parent", "")) if job_data.get("job_slice_parent") else ""

        # Controller node
        data["Controller Node"] = job_data.get("controller_node", "")

        # Instance group
        instance_group = summary_fields.get("instance_group", {})
        data["Instance Group"] = instance_group.get("name", "")

        # Container group (if different from instance group)
        container_group_name = ""
        if instance_group.get("is_container_group", False):
            container_group_name = instance_group.get("name", "")
        data["Container Group"] = container_group_name

        # Timeout
        timeout = job_data.get("timeout", 0)
        data["Timeout"] = str(timeout) if timeout else "None"

    # Common fields for all job types (appended at the end)
    verbosity = job_data.get("verbosity")
    if verbosity is not None:
        data["Verbosity"] = str(verbosity)
    else:
        data["Verbosity"] = ""

    data["Created"] = format_datetime_rich(job_data.get("created", ""), use_utc, output_format)
    data["Modified"] = format_datetime_rich(job_data.get("modified", ""), use_utc, output_format)

    # Extra variables (like inventory show command)
    extra_vars = job_data.get("extra_vars", "")
    if extra_vars:
        data["Extra Variables"] = format_variables_display(extra_vars, "job")
    else:
        data["Extra Variables"] = ""

    # Remove empty fields for cleaner display
    data = {k: v for k, v in data.items() if v not in ["", None, "N/A"]}

    return data


# Add import for show_error_message
from aapclient.output import show_error_message


@job.group("variables")
def job_variables():
    """Manage job variables."""


@job_variables.command("show")
@click.argument("job_id", metavar="<job_id>")
@show_command
def show_job_variables(console, output_format, utc, job_id):
    """Show job extra variables in YAML format."""
    from aapclient.decorators import get_client_from_context
    from aapclient.common.functions import format_variables_yaml_display, parse_variables_for_output

    client_manager = get_client_from_context()
    client = client_manager.controller

    # Validate that job_id is numeric
    try:
        job_id_int = int(job_id)
    except ValueError:
        show_error_message(console, f"Job ID must be numeric, got: '{job_id}'")
        sys.exit(1)

    # First, get the job from unified_jobs to determine its type
    unified_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}unified_jobs/"
    response = client.get(unified_endpoint, params={"id": job_id_int})
    unified_data = response.json()
    results = unified_data.get("results", [])

    if not results:
        show_error_message(console, f"Job {job_id} not found")
        sys.exit(1)

    job_preview = results[0]
    job_type = job_preview.get("type", "")

    # Map job type to specific endpoint
    type_endpoint_map = {
        "job": "jobs",
        "project_update": "project_updates",
        "inventory_update": "inventory_updates",
        "system_job": "system_jobs",
        "workflow_job": "workflow_jobs",
    }

    if job_type not in type_endpoint_map:
        show_error_message(console, f"Unknown job type: {job_type}")
        sys.exit(1)

    # Get the full job details from the specific endpoint
    specific_endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}{type_endpoint_map[job_type]}/{job_id_int}/"
    response = client.get(specific_endpoint)
    job_data = response.json()

    # Extract and parse extra variables
    extra_vars_raw = job_data.get("extra_vars", {})
    extra_vars_parsed = parse_variables_for_output(extra_vars_raw)

    if output_format == "json":
        show_raw_json(extra_vars_parsed)
    elif output_format == "yaml":
        show_raw_yaml(extra_vars_parsed)
    else:
        # Table format showing job name and variables in YAML
        variables_yaml = format_variables_yaml_display(extra_vars_raw)

        # Create a simple key-value display
        data = {"Job": job_data["name"], "Variables": variables_yaml}
        show_details_table(console, data)


def register_job_commands(main_group: click.Group) -> None:
    """Register job commands with the main CLI group."""
    main_group.add_command(job)
