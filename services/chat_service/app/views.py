import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .search import search_messages

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_view(request):
    """
    GET /api/messages/search/?q=hello&channel_id=<uuid>

    Returns matching messages from Elasticsearch for the given channel.
    The caller must be authenticated (JWT). No membership check is enforced
    here — add one if channels can be private.
    """
    query = request.GET.get("q", "").strip()
    channel_id = request.GET.get("channel_id", "").strip()

    if not query:
        return Response(
            {"detail": "Query parameter 'q' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not channel_id:
        return Response(
            {"detail": "Query parameter 'channel_id' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        results = search_messages(query, channel_id)
        return Response(results)
    except Exception:
        logger.exception("Search failed for query=%r channel=%r", query, channel_id)
        return Response(
            {"detail": "Search service is temporarily unavailable."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )