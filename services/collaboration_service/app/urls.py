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
    document_versions_view,
    # Tasks
    tasks_view,
    task_detail_view,
    # Files
    files_view,
    upload_file_view,
    delete_file_view,
)

urlpatterns = [
    # Documents
    path("documents/", create_document_view),
    path("documents/list/", list_documents_view),
    path("documents/<uuid:document_id>/", get_document_view),
    path("documents/<uuid:document_id>/update/", update_document_view),
    path("documents/<uuid:document_id>/archive/", archive_document_view),
    path("documents/<uuid:document_id>/versions/", document_versions_view),

    # Versioning
    path("documents/<uuid:document_id>/restore/", restore_version_view),

    # Permissions
    path("documents/<uuid:document_id>/permissions/grant/", grant_permission_view),
    path("documents/<uuid:document_id>/permissions/revoke/", revoke_permission_view),

    # CRDT snapshots
    path("documents/<uuid:document_id>/snapshot/", save_snapshot_view),

    # Locks
    path("documents/<uuid:document_id>/lock/", acquire_lock_view),
    path("documents/<uuid:document_id>/lock/release/", release_lock_view),

    # Tasks
    path("tasks/", tasks_view),
    path("tasks/<uuid:task_id>/", task_detail_view),

    # Files
    path("files/", files_view),
    path("files/upload/", upload_file_view),
    path("files/<uuid:file_id>/", delete_file_view),
]
