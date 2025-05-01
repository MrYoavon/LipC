import json
import av

from vosk import Model, KaldiRecognizer
from constants import VOSK_MODEL_PATH


# Load a single global Vosk model to reduce memory usage
_VOSK_MODEL = Model(model_path=VOSK_MODEL_PATH)

# Configure resampler for audio frames
_RESAMPLER = av.AudioResampler(
    format="s16",    # signed 16-bit PCM (little-endian)
    layout="mono",   # single channel
    rate=16000       # 16 kHz
)


class VoskRecognizer:
    """
    Wrapper around Vosk KaldiRecognizer for streaming speech-to-text.

    This class initializes the recognizer with a shared Vosk model, processes
    raw PCM audio chunks, and returns partial or final JSON transcription results.
    """

    def __init__(self, sample_rate: int = 16000):
        """
        Initialize the Vosk model and recognizer.

        Args:
            sample_rate (int): Audio sample rate (default is 16000 Hz).
        """
        self.sample_rate = sample_rate
        self.recognizer = KaldiRecognizer(_VOSK_MODEL, self.sample_rate)

    def process_audio_chunk(self, audio_chunk: bytes) -> str:
        """
        Process a chunk of raw PCM audio data.

        When a new chunk of audio is received from an aiortc audio track,
        feed it into this function. It returns either a complete (final) result
        if the recognizer has a confident transcription or a partial result.

        Args:
            audio_chunk (bytes): The raw PCM audio data chunk.

        Returns:
            str: The transcription result.
                  The result is either a complete result (if recognized) or a partial result.
        """
        if self.recognizer.AcceptWaveform(audio_chunk):
            # The recognizer has finalized this audio segment.
            result = json.loads(self.recognizer.Result())
        else:
            # Return a partial result for ongoing speech.
            result = json.loads(self.recognizer.PartialResult())
        return result

    def get_final_result(self) -> dict:
        """
        Retrieve the final transcription after all audio has been processed.

        Returns:
            dict: Final JSON result from Vosk with 'text' field.
        """
        return json.loads(self.recognizer.FinalResult())

    def reset(self) -> None:
        """
        Reset the recognizer state to process a new audio stream.

        This re-initializes the KaldiRecognizer while retaining the shared model.
        """
        self.recognizer = KaldiRecognizer(_VOSK_MODEL, self.sample_rate)


def convert_audio_frame_to_pcm(frame: av.AudioFrame) -> bytes:
    """
    Convert and resample an AV AudioFrame to raw PCM bytes.

    Args:
        frame (av.AudioFrame): Input audio frame from aiortc track.

    Returns:
        bytes: Concatenated PCM audio bytes, resampled to 16 kHz mono 16-bit.
    """
    # Resample the audio frame to the target format
    converted = _RESAMPLER.resample(frame)
    # Ensure we have a list of frames
    frames = converted if isinstance(converted, list) else [converted]
    # Extract and return raw PCM bytes from each plane
    pcm_chunks = [bytes(f.planes[0])[: f.samples * 2] for f in frames]
    return b"".join(pcm_chunks)
