"""
Operational Transformation helpers.

NOTE: This module is NOT used by the Yjs/CRDT WebSocket path. Yjs handles
conflict resolution internally via its CRDT algorithm — you should never
manually transform Yjs operations with OT functions. Doing so would corrupt
the document state.

This module is kept for reference only, or for use in a plain-text fallback
editor that does NOT use Yjs. If you're going full Yjs, you can delete this.

For a real OT engine consider using `ot.py` (sharedb-compatible) or
`python-ot` if you need server-side transformation for a plain textarea.
"""


def apply_operation(current_text: str, operation: dict) -> str:
    """
    Apply a single insert or delete operation to `current_text`.

    operation format:
        {"type": "insert", "position": int, "text": str}
        {"type": "delete", "position": int, "length": int}
    """
    op_type = operation.get("type")

    if op_type == "insert":
        pos = operation["position"]
        text = operation["text"]
        return current_text[:pos] + text + current_text[pos:]

    elif op_type == "delete":
        pos = operation["position"]
        length = operation["length"]
        return current_text[:pos] + current_text[pos + length:]

    return current_text


def transform(op_a: dict, op_b: dict) -> dict:
    """
    Transform op_a against op_b so that op_a can be applied after op_b.
    Minimal implementation for insert/delete against insert/delete.
    """
    if op_a["type"] == "insert" and op_b["type"] == "insert":
        if op_b["position"] <= op_a["position"]:
            return {**op_a, "position": op_a["position"] + len(op_b["text"])}

    elif op_a["type"] == "insert" and op_b["type"] == "delete":
        if op_b["position"] < op_a["position"]:
            return {**op_a, "position": max(
                op_b["position"],
                op_a["position"] - op_b["length"]
            )}

    elif op_a["type"] == "delete" and op_b["type"] == "insert":
        if op_b["position"] <= op_a["position"]:
            return {**op_a, "position": op_a["position"] + len(op_b["text"])}

    elif op_a["type"] == "delete" and op_b["type"] == "delete":
        if op_b["position"] < op_a["position"]:
            overlap = max(
                0,
                min(op_b["position"] + op_b["length"], op_a["position"]) - op_b["position"]
            )
            return {**op_a, "position": op_a["position"] - op_b["length"] + overlap}

    return op_a