import asyncio
import json
import logging
import os
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
import cv2

from mpc001.pipelines.pipeline import InferencePipeline
from .state import clients  # clients is assumed to be a dict holding websocket and peer connection info
# from .lip_reader import LipReadingPipeline
# from .mouth_detection import MouthDetector


class WebRTCServer:
    """
    Encapsulates a server-side WebRTC connection.
    Creates an RTCPeerConnection, registers event handlers, and manages the SDP offer/answer exchange.
    """
    def __init__(self, websocket, sender):
        self.websocket = websocket
        self.sender = sender
        self.pc = RTCPeerConnection()
        # Store the connection for later ICE/answer handling.
        clients[sender]["pc"] = self.pc

        # Register event handlers
        self.pc.on("track", self.on_track)
        # self.pc.on("icecandidate", self.on_icecandidate)  # ICE trickle isn't implemented as of the time of writing in aiortc.

        # # Initialize the lip reading pipeline (update the model_path as needed).
        # print(f"Does model exist? {os.path.exists('models/final_model.keras')}")
        # self.pipeline = LipReadingPipeline(model_path="models/cp-0029.keras")

        # self.detector = MouthDetector()

        self.pipeline = InferencePipeline(
            config_filename="mpc001/configs/LRS3_V_WER19.1.ini",
            detector="mediapipe",
            face_track=True,
        )

    async def on_track(self, track):
        logging.info(f"Received {track.kind} track from {self.sender}")
        track.onended = lambda: logging.info(f"{track.kind} track from {self.sender} ended")

        if track.kind == "video":
            self.video_writer = None  # Initialize if you decide to record video.
            frame_buffer = []         # Buffer to accumulate frames.
            buffer_size = 30          # Adjust this to the number of frames you want per inference run.
            # try:
            while True:
                # Receive a frame from the video track.
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                frame_buffer.append(img)

                # Once we've accumulated enough frames, run inference.
                if len(frame_buffer) >= buffer_size:
                    # Offload inference to a thread so as not to block the event loop.
                    # forward_buffer() is the custom method that processes the list of frames.
                    prediction = await asyncio.to_thread(self.pipeline.forward_buffer, frame_buffer)
                    if prediction is not None:
                        logging.info(f"Model Prediction: {prediction}")
                        # Here you can send the prediction back to the client or process it further.
                    else:
                        logging.debug("Insufficient data for a complete prediction, accumulating frames...")
                    # Clear the buffer (or implement a sliding window if desired).
                    frame_buffer = []

                # Yield control to the event loop.
                await asyncio.sleep(0)
            # except Exception as e:
            #     logging.error(f"Error processing video track from {self.sender}: {e}")
            # finally:
            #     # Release the VideoWriter when done
            #     if self.video_writer is not None:
            #         self.video_writer.release()
            #         logging.info(f"Released video writer for {self.sender}")
        elif track.kind == "audio":
            # Here you could pass the audio frames to a playback library (e.g., PyAudio)
            logging.info(f"Received an audio track from {self.sender}")

    async def on_icecandidate(self, candidate):
        if candidate is None:
            logging.info(f"No more ICE candidates for {self.sender}")
        else:
            print(f"ICE CANDIDATE GENERATED: {candidate}")
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
            await self.websocket.send(json.dumps(message))

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
        print(f"ANSWER GENERATED: {answer}")

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


# Message handling functions

async def handle_offer(websocket, data):
    """
    Handle an SDP offer from a client.
    Data should include "from", "target", and "payload" (the SDP).
    """
    sender = data.get("from")
    target = data.get("target")
    logging.info("Received offer from %s to %s", sender, target)

    if target == "server":
        await handle_server_offer(websocket, data)
        return

    if sender not in clients:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "Sender not authenticated."
        }))
        return

    # Relay offer to the target client
    target_websocket = clients[target]["ws"]
    await target_websocket.send(json.dumps(data))

async def handle_answer(websocket, data):
    """
    Handle an SDP answer from a client.
    """
    sender = data.get("from")
    target = data.get("target")
    logging.info("Relaying answer from %s to %s", sender, target)

    if target == "server":
        await handle_server_answer(websocket, data)
        return

    if target not in clients:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "Target not connected."
        }))
        return

    target_websocket = clients[target]["ws"]
    await target_websocket.send(json.dumps(data))

async def handle_ice_candidate(websocket, data):
    """
    Handle an ICE candidate from a client.
    """
    sender = data.get("from")
    target = data.get("target")
    logging.info("Relaying ICE candidate from %s to %s", sender, target)

    if target == "server":
        await handle_server_ice_candidate(websocket, data)
        return

    if target not in clients:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "Target not connected."
        }))
        return

    target_websocket = clients[target]["ws"]
    await target_websocket.send(json.dumps(data))

async def handle_server_offer(websocket, data):
    """
    Handle an SDP offer from a client that is intended for the server.
    """
    sender = data.get("from")
    offer_data = data.get("payload")
    logging.info("Handling server offer from %s", sender)

    server_connection = WebRTCServer(websocket, sender)
    response = await server_connection.handle_offer(offer_data)
    await websocket.send(json.dumps(response))
    logging.info("Server sent answer to %s", sender)

async def handle_server_answer(websocket, data):
    """
    Handle an SDP answer from a client for a server-initiated connection.
    """
    sender = data.get("from")
    answer_data = data.get("payload")
    logging.info("Handling server answer from %s", sender)

    if sender not in clients or "pc" not in clients[sender]:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "No active server connection for sender."
        }))
        return

    pc = clients[sender]["pc"]
    answer = RTCSessionDescription(sdp=answer_data["sdp"], type=answer_data["type"])
    await pc.setRemoteDescription(answer)

async def handle_server_ice_candidate(websocket, data):
    """
    Handle an ICE candidate intended for the server's peer connection.
    """
    sender = data.get("from")
    candidate_dict = data.get("payload")
    logging.info("Handling server ICE candidate from %s", sender)

    if sender not in clients or "pc" not in clients[sender]:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "No active server connection for sender."
        }))
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
        # generation=candidate_data["generation"],
        # ufrag=candidate_data["ufrag"],
        # network_id=candidate_data["network_id"],
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
