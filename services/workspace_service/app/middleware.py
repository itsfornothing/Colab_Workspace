from .models import Workspace, Membership


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        workspace_id = request.headers.get("X-Workspace-ID")
        request.workspace = None
        request.membership = None

        if workspace_id and request.user.is_authenticated:
            try:
                workspace = Workspace.objects.get(id=workspace_id)

                membership = Membership.objects.filter(
                    user=request.user,
                    workspace=workspace
                ).first()

                if membership:
                    request.workspace = workspace
                    request.membership = membership

            except Workspace.DoesNotExist:
                pass

        return self.get_response(request)