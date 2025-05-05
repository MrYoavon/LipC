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


logger = logging.getLogger(__name__)


class WebRTCServer:
    """
    Server-side WebRTC connection handler.

    Manages peer connection events, media track processing (video lip-reading or audio transcription),
    and call lifecycle including database recording and relaying messages between peers.
    """

    def __init__(self, websocket, sender: str, aes_key: bytes, target: str = None, model_type: str = "lip"):
        """
        Initialize a WebRTCServer instance for a given call session.

        Args:
            websocket: WebSocket connection for signaling and relayed messages.
            sender (str): User ID of the initiating client.
            aes_key (bytes): AES key for encrypting messages.
            target (str, optional): User ID of the call partner. Defaults to None.
            model_type (str, optional): Inference mode, either 'lip' or 'vosk'. Defaults to "lip".
        """
        self.websocket = websocket
        self.sender = sender
        self.aes_key = aes_key
        self.target = target  # Save the call partner's user_id
        self.model_type = model_type
        self.pc = RTCPeerConnection()
        clients[sender]["pc"] = self.pc

        # Setup recognizer for audio transcription if needed
        self.recognizer = VoskRecognizer(sample_rate=16000)
        self.pcm_buffer = bytearray()
        self.buffered_ms = 0.0
        self.sample_rate = self.recognizer.sample_rate

        self.call_id = None  # Will be set once call is established

        # Register event handlers on the RTCPeerConnection
        self.pc.on("track", self._on_track)
        self.pc.on("connectionstatechange", self._on_pc_state)

    async def _on_track(self, track):
        """
        Dispatch incoming media tracks to the appropriate processor.

        Args:
            track: The incoming MediaStreamTrack (video or audio).
        """
        logger.info(f"Received {track.kind} track from {self.sender}")
        track.onended = lambda: logger.info(
            f"{track.kind} track from {self.sender} ended")

        # Ensure the call_id is retrieved before processing frames
        await self._ensure_call_id()

        if track.kind == "video" and self.model_type == "lip":
            await self._process_video(track)
        elif track.kind == "audio" and self.model_type == "vosk":
            await self._process_audio(track)

    async def _ensure_call_id(self):
        """
        Wait until the call_id is set in pending_calls for this session.

        Polls pending_calls for an entry matching sender and target to obtain call_id.
        """
        while self.call_id is None:
            key = call_key(self.sender, self.target)
            info = pending_calls.get(key, {})
            self.call_id = info.get("call_id")
            if self.call_id is None:
                await asyncio.sleep(0.1)

    async def _process_video(self, track):
        """
        Process video frames for lip-reading predictions and record them.

        Args:
            track: Video MediaStreamTrack.
        """
        logger.info(f"Starting lip-reading video for {self.sender}")
        loop = asyncio.get_event_loop()

        while True:
            try:
                frame = await track.recv()
            except Exception as exc:
                logger.error(f"Error receiving video frame: {exc}")
                break

            frame_array = frame.to_ndarray(format="bgr24")
            # Run inference in TensorFlow executor
            prediction = await loop.run_in_executor(
                thread_executors.get_tf_executor(),
                thread_executors.lip_read,
                frame_array
            )

            if not prediction:
                continue

            # Save prediction to database
            await append_line(self.call_id, speaker_id=self.sender,
                              text=prediction, source="lip")
            logger.info(f"Lip prediction for {self.sender}: {prediction}")

            # Relay prediction to partner
            await self._relay_message(
                msg_type="lip_reading_prediction",
                payload={"from": self.sender, "prediction": prediction}
            )

    async def _process_audio(self, track):
        """
        Accumulate and send audio frames to Vosk for transcription.

        Args:
            track: Audio MediaStreamTrack.
        """
        logger.info(f"Starting Vosk audio for {self.sender}")
        loop = asyncio.get_event_loop()

        while True:
            try:
                frame: av.AudioFrame = await track.recv()
            except Exception as exc:
                logger.error(f"Error receiving audio frame: {exc}")
                break

            # Convert frame to PCM and buffer
            pcm = convert_audio_frame_to_pcm(frame)
            self.pcm_buffer.extend(pcm)
            samples = len(pcm) / 2
            self.buffered_ms += (samples / self.sample_rate) * 1000

            # Process chunks when enough audio is buffered
            if self.buffered_ms >= TARGET_CHUNK_SIZE:
                chunk = bytes(self.pcm_buffer)
                self.pcm_buffer.clear()
                self.buffered_ms = 0.0

                duration_ms = len(chunk) / 2 / self.sample_rate * 1000
                logger.debug(f"Feeding Vosk {duration_ms:.1f} ms of audio")

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

                logger.info(
                    f"Vosk {result_type} result for {self.sender}: {text}")

                if result_type == "final":
                    await append_line(self.call_id, speaker_id=self.sender,
                                      text=text, source="vosk")

                await self._relay_message(
                    msg_type="lip_reading_prediction",
                    payload={"from": self.sender, "prediction": text}
                )

        # After track ends, fetch and log final Vosk result
        final = self.recognizer.get_final_result()
        logger.info(f"Vosk final result for {self.sender}: {final}")

    async def _relay_message(self, msg_type, payload):
        """
        Encrypt and send a signaling message to the call partner.

        Args:
            msg_type (str): The type of message to send.
            payload (dict): The message payload.
        """
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
        """
        Handle an SDP offer by generating and returning an answer.

        Args:
            offer_data (dict): Contains 'sdp' and 'type' fields from client.

        Returns:
            dict: A dict with server's SDP answer for signaling back to client.
        """
        sdp = self._strip_rtx(offer_data["sdp"])
        offer = RTCSessionDescription(sdp=sdp, type=offer_data["type"])
        await self.pc.setRemoteDescription(offer)

        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        logger.info(f"Generated answer for {self.sender}")

        return {"from": "server", "target": self.sender, "answer": {"sdp": answer.sdp, "type": answer.type}}

    def _strip_rtx(self, sdp: str) -> str:
        """
        Remove RTX codec entries from SDP to improve interoperability.

        Args:
            sdp (str): Original session description string.

        Returns:
            str: Filtered SDP with RTX entries removed.
        """
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
        """
        Handle changes in peer connection state and terminate call if needed.
        """
        state = self.pc.connectionState
        logger.info(f"PC state for {self.sender}: {state}")
        if state in ("closed", "failed"):
            await self._terminate_call()
        elif state == "disconnected":
            await asyncio.sleep(5)
            if self.pc.connectionState == "disconnected":
                await self._terminate_call()

    async def _terminate_call(self):
        """
        Finalize call recording, update database, and clean up resources.
        """
        if self.call_id:
            key = call_key(self.sender, self.target)
            info = pending_calls.get(key)
            if info and not info.get("ended"):
                await finish_call(self.call_id)
                info["ended"] = True
            pending_calls.pop(key, None)

        await self.pc.close()
        logger.info(f"Call {self.call_id} ended for {self.sender}")


# ----- Top-level message handling functions -----

class SignalingHandler:
    """
    Handles incoming signaling messages for WebRTC connections.
    """

    async def handle_offer(self, websocket, data, aes_key):
        """
        Relay or process a client's SDP offer message.

        Args:
            websocket: WebSocket connection for signaling.
            data (dict): Parsed message containing 'user_id', 'payload', and 'jwt'.
            aes_key (bytes): AES encryption key.
        """
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

        logger.info(f"Offer from {sender} to {target}")

        if target == "server":
            return await self.handle_server_offer(websocket, data, aes_key)

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

    async def handle_answer(self, websocket, data, aes_key):
        """
        Relay or process a client's SDP answer message.

        Args:
            websocket: WebSocket connection.
            data (dict): Parsed message with 'user_id', 'jwt', and 'payload'.
            aes_key (bytes): AES encryption key.
        """
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

        logger.info(f"Answer from {sender} to {target}")

        if target == "server":
            return await self.handle_server_answer(websocket, data, aes_key)

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
            info["call_id"] = await start_call(
                info["caller"], info["callee"])  # Single DB record

        await structure_encrypt_send_message(
            websocket=clients[target]["ws"],
            aes_key=clients[target].get("aes_key", aes_key),
            msg_type="answer",
            success=True,
            payload=payload
        )

    async def handle_ice_candidate(self, websocket, data, aes_key):
        """
        Relay an ICE candidate between peers or to the server handler.

        Args:
            websocket: WebSocket connection.
            data (dict): Parsed message with 'user_id', 'jwt', and 'payload'.
            aes_key (bytes): AES encryption key.
        """
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

        logger.info(f"ICE candidate from {sender} to {target}")

        if target == "server":
            return await self.handle_server_ice_candidate(websocket, data, aes_key)

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

    async def handle_server_offer(self, websocket, data, aes_key):
        """
        Handle a client SDP offer directed to the server.

        Args:
            websocket: WebSocket connection.
            data (dict): Parsed message containing 'jwt' and 'payload'.
            aes_key (bytes): AES encryption key.
        """
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

        logger.info(f"Server-side offer from {sender} for {other_user}")

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
        logger.info(f"Sent server answer to {sender}")

    async def handle_server_answer(self, websocket, data, aes_key):
        """
        Handle a client's SDP answer to a server-initiated offer.

        Args:
            websocket: WebSocket connection.
            data (dict): Parsed message containing 'jwt' and 'payload'.
            aes_key (bytes): AES encryption key.
        """
        user_id = data.get("user_id")
        payload = data.get("payload", {})
        sender = payload.get("from")
        answer = payload.get("answer")

        valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
        if not valid:
            return await send_error_message(websocket, aes_key, "answer", err)

        logger.info(f"Server-side answer from {sender}")

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

    async def handle_server_ice_candidate(self, websocket, data, aes_key):
        """
        Handle an ICE candidate for a server-side connection.

        Args:
            websocket: WebSocket connection.
            data (dict): Parsed message containing 'jwt' and 'payload'.
            aes_key (bytes): AES encryption key.
        """
        user_id = data.get("user_id")
        payload = data.get("payload", {})
        sender = payload.get("from")
        candidate_dict = payload.get("candidate", {})

        valid, err = verify_jwt_in_message(data.get("jwt"), "access", user_id)
        if not valid:
            return await send_error_message(websocket, aes_key, "ice_candidate", err)

        logger.info(f"Server-side ICE candidate from {sender}")

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
        data = self._parse_candidate(candidate_str)
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

    def _parse_candidate(self, candidate_str: str) -> dict:
        """
        Parse an SDP ICE candidate string into its components.

        Args:
            candidate_str (str): Raw SDP ICE candidate line.

        Returns:
            dict: Parsed ICE candidate fields (foundation, component, protocol, etc.).
        """
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
