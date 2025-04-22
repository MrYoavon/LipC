import asyncio
import logging
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription

# from constants import VOSK_MODEL_PATH
from services.state import clients, pending_calls, call_key
from services.crypto_utils import structure_encrypt_send_message
from services.jwt_utils import verify_jwt_in_message
from database.call_history import start_call, append_line, finish_call
from services.lip_reading.lip_reader import LipReadingPipeline, get_lip_model
# from services.lip_reading.realtime_stt_helper import AudioTranscriber
# from services.lip_reading.vosk_helper import (
#     VoskRecognizer,
#     convert_audio_frame_to_pcm
# )


class WebRTCServer:
    """
    Encapsulates a server-side WebRTC connection.
    Creates an RTCPeerConnection, registers event handlers, and manages the SDP offer/answer exchange.
    """

    def __init__(self, websocket, sender, aes_key, target=None):
        self.websocket = websocket
        self.sender = sender
        self.aes_key = aes_key
        self.target = target  # Save the call partner's user_id
        self.pc = RTCPeerConnection()
        # Store the connection for later ICE/answer handling.
        clients[sender]["pc"] = self.pc

        # Register event handlers
        self.pc.on("track", self.on_track)
        self.pc.on("connectionstatechange", self._on_pc_state)

        self.call_id = None

        # self.audio_transcriber = AudioTranscriber(model="tiny")  # RealtimeSTT
        # self.recognizer = VoskRecognizer(sample_rate=48000)  # Vosk

    async def on_track(self, track):
        logging.info(f"Received {track.kind} track from {self.sender}")
        track.onended = lambda: logging.info(
            f"{track.kind} track from {self.sender} ended")

        if track.kind == "video":
            logging.info(
                f"Starting video processing for lip reading for {self.sender}")
            shared_model = await get_lip_model()
            lip_reader_pipeline = LipReadingPipeline(shared_model)
            key = call_key(self.sender, self.target)
            self.call_id = pending_calls.get(key, {}).get("call_id")

            while True:
                try:
                    # Receive a frame from the video track (this is asynchronous)
                    frame = await track.recv()
                except Exception as e:
                    logging.error(f"Error receiving video frame: {e}")
                    break

                # Convert the frame to a numpy array
                frame_array = frame.to_ndarray(format="bgr24")

                # Process the frame.
                # Since inference might block, I'll run it in a separate thread:
                prediction = await asyncio.to_thread(
                    lip_reader_pipeline.process_frame, frame_array
                )

                if prediction is None:
                    continue

                append_line(
                    self.call_id,
                    speaker_id=self.sender,
                    text=prediction,
                    source="lip"
                )
                logging.info(
                    f"Lip reading prediction for {self.sender}: {prediction}")

                call_partner = self.target
                if call_partner and call_partner in clients:
                    target_ws = clients[call_partner]["ws"]
                    target_aes_key = clients[call_partner].get(
                        "aes_key", self.aes_key)
                    await structure_encrypt_send_message(
                        websocket=target_ws,
                        aes_key=target_aes_key,
                        msg_type="lip_reading_prediction",
                        success=True,
                        payload={
                            "from": self.sender,
                            "prediction": prediction
                        }
                    )

        elif track.kind == "audio":
            logging.info(f"Received an audio track from {self.sender}")

            # while True:
            #     try:
            #         frame = await track.recv()
            #     except Exception as e:
            #         logging.error(f"Error receiving audio frame: {e}")
            #         break

            #     # # Transcribe the received audio frame asynchronously with RealtimeSTT.
            #     # transcription = await self.audio_transcriber.transcribe_audio_frame(frame)
            #     # if transcription:
            #     #     logging.info(
            #     #         f"Audio transcription for {self.sender}: {transcription}")

            #     # Trancribe the received audio frame asynchronously with Vosk.
            #     # Convert the frame to PCM bytes.
            #     pcm_bytes = convert_audio_frame_to_pcm(frame)
            #     # Process the PCM bytes with Vosk recognizer.
            #     result = await asyncio.to_thread(self.recognizer.process_audio_chunk, pcm_bytes)
            #     if result:
            #         logging.info(
            #             f"Vosk final result {self.sender}: {result}")

            # logging.info(
            #     f"Vosk final final result {self.sender}: {self.recognizer.get_final_result()}")

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
            "from": "server",
            "target": self.sender,
            "answer": {
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

    async def _on_pc_state(self):
        state = self.pc.connectionState
        logging.info(f"Peer connection state changed: {state}")
        if state in ("closed", "failed"):
            await self._end_call()
        elif state == "disconnected":
            # give ICE restart a chance
            await asyncio.sleep(5)
            if self.pc.connectionState == "disconnected":
                await self._end_call()

    async def _end_call(self):
        if self.call_id:
            key = call_key(self.sender, self.target)
            info = pending_calls.get(key)
            if info and not info["ended"]:
                await asyncio.to_thread(finish_call, self.call_id)
                info["ended"] = True   # mark finished
            if info and info["ended"]:
                pending_calls.pop(key, None)
        await self.pc.close()
        logging.info(f"Call {self.call_id} ended for {self.sender}")


# ----- Message handling functions follow. These are called by the main handler -----

async def handle_offer(websocket, data, aes_key):
    """
    Handle an SDP offer from a client.
    Data should include "from", "target", and "offer" inside the payload.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    target = payload.get("target")

    # Verify JWT for the sender.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for sender {sender}: {result}")
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="offer",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    logging.info(f"Received offer from {sender} to {target}")

    if target == "server":
        await handle_server_offer(websocket, data, aes_key)
        return

    if sender not in clients:
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="offer",
            success=False,
            error_code="SENDER_NOT_AUTHENTICATED",
            error_message="Sender not authenticated."
        )
        return

    # Relay offer to the target.
    if target not in clients:
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="offer",
            success=False,
            error_code="TARGET_NOT_CONNECTED",
            error_message="Target not connected."
        )
        return

    # remember who started the call; no DB write yet
    key = call_key(sender, target)
    pending_calls.setdefault(
        key,
        {"caller": sender, "callee": target, "call_id": None, "ended": False}
    )
    target_ws = clients[target]["ws"]
    target_aes_key = clients[target].get("aes_key", aes_key)
    await structure_encrypt_send_message(
        websocket=target_ws,
        aes_key=target_aes_key,
        msg_type="offer",
        success=True,
        payload=payload
    )


async def handle_answer(websocket, data, aes_key):
    """
    Handle an SDP answer from a client.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    target = payload.get("target")

    # Verify JWT for the sender.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for sender {sender}: {result}")
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="answer",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    logging.info(f"Relaying answer from {sender} to {target}")

    if target == "server":
        await handle_server_answer(websocket, data, aes_key)
        return

    if target not in clients:
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="answer",
            success=False,
            error_code="TARGET_NOT_CONNECTED",
            error_message="Target not connected."
        )
        return

    key = call_key(sender, target)
    info = pending_calls.get(key)

    if info and info["call_id"] is None:
        # Confirm who is caller / callee
        caller_id = info["caller"]
        callee_id = info["callee"]

        # 1. INSERT ONE RECORD
        call_id = start_call(caller_id, callee_id)
        info["call_id"] = call_id

    target_ws = clients[target]["ws"]
    target_aes_key = clients[target].get("aes_key", aes_key)
    await structure_encrypt_send_message(
        websocket=target_ws,
        aes_key=target_aes_key,
        msg_type="answer",
        success=True,
        payload=payload
    )


async def handle_ice_candidate(websocket, data, aes_key):
    """
    Handle an ICE candidate from a client.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    target = payload.get("target")

    # Verify JWT for the sender.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for sender {sender}: {result}")
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="ice_candidate",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    logging.info(f"Relaying ICE candidate from {sender} to {target}")

    if target == "server":
        await handle_server_ice_candidate(websocket, data, aes_key)
        return

    if target not in clients:
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="ice_candidate",
            success=False,
            error_code="TARGET_NOT_CONNECTED",
            error_message="Target not connected."
        )
        return

    target_ws = clients[target]["ws"]
    target_aes_key = clients[target].get("aes_key", aes_key)
    await structure_encrypt_send_message(
        websocket=target_ws,
        aes_key=target_aes_key,
        msg_type="ice_candidate",
        success=True,
        payload=payload
    )


async def handle_server_offer(websocket, data, aes_key):
    """
    Handle an SDP offer from a client that is intended for the server.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    other_user = payload.get("other_user")
    offer_data = payload.get("offer")

    # Verify JWT for the sender.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for sender {sender}: {result}")
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="server_offer",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    logging.info(f"Handling server offer from {sender}")

    server_connection = WebRTCServer(websocket, sender, aes_key, other_user)
    response = await server_connection.handle_offer(offer_data)
    await structure_encrypt_send_message(
        websocket,
        aes_key,
        msg_type="answer",
        success=True,
        payload=response
    )
    logging.info(f"Server sent answer to {sender}")


async def handle_server_answer(websocket, data, aes_key):
    """
    Handle an SDP answer from a client for a server-initiated connection.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    answer_data = payload.get("answer")

    # Verify JWT for the sender.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for sender {sender}: {result}")
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="answer",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    logging.info(f"Handling server answer from {sender}")

    if sender not in clients or "pc" not in clients[sender]:
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="answer",
            success=False,
            error_code="NO_ACTIVE_CONNECTION",
            error_message="No active server connection for sender."
        )
        return

    pc = clients[sender]["pc"]
    answer = RTCSessionDescription(
        sdp=answer_data["sdp"], type=answer_data["type"])
    await pc.setRemoteDescription(answer)


async def handle_server_ice_candidate(websocket, data, aes_key):
    """
    Handle an ICE candidate intended for the server's peer connection.
    """
    user_id = data.get("user_id")
    payload = data.get("payload")
    sender = payload.get("from")
    candidate_dict = payload.get("candidate")

    # Verify JWT for the sender.
    valid, result = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        logging.warning(f"Invalid JWT for sender {sender}: {result}")
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="ice_candidate",
            success=False,
            error_code=result.get("error", "INVALID_JWT"),
            error_message=result.get("message", "JWT verification failed.")
        )
        return

    logging.info(f"Handling server ICE candidate from {sender}")

    if sender not in clients or "pc" not in clients[sender]:
        await structure_encrypt_send_message(
            websocket,
            aes_key,
            msg_type="ice_candidate",
            success=False,
            error_code="NO_ACTIVE_CONNECTION",
            error_message="No active server connection for sender."
        )
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
