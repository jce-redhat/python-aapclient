"""Main shell application for AAP client."""
import sys
from cliff.app import App
from cliff.commandmanager import CommandManager
from aapclient.common.clientmanager import AAPClientManager


class AAPApp(App):
    """Main application for AAP client."""

    def __init__(self):
        # Create command manager with multiple namespaces
        command_manager = CommandManager('aap.common')
        # Add API-specific command groups
        command_manager.add_command_group('aap.gateway')
        command_manager.add_command_group('aap.controller')
        command_manager.add_command_group('aap.eda')

        super().__init__(
            description='Ansible Automation Platform (AAP) Command Line Interface',
            version='0.1.0',
            command_manager=command_manager,
            deferred_help=True,
        )

        # Initialize client manager (lazy-loaded)
        self._client_manager = None

    def build_option_parser(self, description, version, argparse_kwargs=None):
        """Build option parser with global AAP connection arguments."""
        parser = super().build_option_parser(description, version, argparse_kwargs)

        # Add global AAP connection arguments
        aap_group = parser.add_argument_group('AAP Connection')
        aap_group.add_argument(
            '--aap-host',
            metavar='<host>',
            help='AAP host URL (overrides AAP_HOST environment variable)'
        )
        aap_group.add_argument(
            '--aap-username',
            metavar='<username>',
            help='AAP username (overrides AAP_USERNAME environment variable)'
        )
        aap_group.add_argument(
            '--aap-password',
            metavar='<password>',
            help='AAP password (overrides AAP_PASSWORD environment variable)'
        )
        aap_group.add_argument(
            '--aap-token',
            metavar='<token>',
            help='AAP API token (overrides AAP_TOKEN environment variable)'
        )
        aap_group.add_argument(
            '--aap-timeout',
            type=int,
            metavar='<seconds>',
            help='Connection timeout in seconds (overrides AAP_TIMEOUT environment variable)'
        )

        return parser

    @property
    def client_manager(self):
        """
        Get centralized client manager for AAP APIs.

        Provides lazy-loaded access to Controller, Gateway, EDA, and Galaxy clients
        with shared configuration and validation.

        Returns:
            AAPClientManager: Configured client manager instance
        """
        if self._client_manager is None:
            # Extract AAP connection overrides from command-line arguments
            config_overrides = {}
            if hasattr(self.options, 'aap_host') and self.options.aap_host:
                config_overrides['host'] = self.options.aap_host
            if hasattr(self.options, 'aap_username') and self.options.aap_username:
                config_overrides['username'] = self.options.aap_username
            if hasattr(self.options, 'aap_password') and self.options.aap_password:
                config_overrides['password'] = self.options.aap_password
            if hasattr(self.options, 'aap_token') and self.options.aap_token:
                config_overrides['token'] = self.options.aap_token
            if hasattr(self.options, 'aap_timeout') and self.options.aap_timeout:
                config_overrides['timeout'] = self.options.aap_timeout

            self._client_manager = AAPClientManager(config_overrides=config_overrides)
        return self._client_manager

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
