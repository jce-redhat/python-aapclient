"""Host metrics commands."""

from aapclient.common.basecommands import AAPShowCommand, AAPListCommand, AAPCommand
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST,
    HTTP_NO_CONTENT
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import format_datetime, resolve_host_metric_name


def _format_host_metrics_data(host_metrics_data, use_utc=False):
    """
    Format host metrics data consistently

    Args:
        host_metrics_data (dict): Host metrics data from API response
        use_utc (bool): If True, display timestamps in UTC; if False, display in local time

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract host metrics details
    id_value = host_metrics_data.get('id', '')
    hostname = host_metrics_data.get('hostname', '')
    automated_counter = host_metrics_data.get('automated_counter', 0)
    deleted_counter = host_metrics_data.get('deleted_counter', 0)
    deleted = host_metrics_data.get('deleted', False)
    used_in_inventories = host_metrics_data.get('used_in_inventories', '')

    # Format datetime fields using common function
    first_automation = format_datetime(host_metrics_data.get('first_automation', ''), use_utc)
    last_automation = format_datetime(host_metrics_data.get('last_automation', ''), use_utc)
    last_deleted = format_datetime(host_metrics_data.get('last_deleted', ''), use_utc)

    # Format fields for display
    columns = [
        'ID',
        'Hostname',
        'Automations',
        'First Automated',
        'Last Automated',
        'Deleted',
        'Deletions',
        'Last Deleted',
        'Used in Inventories'
    ]

    values = [
        id_value,
        hostname,
        automated_counter,
        first_automation,
        last_automation,
        'Yes' if deleted else 'No',
        deleted_counter,
        last_deleted,
        used_in_inventories if used_in_inventories else ''
    ]

    return (columns, values)


class HostMetricsListCommand(AAPListCommand):
    """List host metrics."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--limit',
            type=int,
            metavar='N',
            help='Limit the number of results returned (default: 20)'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the host metrics list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query host_metrics endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}host_metrics/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "host_metrics endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()
                host_metrics = data.get('results', [])

                # Define columns for output
                columns = ['ID', 'Hostname', 'Automations', 'First Automated', 'Last Automated', 'Deleted', 'Deletions']
                rows = []

                for host_metric in host_metrics:
                    # Format datetime fields
                    first_automation = format_datetime(host_metric.get('first_automation', ''), False)
                    last_automation = format_datetime(host_metric.get('last_automation', ''), False)

                    row = [
                        host_metric.get('id', ''),
                        host_metric.get('hostname', ''),
                        host_metric.get('automated_counter', 0),
                        first_automation,
                        last_automation,
                        'Yes' if host_metric.get('deleted', False) else 'No',
                        host_metric.get('deleted_counter', 0)
                    ]
                    rows.append(row)

                return (columns, rows)
            else:
                raise AAPClientError(f"Controller API failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class HostMetricsShowCommand(AAPShowCommand):
    """Show detailed information about a host metric."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # UTC option for timestamp display
        parser.add_argument(
            '--utc',
            action='store_true',
            help='Display timestamps in UTC (default: local time)'
        )

        # Allow --id to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Host metric ID (overrides positional parameter)'
        )

        # Positional parameter for host metric hostname or ID
        parser.add_argument(
            'host_metric',
            nargs='?',
            help='Host metric hostname or ID to show'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the host metrics show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine host metric identifier to use
            host_metric_identifier = parsed_args.id if parsed_args.id else parsed_args.host_metric

            if not host_metric_identifier:
                raise AAPClientError("Host metric hostname or ID is required")

            # Store original identifier for error messages
            original_identifier = host_metric_identifier

            # Resolve hostname or ID to ID using common function
            try:
                host_metric_id = resolve_host_metric_name(client, host_metric_identifier)
            except AAPResourceNotFoundError:
                # Re-raise with original identifier for consistent error message format
                raise AAPResourceNotFoundError("Host Metric", original_identifier)

            # Query specific host metric
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}host_metrics/{host_metric_id}/"
            try:
                response = client.get(endpoint)

                if response.status_code == HTTP_OK:
                    host_metrics_data = response.json()
                    return _format_host_metrics_data(host_metrics_data, parsed_args.utc)
                elif response.status_code == HTTP_NOT_FOUND:
                    raise AAPResourceNotFoundError("Host Metric", original_identifier)
                else:
                    raise AAPClientError(f"Controller API failed with status {response.status_code}")

            except AAPAPIError as api_error:
                # Handle API errors, especially 404s
                if api_error.status_code == HTTP_NOT_FOUND:
                    raise AAPResourceNotFoundError("Host Metric", original_identifier)
                else:
                    # Re-raise other API errors
                    raise

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class HostMetricsDeleteCommand(AAPCommand):
    """Soft delete a host metric (marks as deleted and increments counter)."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # Allow --id to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Host metric ID (overrides positional parameter)'
        )

        # Positional parameter for host metric hostname or ID
        parser.add_argument(
            'host_metric',
            nargs='?',
            help='Host metric hostname or ID to delete'
        )

        return parser

    def take_action(self, parsed_args):
        """Execute the host metrics delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine host metric identifier to use
            host_metric_identifier = parsed_args.id if parsed_args.id else parsed_args.host_metric

            if not host_metric_identifier:
                raise AAPClientError("Host metric hostname or ID is required")

            # Store original identifier for messages
            original_identifier = host_metric_identifier

            # Resolve hostname or ID to ID using common function
            try:
                host_metric_id = resolve_host_metric_name(client, host_metric_identifier)
            except AAPResourceNotFoundError:
                # Re-raise with original identifier for consistent error message format
                raise AAPResourceNotFoundError("Host Metric", original_identifier)

            # Delete the host metric (API performs soft delete automatically)
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}host_metrics/{host_metric_id}/"
            try:
                response = client.delete(endpoint)

                if response.status_code == HTTP_NO_CONTENT:
                    print(f"Host metric '{original_identifier}' soft deleted successfully")
                elif response.status_code == HTTP_NOT_FOUND:
                    raise AAPResourceNotFoundError("Host Metric", original_identifier)
                elif response.status_code == HTTP_BAD_REQUEST:
                    error_details = response.text
                    raise AAPClientError(f"Bad request: {error_details}")
                else:
                    raise AAPClientError(f"Failed to delete host metric: {response.status_code}")

            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    raise AAPResourceNotFoundError("Host Metric", original_identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    error_details = getattr(api_error, 'response', None)
                    if error_details and hasattr(error_details, 'text'):
                        error_message = error_details.text
                    else:
                        error_message = str(api_error)
                    raise AAPClientError(f"Bad request: {error_message}")
                else:
                    raise

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
