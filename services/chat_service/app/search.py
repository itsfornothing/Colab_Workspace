import logging
import os

logger = logging.getLogger(__name__)

INDEX = "messages"


def _get_es():
    try:
        from elasticsearch import Elasticsearch
        es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        return Elasticsearch(es_url)
    except ImportError:
        return None


def index_message(message):
    """Index or re-index a message document in Elasticsearch."""
    es = _get_es()
    if not es:
        return
    doc = {
        "id": str(message.id),
        "channel_id": str(message.channel_id),
        "sender_id": str(message.sender_id),
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }
    es.index(index=INDEX, id=str(message.id), document=doc)


def delete_message_doc(message_id):
    """Remove a message document from Elasticsearch."""
    es = _get_es()
    if not es:
        return
    try:
        from elasticsearch import NotFoundError
        es.delete(index=INDEX, id=str(message_id))
    except Exception:
        pass


def search_messages(query: str, channel_id: str) -> list:
    """Full-text search within a channel."""
    es = _get_es()
    if not es:
        return []
    response = es.search(
        index=INDEX,
        query={
            "bool": {
                "must": [
                    {"match": {"content": query}},
                    {"term": {"channel_id": str(channel_id)}},
                ]
            }
        },
        size=50,
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]