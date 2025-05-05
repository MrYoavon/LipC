# utils/state.py
from typing import Dict, Tuple, Optional
from bson import ObjectId

# ----------------------------------------------------------------------------
# Global session and call state
# ----------------------------------------------------------------------------

# Mapping of user IDs to session info: websocket, username, AES key, peer connection, and model preference.
clients: Dict[str, Dict[str, Optional[object]]] = {}

# Mapping of call keys to pending call metadata, including caller, callee, and database call_id.
pending_calls: Dict[Tuple[str, str], Dict[str, Optional[ObjectId]]] = {}

# Mapping of username to failed login attempts, including the number of attempts and the timestamp of the end of the block.
failed_login_attempts: Dict[str, dict] = {}


def call_key(uid1: str, uid2: str) -> Tuple[str, str]:
    """
    Generate a consistent, order-independent key for a pair of user IDs.

    Args:
        uid1 (str): First user ID.
        uid2 (str): Second user ID.

    Returns:
        Tuple[str, str]: Sorted tuple of the two user IDs, suitable as a dictionary key.
    """
    return tuple(sorted([uid1, uid2]))
