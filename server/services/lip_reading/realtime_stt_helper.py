# realtime_stt_helper.py

import asyncio
import logging
import numpy as np
from RealtimeSTT import audio_recorder  # Import the package's main class


def convert_audio_frame_to_pcm(frame) -> bytes:
    """
    Converts an aiortc AudioFrame to PCM bytes suitable for the RealtimeSTT recognizer.

    The conversion assumes that the AudioFrame returns a numpy array with shape
    (channels, samples). When more than one channel is present, the channels are mixed
    to mono by averaging.
    """
    # Get audio data as a NumPy array (e.g. shape (channels, samples))
    audio = frame.to_ndarray()

    # Mix channels (if needed) to create a mono channel stream
    if audio.ndim > 1:
        audio = np.mean(audio, axis=0).astype(np.int16)
    else:
        audio = audio.astype(np.int16)

    # Convert the NumPy array to raw bytes (PCM 16-bit little-endian)
    return audio.tobytes()


class AudioTranscriber:
    """
    Helper class for transcribing audio frames using RealtimeSTT.

    The transcriber is initialized with a speech model and sample rate.
    The transcribe_audio_frame method accepts an aiortc AudioFrame,
    converts it to PCM, and then calls the recognizer to obtain a transcription.
    """

    def __init__(self, model: str = "large-v2"):
        """
        Initialize the transcriber.

        :param model: The size of the speech recognition model (e.g. tiny, large).
        """
        self.stt = audio_recorder.AudioToTextRecorder(
            model=model,
            # enable_realtime_transcription=True,
            # realtime_model_type="tiny",
            # on_realtime_transcription_update=self.realtime_callback,
            # realtime_processing_pause=0.2,
            use_microphone=False,
            spinner=False,
            print_transcription_time=True,
            device="cpu",
        )

    async def transcribe_audio_frame(self, frame) -> str:
        """
        Transcribe an audio frame.

        :param frame: The aiortc AudioFrame to be transcribed.
        :return: The recognized speech as text.
        """
        # Convert the audio frame to PCM bytes
        pcm_data = convert_audio_frame_to_pcm(frame)

        # Call the recognizer in a separate thread if the call is blocking.
        # The 'recognize' method is assumed to be synchronous.
        await asyncio.to_thread(self.stt.feed_audio, pcm_data)
        return self.stt.text()

    # def realtime_callback(text):
    #     # This callback will be called with each update.
    #     logging.info(f"Realtime update: {text}")
    #     # Here you can, for example, forward the text to a WebSocket,
    #     # update a GUI subtitle view, etc.
