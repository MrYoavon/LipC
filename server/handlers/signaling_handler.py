# handlers/signaling_handler.py
import asyncio
import logging
import av
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription

from constants import TARGET_CHUNK_SIZE
from database.call_history import start_call, append_line, finish_call
from services import thread_executors
from services.crypto_utils import send_error_message, structure_encrypt_send_message
from services.jwt_utils import verify_jwt_in_message
from services.lip_reading.vosk_helper import VoskRecognizer, convert_audio_frame_to_pcm
from services.state import clients, pending_calls, call_key


class WebRTCServer:
    """
    Server-side WebRTC connection handler:
    - Manages peer connection events
    - Handles video lip-reading and audio Vosk transcription
    - Records call history to the database
    """

    def __init__(self, websocket, sender, aes_key, target=None, model_type="lip"):
        self.websocket = websocket
        self.sender = sender
        self.aes_key = aes_key
        self.target = target  # Save the call partner's user_id
        self.model_type = model_type
        self.pc = RTCPeerConnection()
        clients[sender]["pc"] = self.pc

        self.recognizer = VoskRecognizer(sample_rate=16000)  # Vosk
        # Buffer for audio chunks
        self.pcm_buffer = bytearray()
        self.buffered_ms = 0.0
        self.sample_rate = self.recognizer.sample_rate

        # Call record ID
        self.call_id = None

        # Register event handlers
        self.pc.on("track", self._on_track)
        self.pc.on("connectionstatechange", self._on_pc_state)

    async def _on_track(self, track):
        """Dispatch incoming media tracks to appropriate processors."""
        logging.info(f"Received {track.kind} track from {self.sender}")
        track.onended = lambda: logging.info(
            f"{track.kind} track from {self.sender} ended")

        # Ensure call_id is set from pending_calls
        await self._ensure_call_id()

        if track.kind == "video" and self.model_type == "lip":
            await self._process_video(track)
        elif track.kind == "audio" and self.model_type == "vosk":
            await self._process_audio(track)

    async def _ensure_call_id(self):
        """Retrieve call ID from pending_calls if not yet set."""
        while self.call_id is None:
            key = call_key(self.sender, self.target)
            info = pending_calls.get(key, {})
            self.call_id = info.get("call_id")
            if self.call_id is None:
                await asyncio.sleep(0.1)

    async def _process_video(self, track):
        """Process video frames for lip-reading predictions."""
        logging.info(f"Starting lip-reading video for {self.sender}")
        loop = asyncio.get_event_loop()

        while True:
            try:
                frame = await track.recv()
            except Exception as exc:
                logging.error(f"Error receiving video frame: {exc}")
                break

            frame_array = frame.to_ndarray(format="bgr24")
            prediction = await loop.run_in_executor(
                thread_executors.get_tf_executor(),
                thread_executors.lip_read,
                frame_array
            )

            if not prediction:
                continue

            append_line(self.call_id, speaker_id=self.sender,
                        text=prediction, source="lip")
            logging.info(f"Lip prediction for {self.sender}: {prediction}")

            await self._relay_message(
                msg_type="lip_reading_prediction",
                payload={"from": self.sender, "prediction": prediction}
            )

    async def _process_audio(self, track):
        """Accumulate audio frames and send chunks to Vosk for transcription."""
        logging.info(f"Starting Vosk audio for {self.sender}")
        loop = asyncio.get_event_loop()

        while True:
            try:
                frame: av.AudioFrame = await track.recv()
            except Exception as exc:
                logging.error(f"Error receiving audio frame: {exc}")
                break

            pcm = convert_audio_frame_to_pcm(frame)
            self.pcm_buffer.extend(pcm)
            samples = len(pcm) / 2
            self.buffered_ms += (samples / self.sample_rate) * 1000

            if self.buffered_ms < TARGET_CHUNK_SIZE:
                continue

            chunk = bytes(self.pcm_buffer)
            self.pcm_buffer.clear()
            self.buffered_ms = 0.0

            duration_ms = len(chunk) / 2 / self.sample_rate * 1000
            logging.debug(f"Feeding Vosk {duration_ms:.1f} ms of audio")

            result = await loop.run_in_executor(
                thread_executors.get_speech_executor(),
                thread_executors.vosk_transcribe,
                self.recognizer,
                chunk,
            )
            if not result:
                continue

            text = result.get("text") or result.get("partial")
            result_type = "final" if "text" in result else "partial"
            if not text:
                continue

            logging.info(
                f"Vosk {result_type} result for {self.sender}: {text}")

            if result_type == "final":
                append_line(self.call_id, speaker_id=self.sender,
                            text=text, source="vosk")

            await self._relay_message(
                msg_type="lip_reading_prediction",
                payload={"from": self.sender, "prediction": text}
            )

        final = self.recognizer.get_final_result()
        logging.info(f"Vosk final result for {self.sender}: {final}")

    async def _relay_message(self, msg_type, payload):
        """Encrypt and send a message to the call partner."""
        partner = self.target
        if not partner or partner not in clients:
            return

        ws = clients[partner]["ws"]
        aes = clients[partner].get("aes_key", self.aes_key)
        await structure_encrypt_send_message(
            websocket=ws,
            aes_key=aes,
            msg_type=msg_type,
            success=True,
            payload=payload
        )

    async def handle_offer(self, offer_data):
        """Generate an SDP answer for an incoming offer."""
        sdp = self._strip_rtx(offer_data["sdp"])
        offer = RTCSessionDescription(sdp=sdp, type=offer_data["type"])
        await self.pc.setRemoteDescription(offer)

        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        logging.info(f"Generated answer for {self.sender}")

        return {"from": "server", "target": self.sender, "answer": {"sdp": answer.sdp, "type": answer.type}}

    def _strip_rtx(self, sdp: str) -> str:
        """Remove RTX codec entries from an SDP string."""
        lines = sdp.splitlines()
        filtered, rtx = [], set()

        for line in lines:
            if line.startswith("a=rtpmap") and "rtx/90000" in line:
                rtx.add(line.split()[0].split(":")[1])
                continue
            filtered.append(line)

        result = []
        for line in filtered:
            if any(line.startswith(prefix) and pt in line for prefix in ("a=fmtp:", "a=rtcp-fb:") for pt in rtx):
                continue
            result.append(line)

        return "\r\n".join(result) + "\r\n"

    async def _on_pc_state(self):
        state = self.pc.connectionState
        logging.info(f"PC state for {self.sender}: {state}")
        if state in ("closed", "failed"):
            await self._terminate_call()
        elif state == "disconnected":
            await asyncio.sleep(5)
            if self.pc.connectionState == "disconnected":
                await self._terminate_call()

    async def _terminate_call(self):
        """Finalize call record and clean up peer connection."""
        if self.call_id:
            key = call_key(self.sender, self.target)
            info = pending_calls.get(key)
            if info and not info.get("ended"):
                await asyncio.to_thread(finish_call, self.call_id)
                info["ended"] = True
            pending_calls.pop(key, None)

        await self.pc.close()
        logging.info(f"Call {self.call_id} ended for {self.sender}")


# ----- Top-level message handling functions -----

async def handle_offer(websocket, data, aes_key):
    """Relay or process an SDP offer message from a client."""
    user_id = data.get("user_id")
    payload = data.get("payload", {})
    sender = payload.get("from")
    target = payload.get("target")

    valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        return await send_error_message(
            websocket,
            aes_key,
            "offer",
            error_code=err.get("error"),
            error_message=err.get("message")
        )

    logging.info(f"Offer from {sender} to {target}")

    if target == "server":
        return await handle_server_offer(websocket, data, aes_key)

    if sender not in clients or target not in clients:
        return await send_error_message(
            websocket,
            aes_key,
            "offer",
            error_code="NOT_CONNECTED",
            error_message="Client not connected."
        )

    # Track pending call without DB insert yet
    key = call_key(sender, target)
    pending_calls.setdefault(
        key, {"caller": sender, "callee": target, "call_id": None, "ended": False})

    await structure_encrypt_send_message(
        websocket=clients[target]["ws"],
        aes_key=clients[target].get("aes_key", aes_key),
        msg_type="offer",
        success=True,
        payload=payload
    )


async def handle_answer(websocket, data, aes_key):
    """Relay or process an SDP answer message from a client."""
    user_id = data.get("user_id")
    payload = data.get("payload", {})
    sender = payload.get("from")
    target = payload.get("target")

    valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        return await send_error_message(
            websocket,
            aes_key,
            "answer",
            error_code=err.get("error"),
            error_message=err.get("message")
        )

    logging.info(f"Answer from {sender} to {target}")

    if target == "server":
        return await handle_server_answer(websocket, data, aes_key)

    if target not in clients:
        return await send_error_message(
            websocket,
            aes_key,
            "answer",
            error_code="TARGET_NOT_CONNECTED",
            error_message="Target not connected."
        )

    key = call_key(sender, target)
    info = pending_calls.get(key)
    if info and info.get("call_id") is None:
        info["call_id"] = start_call(
            info["caller"], info["callee"])  # Single DB record

    await structure_encrypt_send_message(
        websocket=clients[target]["ws"],
        aes_key=clients[target].get("aes_key", aes_key),
        msg_type="answer",
        success=True,
        payload=payload
    )


async def handle_ice_candidate(websocket, data, aes_key):
    """Relay an ICE candidate between peers or to server handler."""
    user_id = data.get("user_id")
    payload = data.get("payload", {})
    sender = payload.get("from")
    target = payload.get("target")

    valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        return await send_error_message(
            websocket,
            aes_key,
            "ice_candidate",
            error_code=err.get("error"),
            error_message=err.get("message")
        )

    logging.info(f"ICE candidate from {sender} to {target}")

    if target == "server":
        return await handle_server_ice_candidate(websocket, data, aes_key)

    if target not in clients:
        return await send_error_message(
            websocket,
            aes_key,
            "ice_candidate",
            error_code="TARGET_NOT_CONNECTED",
            error_message="Target not connected."
        )

    await structure_encrypt_send_message(
        websocket=clients[target]["ws"],
        aes_key=clients[target].get("aes_key", aes_key),
        msg_type="ice_candidate",
        success=True,
        payload=payload
    )


# ----- Server-directed handlers -----


async def handle_server_offer(websocket, data, aes_key):
    """Handle a client offer intended for the server."""
    user_id = data.get("user_id")
    payload = data.get("payload", {})
    sender = payload.get("from")
    other_user = payload.get("other_user")
    offer = payload.get("offer")

    valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        return await send_error_message(
            websocket,
            aes_key,
            "server_offer",
            error_code=err.get("error"),
            error_message=err.get("message")
        )

    logging.info(f"Server-side offer from {sender} for {other_user}")

    model_type = clients.get(sender, {}).get("model_type", "lip")
    server_conn = WebRTCServer(
        websocket, sender, aes_key, target=other_user, model_type=model_type)
    response = await server_conn.handle_offer(offer)

    await structure_encrypt_send_message(
        websocket=websocket,
        aes_key=aes_key,
        msg_type="answer",
        success=True,
        payload=response
    )
    logging.info(f"Sent server answer to {sender}")


async def handle_server_answer(websocket, data, aes_key):
    """Handle a client answer to a server-initiated offer."""
    user_id = data.get("user_id")
    payload = data.get("payload", {})
    sender = payload.get("from")
    answer = payload.get("answer")

    valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        return await send_error_message(websocket, aes_key, "answer", err)

    logging.info(f"Server-side answer from {sender}")

    client = clients.get(sender, {})
    pc = client.get("pc")
    if not pc:
        return await send_error_message(
            websocket,
            aes_key,
            "answer",
            error_code="NO_ACTIVE_CONNECTION",
            error_message="No active server connection."
        )

    desc = RTCSessionDescription(
        sdp=answer.get("sdp"), type=answer.get("type"))
    await pc.setRemoteDescription(desc)


async def handle_server_ice_candidate(websocket, data, aes_key):
    """Handle ICE candidate for a server-side peer connection."""
    user_id = data.get("user_id")
    payload = data.get("payload", {})
    sender = payload.get("from")
    candidate_dict = payload.get("candidate", {})

    valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
    if not valid:
        return await send_error_message(websocket, aes_key, "ice_candidate", err)

    logging.info(f"Server-side ICE candidate from {sender}")

    client = clients.get(sender, {})
    pc = client.get("pc")
    if not pc:
        return await send_error_message(
            websocket,
            aes_key,
            "ice_candidate",
            error_code="NO_ACTIVE_CONNECTION",
            error_message="No active server connection."
        )

    candidate_str = candidate_dict.get("candidate")
    data = parse_candidate(candidate_str)
    cand = RTCIceCandidate(
        foundation=data["foundation"],
        component=data["component"],
        protocol=data["protocol"],
        priority=data["priority"],
        ip=data["ip"],
        port=data["port"],
        type=data.get("type"),
        tcpType=data.get("tcpType"),
        sdpMid=candidate_dict.get("sdpMid"),
        sdpMLineIndex=candidate_dict.get("sdpMLineIndex")
    )
    await pc.addIceCandidate(cand)


# ----- Utility Functions -----

def parse_candidate(candidate_str: str) -> dict:
    """Convert SDP candidate string into a dict for RTCIceCandidate."""
    parts = candidate_str.split()
    data = {
        "foundation": parts[0],
        "component": int(parts[1]),
        "protocol": parts[2],
        "priority": int(parts[3]),
        "ip": parts[4],
        "port": int(parts[5]),
        "type": None,
        "tcpType": None,
        "generation": None,
        "ufrag": None,
        "network_id": None,
    }
    i = 6
    while i < len(parts):
        key = parts[i]
        if key == "typ":
            data["type"] = parts[i + 1]
            i += 2
        elif key == "tcptype":
            data["tcpType"] = parts[i + 1]
            i += 2
        elif key == "generation":
            data["generation"] = int(parts[i + 1])
            i += 2
        elif key == "ufrag":
            data["ufrag"] = parts[i + 1]
            i += 2
        elif key == "network-id":
            data["network_id"] = int(parts[i + 1])
            i += 2
        else:
            i += 1  # Skip unknown keys
    return data
