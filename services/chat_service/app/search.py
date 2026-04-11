import logging
from elasticsearch import Elasticsearch, NotFoundError

logger = logging.getLogger(__name__)

es = Elasticsearch("http://localhost:9200")

INDEX = "messages"


def index_message(message):
    """Index or re-index a message document in Elasticsearch."""
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
    try:
        es.delete(index=INDEX, id=str(message_id))
    except NotFoundError:
        pass  # Already gone — not an error
    except Exception:
        logger.exception("Failed to delete ES doc for message %s", message_id)


def search_messages(query: str, channel_id: str) -> list:
    """
    Full-text search within a channel.
    Uses the modern keyword-argument style (elasticsearch-py v8+).
    """
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
        size=50,  # Cap results per request
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]