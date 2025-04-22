# utils/state.py
import logging
from typing import Dict, Tuple, Optional
from bson import ObjectId

# Dictionary mapping client IDs to their peer connections, AES keys and WebSocket objects.
clients = {
    # "client_identifier": {"ws": <websocket instance>, "username": <username>, "aes_key": <session AES key>, "pc": <optional PeerConnection>}
}

# key = tuple(sorted([caller_id, callee_id]))
pending_calls: Dict[Tuple[str, str], Dict[str, Optional[ObjectId]]] = {}


def call_key(uid1: str, uid2: str) -> Tuple[str, str]:
    return tuple(sorted([uid1, uid2]))


# Configure logging
logging.basicConfig(level=logging.INFO)
