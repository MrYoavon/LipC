# utils/state.py
import logging

# Dictionary mapping client IDs to their peer connections, AES keys and WebSocket objects.
clients = {
    # "client_identifier": {"ws": <websocket instance>, "username": <username>, "aes_key": <session AES key>, "pc": <optional PeerConnection>}
}

# Configure logging (or this can be done in run.py)
logging.basicConfig(level=logging.INFO)
