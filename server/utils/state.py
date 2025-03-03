# utils/state.py
import logging

# Dictionary mapping client IDs to their peer connections and WebSocket objects.
# Example: { "clientA": {"pc": RTCPeerConnection, "ws": websocket}, ... }
clients = {}

# Configure logging (or this can be done in run.py)
logging.basicConfig(level=logging.INFO)
