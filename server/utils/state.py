# utils/state.py
import logging
from aiortc.contrib.media import MediaRelay

# Dictionary mapping client IDs to their peer connections and WebSocket objects.
# Example: { "clientA": {"pc": RTCPeerConnection, "ws": websocket}, ... }
clients = {}

# Initialize MediaRelay to subscribe to incoming video tracks.
relay = MediaRelay()

# Configure logging (or this can be done in run.py)
logging.basicConfig(level=logging.INFO)
