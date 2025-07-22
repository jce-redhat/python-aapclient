"""Common utility functions for AAP client."""

from aapclient.common.constants import (
    GATEWAY_API_VERSION_ENDPOINT,
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError


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
