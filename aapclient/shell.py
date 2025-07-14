"""Main shell application for AAP client."""
import sys
from cliff.app import App
from cliff.commandmanager import CommandManager


class AAPApp(App):
    """Main application for AAP client."""

    def __init__(self):
        super().__init__(
            description='Ansible Automation Platform (AAP) Command Line Interface',
            version='0.1.0',
            command_manager=CommandManager('aap.common'),
            deferred_help=True,
        )

    def initialize_app(self, argv):
        """Initialize the application."""
        self.LOG.debug('initialize_app')

    def prepare_to_run_command(self, cmd):
        """Prepare to run a command."""
        self.LOG.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        """Clean up after a command."""
        self.LOG.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.LOG.debug('got an error: %s', err)


def main(argv=sys.argv[1:]):
    """Main entry point for the AAP client."""
    app = AAPApp()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main())
