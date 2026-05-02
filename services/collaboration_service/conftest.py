"""
conftest.py for collaboration service integration tests.

Patches the presence module to use in-memory storage instead of Redis,
allowing WebSocket tests to run without a live Redis instance.
"""
import pytest
from unittest.mock import patch

# In-memory presence store for tests
_presence_store = {}


def _set_user_active(doc_id, user_id):
    key = str(doc_id)
    _presence_store.setdefault(key, set()).add(str(user_id))


def _remove_user_active(doc_id, user_id):
    key = str(doc_id)
    if key in _presence_store:
        _presence_store[key].discard(str(user_id))


def _get_active_users(doc_id):
    return list(_presence_store.get(str(doc_id), set()))


def _is_user_active(doc_id, user_id):
    return str(user_id) in _presence_store.get(str(doc_id), set())


@pytest.fixture(autouse=True)
def patch_presence():
    """
    Auto-use fixture that patches presence functions for all tests.
    This ensures WebSocket tests work without a live Redis instance.
    """
    _presence_store.clear()
    with patch("app.consumers.set_user_active", _set_user_active), \
         patch("app.consumers.remove_user_active", _remove_user_active), \
         patch("app.consumers.get_active_users", _get_active_users):
        yield
    _presence_store.clear()
