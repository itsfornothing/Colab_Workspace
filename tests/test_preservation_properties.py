"""
Preservation Property Tests - Docs Data Loss on Restart

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

These tests capture the BASELINE behavior of update-ip.sh and list_documents_view
that must be PRESERVED after the bugfix is applied (tasks 3.1 and 3.2).

Methodology: observation-first static code inspection.
- Tests observe what the UNFIXED code already does correctly.
- Tests PASS on unfixed code (confirming baseline behavior).
- Tests continue to PASS after the fix (confirming no regressions).

No Django ORM, no Docker, no live HTTP calls — fast and reproducible.
"""

import os
import re

# Resolve paths relative to this test file so tests work from any cwd
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDATE_IP_SH = os.path.join(WORKSPACE_ROOT, "update-ip.sh")
VIEWS_PY = os.path.join(
    WORKSPACE_ROOT,
    "services", "collaboration_service", "app", "views.py"
)


def _get_script_content():
    """Read and return the full content of update-ip.sh."""
    with open(UPDATE_IP_SH, "r") as f:
        return f.read()


def _get_list_documents_view_body():
    """
    Extract the body of list_documents_view from views.py using the same
    regex pattern as the exploration test.
    """
    with open(VIEWS_PY, "r") as f:
        views_content = f.read()

    func_match = re.search(
        r"def list_documents_view\(.*?\n(.*?)(?=\n@api_view|\Z)",
        views_content,
        re.DOTALL,
    )
    assert func_match, (
        "Could not locate list_documents_view in views.py — "
        "the function may have been renamed or moved."
    )
    return func_match.group(0)


# ---------------------------------------------------------------------------
# Property 3: Preservation — IP Update Functionality (Requirements 3.1, 3.2, 3.3)
# ---------------------------------------------------------------------------

def test_update_ip_updates_env_local_files():
    """
    Property 3a: update-ip.sh contains sed commands that update all six
    service .env.local files.

    Preservation: The script must continue to update all service env files
    with the new IP address after the fix is applied (Requirement 3.1).

    This PASSES on unfixed code — these sed commands are already correct.
    """
    script_content = _get_script_content()

    env_local_files = [
        "services/user_service/.env.local",
        "services/workspace_service/.env.local",
        "services/chat_service/.env.local",
        "services/collaboration_service/.env.local",
        "services/media_service/.env.local",
        "services/notification_service/.env.local",
    ]

    for env_file in env_local_files:
        assert env_file in script_content, (
            f"\n\n[PRESERVATION FAILURE - Property 3a]\n"
            f"update-ip.sh does NOT reference '{env_file}'.\n\n"
            f"This means the script no longer updates this service's .env.local file,\n"
            f"which would break IP propagation for that service.\n\n"
            f"Requirement 3.1: The script SHALL CONTINUE TO update all service .env.local files."
        )


def test_update_ip_updates_constants_dart():
    """
    Property 3b: update-ip.sh contains a sed command targeting
    frontend/mobile/mobile_app/lib/core/constants.dart.

    Preservation: The script must continue to update the Flutter constants
    file with the new IP address after the fix is applied (Requirement 3.1).

    This PASSES on unfixed code — the constants.dart sed command is already correct.
    """
    script_content = _get_script_content()

    constants_path = "frontend/mobile/mobile_app/lib/core/constants.dart"
    assert constants_path in script_content, (
        f"\n\n[PRESERVATION FAILURE - Property 3b]\n"
        f"update-ip.sh does NOT reference '{constants_path}'.\n\n"
        f"This means the script no longer updates the Flutter constants file,\n"
        f"which would break the mobile app's ability to connect to the new IP.\n\n"
        f"Requirement 3.1: The script SHALL CONTINUE TO update constants.dart."
    )


def test_update_ip_updates_docker_compose_allowed_hosts():
    """
    Property 3c: update-ip.sh contains sed commands updating
    DJANGO_ALLOWED_HOSTS in docker-compose.yml.

    Preservation: The script must continue to update DJANGO_ALLOWED_HOSTS
    in docker-compose.yml after the fix is applied (Requirement 3.1).

    This PASSES on unfixed code — the ALLOWED_HOSTS sed commands are already correct.
    """
    script_content = _get_script_content()

    assert "DJANGO_ALLOWED_HOSTS" in script_content, (
        f"\n\n[PRESERVATION FAILURE - Property 3c]\n"
        f"update-ip.sh does NOT reference 'DJANGO_ALLOWED_HOSTS'.\n\n"
        f"This means the script no longer updates the allowed hosts configuration,\n"
        f"which would cause Django to reject requests from the new IP.\n\n"
        f"Requirement 3.1: The script SHALL CONTINUE TO update DJANGO_ALLOWED_HOSTS."
    )

    assert "docker-compose.yml" in script_content, (
        f"\n\n[PRESERVATION FAILURE - Property 3c]\n"
        f"update-ip.sh does NOT reference 'docker-compose.yml'.\n\n"
        f"This means the script no longer updates the docker-compose configuration,\n"
        f"which would leave DJANGO_ALLOWED_HOSTS with the old IP.\n\n"
        f"Requirement 3.1: The script SHALL CONTINUE TO update docker-compose.yml."
    )


def test_update_ip_runs_docker_cp_steps():
    """
    Property 3d: update-ip.sh contains docker cp commands for re-applying
    custom code fixes after container restarts.

    Preservation: The script must continue to re-apply all custom code fixes
    via docker cp after the fix is applied (Requirement 3.3).

    This PASSES on unfixed code — the docker cp commands are already present.
    """
    script_content = _get_script_content()

    # Assert that key files are copied back into containers
    copied_files = [
        "authentication.py",
        "views.py",
        "consumers.py",
        "settings.py",
    ]

    for filename in copied_files:
        assert filename in script_content, (
            f"\n\n[PRESERVATION FAILURE - Property 3d]\n"
            f"update-ip.sh does NOT contain a docker cp command for '{filename}'.\n\n"
            f"This means the script no longer re-applies the custom {filename} fix\n"
            f"after container restarts, which would cause the service to run with\n"
            f"the default (unfixed) version of the file.\n\n"
            f"Requirement 3.3: The script SHALL CONTINUE TO re-apply all custom code fixes."
        )

    # Assert docker cp appears multiple times (at least 4 copy operations)
    docker_cp_count = script_content.count("docker cp")
    assert docker_cp_count >= 4, (
        f"\n\n[PRESERVATION FAILURE - Property 3d]\n"
        f"update-ip.sh contains only {docker_cp_count} 'docker cp' command(s), "
        f"but at least 4 are expected.\n\n"
        f"This means some custom code fix re-apply steps have been removed,\n"
        f"which would cause services to run with default (unfixed) code.\n\n"
        f"Requirement 3.3: The script SHALL CONTINUE TO re-apply all custom code fixes via docker cp."
    )


def test_update_ip_restarts_application_containers():
    """
    Property 3e: update-ip.sh contains docker compose up and docker restart
    commands for application-layer containers, including collaboration-service.

    Preservation: The script must continue to rebuild and restart application
    containers after the fix is applied (Requirements 3.2, 3.3).

    This PASSES on unfixed code — the restart commands are already present.
    """
    script_content = _get_script_content()

    assert "docker compose up" in script_content, (
        f"\n\n[PRESERVATION FAILURE - Property 3e]\n"
        f"update-ip.sh does NOT contain a 'docker compose up' command.\n\n"
        f"This means the script no longer rebuilds and recreates application containers,\n"
        f"which would leave services running with the old IP configuration.\n\n"
        f"Requirement 3.2: The script SHALL CONTINUE TO rebuild and restart collaboration-service."
    )

    assert "docker restart" in script_content, (
        f"\n\n[PRESERVATION FAILURE - Property 3e]\n"
        f"update-ip.sh does NOT contain a 'docker restart' command.\n\n"
        f"This means the script no longer restarts services after applying code fixes,\n"
        f"which would leave services running with stale code.\n\n"
        f"Requirement 3.3: The script SHALL CONTINUE TO restart services with updated files."
    )

    assert "collaboration-service" in script_content, (
        f"\n\n[PRESERVATION FAILURE - Property 3e]\n"
        f"update-ip.sh does NOT reference 'collaboration-service' in restart commands.\n\n"
        f"This means the collaboration service is no longer restarted during IP updates,\n"
        f"which would leave it running with the old IP configuration.\n\n"
        f"Requirement 3.2: The script SHALL CONTINUE TO restart collaboration-service."
    )


# ---------------------------------------------------------------------------
# Property 4: Preservation — Document List Response Fields (Requirements 3.4–3.7)
# ---------------------------------------------------------------------------

def test_list_documents_view_returns_id_field():
    """
    Property 4a: list_documents_view contains "id" as a response key.

    Preservation: The "id" field must continue to be returned in the document
    list response after the fix is applied (Requirement 3.5).

    This PASSES on unfixed code — "id" is already present in the response.
    """
    func_body = _get_list_documents_view_body()

    assert '"id"' in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4a]\n"
        f"list_documents_view does NOT contain '\"id\"' as a response key.\n\n"
        f"This means the document ID is no longer returned in the list response,\n"
        f"which would break the Flutter client's ability to identify documents.\n\n"
        f"Requirement 3.5: The endpoint SHALL CONTINUE TO return the 'id' field."
    )


def test_list_documents_view_returns_title_field():
    """
    Property 4b: list_documents_view contains "title" as a response key.

    Preservation: The "title" field must continue to be returned in the document
    list response after the fix is applied (Requirements 3.5, 3.6).

    This PASSES on unfixed code — "title" is already present in the response.
    """
    func_body = _get_list_documents_view_body()

    assert '"title"' in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4b]\n"
        f"list_documents_view does NOT contain '\"title\"' as a response key.\n\n"
        f"This means document titles are no longer returned in the list response,\n"
        f"which would cause all documents to display as 'Untitled' in the Flutter app.\n\n"
        f"Requirement 3.5, 3.6: The endpoint SHALL CONTINUE TO return the 'title' field."
    )


def test_list_documents_view_returns_workspace_id_field():
    """
    Property 4c: list_documents_view contains "workspace_id" as a response key.

    Preservation: The "workspace_id" field must continue to be returned in the
    document list response after the fix is applied (Requirement 3.5).

    This PASSES on unfixed code — "workspace_id" is already present in the response.
    """
    func_body = _get_list_documents_view_body()

    assert '"workspace_id"' in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4c]\n"
        f"list_documents_view does NOT contain '\"workspace_id\"' as a response key.\n\n"
        f"This means the workspace association is no longer returned in the list response,\n"
        f"which would break the Flutter client's ability to group documents by workspace.\n\n"
        f"Requirement 3.5: The endpoint SHALL CONTINUE TO return the 'workspace_id' field."
    )


def test_list_documents_view_returns_last_edited_by_field():
    """
    Property 4d: list_documents_view contains "last_edited_by" as a response key.

    Preservation: The "last_edited_by" field must continue to be returned in the
    document list response after the fix is applied (Requirement 3.5).

    This PASSES on unfixed code — "last_edited_by" is already present in the response.
    """
    func_body = _get_list_documents_view_body()

    assert '"last_edited_by"' in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4d]\n"
        f"list_documents_view does NOT contain '\"last_edited_by\"' as a response key.\n\n"
        f"This means the last editor information is no longer returned in the list response,\n"
        f"which would break the Flutter client's ability to display who last edited a document.\n\n"
        f"Requirement 3.5: The endpoint SHALL CONTINUE TO return the 'last_edited_by' field."
    )


def test_list_documents_view_filters_by_workspace():
    """
    Property 4e: list_documents_view calls list_documents(request.user, workspace_id),
    passing workspace_id to the service layer for filtering.

    Preservation: The workspace filtering logic must continue to work after the
    fix is applied (Requirement 3.4).

    This PASSES on unfixed code — list_documents is already called with workspace_id.
    """
    func_body = _get_list_documents_view_body()

    assert "list_documents" in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4e]\n"
        f"list_documents_view does NOT call 'list_documents' in its body.\n\n"
        f"This means the service layer is no longer used to fetch documents,\n"
        f"which would break permission checks and workspace filtering.\n\n"
        f"Requirement 3.4: The endpoint SHALL CONTINUE TO filter documents by workspace."
    )

    assert "workspace_id" in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4e]\n"
        f"list_documents_view does NOT reference 'workspace_id' in its body.\n\n"
        f"This means workspace filtering is no longer applied when listing documents,\n"
        f"which would return documents from all workspaces to every user.\n\n"
        f"Requirement 3.4: The endpoint SHALL CONTINUE TO filter documents by workspace_id."
    )


def test_list_documents_view_requires_workspace_id_param():
    """
    Property 4f: list_documents_view validates that workspace_id query param
    is present and returns HTTP 400 if it is missing.

    Preservation: The input validation must continue to work after the fix is
    applied (Requirement 3.4).

    This PASSES on unfixed code — the 400 validation is already present.
    """
    func_body = _get_list_documents_view_body()

    assert "workspace_id" in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4f]\n"
        f"list_documents_view does NOT reference 'workspace_id' in its body.\n\n"
        f"This means the workspace_id parameter is no longer validated,\n"
        f"which would allow requests without a workspace_id to proceed.\n\n"
        f"Requirement 3.4: The endpoint SHALL CONTINUE TO require workspace_id."
    )

    assert "HTTP_400_BAD_REQUEST" in func_body, (
        f"\n\n[PRESERVATION FAILURE - Property 4f]\n"
        f"list_documents_view does NOT contain 'HTTP_400_BAD_REQUEST' in its body.\n\n"
        f"This means the endpoint no longer returns a 400 error when workspace_id\n"
        f"is missing, which would allow invalid requests to proceed silently.\n\n"
        f"Requirement 3.4: The endpoint SHALL CONTINUE TO return 400 when workspace_id is absent."
    )
