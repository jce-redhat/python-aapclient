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
            '--hostname',
            metavar='<hostname>',
            help='AAP hostname URL (overrides AAP_HOSTNAME environment variable)'
        )
        aap_group.add_argument(
            '--username',
            metavar='<username>',
            help='AAP username (overrides AAP_USERNAME environment variable)'
        )
        aap_group.add_argument(
            '--password',
            metavar='<password>',
            help='AAP password (overrides AAP_PASSWORD environment variable)'
        )
        aap_group.add_argument(
            '--token',
            metavar='<token>',
            help='AAP API token (overrides AAP_TOKEN environment variable)'
        )
        aap_group.add_argument(
            '--request-timeout',
            type=int,
            metavar='<seconds>',
            help='Connection timeout in seconds (overrides AAP_REQUEST_TIMEOUT environment variable)'
        )
        aap_group.add_argument(
            '--validate-certs',
            choices=['true', 'false'],
            metavar='<true|false>',
            help='Enable or disable SSL certificate verification (overrides AAP_VALIDATE_CERTS environment variable)'
        )
        aap_group.add_argument(
            '--ca-bundle',
            metavar='<path>',
            help='Path to CA certificate bundle file (overrides AAP_CA_BUNDLE environment variable)'
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
            if hasattr(self.options, 'hostname') and self.options.hostname:
                config_overrides['hostname'] = self.options.hostname
            if hasattr(self.options, 'username') and self.options.username:
                config_overrides['username'] = self.options.username
            if hasattr(self.options, 'password') and self.options.password:
                config_overrides['password'] = self.options.password
            if hasattr(self.options, 'token') and self.options.token:
                config_overrides['token'] = self.options.token
            if hasattr(self.options, 'request_timeout') and self.options.request_timeout:
                config_overrides['request_timeout'] = self.options.request_timeout

            # Handle SSL verification argument
            if hasattr(self.options, 'validate_certs') and self.options.validate_certs:
                config_overrides['validate_certs'] = self.options.validate_certs.lower() == 'true'

            if hasattr(self.options, 'ca_bundle') and self.options.ca_bundle:
                config_overrides['ca_bundle'] = self.options.ca_bundle

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
