import asyncio
import json
import logging
import os
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
import cv2

from services.state import clients  # clients is assumed to be a dict holding websocket and peer connection info
from services.crypto_utils import send_encrypted  # Import the helper to encrypt outgoing messages

class WebRTCServer:
    """
    Encapsulates a server-side WebRTC connection.
    Creates an RTCPeerConnection, registers event handlers, and manages the SDP offer/answer exchange.
    """
    def __init__(self, websocket, sender, aes_key):
        self.websocket = websocket
        self.sender = sender
        self.aes_key = aes_key
        self.pc = RTCPeerConnection()
        # Store the connection for later ICE/answer handling.
        clients[sender]["pc"] = self.pc

        # Register event handlers
        self.pc.on("track", self.on_track)
        # self.pc.on("icecandidate", self.on_icecandidate)  # ICE trickle isn't implemented in aiortc by default.

    async def on_track(self, track):
        logging.info(f"Received {track.kind} track from {self.sender}")
        track.onended = lambda: logging.info(f"{track.kind} track from {self.sender} ended")

        if track.kind == "video":
            logging.info(f"Received a video track from {self.sender}")
            # Video handling/inference code could go here.
        elif track.kind == "audio":
            logging.info(f"Received an audio track from {self.sender}")
            # Audio handling code could go here.

    async def on_icecandidate(self, candidate):
        if candidate is None:
            logging.info(f"No more ICE candidates for {self.sender}")
        else:
            candidate_payload = {
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex,
            }
            message = {
                "type": "ice_candidate",
                "from": "server",
                "target": self.sender,
                "payload": candidate_payload,
            }
            logging.info(f"Sending ICE candidate to {self.sender} | {candidate_payload}")
            await send_encrypted(self.websocket, json.dumps(message), self.aes_key)

    async def handle_offer(self, offer_data):
        """
        Sets the remote description from the client's offer, creates an answer,
        and sets the local description.
        Returns the answer message to send back to the client.
        """
        offer_sdp = offer_data["sdp"]
        cleaned_sdp = self.remove_rtx(offer_sdp)
        offer = RTCSessionDescription(sdp=cleaned_sdp, type=offer_data["type"])
        await self.pc.setRemoteDescription(offer)

        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        logging.info(f"ANSWER GENERATED: {answer}")

        return {
            "type": "answer",
            "from": "server",
            "target": self.sender,
            "payload": {
                "sdp": answer.sdp,
                "type": answer.type,
            },
        }

    def remove_rtx(self, sdp: str) -> str:
        lines = sdp.splitlines()
        filtered_lines = []
        rtx_payloads = set()
        for line in lines:
            if line.startswith("a=rtpmap") and "rtx/90000" in line:
                payload_type = line.split()[0].split(":")[1]
                rtx_payloads.add(payload_type)
                continue
            filtered_lines.append(line)
        
        # Remove fmtp and rtcp-fb lines related to RTX payloads
        filtered_lines = [
            line for line in filtered_lines
            if not ((line.startswith("a=fmtp:") or line.startswith("a=rtcp-fb:")) and any(pt in line for pt in rtx_payloads))
        ]
        return "\r\n".join(filtered_lines) + "\r\n"


# ----- Message handling functions follow. These are called by the main handler -----

async def handle_offer(websocket, data, aes_key):
    """
    Handle an SDP offer from a client.
    Data should include "from", "target", and "payload" (the SDP).
    """
    sender = data.get("from")
    target = data.get("target")
    logging.info(f"Received offer from {sender} to {target}")

    if target == "server":
        await handle_server_offer(websocket, data, aes_key)
        return

    if sender not in clients:
        await send_encrypted(websocket, json.dumps({
            "type": "error",
            "message": "Sender not authenticated."
        }), aes_key)
        return

    target_ws = clients[target]["ws"]
    target_aes_key = clients[target].get("aes_key", aes_key)
    await send_encrypted(target_ws, json.dumps(data), target_aes_key)


async def handle_answer(websocket, data, aes_key):
    """
    Handle an SDP answer from a client.
    """
    sender = data.get("from")
    target = data.get("target")
    logging.info(f"Relaying answer from {sender} to {target}")

    if target == "server":
        await handle_server_answer(websocket, data, aes_key)
        return

    if target not in clients:
        await send_encrypted(websocket, json.dumps({
            "type": "error",
            "message": "Target not connected."
        }), aes_key)
        return

    target_ws = clients[target]["ws"]
    target_aes_key = clients[target].get("aes_key", aes_key)
    await send_encrypted(target_ws, json.dumps(data), target_aes_key)


async def handle_ice_candidate(websocket, data, aes_key):
    """
    Handle an ICE candidate from a client.
    """
    sender = data.get("from")
    target = data.get("target")
    logging.info(f"Relaying ICE candidate from {sender} to {target}")

    if target == "server":
        await handle_server_ice_candidate(websocket, data, aes_key)
        return

    if target not in clients:
        await send_encrypted(websocket, json.dumps({
            "type": "error",
            "message": "Target not connected."
        }), aes_key)
        return

    target_ws = clients[target]["ws"]
    target_aes_key = clients[target].get("aes_key", aes_key)
    await send_encrypted(target_ws, json.dumps(data), target_aes_key)


async def handle_server_offer(websocket, data, aes_key):
    """
    Handle an SDP offer from a client that is intended for the server.
    """
    sender = data.get("from")
    offer_data = data.get("payload")
    logging.info(f"Handling server offer from {sender}")

    server_connection = WebRTCServer(websocket, sender, aes_key)
    response = await server_connection.handle_offer(offer_data)
    await send_encrypted(websocket, json.dumps(response), aes_key)
    logging.info(f"Server sent answer to {sender}")


async def handle_server_answer(websocket, data, aes_key):
    """
    Handle an SDP answer from a client for a server-initiated connection.
    """
    sender = data.get("from")
    answer_data = data.get("payload")
    logging.info(f"Handling server answer from {sender}")

    if sender not in clients or "pc" not in clients[sender]:
        await send_encrypted(websocket, json.dumps({
            "type": "error",
            "message": "No active server connection for sender."
        }), aes_key)
        return

    pc = clients[sender]["pc"]
    answer = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
    await pc.setRemoteDescription(answer)


async def handle_server_ice_candidate(websocket, data, aes_key):
    """
    Handle an ICE candidate intended for the server's peer connection.
    """
    sender = data.get("from")
    candidate_dict = data.get("payload")
    logging.info(f"Handling server ICE candidate from {sender}")

    if sender not in clients or "pc" not in clients[sender]:
        await send_encrypted(websocket, json.dumps({
            "type": "error",
            "message": "No active server connection for sender."
        }), aes_key)
        return

    pc = clients[sender]["pc"]
    candidate_str = candidate_dict.get("candidate")
    candidate_data = parse_candidate(candidate_str)
    candidate = RTCIceCandidate(
        foundation=candidate_data["foundation"],
        component=candidate_data["component"],
        protocol=candidate_data["protocol"],
        priority=candidate_data["priority"],
        ip=candidate_data["ip"],
        port=candidate_data["port"],
        type=candidate_data["type"],
        tcpType=candidate_data["tcpType"],
        sdpMid=candidate_dict.get("sdpMid"),
        sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
    )
    await pc.addIceCandidate(candidate)


def parse_candidate(candidate_str):
    candidate_parts = candidate_str.split()
    
    candidate_data = {
        "foundation": candidate_parts[0],
        "component": int(candidate_parts[1]),
        "protocol": candidate_parts[2],
        "priority": int(candidate_parts[3]),
        "ip": candidate_parts[4],
        "port": int(candidate_parts[5]),
        "type": None,
        "tcpType": None,
        "generation": None,
        "ufrag": None,
        "network_id": None
    }

    i = 6
    while i < len(candidate_parts):
        if candidate_parts[i] == "typ":
            candidate_data["type"] = candidate_parts[i + 1]
            i += 2
        elif candidate_parts[i] == "tcptype":
            candidate_data["tcpType"] = candidate_parts[i + 1]
            i += 2
        elif candidate_parts[i] == "generation":
            candidate_data["generation"] = int(candidate_parts[i + 1])
            i += 2
        elif candidate_parts[i] == "ufrag":
            candidate_data["ufrag"] = candidate_parts[i + 1]
            i += 2
        elif candidate_parts[i] == "network-id":
            candidate_data["network_id"] = int(candidate_parts[i + 1])
            i += 2
        else:
            i += 1  # Skip unknown keys

    return candidate_data
