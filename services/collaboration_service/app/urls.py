from django.urls import path
from .views import (
    create_document_view,
    list_documents_view,
    get_document_view,
    update_document_view,
    archive_document_view,
    restore_version_view,
    grant_permission_view,
    revoke_permission_view,
    save_snapshot_view,
    acquire_lock_view,
    release_lock_view,
)

urlpatterns = [
    # Documents
    path("documents/", create_document_view),                                          # POST
    path("documents/list/", list_documents_view),                                      # GET  ?workspace_id=
    path("documents/<uuid:document_id>/", get_document_view),                          # GET
    path("documents/<uuid:document_id>/update/", update_document_view),                # PUT
    path("documents/<uuid:document_id>/archive/", archive_document_view),              # POST

    # Versioning
    path("documents/<uuid:document_id>/restore/", restore_version_view),               # POST

    # Permissions
    path("documents/<uuid:document_id>/permissions/grant/", grant_permission_view),    # POST
    path("documents/<uuid:document_id>/permissions/revoke/", revoke_permission_view),  # DELETE

    # CRDT snapshots
    path("documents/<uuid:document_id>/snapshot/", save_snapshot_view),                # POST

    # Locks
    path("documents/<uuid:document_id>/lock/", acquire_lock_view),                     # POST
    path("documents/<uuid:document_id>/lock/release/", release_lock_view),             # DELETE
]