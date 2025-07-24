"""Project commands."""
from aapclient.common.basecommands import AAPShowCommand, AAPListCommand, AAPCommand
from aapclient.common.constants import (
    CONTROLLER_API_VERSION_ENDPOINT,
    HTTP_OK,
    HTTP_CREATED,
    HTTP_NO_CONTENT,
    HTTP_NOT_FOUND,
    HTTP_BAD_REQUEST
)
from aapclient.common.exceptions import AAPClientError, AAPResourceNotFoundError, AAPAPIError
from aapclient.common.functions import resolve_organization_name, resolve_execution_environment_name, resolve_credential_name, resolve_project_name






def _format_project_data(project_data):
    """
    Format project data consistently

    Args:
        project_data (dict): Project data from API response

    Returns:
        tuple: (field_names, field_values) for ShowOne display
    """
    # Extract helper variables from summary_fields
    org_info = project_data.get('summary_fields', {}).get('organization', {})
    ee_info = project_data.get('summary_fields', {}).get('default_environment', {})
    credential_info = project_data.get('summary_fields', {}).get('credential', {})
    signature_validation_credential_info = project_data.get('summary_fields', {}).get('signature_validation_credential', {})
    created_by = project_data.get('summary_fields', {}).get('created_by', {})
    modified_by = project_data.get('summary_fields', {}).get('modified_by', {})
    last_job = project_data.get('summary_fields', {}).get('last_job', {})
    last_update = project_data.get('summary_fields', {}).get('last_update', {})

    # Define comprehensive field mappings as ordered dictionary
    field_data = {
        'ID': str(project_data.get('id', '')),
        'Name': project_data.get('name', ''),
        'Description': project_data.get('description', ''),
        'Organization': org_info.get('name', '') or str(project_data.get('organization', '')),
        'Status': project_data.get('status', ''),
        'SCM Type': project_data.get('scm_type', ''),
        'SCM URL': project_data.get('scm_url', ''),
        'SCM Credential': credential_info.get('name', '') or str(project_data.get('credential', '')),
        'SCM Branch': project_data.get('scm_branch', ''),
        'SCM Refspec': project_data.get('scm_refspec', ''),
        'SCM Revision': project_data.get('scm_revision', ''),
        'SCM Clean': 'Yes' if project_data.get('scm_clean', False) else 'No',
        'SCM Delete on Update': 'Yes' if project_data.get('scm_delete_on_update', False) else 'No',
        'SCM Track Submodules': 'Yes' if project_data.get('scm_track_submodules', False) else 'No',
        'SCM Update on Launch': 'Yes' if project_data.get('scm_update_on_launch', False) else 'No',
        'SCM Update Cache Timeout': project_data.get('scm_update_cache_timeout', 0),
        'Allow Branch Override': 'Yes' if project_data.get('allow_override', False) else 'No',
        'Local Path': project_data.get('local_path', ''),
        'Timeout': project_data.get('timeout', 0),
        'Custom Virtualenv': project_data.get('custom_virtualenv', ''),
        'Execution Environment': ee_info.get('name', '') or str(project_data.get('default_environment', '')),
        'Signature Validation Credential': signature_validation_credential_info.get('name', '') or str(project_data.get('signature_validation_credential', '')),
        'Last Job Run': project_data.get('last_job_run', 'Never'),
        'Last Job Failed': 'Yes' if project_data.get('last_job_failed', False) else 'No',
        'Last Updated': project_data.get('last_updated', 'Never'),
        'Last Update Failed': 'Yes' if project_data.get('last_update_failed', False) else 'No',
        'Next Job Run': project_data.get('next_job_run', ''),
        'Created': project_data.get('created', ''),
        'Created By': created_by.get('username', ''),
        'Modified': project_data.get('modified', ''),
        'Modified By': modified_by.get('username', ''),
    }

    return (field_data.keys(), field_data.values())



class ProjectListCommand(AAPListCommand):
    """List projects."""

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
        """Execute the project list command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Build query parameters
            params = {'order_by': 'id'}  # Sort by ID on server side
            if parsed_args.limit:
                params['page_size'] = parsed_args.limit

            # Query projects endpoint
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}projects/"
            try:
                response = client.get(endpoint, params=params)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", "projects endpoint")

            if response.status_code == HTTP_OK:
                data = response.json()

                # Extract projects from results (already sorted by API)
                projects = data.get('results', [])

                                # Define columns for table display
                columns = [
                    'ID',
                    'Name',
                    'Status',
                    'Type',
                    'Revision',
                    'Organization'
                ]

                # Build rows data
                rows = []
                for project in projects:
                    # Get organization name from summary_fields
                    org_name = 'Unknown'
                    if project.get('summary_fields', {}).get('organization'):
                        org_name = project['summary_fields']['organization'].get('name', 'Unknown')

                    # Format revision to show only first 8 characters of commit hash
                    revision = project.get('scm_revision', '')
                    if revision:
                        revision = revision[:8]

                    row = [
                        project.get('id', ''),
                        project.get('name', ''),
                        project.get('status', ''),
                        project.get('scm_type', ''),
                        revision,
                        org_name
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


class ProjectShowCommand(AAPShowCommand):
    """Show details of a specific project."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Project ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'project',
            nargs='?',
            help='Project name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the project show command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the project
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                project_id = parsed_args.id
            elif parsed_args.project:
                # Use positional parameter - name first, then ID fallback if numeric
                project_id = resolve_project_name(client, parsed_args.project, api="controller")
            else:
                raise AAPClientError("Project identifier is required")

            # Get specific project
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/"
            try:
                response = client.get(endpoint)
                project_data = response.json()

                return _format_project_data(project_data)

            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.project or parsed_args.id)

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ProjectCreateCommand(AAPShowCommand):
    """Create a new project."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'name',
            help='Project name'
        )
        parser.add_argument(
            '--description',
            help='Project description'
        )
        parser.add_argument(
            '--organization',
            required=True,
            help='Organization'
        )
        parser.add_argument(
            '--execution-environment',
            help='Default execution environment for jobs associated with this project'
        )
        parser.add_argument(
            '--signature-validation-credential',
            help='Signature validation Credential'
        )
        parser.add_argument(
            '--scm-type',
            required=True,
            choices=['git', 'svn', 'insights', 'archive'],
            help='Source control type'
        )
        parser.add_argument(
            '--scm-credential',
            dest='credential',
            help='Source Control Credential (git, svn, archive) or Insights Credential (insights)'
        )
        parser.add_argument(
            '--scm-url',
            help='Source control URL for git, svn, or archive SCM type'
        )
        parser.add_argument(
            '--scm-branch',
            help='Branch/tag/commit (git) or revision (svn)'
        )
        parser.add_argument(
            '--scm-refspec',
            help='Source control refspec (git)'
        )
        parser.add_argument(
            '--enable-scm-track-submodules',
            action='store_true',
            dest='scm_track_submodules',
            help='Enable tracking submodules for git SCM type'
        )
        parser.add_argument(
            '--enable-scm-update-on-launch',
            action='store_true',
            dest='scm_update_on_launch',
            help='Enable source control update on job launch'
        )
        parser.add_argument(
            '--enable-scm-allow-branch-override',
            action='store_true',
            dest='allow_override',
            help='Enable allowing a job template to override the branch or revision'
        )
        parser.add_argument(
            '--enable-scm-clean',
            action='store_true',
            dest='scm_clean',
            help='Enable removing local repository modifications prior to project update'
        )
        parser.add_argument(
            '--enable-scm-delete-on-update',
            action='store_true',
            dest='scm_delete_on_update',
            help='Enable deleting local repository prior to project update'
        )
        parser.add_argument(
            '--scm-update-cache-timeout',
            type=int,
            help='Delete local repository prior to project update'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the project create command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Get parser for usage message
            parser = self.get_parser('aap project create')

            # Verify required arguments for different SCM types
            if parsed_args.scm_type in ['git', 'svn', 'archive']:
                if not parsed_args.scm_url:
                    parser.error("argument --scm-url is required when using SCM type '%s'" % parsed_args.scm_type)
            if parsed_args.scm_type == 'insights':
                if not parsed_args.credential:
                    parser.error("argument --scm-credential is required when using SCM type 'insights'")

            # Resolve organization - handle both ID and name
            org_id = resolve_organization_name(client, parsed_args.organization, api="controller")

            # Resolve credential - handle both ID and name (if provided)
            credential_id = None
            if getattr(parsed_args, 'credential', None):
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")

            # Resolve execution environment - handle both ID and name (if provided)
            execution_environment_id = None
            if getattr(parsed_args, 'execution_environment', None):
                execution_environment_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")

            # Resolve signature validation credential - handle both ID and name (if provided)
            signature_validation_credential_id = None
            if getattr(parsed_args, 'signature_validation_credential', None):
                try:
                    signature_validation_credential_id = resolve_credential_name(client, parsed_args.signature_validation_credential, api="controller")
                except AAPResourceNotFoundError:
                    parser.error(f"Signature validation credential '{parsed_args.signature_validation_credential}' not found")

            project_data = {
                'name': parsed_args.name,
                'organization': org_id,
                'scm_type': parsed_args.scm_type
            }

            # Add credential if provided
            if credential_id is not None:
                project_data['credential'] = credential_id

            # Add execution environment if provided
            if execution_environment_id is not None:
                project_data['default_environment'] = execution_environment_id

            # Add signature validation credential if provided
            if signature_validation_credential_id is not None:
                project_data['signature_validation_credential'] = signature_validation_credential_id

            if parsed_args.description:
                project_data['description'] = parsed_args.description
            if getattr(parsed_args, 'scm_url', None):
                project_data['scm_url'] = parsed_args.scm_url
            if getattr(parsed_args, 'scm_branch', None):
                project_data['scm_branch'] = parsed_args.scm_branch
            if getattr(parsed_args, 'scm_refspec', None):
                project_data['scm_refspec'] = parsed_args.scm_refspec
            if getattr(parsed_args, 'scm_track_submodules', None):
                project_data['scm_track_submodules'] = parsed_args.scm_track_submodules
            if getattr(parsed_args, 'scm_update_on_launch', None):
                project_data['scm_update_on_launch'] = parsed_args.scm_update_on_launch
            if getattr(parsed_args, 'allow_override', None):
                project_data['allow_override'] = parsed_args.allow_override
            if getattr(parsed_args, 'scm_clean', None):
                project_data['scm_clean'] = parsed_args.scm_clean
            if getattr(parsed_args, 'scm_delete_on_update', None):
                project_data['scm_delete_on_update'] = parsed_args.scm_delete_on_update
            if getattr(parsed_args, 'scm_update_cache_timeout', None):
                project_data['scm_update_cache_timeout'] = parsed_args.scm_update_cache_timeout

            # Create project
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}projects/"
            try:
                response = client.post(endpoint, json=project_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.name)

            if response.status_code == HTTP_CREATED:
                project_data = response.json()
                print(f"Project '{project_data.get('name', '')}' created successfully")

                return _format_project_data(project_data)
            else:
                raise AAPClientError(f"Project creation failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ProjectSetCommand(AAPShowCommand):
    """Update an existing project."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Project ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'project',
            nargs='?',
            help='Project name or ID'
        )

        # Update fields
        parser.add_argument(
            '--set-name',
            dest='set_name',
            help='Update project name'
        )
        parser.add_argument(
            '--description',
            help='Update project description'
        )
        parser.add_argument(
            '--organization',
            help='Update organization'
        )
        parser.add_argument(
            '--execution-environment',
            help='Update default execution environment for jobs associated with this project'
        )
        parser.add_argument(
            '--signature-validation-credential',
            help='Update signature validation Credential'
        )
        parser.add_argument(
            '--scm-type',
            choices=['git', 'svn', 'insights', 'archive'],
            help='Update source control type'
        )
        parser.add_argument(
            '--scm-credential',
            dest='credential',
            help='Update source Control Credential (git, svn, archive) or Insights Credential (insights)'
        )
        parser.add_argument(
            '--scm-url',
            help='Update source control URL for git, svn, or archive SCM type'
        )
        parser.add_argument(
            '--scm-branch',
            help='Update branch/tag/commit (git) or revision (svn)'
        )
        parser.add_argument(
            '--scm-refspec',
            help='Update source control refspec (git)'
        )
        # SCM Track Submodules group
        track_submodules_group = parser.add_mutually_exclusive_group()
        track_submodules_group.add_argument(
            '--enable-scm-track-submodules',
            action='store_true',
            help='Enable tracking submodules for git SCM type'
        )
        track_submodules_group.add_argument(
            '--disable-scm-track-submodules',
            action='store_true',
            help='Disable tracking submodules for git SCM type'
        )

        # SCM Update on Launch group
        update_on_launch_group = parser.add_mutually_exclusive_group()
        update_on_launch_group.add_argument(
            '--enable-scm-update-on-launch',
            action='store_true',
            help='Enable source control update on job launch'
        )
        update_on_launch_group.add_argument(
            '--disable-scm-update-on-launch',
            action='store_true',
            help='Disable source control update on job launch'
        )

        # SCM Allow Branch Override group
        allow_override_group = parser.add_mutually_exclusive_group()
        allow_override_group.add_argument(
            '--enable-scm-allow-branch-override',
            action='store_true',
            help='Enable allowing a job template to override the branch or revision'
        )
        allow_override_group.add_argument(
            '--disable-scm-allow-branch-override',
            action='store_true',
            help='Disable allowing a job template to override the branch or revision'
        )

        # SCM Clean group
        scm_clean_group = parser.add_mutually_exclusive_group()
        scm_clean_group.add_argument(
            '--enable-scm-clean',
            action='store_true',
            help='Enable removing local repository modifications prior to project update'
        )
        scm_clean_group.add_argument(
            '--disable-scm-clean',
            action='store_true',
            help='Disable removing local repository modifications prior to project update'
        )

        # SCM Delete on Update group
        delete_on_update_group = parser.add_mutually_exclusive_group()
        delete_on_update_group.add_argument(
            '--enable-scm-delete-on-update',
            action='store_true',
            help='Enable deleting local repository prior to project update'
        )
        delete_on_update_group.add_argument(
            '--disable-scm-delete-on-update',
            action='store_true',
            help='Disable deleting local repository prior to project update'
        )
        parser.add_argument(
            '--scm-update-cache-timeout',
            type=int,
            help='Update SCM cache timeout'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the project set command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the project
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                project_id = parsed_args.id
            elif parsed_args.project:
                # Use positional parameter - name first, then ID fallback if numeric
                project_id = resolve_project_name(client, parsed_args.project, api="controller")
            else:
                raise AAPClientError("Project identifier is required")

            # Resolve organization if provided
            if getattr(parsed_args, 'organization', None):
                org_id = resolve_organization_name(client, parsed_args.organization, api="controller")
            else:
                org_id = None

            # Resolve credential if provided
            if getattr(parsed_args, 'credential', None):
                credential_id = resolve_credential_name(client, parsed_args.credential, api="controller")
            else:
                credential_id = None

            # Resolve execution environment if provided
            if getattr(parsed_args, 'execution_environment', None):
                execution_environment_id = resolve_execution_environment_name(client, parsed_args.execution_environment, api="controller")
            else:
                execution_environment_id = None

            # Resolve signature validation credential if provided
            if getattr(parsed_args, 'signature_validation_credential', None):
                try:
                    signature_validation_credential_id = resolve_credential_name(client, parsed_args.signature_validation_credential, api="controller")
                except AAPResourceNotFoundError:
                    parser = self.get_parser('aap project set')
                    parser.error(f"Signature validation credential '{parsed_args.signature_validation_credential}' not found")
            else:
                signature_validation_credential_id = None

            # Prepare project update data
            project_data = {}

            if parsed_args.set_name:
                project_data['name'] = parsed_args.set_name
            if parsed_args.description:
                project_data['description'] = parsed_args.description
            if org_id is not None:
                project_data['organization'] = org_id
            if credential_id is not None:
                project_data['credential'] = credential_id
            if execution_environment_id is not None:
                project_data['default_environment'] = execution_environment_id
            if signature_validation_credential_id is not None:
                project_data['signature_validation_credential'] = signature_validation_credential_id
            if getattr(parsed_args, 'scm_type', None):
                project_data['scm_type'] = parsed_args.scm_type
            if getattr(parsed_args, 'scm_url', None):
                project_data['scm_url'] = parsed_args.scm_url
            if getattr(parsed_args, 'scm_branch', None):
                project_data['scm_branch'] = parsed_args.scm_branch
            if getattr(parsed_args, 'scm_refspec', None):
                project_data['scm_refspec'] = parsed_args.scm_refspec
            # Handle boolean option groups following OpenStack pattern
            if getattr(parsed_args, 'enable_scm_track_submodules', None):
                project_data['scm_track_submodules'] = True
            if getattr(parsed_args, 'disable_scm_track_submodules', None):
                project_data['scm_track_submodules'] = False
            if getattr(parsed_args, 'enable_scm_update_on_launch', None):
                project_data['scm_update_on_launch'] = True
            if getattr(parsed_args, 'disable_scm_update_on_launch', None):
                project_data['scm_update_on_launch'] = False
            if getattr(parsed_args, 'enable_scm_allow_branch_override', None):
                project_data['allow_override'] = True
            if getattr(parsed_args, 'disable_scm_allow_branch_override', None):
                project_data['allow_override'] = False
            if getattr(parsed_args, 'enable_scm_clean', None):
                project_data['scm_clean'] = True
            if getattr(parsed_args, 'disable_scm_clean', None):
                project_data['scm_clean'] = False
            if getattr(parsed_args, 'enable_scm_delete_on_update', None):
                project_data['scm_delete_on_update'] = True
            if getattr(parsed_args, 'disable_scm_delete_on_update', None):
                project_data['scm_delete_on_update'] = False
            if getattr(parsed_args, 'scm_update_cache_timeout', None):
                project_data['scm_update_cache_timeout'] = parsed_args.scm_update_cache_timeout

            if not project_data:
                raise AAPClientError("At least one field must be specified to update")

            # Update project
            endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/"
            try:
                response = client.patch(endpoint, json=project_data)
            except AAPAPIError as api_error:
                self.handle_api_error(api_error, "Controller API", parsed_args.project or parsed_args.id)

            if response.status_code == HTTP_OK:
                project_data = response.json()
                print(f"Project '{project_data.get('name', '')}' updated successfully")

                return _format_project_data(project_data)
            else:
                raise AAPClientError(f"Project update failed with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")


class ProjectDeleteCommand(AAPCommand):
    """Delete a project."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        # ID option to override positional parameter
        parser.add_argument(
            '--id',
            type=int,
            help='Project ID (overrides positional parameter)'
        )

        # Positional parameter for name lookup with ID fallback
        parser.add_argument(
            'project',
            nargs='?',
            help='Project name or ID'
        )
        return parser

    def take_action(self, parsed_args):
        """Execute the project delete command."""
        try:
            # Get client from centralized client manager
            client = self.controller_client

            # Determine how to resolve the project
            if parsed_args.id:
                # Use explicit ID (ignores positional parameter)
                project_id = parsed_args.id
                project_identifier = str(parsed_args.id)
            elif parsed_args.project:
                # Use positional parameter - name first, then ID fallback if numeric
                project_id = resolve_project_name(client, parsed_args.project, api="controller")
                project_identifier = parsed_args.project
            else:
                raise AAPClientError("Project identifier is required")

            # Get project details first for confirmation
            try:
                endpoint = f"{CONTROLLER_API_VERSION_ENDPOINT}projects/{project_id}/"
                response = client.get(endpoint)
            except AAPAPIError as api_error:
                if api_error.status_code == HTTP_NOT_FOUND:
                    # Handle 404 error with proper message
                    raise AAPResourceNotFoundError("Project", project_identifier)
                elif api_error.status_code == HTTP_BAD_REQUEST:
                    # Pass through 400 status messages directly to user
                    raise SystemExit(str(api_error))
                else:
                    # Re-raise other errors
                    raise

            if response.status_code == HTTP_OK:
                project_data = response.json()
                project_name = project_data.get('name', project_identifier)

                # Delete project
                try:
                    delete_response = client.delete(endpoint)
                except AAPAPIError as api_error:
                    if api_error.status_code == HTTP_NOT_FOUND:
                        # Handle 404 error with proper message
                        raise AAPResourceNotFoundError("Project", project_identifier)
                    elif api_error.status_code == HTTP_BAD_REQUEST:
                        # Pass through 400 status messages directly to user
                        raise SystemExit(str(api_error))
                    else:
                        # Re-raise other errors
                        raise

                if delete_response.status_code == HTTP_NO_CONTENT:
                    print(f"Project '{project_name}' deleted successfully")
                else:
                    raise AAPClientError(f"Project deletion failed with status {delete_response.status_code}")
            else:
                raise AAPClientError(f"Failed to get project details with status {response.status_code}")

        except AAPResourceNotFoundError as e:
            raise SystemExit(str(e))
        except AAPClientError as e:
            raise SystemExit(str(e))
        except Exception as e:
            raise SystemExit(f"Unexpected error: {e}")
