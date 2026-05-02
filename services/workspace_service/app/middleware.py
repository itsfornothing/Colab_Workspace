class WorkspaceMiddleware:
    """Attaches X-Workspace-ID header value to request for downstream use."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace_id = request.headers.get("X-Workspace-ID") or request.META.get("HTTP_X_WORKSPACE_ID")
        return self.get_response(request)
