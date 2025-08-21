"""
Common decorators for AAP CLI commands.

This module provides reusable decorators that encapsulate common patterns
across AAP CLI commands, such as error handling, client management, and
output formatting.
"""

import sys
from functools import wraps
from typing import Callable

import click
from rich.console import Console

from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.clientmanager import AAPClientManager


def handle_api_errors(func: Callable) -> Callable:
    """
    Decorator to handle common API errors with rich formatting.

    Catches and formats AAPClientError, AAPResourceNotFoundError, and other
    common exceptions with appropriate styling and exit codes.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except AAPResourceNotFoundError as e:
            console = Console()
            console.print(f"[red]Resource not found:[/red] {e}")
            sys.exit(1)

        except AAPAPIError as e:
            console = Console()
            console.print(f"[red]API Error:[/red] {e}")
            sys.exit(1)

        except AAPClientError as e:
            console = Console()
            console.print(f"[red]Client Error:[/red] {e}")
            sys.exit(1)

        except KeyboardInterrupt:
            console = Console()
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            sys.exit(130)  # Standard exit code for Ctrl+C

        except SystemExit:
            # Re-raise SystemExit to allow clean exit from click.get_current_context().exit()
            raise

        except Exception as e:
            console = Console()
            console.print(f"[red]Unexpected error:[/red] {e}")
            # In development, show traceback
            import os

            if os.getenv("AAP_DEBUG"):
                import traceback

                console.print(traceback.format_exc())
            sys.exit(1)

    return wrapper


def require_client(func: Callable) -> Callable:
    """
    Decorator to ensure client manager is available and configured.

    Validates that the client manager exists in the click context and
    that it's properly configured before executing the command.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = click.get_current_context()

        if "client_manager" not in ctx.obj:
            console = Console()
            console.print("[red]Error:[/red] Client manager not configured")
            sys.exit(1)

        client_manager = ctx.obj["client_manager"]

        try:
            # Validate configuration
            client_manager.config.validate()
        except AAPClientError as e:
            console = Console()
            console.print(f"[red]Configuration error:[/red] {e}")
            sys.exit(1)

        return func(*args, **kwargs)

    return wrapper


def with_console(func: Callable) -> Callable:
    """
    Decorator to inject the rich console into the function.

    Adds the console as the first argument to the decorated function,
    making it easy to access rich formatting capabilities.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = click.get_current_context()
        console = ctx.obj.get("console", Console())

        # Insert console as first argument
        return func(console, *args, **kwargs)

    return wrapper


def with_client_manager(func: Callable) -> Callable:
    """
    Decorator to inject the client manager into the function.

    Adds the client manager as the first argument to the decorated function.
    Should be used with @require_client for safety.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = click.get_current_context()
        client_manager = ctx.obj["client_manager"]

        # Insert client_manager as first argument
        return func(client_manager, *args, **kwargs)

    return wrapper


def common_options(func: Callable) -> Callable:
    """
    Decorator to add common options to commands.

    Adds frequently used options like --format, --verbose, etc.
    to commands that need them.
    """

    @click.option(
        "--format",
        "-f",
        "output_format",
        type=click.Choice(["table", "json", "yaml"]),
        default="table",
        help="Output format",
    )
    @click.option("--utc", is_flag=True, help="Display timestamps in UTC")
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def paginated(default_limit: int = 20):
    """
    Decorator factory to add pagination options to list commands.

    Args:
        default_limit: Default limit for pagination

    Returns:
        Decorator that adds pagination options
    """

    def decorator(func: Callable) -> Callable:
        @click.option("--offset", type=int, default=0, help="Skip this many results")
        @click.option(
            "--limit",
            type=int,
            default=default_limit,
            metavar="N",
            help=f"Limit the number of results returned (default: {default_limit})",
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def sortable(default_fields: list = None, default_sort: str = "id"):
    """
    Decorator factory to add sorting options to list commands.

    Args:
        default_fields: List of available sort fields (defaults to common ones)
        default_sort: Default sort field

    Returns:
        Decorator that adds sorting options
    """
    if default_fields is None:
        default_fields = ["id", "name", "created", "modified"]

    def decorator(func: Callable) -> Callable:
        @click.option(
            "--sort-by",
            type=click.Choice(default_fields),
            default=default_sort,
            help=f"Sort results by field (default: {default_sort})",
        )
        @click.option("--reverse", is_flag=True, help="Reverse sort order (descending)")
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def confirm_destructive(message: str = "Are you sure?"):
    """
    Decorator factory to add confirmation prompt for destructive operations.

    Args:
        message: Confirmation message to display

    Returns:
        Decorator that adds confirmation prompt
    """

    def decorator(func: Callable) -> Callable:
        @click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract --yes flag from kwargs
            skip_confirm = kwargs.pop("yes", False)

            if not skip_confirm:
                if not click.confirm(message):
                    click.echo("Operation cancelled.")
                    sys.exit(0)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def with_progress(description: str = "Processing..."):
    """
    Decorator factory to wrap long-running operations with a progress indicator.

    Args:
        description: Description to show in progress indicator

    Returns:
        Decorator that shows progress during operation
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            from rich.progress import Progress, SpinnerColumn, TextColumn

            with Progress(
                SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=Console()
            ) as progress:
                task = progress.add_task(description, total=None)

                try:
                    result = func(*args, **kwargs)
                    progress.update(task, description="[green]Complete![/green]")
                    return result
                except Exception:
                    progress.update(task, description="[red]Failed![/red]")
                    raise

        return wrapper

    return decorator


# Composite decorators for common command patterns


def standard_command(func: Callable) -> Callable:
    """
    Composite decorator for standard commands.

    Combines error handling, client requirement, and console injection.
    """
    return handle_api_errors(require_client(with_console(func)))


def list_command(default_limit: int = 20, sort_fields: list = None, default_sort: str = "id"):
    """
    Composite decorator factory for list commands.

    Combines standard command setup with pagination and sorting options.

    Args:
        default_limit: Default limit for pagination
        sort_fields: Available sort fields (defaults to common ones)
        default_sort: Default sort field
    """

    def decorator(func: Callable) -> Callable:
        return standard_command(sortable(sort_fields, default_sort)(paginated(default_limit)(common_options(func))))

    return decorator


def show_command(func: Callable) -> Callable:
    """
    Composite decorator for show commands.

    Combines standard command setup with common show options.
    """
    return standard_command(common_options(func))


def create_command(func: Callable) -> Callable:
    """
    Composite decorator for create commands.

    Combines standard command setup.
    """
    return standard_command(func)


def update_command(func: Callable) -> Callable:
    """
    Composite decorator for update/set commands.

    Combines standard command setup.
    """
    return standard_command(func)


def delete_command(confirm_message: str = "Are you sure you want to delete this resource?"):
    """
    Composite decorator factory for delete commands.

    Combines standard command setup with confirmation prompt.
    """

    def decorator(func: Callable) -> Callable:
        return standard_command(confirm_destructive(confirm_message)(func))

    return decorator


# Context helpers that can be used within decorated functions


def get_client_from_context() -> AAPClientManager:
    """Get client manager from current click context."""
    ctx = click.get_current_context()
    return ctx.obj["client_manager"]


def get_console_from_context() -> Console:
    """Get rich console from current click context."""
    ctx = click.get_current_context()
    return ctx.obj.get("console", Console())


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    ctx = click.get_current_context()
    return ctx.obj.get("verbose", 0) > 0


def is_quiet() -> bool:
    """Check if quiet mode is enabled."""
    ctx = click.get_current_context()
    return ctx.obj.get("quiet", False)


def validate_resource_identifier(ctx, param, value):
    """
    Click callback to validate that either a positional argument or --id option is provided.

    This callback should be used on the positional argument for show commands that also
    accept an --id option. It ensures exactly one identifier is provided.

    Args:
        ctx: Click context
        param: The parameter being validated (positional argument)
        value: The value of the positional argument

    Returns:
        The value if validation passes

    Raises:
        click.UsageError: If neither positional argument nor --id is provided
    """
    # Get the --id parameter value from the context
    id_value = ctx.params.get("id")

    # If neither positional argument nor --id is provided, raise an error
    if not value and not id_value:
        resource_name = param.metavar.strip("<>") if param.metavar else "resource"
        raise click.UsageError(f"Either {resource_name} name or --id must be provided.")

    return value
