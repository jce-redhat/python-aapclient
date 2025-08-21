"""
Rich output formatting utilities for AAP CLI.

This module provides standardized rich formatting functions that create
beautiful, consistent output across all AAP CLI commands.
"""

from typing import Dict, List, Any, Optional, Union

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.tree import Tree
from rich import box


def create_table(
    columns: List[str],
    rows: List[List[Any]],
    title: Optional[str] = None,
    show_header: bool = True,
    show_lines: bool = False,
    box_style: Optional[box.Box] = None,
) -> Table:
    """
    Create a rich table from columns and rows.

    Args:
        columns: List of column headers
        rows: List of rows, where each row is a list of values
        title: Optional table title
        show_header: Whether to show column headers
        show_lines: Whether to show lines between rows
        box_style: Box style for the table

    Returns:
        Rich Table object ready for printing
    """
    table = Table(
        title=title,
        show_header=show_header,
        show_lines=show_lines,
        box=box_style or box.ROUNDED,
        header_style="bold magenta",
    )

    # Add columns with appropriate styling
    for i, column in enumerate(columns):
        if column.lower() in ["id", "count", "port", "timeout"]:
            # Numeric columns - right align
            table.add_column(column, justify="right", style="cyan")
        elif column.lower() in ["status", "state", "enabled"]:
            # Status columns - center align with conditional coloring
            table.add_column(column, justify="center")
        elif column.lower() in ["name", "username", "hostname"]:
            # Important identifier columns - bold
            table.add_column(column, style="bold white")
        else:
            # Default columns
            table.add_column(column)

    # Add rows with conditional styling
    for row in rows:
        styled_row = []
        for i, cell in enumerate(row):
            cell_str = str(cell) if cell is not None else ""

            # Apply conditional styling based on content
            if columns[i].lower() in ["status", "state", "enabled"]:
                styled_row.append(_style_status_cell(cell_str))
            elif columns[i].lower() == "id" and cell_str.isdigit():
                styled_row.append(f"[dim]{cell_str}[/dim]")
            else:
                styled_row.append(cell_str)

        table.add_row(*styled_row)

    return table


def show_key_value(console: Console, data: Dict[str, Any], title: Optional[str] = None, panel: bool = True) -> None:
    """
    Display key-value pairs in a formatted table.

    Args:
        console: Rich console for output
        data: Dictionary of key-value pairs to display
        title: Optional title for the display
        panel: Whether to wrap in a panel
    """
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED, padding=(0, 1))
    table.add_column("Field", style="cyan", width=30)
    table.add_column("Value", style="white")

    for key, value in data.items():
        # Format value based on type and content
        if isinstance(value, bool):
            formatted_value = "[green]Yes[/green]" if value else "[red]No[/red]"
        elif isinstance(value, (int, float)) and key.lower() in ["timeout", "port", "capacity"]:
            formatted_value = f"[cyan]{value}[/cyan]"
        elif value in ["good", "successful", "ok", "active", "running"]:
            formatted_value = f"[green]{value}[/green]"
        elif value in ["failed", "error", "inactive", "stopped"]:
            formatted_value = f"[red]{value}[/red]"
        elif value in ["pending", "waiting", "unknown"]:
            formatted_value = f"[yellow]{value}[/yellow]"
        else:
            formatted_value = str(value) if value is not None else "[dim]None[/dim]"

        table.add_row(key, formatted_value)

    if panel and title:
        content = Panel(table, title=title, title_align="left")
        console.print(content)
    else:
        if title:
            console.print(f"[bold magenta]{title}[/bold magenta]")
        console.print(table)


def show_details_table(console: Console, data: Dict[str, Any]) -> None:
    """
    Display key-value pairs in a simple formatted table without panel wrapper.

    This is the unified function for displaying resource details consistently
    across create, show, and set commands without varying header titles.

    Args:
        console: Rich console for output
        data: Dictionary of key-value pairs to display
    """
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED, padding=(0, 1))
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    for key, value in data.items():
        # Format value based on type and content
        if isinstance(value, bool):
            formatted_value = "[green]Yes[/green]" if value else "[red]No[/red]"
        elif isinstance(value, (int, float)) and key.lower() in ["timeout", "port", "capacity"]:
            formatted_value = f"[cyan]{value}[/cyan]"
        elif value in ["good", "successful", "ok", "active", "running"]:
            formatted_value = f"[green]{value}[/green]"
        elif value in ["failed", "error", "inactive", "stopped"]:
            formatted_value = f"[red]{value}[/red]"
        elif value in ["pending", "waiting", "unknown"]:
            formatted_value = f"[yellow]{value}[/yellow]"
        else:
            formatted_value = str(value) if value is not None else "[dim]None[/dim]"

        table.add_row(key, formatted_value)

    console.print(table)


def format_value_for_output(value: Any, key: str, output_format: str = "table") -> str:
    """
    Format a value for display with or without rich markup based on output format.

    Args:
        value: The value to format
        key: The field name (used for context-specific formatting)
        output_format: Output format ('table', 'json', 'yaml')

    Returns:
        Formatted value string
    """
    if output_format in ["json", "yaml"]:
        # Plain formatting for JSON/YAML
        if isinstance(value, bool):
            return "Yes" if value else "No"
        elif value in [
            "good",
            "successful",
            "ok",
            "active",
            "running",
            "failed",
            "error",
            "inactive",
            "stopped",
            "pending",
            "waiting",
            "unknown",
        ]:
            return str(value)
        else:
            return str(value) if value is not None else "None"
    else:
        # Rich formatting for table output
        if isinstance(value, bool):
            # Special handling for 'deleted' field - Yes (True) is bad, No (False) is good
            if key.lower() == "deleted":
                return "[red]Yes[/red]" if value else "[green]No[/green]"
            else:
                # Default: Yes (True) is good, No (False) is bad
                return "[green]Yes[/green]" if value else "[red]No[/red]"
        elif isinstance(value, (int, float)) and key.lower() in ["timeout", "port", "capacity"]:
            return f"[cyan]{value}[/cyan]"
        elif value in ["good", "successful", "ok", "active", "running"]:
            return f"[green]{value}[/green]"
        elif value in ["failed", "error", "inactive", "stopped"]:
            return f"[red]{value}[/red]"
        elif value in ["pending", "waiting", "unknown"]:
            return f"[yellow]{value}[/yellow]"
        else:
            return str(value) if value is not None else "[dim]None[/dim]"


def show_raw_json(data: Any) -> None:
    """
    Display raw JSON data without rich formatting for piping to tools like jq.

    Args:
        data: Data to display as raw JSON
    """
    import json
    import sys

    json_str = json.dumps(data, indent=2, default=str)
    print(json_str, file=sys.stdout)


def show_raw_yaml(data: Any) -> None:
    """
    Display raw YAML data without rich formatting for piping to tools like yq.

    Args:
        data: Data to display as raw YAML
    """
    import sys
    from collections import OrderedDict

    def convert_ordered_dict(obj):
        """Recursively convert OrderedDict to regular dict while preserving order."""
        if isinstance(obj, OrderedDict):
            return dict(obj)
        elif isinstance(obj, dict):
            return {k: convert_ordered_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_ordered_dict(item) for item in obj]
        else:
            return obj

    try:
        import yaml

        # Convert OrderedDict to regular dict to avoid YAML object notation
        # while preserving field order with sort_keys=False
        clean_data = convert_ordered_dict(data)
        yaml_str = yaml.dump(clean_data, default_flow_style=False, indent=2, sort_keys=False)
    except ImportError:
        # Fallback to JSON if PyYAML not available
        import json

        yaml_str = json.dumps(data, indent=2, default=str)

    print(yaml_str, file=sys.stdout)


def show_success_message(console: Console, message: str) -> None:
    """Display a success message with green styling."""
    console.print(f"[green]✓[/green] {message}")


def show_error_message(console: Console, message: str) -> None:
    """Display an error message with red styling."""
    console.print(f"[red]✗[/red] {message}")


def show_warning_message(console: Console, message: str) -> None:
    """Display a warning message with yellow styling."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def show_info_message(console: Console, message: str) -> None:
    """Display an info message with blue styling."""
    console.print(f"[blue]ℹ[/blue] {message}")


def create_progress_bar(description: str = "Processing...") -> Progress:
    """
    Create a progress bar for long-running operations.

    Args:
        description: Description text for the progress bar

    Returns:
        Rich Progress object
    """
    return Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=Console())


def create_tree_view(root_name: str) -> Tree:
    """
    Create a tree view for hierarchical data.

    Args:
        root_name: Name of the root node

    Returns:
        Rich Tree object
    """
    return Tree(f"[bold blue]{root_name}[/bold blue]")


def format_datetime_rich(dt_str: str, use_utc: bool = False, output_format: str = "table") -> str:
    """
    Format datetime string with rich styling for table output or plain text for JSON/YAML.

    Args:
        dt_str: ISO format datetime string
        use_utc: Whether to display in UTC
        output_format: Output format ('table', 'json', 'yaml')

    Returns:
        Formatted datetime string with or without rich styling based on output format
    """
    if not dt_str:
        return "Never" if output_format in ["json", "yaml"] else "[dim]Never[/dim]"

    try:
        # This would use the existing format_datetime function from common.functions
        from aapclient.common.functions import format_datetime

        formatted = format_datetime(dt_str, use_utc)
        return formatted if output_format in ["json", "yaml"] else f"[dim]{formatted}[/dim]"
    except Exception:
        return dt_str if output_format in ["json", "yaml"] else f"[dim]{dt_str}[/dim]"


def format_duration_rich(seconds: Union[int, float], output_format: str = "table") -> str:
    """
    Format duration in seconds to human-readable format with styling for table or plain for JSON/YAML.

    Args:
        seconds: Duration in seconds
        output_format: Output format ('table', 'json', 'yaml')

    Returns:
        Formatted duration string with or without rich styling based on output format
    """
    if not seconds or seconds <= 0:
        return "N/A" if output_format in ["json", "yaml"] else "[dim]N/A[/dim]"

    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        duration_str = f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        duration_str = f"{minutes}m {secs}s"
    else:
        duration_str = f"{secs}s"

    return duration_str if output_format in ["json", "yaml"] else f"[cyan]{duration_str}[/cyan]"


def _style_status_cell(value: str) -> str:
    """
    Apply conditional styling to status/state cell values.

    Args:
        value: Cell value to style

    Returns:
        Styled cell value
    """
    value_lower = value.lower()

    # Success states
    if value_lower in ["yes", "true", "success", "successful", "ok", "good", "active", "running", "enabled"]:
        return f"[green]{value}[/green]"

    # Error states
    elif value_lower in ["no", "false", "failed", "error", "bad", "inactive", "stopped", "disabled"]:
        return f"[red]{value}[/red]"

    # Warning states
    elif value_lower in ["pending", "waiting", "unknown", "warning"]:
        return f"[yellow]{value}[/yellow]"

    # Default
    else:
        return value


def paginate_output(console: Console, content: Any, page_size: int = 20) -> None:
    """
    Display content with pagination support.

    Args:
        console: Rich console for output
        content: Content to paginate (Table, list, etc.)
        page_size: Number of items per page
    """
    # For now, just print the content directly
    # Future enhancement: implement actual pagination
    console.print(content)


# Predefined color schemes for different resource types
RESOURCE_COLORS = {
    "template": "blue",
    "project": "green",
    "inventory": "yellow",
    "credential": "red",
    "user": "cyan",
    "team": "magenta",
    "organization": "white",
    "host": "bright_blue",
    "group": "bright_green",
}
