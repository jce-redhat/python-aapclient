"""
Main Click-based CLI application for AAP client.

This module provides the core click group and global configuration management for the enhanced AAP CLI experience.
"""

import sys
from typing import Optional, List

import click
from rich.console import Console

from aapclient.common.clientmanager import AAPClientManager
from aapclient.common.constants import AAPCLI_VERSION
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError


# Global console instance for rich output
console = Console()


@click.group()
@click.option("--url", envvar="AAP_URL", metavar="<url>", help="AAP URL (overrides AAP_URL environment variable)")
@click.option(
    "--username",
    envvar="AAP_USERNAME",
    metavar="<username>",
    help="AAP username (overrides AAP_USERNAME environment variable)",
)
@click.option(
    "--password",
    envvar="AAP_PASSWORD",
    metavar="<password>",
    help="AAP password (overrides AAP_PASSWORD environment variable)",
)
@click.option(
    "--token", envvar="AAP_TOKEN", metavar="<token>", help="AAP API token (overrides AAP_TOKEN environment variable)"
)
@click.option(
    "--request-timeout",
    envvar="AAP_REQUEST_TIMEOUT",
    type=int,
    metavar="<seconds>",
    help="Connection timeout in seconds (overrides AAP_REQUEST_TIMEOUT environment variable)",
)
@click.option(
    "--validate-certs/--no-validate-certs",
    envvar="AAP_VALIDATE_CERTS",
    default=None,
    help="Enable or disable SSL certificate verification (overrides AAP_VALIDATE_CERTS environment variable)",
)
@click.option(
    "--ca-bundle",
    envvar="AAP_CA_BUNDLE",
    metavar="<path>",
    help="Path to CA certificate bundle file (overrides AAP_CA_BUNDLE environment variable)",
)
# @click.version_option(version=AAPCLI_VERSION, prog_name='aap')
@click.version_option(version=AAPCLI_VERSION, prog_name="python-aapclient", message="%(prog)s v%(version)s")
@click.pass_context
def cli(ctx, url, username, password, token, request_timeout, validate_certs, ca_bundle):
    """
    Ansible Automation Platform (AAP) Command Line Interface.

    Modern CLI with rich output formatting and enhanced user experience.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Configure console (no quiet mode)
    ctx.obj["console"] = Console()

    # Set default verbosity level
    ctx.obj["verbose"] = 0
    ctx.obj["quiet"] = False

    # Build configuration overrides from command-line arguments
    config_overrides = {}

    if url:
        config_overrides["url"] = url
    if username:
        config_overrides["username"] = username
    if password:
        config_overrides["password"] = password
    if token:
        config_overrides["token"] = token
    if request_timeout:
        config_overrides["request_timeout"] = request_timeout
    if validate_certs is not None:
        config_overrides["validate_certs"] = validate_certs
    if ca_bundle:
        config_overrides["ca_bundle"] = ca_bundle

    # Initialize client manager with configuration overrides
    try:
        ctx.obj["client_manager"] = AAPClientManager(config_overrides=config_overrides)
        # Validate configuration early to catch issues
        ctx.obj["client_manager"].config.validate()
    except AAPClientError as e:
        ctx.obj["console"].print(f"[red]Error:[/red] {e}")
        ctx.exit(1)


# Utility functions for command implementations
def get_client_manager(ctx: click.Context) -> AAPClientManager:
    """Get the client manager from click context."""
    return ctx.obj["client_manager"]


def get_console(ctx: click.Context) -> Console:
    """Get the rich console from click context."""
    return ctx.obj["console"]


def handle_exceptions(func):
    """Decorator to handle common exceptions in click commands."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AAPResourceNotFoundError as e:
            console.print(f"[red]Resource not found:[/red] {e}")
            sys.exit(1)
        except AAPClientError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user.[/yellow]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}")
            sys.exit(1)

    return wrapper


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the click-based AAP CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if argv is None:
        argv = sys.argv[1:]

    try:
        # Import subcommands to register them with the main group
        from aapclient.common.commands import register_common_commands

        register_common_commands(cli)

        # Register controller commands
        from aapclient.controller.v2.templates import register_template_commands
        from aapclient.controller.v2.inventories import register_inventory_commands
        from aapclient.controller.v2.projects import register_project_commands
        from aapclient.controller.v2.credentials import register_credential_commands
        from aapclient.controller.v2.execution_environments import register_execution_environment_commands
        from aapclient.controller.v2.instances import register_instance_commands
        from aapclient.controller.v2.jobs import register_job_commands
        from aapclient.controller.v2.groups import register_group_commands
        from aapclient.controller.v2.hosts import register_host_commands

        register_template_commands(cli)
        register_inventory_commands(cli)
        register_project_commands(cli)
        register_credential_commands(cli)
        register_execution_environment_commands(cli)
        register_instance_commands(cli)
        register_job_commands(cli)
        register_group_commands(cli)
        register_host_commands(cli)

        # Register gateway commands
        from aapclient.gateway.v1.organizations import register_organization_commands
        from aapclient.gateway.v1.teams import register_team_commands
        from aapclient.gateway.v1.users import register_user_commands
        from aapclient.gateway.v1.applications import register_application_commands
        from aapclient.gateway.v1.tokens import register_token_commands

        register_organization_commands(cli)
        register_team_commands(cli)
        register_user_commands(cli)
        register_application_commands(cli)
        register_token_commands(cli)

        # Run the CLI
        cli(argv, standalone_mode=False)
        return 0

    except click.ClickException as e:
        # Click exceptions are already formatted nicely
        e.show()
        return e.exit_code
    except SystemExit as e:
        return e.code
    except Exception as e:
        console.print(f"[red]Fatal error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
