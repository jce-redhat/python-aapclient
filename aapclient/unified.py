"""
Unified dispatcher for AAP CLI supporting both cliff and click+rich formats.

This module provides intelligent dispatching between the legacy cliff-based CLI
and the new click+rich CLI based on user preferences and terminal capabilities.
"""

import sys
import os
import argparse
from typing import List, Optional, Tuple


def detect_output_preference(argv: List[str]) -> Tuple[str, List[str]]:
    """
    Detect user's preferred output format and return cleaned arguments.

    Detection priority:
    1. Explicit command line flags (--rich, --legacy, --output-format)
    2. Environment variable (AAP_OUTPUT_FORMAT)
    3. Terminal capability detection
    4. Default to cliff for backwards compatibility

    Args:
        argv: Command line arguments

    Returns:
        Tuple of (format_preference, cleaned_argv)
    """

    # Create parser for format detection
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output-format', choices=['rich', 'cliff', 'legacy'])
    parser.add_argument('--rich', action='store_true', help='Use rich output format')
    parser.add_argument('--legacy', action='store_true', help='Use legacy cliff format')

    # Parse known args to extract format options
    try:
        known_args, remaining_argv = parser.parse_known_args(argv)
    except SystemExit:
        # If parsing fails, default to cliff and pass through all args
        return 'cliff', argv

    # Determine format preference
    if known_args.rich or known_args.output_format == 'rich':
        return 'rich', remaining_argv
    elif known_args.legacy or known_args.output_format in ['cliff', 'legacy']:
        return 'cliff', remaining_argv

    # Check environment variable
    env_format = os.getenv('AAP_OUTPUT_FORMAT', '').lower()
    if env_format in ['rich', 'click']:
        return 'rich', remaining_argv
    elif env_format in ['cliff', 'legacy']:
        return 'cliff', remaining_argv

    # During transition period, default to cliff for backwards compatibility
    # Auto-detection can be enabled later when rich becomes the primary format
    return 'cliff', remaining_argv


def _supports_rich_output() -> bool:
    """
    Detect if terminal supports rich output features.

    Returns:
        True if terminal likely supports rich features, False otherwise
    """
    # Check if running in a terminal
    if not (hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()):
        return False

    # Check terminal type
    term = os.getenv('TERM', '').lower()
    if term in ['dumb', '']:
        return False

    # Check for common CI/automation environments
    ci_indicators = [
        'CI', 'CONTINUOUS_INTEGRATION', 'BUILD_NUMBER',
        'JENKINS_URL', 'GITHUB_ACTIONS', 'GITLAB_CI'
    ]
    if any(os.getenv(indicator) for indicator in ci_indicators):
        return False

    # Check for explicit color support
    if os.getenv('COLORTERM') or os.getenv('FORCE_COLOR'):
        return True

    # Most modern terminals support rich features
    if any(term.startswith(prefix) for prefix in ['xterm', 'screen', 'tmux']):
        return True

    # Conservative default
    return False


def show_migration_notice(format_used: str, command_args: List[str]) -> None:
    """
    Show users information about dual support during transition.

    Args:
        format_used: The format that was selected ('rich' or 'cliff')
        command_args: The command arguments being executed
    """
    # Only show notice for interactive terminals
    if not (hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()):
        return

    # Don't show for help commands
    if not command_args or command_args[0] in ['--help', '-h', 'help']:
        return


def main(argv: Optional[List[str]] = None) -> int:
    """
    Unified main entry point that dispatches to cliff or click based on preference.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    if argv is None:
        argv = sys.argv[1:]

    # Detect format preference and clean argv
    output_format, clean_argv = detect_output_preference(argv)

    # Show migration notice (only in interactive mode)
    show_migration_notice(output_format, clean_argv)

    try:
        if output_format == 'rich':
            # Try to import and run click-based CLI
            try:
                from aapclient.cli.core import main as click_main
                return click_main(clean_argv)
            except ImportError as e:
                if 'rich' in str(e) or 'click' in str(e):
                    print(f"Warning: Rich output requested but dependencies not available.", file=sys.stderr)
                    print(f"Install with: pip install 'python-aapclient[rich]'", file=sys.stderr)
                    print(f"Falling back to legacy format...", file=sys.stderr)

                    # Fallback to cliff
                    from aapclient.shell import main as cliff_main
                    return cliff_main(clean_argv)
                else:
                    raise
        else:
            # Import and run cliff-based CLI
            from aapclient.shell import main as cliff_main
            return cliff_main(clean_argv)

    except ImportError as e:
        print(f"Error: Failed to import CLI implementation: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        return 130
    except SystemExit as e:
        # Re-raise SystemExit to allow clean exit from CLI commands
        return e.code if e.code is not None else 1
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


# Configuration management for persistent preferences
class UserPreferences:
    """Manage user preferences for output format."""

    CONFIG_DIR = os.path.expanduser('~/.config/aap')
    CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.ini')

    @classmethod
    def load_preference(cls) -> Optional[str]:
        """Load user's saved output format preference."""
        if not os.path.exists(cls.CONFIG_FILE):
            return None

        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(cls.CONFIG_FILE)

            return config.get('display', 'output_format', fallback=None)
        except Exception:
            return None

    @classmethod
    def save_preference(cls, format_type: str) -> None:
        """Save user's output format preference."""
        os.makedirs(cls.CONFIG_DIR, exist_ok=True)

        try:
            import configparser
            config = configparser.ConfigParser()

            # Load existing config if it exists
            if os.path.exists(cls.CONFIG_FILE):
                config.read(cls.CONFIG_FILE)

            # Ensure sections exist
            if not config.has_section('display'):
                config.add_section('display')

            # Set preference
            config.set('display', 'output_format', format_type)

            # Save to file
            with open(cls.CONFIG_FILE, 'w') as f:
                config.write(f)

        except Exception as e:
            print(f"Warning: Could not save preference: {e}", file=sys.stderr)


def test_dispatcher():
    """Test the dispatcher with various argument combinations."""
    test_cases = [
        # (argv, expected_format, description)
        (['ping'], 'cliff', 'Basic command - defaults to cliff for compatibility'),
        (['ping', '--rich'], 'rich', 'Explicit rich format'),
        (['ping', '--legacy'], 'cliff', 'Explicit legacy format'),
        (['ping', '--output-format=rich'], 'rich', 'Rich via --output-format'),
        (['template', 'list', '--limit', '10'], 'cliff', 'Complex command - defaults to cliff'),
    ]

    print("Testing unified dispatcher...")

    for argv, expected_format, description in test_cases:
        print(f"\n{description}")
        print(f"Command: aap {' '.join(argv)}")

        detected_format, clean_argv = detect_output_preference(argv)

        print(f"Detected format: {detected_format}")
        print(f"Clean argv: {clean_argv}")

        if expected_format != 'auto' and detected_format != expected_format:
            print(f"❌ FAIL: Expected {expected_format}, got {detected_format}")
        else:
            print("✅ PASS")


if __name__ == '__main__':
    # Run tests if called with --test
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        test_dispatcher()
    else:
        sys.exit(main())
