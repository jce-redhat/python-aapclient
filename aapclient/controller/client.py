# Copyright (c) 2025 Chris Edillon
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AAP Controller API Client"""

import logging
import requests
from typing import Any, Dict, List, Optional

from aapclient.common.aapconfig import AAPConfig


LOG = logging.getLogger(__name__)

API_NAME = 'controller'
API_VERSION = '2'
DEFAULT_API_VERSION = '2'


class ControllerClientError(Exception):
    """Exception raised by Controller client"""
    pass


class Client:
    """AAP Controller API Client"""

    def __init__(self, config: AAPConfig):
        self.config = config
        self.session = requests.Session()

        # Set up authentication
        auth_headers = config.get_auth_headers()
        if auth_headers:
            self.session.headers.update(auth_headers)

        # Set up SSL verification
        ssl_config = config.get_ssl_config()
        self.session.verify = ssl_config['verify']

        # Set up base URL - try to detect API version
        self.base_url = self._get_base_url()

    def _get_base_url(self) -> str:
        """Get the base URL for the controller API"""
        # Try new AAP 2.5+ structure first
        try:
            resp = self.session.get(f"{self.config.host}/api/")
            if resp.status_code == 200:
                api_info = resp.json()
                if 'apis' in api_info and 'controller' in api_info['apis']:
                    # AAP 2.5+ structure
                    controller_path = api_info['apis']['controller']
                    # Get versioned path
                    resp = self.session.get(f"{self.config.host}{controller_path}")
                    if resp.status_code == 200:
                        version_info = resp.json()
                        if 'current_version' in version_info:
                            return f"{self.config.host}{version_info['current_version']}"
                        elif 'available_versions' in version_info:
                            # Use the highest version available
                            versions = version_info['available_versions']
                            if 'v2' in versions:
                                return f"{self.config.host}{versions['v2']}"
        except Exception as e:
            LOG.debug(f"Failed to detect AAP 2.5+ structure: {e}")

        # Fall back to AAP 2.4 structure
        return f"{self.config.host}/api/v2/"

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the AAP API"""
        url = f"{self.base_url}{endpoint.lstrip('/')}"

        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=data,
                timeout=self.config.timeout
            )
            resp.raise_for_status()

            # DELETE requests often return empty responses
            if method.upper() == 'DELETE':
                if resp.text.strip():
                    try:
                        return resp.json()
                    except ValueError:
                        # If we can't parse JSON, just return an empty dict
                        return {}
                else:
                    # Empty response is expected for DELETE
                    return {}
            else:
                return resp.json()
        except requests.exceptions.RequestException as e:
            raise ControllerClientError(f"API request failed: {e}")

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request"""
        return self._make_request('GET', endpoint, params=params)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST request"""
        return self._make_request('POST', endpoint, data=data)

    def patch(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PATCH request"""
        return self._make_request('PATCH', endpoint, data=data)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PUT request"""
        return self._make_request('PUT', endpoint, data=data)

    def delete(self, endpoint: str) -> None:
        """DELETE request"""
        self._make_request('DELETE', endpoint)

    def ping(self) -> Dict[str, Any]:
        """Ping the API to check connectivity"""
        return self.get('ping/')

    # Projects
    def list_projects(self, **params) -> Dict[str, Any]:
        """List projects"""
        return self.get('projects/', params=params)

    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get a specific project"""
        return self.get(f'projects/{project_id}/')

    def create_project(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new project"""
        return self.post('projects/', data=data)

    def update_project(self, project_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a project"""
        return self.patch(f'projects/{project_id}/', data=data)

    def delete_project(self, project_id: int) -> None:
        """Delete a project"""
        self.delete(f'projects/{project_id}/')

    # Organizations
    def list_organizations(self, **params) -> Dict[str, Any]:
        """List organizations"""
        return self.get('organizations/', params=params)

    def get_organization(self, org_id: int) -> Dict[str, Any]:
        """Get a specific organization"""
        return self.get(f'organizations/{org_id}/')

    def create_organization(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new organization"""
        return self.post('organizations/', data=data)

    def update_organization(self, org_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an organization"""
        return self.patch(f'organizations/{org_id}/', data=data)

    def delete_organization(self, org_id: int) -> None:
        """Delete an organization"""
        self.delete(f'organizations/{org_id}/')

    # Job Templates
    def list_job_templates(self, **params) -> Dict[str, Any]:
        """List job templates"""
        return self.get('job_templates/', params=params)

    def get_job_template(self, template_id: int) -> Dict[str, Any]:
        """Get a specific job template"""
        return self.get(f'job_templates/{template_id}/')

    def create_job_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job template"""
        return self.post('job_templates/', data=data)

    def update_job_template(self, template_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a job template"""
        return self.patch(f'job_templates/{template_id}/', data=data)

    def delete_job_template(self, template_id: int) -> None:
        """Delete a job template"""
        self.delete(f'job_templates/{template_id}/')

    def launch_job_template(self, template_id: int, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Launch a job template"""
        return self.post(f'job_templates/{template_id}/launch/', data=data or {})

    # Jobs
    def list_jobs(self, **params) -> Dict[str, Any]:
        """List jobs"""
        return self.get('jobs/', params=params)

    def get_job(self, job_id: int) -> Dict[str, Any]:
        """Get a specific job"""
        return self.get(f'jobs/{job_id}/')

    def cancel_job(self, job_id: int) -> Dict[str, Any]:
        """Cancel a job"""
        return self.post(f'jobs/{job_id}/cancel/')

    def get_job_output(self, job_id: int) -> Dict[str, Any]:
        """Get job output"""
        return self.get(f'jobs/{job_id}/stdout/')

    # Credentials
    def list_credentials(self, **params) -> Dict[str, Any]:
        """List credentials"""
        return self.get('credentials/', params=params)

    def get_credential(self, credential_id: int) -> Dict[str, Any]:
        """Get a specific credential"""
        return self.get(f'credentials/{credential_id}/')

    def create_credential(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new credential"""
        return self.post('credentials/', data=data)

    def update_credential(self, credential_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a credential"""
        return self.patch(f'credentials/{credential_id}/', data=data)

    def delete_credential(self, credential_id: int) -> None:
        """Delete a credential"""
        self.delete(f'credentials/{credential_id}/')

    # Inventories
    def list_inventories(self, **params) -> Dict[str, Any]:
        """List inventories"""
        return self.get('inventories/', params=params)

    def get_inventory(self, inventory_id: int) -> Dict[str, Any]:
        """Get a specific inventory"""
        return self.get(f'inventories/{inventory_id}/')

    def create_inventory(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new inventory"""
        return self.post('inventories/', data=data)

    def update_inventory(self, inventory_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an inventory"""
        return self.patch(f'inventories/{inventory_id}/', data=data)

    def delete_inventory(self, inventory_id: int) -> None:
        """Delete an inventory"""
        self.delete(f'inventories/{inventory_id}/')

    # Users
    def list_users(self, **params) -> Dict[str, Any]:
        """List users"""
        return self.get('users/', params=params)

    def get_user(self, user_id: int) -> Dict[str, Any]:
        """Get a specific user"""
        return self.get(f'users/{user_id}/')

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        return self.post('users/', data=data)

    def update_user(self, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a user"""
        return self.patch(f'users/{user_id}/', data=data)

    def delete_user(self, user_id: int) -> None:
        """Delete a user"""
        self.delete(f'users/{user_id}/')
    
    # Workflow Job Templates
    def list_workflow_job_templates(self, **params) -> Dict[str, Any]:
        """List workflow job templates"""
        return self.get('workflow_job_templates/', params=params)
    
    def get_workflow_job_template(self, template_id: int) -> Dict[str, Any]:
        """Get a specific workflow job template"""
        return self.get(f'workflow_job_templates/{template_id}/')
    
    def create_workflow_job_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new workflow job template"""
        return self.post('workflow_job_templates/', data=data)
    
    def update_workflow_job_template(self, template_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a workflow job template"""
        return self.patch(f'workflow_job_templates/{template_id}/', data=data)
    
    def delete_workflow_job_template(self, template_id: int) -> None:
        """Delete a workflow job template"""
        self.delete(f'workflow_job_templates/{template_id}/')
    
    def launch_workflow_job_template(self, template_id: int, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Launch a workflow job template"""
        return self.post(f'workflow_job_templates/{template_id}/launch/', data=data or {})
    
    # Workflow Jobs
    def list_workflow_jobs(self, **params) -> Dict[str, Any]:
        """List workflow jobs"""
        return self.get('workflow_jobs/', params=params)
    
    def get_workflow_job(self, job_id: int) -> Dict[str, Any]:
        """Get a specific workflow job"""
        return self.get(f'workflow_jobs/{job_id}/')
    
    def cancel_workflow_job(self, job_id: int) -> Dict[str, Any]:
        """Cancel a workflow job"""
        return self.post(f'workflow_jobs/{job_id}/cancel/')
    
    def relaunch_workflow_job(self, job_id: int) -> Dict[str, Any]:
        """Relaunch a workflow job"""
        return self.post(f'workflow_jobs/{job_id}/relaunch/')
    
    # Workflow Job Template Nodes
    def list_workflow_job_template_nodes(self, template_id: int, **params) -> Dict[str, Any]:
        """List nodes for a workflow job template"""
        return self.get(f'workflow_job_templates/{template_id}/workflow_nodes/', params=params)
    
    def get_workflow_job_template_node(self, template_id: int, node_id: int) -> Dict[str, Any]:
        """Get a specific workflow job template node"""
        return self.get(f'workflow_job_templates/{template_id}/workflow_nodes/{node_id}/')
    
    def create_workflow_job_template_node(self, template_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a workflow job template node"""
        return self.post(f'workflow_job_templates/{template_id}/workflow_nodes/', data=data)
    
    def update_workflow_job_template_node(self, template_id: int, node_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a workflow job template node"""
        return self.patch(f'workflow_job_templates/{template_id}/workflow_nodes/{node_id}/', data=data)
    
    def delete_workflow_job_template_node(self, template_id: int, node_id: int) -> None:
        """Delete a workflow job template node"""
        self.delete(f'workflow_job_templates/{template_id}/workflow_nodes/{node_id}/')


def make_client(instance):
    """Factory function for creating client instances"""
    # This will be called by the plugin system
    return Client
