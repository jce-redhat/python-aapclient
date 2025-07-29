"""Common utility functions for AAP client."""

from datetime import datetime, timezone
from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError


def format_duration(elapsed_seconds):
    """
    Format elapsed time in human-readable format with units.

    Args:
        elapsed_seconds (float): Duration in seconds

    Returns:
        str: Formatted duration (e.g., "20s", "1m 22s", "1h 5m 30s")
    """
    if not elapsed_seconds:
        return "0s"

    total_seconds = int(elapsed_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:  # Always show seconds if no other units
        parts.append(f"{seconds}s")

    return " ".join(parts)


def format_datetime(iso_datetime_str, use_utc=False):
    """
    Format ISO datetime string to YYYY-MM-DD HH:MM:SS TZ format.
    Displays in UTC or local time based on use_utc parameter.

    Args:
        iso_datetime_str (str): ISO format datetime string
        use_utc (bool): If True, display in UTC; if False, display in local time

    Returns:
        str: Formatted datetime with timezone or original string if parsing fails
    """
    if not iso_datetime_str:
        return ''

    try:
        # Parse ISO datetime with timezone awareness
        if 'T' in iso_datetime_str:
            # Handle datetime with timezone (Z indicates UTC)
            if iso_datetime_str.endswith('Z'):
                # Remove 'Z' and parse as UTC
                clean_datetime = iso_datetime_str[:-1]
                if '.' in clean_datetime:
                    # Handle microseconds
                    dt = datetime.fromisoformat(clean_datetime).replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.fromisoformat(clean_datetime).replace(tzinfo=timezone.utc)
            else:
                # Try to parse with timezone info
                dt = datetime.fromisoformat(iso_datetime_str)

            if use_utc:
                # Convert to UTC for display
                utc_dt = dt.astimezone(timezone.utc)
                return utc_dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            else:
                # Convert to local time for display (Python will use system timezone)
                local_dt = dt.astimezone()
                return local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            return iso_datetime_str
    except (ValueError, AttributeError):
        # Return original string if parsing fails
        return iso_datetime_str


def resolve_organization_name(client, identifier, api="gateway"):
    """
    Resolve organization identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Organization name or ID
        api: API to use for resolution ("gateway" or "controller"). Defaults to "gateway".

    Returns:
        int: Organization ID

    Raises:
        AAPResourceNotFoundError: If organization not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "gateway":
        api_endpoint = GATEWAY_API_VERSION_ENDPOINT
    elif api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as organization name lookup
    try:
        endpoint = f"{api_endpoint}organizations/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for organization '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        org_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}organizations/{org_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return org_id
        else:
            raise AAPResourceNotFoundError("Organization", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Organization", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Organization", identifier)


def resolve_team_name(client, identifier, api="gateway"):
    """
    Resolve team identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Team name or ID
        api: API to use for resolution ("gateway" or "controller"). Defaults to "gateway".
             Note: Teams are only available in Gateway API.

    Returns:
        int: Team ID

    Raises:
        AAPResourceNotFoundError: If team not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "gateway":
        api_endpoint = GATEWAY_API_VERSION_ENDPOINT
    elif api == "controller":
        # Teams are not available in Controller API
        raise AAPClientError("Teams are only available in Gateway API. Use api='gateway'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as team name lookup
    try:
        endpoint = f"{api_endpoint}teams/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for team '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        team_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}teams/{team_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return team_id
        else:
            raise AAPResourceNotFoundError("Team", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Team", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Team", identifier)


def resolve_user_name(client, identifier, api="gateway"):
    """
    Resolve user identifier (username or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Username or User ID
        api: API to use for resolution ("gateway" or "controller"). Defaults to "gateway".
             Note: Users are only available in Gateway API.

    Returns:
        int: User ID

    Raises:
        AAPResourceNotFoundError: If user not found by username or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "gateway":
        api_endpoint = GATEWAY_API_VERSION_ENDPOINT
    elif api == "controller":
        # Users are not available in Controller API
        raise AAPClientError("Users are only available in Gateway API. Use api='gateway'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as username lookup
    try:
        endpoint = f"{api_endpoint}users/"
        params = {'username': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Username lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for user '{identifier}'")
    except AAPAPIError:
        # API error during username lookup, continue to ID lookup
        pass

    # Username lookup failed, try as ID if it's numeric
    try:
        user_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}users/{user_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return user_id
        else:
            raise AAPResourceNotFoundError("User", identifier)
    except ValueError:
        # Not a valid integer, and username lookup already failed
        raise AAPResourceNotFoundError("User", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("User", identifier)


def resolve_execution_environment_name(client, identifier, api="controller"):
    """
    Resolve execution environment identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Execution environment name or ID
        api: API to use for resolution ("gateway" or "controller"). Defaults to "controller".
             Note: Execution environments are only available in Controller API.

    Returns:
        int: Execution environment ID

    Raises:
        AAPResourceNotFoundError: If execution environment not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Execution environments are not available in Gateway API
        raise AAPClientError("Execution environments are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as execution environment name lookup
    try:
        endpoint = f"{api_endpoint}execution_environments/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for execution environment '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        ee_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}execution_environments/{ee_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return ee_id
        else:
            raise AAPResourceNotFoundError("Execution Environment", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Execution Environment", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Execution Environment", identifier)


def resolve_credential_name(client, identifier, api="controller"):
    """
    Resolve credential identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Credential name or ID
        api: API to use for resolution ("gateway" or "controller"). Defaults to "controller".
             Note: Credentials are only available in Controller API.

    Returns:
        int: Credential ID

    Raises:
        AAPResourceNotFoundError: If credential not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Credentials are not available in Gateway API
        raise AAPClientError("Credentials are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as credential name lookup
    try:
        endpoint = f"{api_endpoint}credentials/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for credential '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        credential_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}credentials/{credential_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return credential_id
        else:
            raise AAPResourceNotFoundError("Credential", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Credential", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Credential", identifier)


def resolve_inventory_name(client, identifier, api="controller"):
    """
    Resolve inventory identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Inventory name or ID
        api: API to use for resolution ("gateway" or "controller"). Defaults to "controller".
             Note: Inventories are only available in Controller API.

    Returns:
        int: Inventory ID

    Raises:
        AAPResourceNotFoundError: If inventory not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Inventories are not available in Gateway API
        raise AAPClientError("Inventories are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as inventory name lookup
    try:
        endpoint = f"{api_endpoint}inventories/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for inventory '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        inventory_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}inventories/{inventory_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return inventory_id
        else:
            raise AAPResourceNotFoundError("Inventory", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Inventory", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Inventory", identifier)


def resolve_instance_group_name(client, identifier, api="controller"):
    """Resolve instance group identifier to instance group ID.

    Args:
        client: AAPHTTPClient instance
        identifier: Instance group name or ID
        api: API to use for resolution ("controller"). Defaults to "controller".
             Note: Instance groups are only available in Controller API.

    Returns:
        int: Instance group ID

    Raises:
        AAPResourceNotFoundError: If instance group not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    else:
        raise AAPClientError("Instance groups are only available in Controller API. Use api='controller'.")

    # Try name-based lookup first
    endpoint = f"{api_endpoint}instance_groups/"
    params = {'name': identifier}

    try:
        response = client.get(endpoint, params=params)
        if response.status_code == HTTP_OK:
            data = response.json()
            if data['count'] == 1:
                return data['results'][0]['id']
            elif data['count'] == 0:
                # Name not found, try ID lookup if it's numeric
                pass
            else:
                raise AAPClientError(f"Multiple instance groups found with name '{identifier}'")
        else:
            raise AAPAPIError("Failed to search instance groups", response.status_code)
    except AAPAPIError:
        # If name lookup fails, try ID lookup
        pass

    # Try ID lookup if name lookup failed or if identifier is numeric
    try:
        instance_group_id = int(identifier)
        endpoint = f"{api_endpoint}instance_groups/{instance_group_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return instance_group_id
        else:
            raise AAPResourceNotFoundError("Instance Group", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Instance Group", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Instance Group", identifier)


def resolve_host_name(client, identifier, api="controller"):
    """
    Resolve host identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Host name or ID
        api: API to use for resolution ("controller"). Defaults to "controller".
             Note: Hosts are only available in Controller API.

    Returns:
        int: Host ID

    Raises:
        AAPResourceNotFoundError: If host not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Hosts are not available in Gateway API
        raise AAPClientError("Hosts are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as host name lookup
    try:
        endpoint = f"{api_endpoint}hosts/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for host '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        host_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}hosts/{host_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return host_id
        else:
            raise AAPResourceNotFoundError("Host", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Host", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Host", identifier)


def resolve_instance_name(client, identifier, api="controller"):
    """
    Resolve instance identifier (hostname or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Instance hostname or ID
        api: API to use for resolution ("controller"). Defaults to "controller".
             Note: Instances are only available in Controller API.

    Returns:
        int: Instance ID

    Raises:
        AAPResourceNotFoundError: If instance not found by hostname or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Instances are not available in Gateway API
        raise AAPClientError("Instances are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as instance hostname lookup
    try:
        endpoint = f"{api_endpoint}instances/"
        params = {'hostname': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Hostname lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for instance '{identifier}'")
    except AAPAPIError:
        # API error during hostname lookup, continue to ID lookup
        pass

    # Hostname lookup failed, try as ID if it's numeric
    try:
        instance_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}instances/{instance_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return instance_id
        else:
            raise AAPResourceNotFoundError("Instance", identifier)
    except ValueError:
        # Not a valid integer, and hostname lookup already failed
        raise AAPResourceNotFoundError("Instance", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Instance", identifier)


def resolve_project_name(client, identifier, api="controller"):
    """
    Resolve project identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Project name or ID
        api: API to use for resolution ("controller"). Defaults to "controller".
             Note: Projects are only available in Controller API.

    Returns:
        int: Project ID

    Raises:
        AAPResourceNotFoundError: If project not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Projects are not available in Gateway API
        raise AAPClientError("Projects are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as project name lookup
    try:
        endpoint = f"{api_endpoint}projects/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for project '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        project_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}projects/{project_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return project_id
        else:
            raise AAPResourceNotFoundError("Project", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Project", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Project", identifier)


def resolve_group_name(client, identifier, api="controller"):
    """
    Resolve group identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Group name or ID
        api: API to use for resolution ("controller"). Defaults to "controller".
             Note: Groups are only available in Controller API.

    Returns:
        int: Group ID

    Raises:
        AAPResourceNotFoundError: If group not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Groups are not available in Gateway API
        raise AAPClientError("Groups are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as group name lookup
    try:
        endpoint = f"{api_endpoint}groups/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for group '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        group_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}groups/{group_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return group_id
        else:
            raise AAPResourceNotFoundError("Group", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Group", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Group", identifier)


def resolve_job_name(client, identifier, api="controller"):
    """
    Resolve job identifier (name or ID) to ID for use by other resource commands.

    Args:
        client: AAPHTTPClient instance
        identifier: Job name or ID
        api: API to use for resolution ("controller"). Defaults to "controller".
             Note: Jobs are only available in Controller API.

    Returns:
        int: Job ID

    Raises:
        AAPResourceNotFoundError: If job not found by name or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Jobs are only available in Controller API.")

    # First try as job name lookup using unified_jobs endpoint
    try:
        endpoint = f"{api_endpoint}unified_jobs/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Name lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for job '{identifier}'")
    except AAPAPIError:
        # API error during name lookup, continue to ID lookup
        pass

    # Name lookup failed, try as ID if it's numeric
    try:
        job_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}unified_jobs/{job_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return job_id
        else:
            raise AAPResourceNotFoundError("Job", identifier)
    except ValueError:
        # Not a valid integer, and name lookup already failed
        raise AAPResourceNotFoundError("Job", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Job", identifier)


def resolve_application_name(client, identifier, api="gateway"):
    """
    Resolve application name to ID using Gateway API.

    Args:
        client: HTTP client instance
        identifier: Application name or ID
        api: API type (for compatibility with other resolve functions)

    Returns:
        int: Application ID

    Raises:
        AAPResourceNotFoundError: If application not found
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Application resolution only works with Gateway API
    if api != "gateway":
        raise AAPClientError(f"Invalid API type '{api}'. Applications are only available in Gateway API.")

    # If already an integer, return as-is
    try:
        return int(identifier)
    except (ValueError, TypeError):
        pass

    # Search by name
    try:
        endpoint = f"{GATEWAY_API_VERSION_ENDPOINT}applications/"
        params = {'name': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                raise AAPResourceNotFoundError("Application", identifier)
        else:
            raise AAPClientError(f"Failed to search applications: {response.status_code}")

    except AAPResourceNotFoundError:
        raise
    except Exception as e:
        raise AAPClientError(f"Error resolving application name: {e}")


def resolve_host_metric_name(client, identifier, api="controller"):
    """
    Resolve host metric identifier (hostname or ID) to ID.

    Args:
        client: AAPHTTPClient instance
        identifier: Host metric hostname or ID
        api: API to use for resolution ("controller"). Defaults to "controller".
             Note: Host metrics are only available in Controller API.

    Returns:
        int: Host metric ID

    Raises:
        AAPResourceNotFoundError: If host metric not found by hostname or ID
        AAPClientError: If invalid API type specified or API error occurs
    """
    # Determine which API endpoint to use
    if api == "controller":
        api_endpoint = CONTROLLER_API_VERSION_ENDPOINT
    elif api == "gateway":
        # Host metrics are not available in Gateway API
        raise AAPClientError("Host metrics are only available in Controller API. Use api='controller'.")
    else:
        raise AAPClientError(f"Invalid API type '{api}'. Must be 'gateway' or 'controller'.")

    # First try as hostname lookup
    try:
        endpoint = f"{api_endpoint}host_metrics/"
        params = {'hostname': identifier}
        response = client.get(endpoint, params=params)

        if response.status_code == HTTP_OK:
            data = response.json()
            results = data.get('results', [])
            if results:
                return results[0]['id']
            else:
                # Hostname lookup failed, continue to ID lookup
                pass
        else:
            raise AAPClientError(f"Failed to search for host metric '{identifier}'")
    except AAPAPIError:
        # API error during hostname lookup, continue to ID lookup
        pass

    # Hostname lookup failed, try as ID if it's numeric
    try:
        host_metric_id = int(identifier)
        # Verify the ID exists by trying to get it
        endpoint = f"{api_endpoint}host_metrics/{host_metric_id}/"
        response = client.get(endpoint)
        if response.status_code == HTTP_OK:
            return host_metric_id
        else:
            raise AAPResourceNotFoundError("Host Metric", identifier)
    except ValueError:
        # Not a valid integer, and hostname lookup already failed
        raise AAPResourceNotFoundError("Host Metric", identifier)
    except AAPAPIError:
        # API error during ID lookup
        raise AAPResourceNotFoundError("Host Metric", identifier)
