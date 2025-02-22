# utils/signaling.py
import json
import logging
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from .state import clients, relay

async def handle_offer(websocket, data):
    """
    Handle an SDP offer from a client.
    Data should contain: "from", "target", and "offer" (SDP).
    """
    sender = data.get("from")
    target = data.get("target")
    offer = data.get("payload")
    logging.info(f"Received offer from {sender} to {target}")
    
    if sender not in clients:
        await websocket.send(json.dumps({"type": "error", "message": "Sender not authenticated."}))
        return

    # Create a new RTCPeerConnection for the sender if it doesn't exist.
    pc = RTCPeerConnection()
    clients[sender]["pc"] = pc

    @pc.on("track")
    def on_track(track):
        logging.info(f"Track received from {sender}: {track.kind}")
        if track.kind == "video":
            # No longer forwarding video tracks to other clients because they will be sending it back and forth directly between each other.
            # # Subscribe to the incoming video track.
            # forwarded_track = relay.subscribe(track)
            # # If the target is connected and has a peer connection, add the track.
            # if target in clients and clients[target]["pc"]:
            #     clients[target]["pc"].addTrack(forwarded_track)

            # We should later add the lip reading in real time functionality here.
            # For example:
            # subtitles = run_lip_reading(forwarded_track)
            # Then send subtitles via websocket to clients.
            pass
     
    # # Set remote description using the received offer.
    # await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
    # answer = await pc.createAnswer()
    # await pc.setLocalDescription(answer)

    # # Relay the answer back to the sender.
    # response = {
    #     "type": "answer",
    #     "from": sender,
    #     "to": target,
    #     "answer": {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
    # }
    # await websocket.send(json.dumps(response))
    # logging.info(f"Sent answer from server to {sender}")

    target_websocket = clients[target]["ws"]
    await target_websocket.send(json.dumps(data))


async def handle_answer(websocket, data):
    """
    Handle an SDP answer from a client.
    """
    sender = data.get("from")
    target = data.get("target")
    answer = data.get("payload")
    logging.info(f"Relaying answer from {sender} to {target}")
    
    # if target in clients and clients[target]["pc"]:
    #     pc = clients[target]["pc"]
    #     await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
    #     logging.info(f"Set remote description for {target}")
    # else:
    #     await websocket.send(json.dumps({"type": "error", "message": "Target peer connection not found."}))

    if target not in clients:
        await websocket.send(json.dumps({"type": "error", "message": "Target not connected."}))
        return

    target_websocket = clients[target]["ws"]
    print(f"Sender: {sender}, Target: {target}, Answer: {answer}, websocket: {target_websocket}")
    await target_websocket.send(json.dumps(data))


async def handle_ice_candidate(websocket, data):
    """
    Handle an ICE candidate from a client.
    """
    sender = data.get("from")
    target = data.get("target")
    candidate_dict = data.get("payload")

    # logging.info(f"ICE candidate from {sender} for {target}")
    
    # if "candidate" not in candidate_dict or "sdpMid" not in candidate_dict or "sdpMLineIndex" not in candidate_dict:
    #     print("Error: Invalid candidate structure", candidate_dict)
    #     return

    # if sender in clients and clients[sender]["pc"]:
    #     pc = clients[sender]["pc"]
    #     # Add the candidate to the peer connection.
    #     candidate_data = parse_candidate(candidate_dict["candidate"])
        
    #     candidate = RTCIceCandidate(
    #         foundation=candidate_data.get("foundation", ""),  
    #         component=candidate_data.get("component", 1),
    #         protocol=candidate_data.get("protocol", "udp"),
    #         priority=candidate_data.get("priority", 0),
    #         ip=candidate_data.get("ip", ""),
    #         port=candidate_data.get("port", 0),
    #         type=candidate_data.get("type", ""),
    #         sdpMid=candidate_dict["sdpMid"],
    #         sdpMLineIndex=candidate_dict["sdpMLineIndex"]
    #     )
    #     await pc.addIceCandidate(candidate)
    # else:
    #     await websocket.send(json.dumps({"type": "error", "message": "Peer connection not found."}))

    logging.info(f"Relaying ICE candidate from {sender} to {target}")

    if target not in clients:
        await websocket.send(json.dumps({"type": "error", "message": "Target not connected."}))
        return

    target_websocket = clients[target]["ws"]
    await target_websocket.send(json.dumps(data))


def parse_candidate(candidate_str):
    candidate_parts = candidate_str.split()
    
    candidate_data = {
        "foundation": candidate_parts[0],
        "component": int(candidate_parts[1]),
        "protocol": candidate_parts[2],
        "priority": int(candidate_parts[3]),
        "ip": candidate_parts[4],
        "port": int(candidate_parts[5]),
        "type": None,  # To be set later
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
