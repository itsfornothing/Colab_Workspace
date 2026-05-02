"""
Bug Condition Exploration Test - Docs Data Loss on Restart

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

This test uses static code inspection (reading file contents as strings) to
surface the two defects described in the bugfix spec. It does NOT run Docker
or make live HTTP calls, making it fast and reproducible.

CRITICAL: Both tests in this file are EXPECTED TO FAIL on unfixed code.
Failure confirms the bugs exist. When the fix is applied (tasks 3.1 and 3.2),
these tests will pass, confirming both defects are resolved.

Defect 1 (Requirement 1.1, 1.2):
  update-ip.sh force-removes collaboration-db via `docker rm -f`, introducing
  a cold-start timing window that can cause data loss.
  Bug Condition: "collaboration-db" IN input.dockerRmCommand

Defect 2 (Requirement 1.3, 1.4):
  list_documents_view returns "updated_at" (raw datetime, wrong key) instead
  of "last_edited_at" serialized via .isoformat().
  Bug Condition: "updated_at" IN responseKeys AND "last_edited_at" NOT IN responseKeys
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


# ---------------------------------------------------------------------------
# Defect 1 - Script test
# ---------------------------------------------------------------------------

def test_collaboration_db_not_in_docker_rm_command():
    """
    Defect 1: update-ip.sh must NOT include 'collaboration-db' in the
    `docker rm -f` command.

    Bug Condition (from design.md):
        "collaboration-db" IN input.dockerRmCommand

    Expected counterexample on UNFIXED code:
        Line 36 of update-ip.sh contains:
            docker rm -f collaboration-service collaboration-db collaboration-redis ...

    This test FAILS on unfixed code (confirming the bug exists).
    This test PASSES after fix (task 3.1 removes collaboration-db from the command).
    """
    with open(UPDATE_IP_SH, "r") as f:
        script_content = f.read()

    # Find all `docker rm -f` lines in the script
    docker_rm_lines = [
        line.strip()
        for line in script_content.splitlines()
        if re.search(r"docker\s+rm\s+-f", line)
    ]

    assert docker_rm_lines, (
        "No `docker rm -f` command found in update-ip.sh — "
        "the script structure may have changed."
    )

    # Assert that none of the docker rm -f lines contain 'collaboration-db'
    # On UNFIXED code this assertion FAILS, surfacing the counterexample.
    for line in docker_rm_lines:
        assert "collaboration-db" not in line, (
            f"\n\n[COUNTEREXAMPLE FOUND - Defect 1]\n"
            f"update-ip.sh contains 'collaboration-db' in a `docker rm -f` command:\n"
            f"  {line}\n\n"
            f"This confirms Bug Condition 1:\n"
            f"  'collaboration-db' IN input.dockerRmCommand\n\n"
            f"Impact: The database container is force-removed on every IP update,\n"
            f"introducing a cold-start timing window where collaboration-service\n"
            f"may connect before Postgres finishes recovery, causing data loss.\n\n"
            f"Fix (task 3.1): Remove 'collaboration-db' from the docker rm -f command."
        )


# ---------------------------------------------------------------------------
# Defect 2 - API field test
# ---------------------------------------------------------------------------

def test_list_documents_view_uses_last_edited_at_with_isoformat():
    """
    Defect 2: list_documents_view must return 'last_edited_at' (not 'updated_at')
    with a value produced by .isoformat().

    Bug Condition (from design.md):
        "updated_at" IN responseKeys AND "last_edited_at" NOT IN responseKeys

    Expected counterexample on UNFIXED code:
        list_documents_view contains:
            "updated_at": d.updated_at,
        (raw datetime object, wrong key — Flutter reads json['last_edited_at']
         which is absent, so lastEditedAt is always null)

    This test FAILS on unfixed code (confirming the bug exists).
    This test PASSES after fix (task 3.2 renames key and adds .isoformat()).
    """
    with open(VIEWS_PY, "r") as f:
        views_content = f.read()

    # Extract the body of list_documents_view for targeted inspection.
    # We look for the function definition and capture everything up to the
    # next top-level @api_view decorator (or end of file).
    func_match = re.search(
        r"def list_documents_view\(.*?\n(.*?)(?=\n@api_view|\Z)",
        views_content,
        re.DOTALL,
    )
    assert func_match, (
        "Could not locate list_documents_view in views.py — "
        "the function may have been renamed or moved."
    )

    func_body = func_match.group(0)

    # --- Assert 1: 'last_edited_at' key IS present in the response dict ---
    assert '"last_edited_at"' in func_body, (
        f"\n\n[COUNTEREXAMPLE FOUND - Defect 2a]\n"
        f"list_documents_view does NOT contain '\"last_edited_at\"' in its response.\n\n"
        f"This confirms Bug Condition 2:\n"
        f"  'last_edited_at' NOT IN responseKeys\n\n"
        f"Impact: Document.fromJson reads json['last_edited_at'] which is absent,\n"
        f"so lastEditedAt is always null and documents display as 'Untitled'.\n\n"
        f"Fix (task 3.2): Change '\"updated_at\": d.updated_at' to\n"
        f"                '\"last_edited_at\": d.updated_at.isoformat()'"
    )

    # --- Assert 2: 'updated_at' key is NOT used as a response dict key ---
    # We check for the pattern `"updated_at":` inside the response list
    # comprehension. We allow 'updated_at' to appear as an attribute access
    # (d.updated_at) but not as a response key.
    assert '"updated_at"' not in func_body, (
        f"\n\n[COUNTEREXAMPLE FOUND - Defect 2b]\n"
        f"list_documents_view still contains '\"updated_at\"' as a response key.\n\n"
        f"This confirms Bug Condition 2:\n"
        f"  'updated_at' IN responseKeys\n\n"
        f"Impact: The Flutter client reads json['last_edited_at'] (not 'updated_at'),\n"
        f"so the timestamp is never populated and documents appear as 'Untitled'.\n\n"
        f"Fix (task 3.2): Rename '\"updated_at\"' to '\"last_edited_at\"' and\n"
        f"                serialize with .isoformat()"
    )

    # --- Assert 3: .isoformat() IS called on the timestamp value ---
    assert "isoformat()" in func_body, (
        f"\n\n[COUNTEREXAMPLE FOUND - Defect 2c]\n"
        f"list_documents_view does NOT call .isoformat() on the timestamp.\n\n"
        f"Impact: A raw Python datetime object is returned, which may cause\n"
        f"JSON serialization issues and prevents the Flutter client from\n"
        f"parsing the timestamp as an ISO 8601 string.\n\n"
        f"Fix (task 3.2): Change 'd.updated_at' to 'd.updated_at.isoformat()'"
    )
