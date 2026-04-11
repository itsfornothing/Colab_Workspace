"""
Sharding helper — maps a document_id to a Redis channel-layer shard.

BUG FIX: Python's built-in hash() is non-deterministic across processes
(PYTHONHASHSEED randomisation introduced in Python 3.3). Two workers would
compute different shard IDs for the same document_id, placing their
consumers in different channel-layer groups — so messages would never
reach all peers. Fixed by using a stable hash (MD5 of the UUID string).

The shard ID is embedded in the channel-layer group name so that, in a
multi-Redis-node setup, documents are distributed across nodes.
"""

import hashlib


def get_shard(document_id: str, total_shards: int = 4) -> int:
    """
    Return a stable integer shard index in [0, total_shards).

    Uses the first 8 hex characters of the MD5 digest of the document_id
    string — cheap, deterministic, and process-independent.
    """
    digest = hashlib.md5(str(document_id).encode()).hexdigest()
    return int(digest[:8], 16) % total_shards


def get_group_name(document_id: str, total_shards: int = 4) -> str:
    """
    Convenience wrapper that returns the full channel-layer group name.
    Use this everywhere instead of constructing the name manually.
    """
    shard_id = get_shard(document_id, total_shards)
    return f"doc_{shard_id}_{document_id}"