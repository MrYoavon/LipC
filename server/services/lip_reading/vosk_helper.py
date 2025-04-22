import json
import numpy as np
import librosa
from vosk import Model, KaldiRecognizer
from constants import VOSK_MODEL_PATH


# one global (thread‑safe) model to save RAM
_VOSK_MODEL = Model(model_path=VOSK_MODEL_PATH)


class VoskRecognizer:
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
            result = self.recognizer.Result()
        # else:
        #     # Return a partial result for ongoing speech.
        #     result = self.recognizer.PartialResult()
            return result

    def get_final_result(self) -> str:
        """
        Retrieve the final transcription result after the audio stream ends.

        Returns:
            str: The final recognition result.
        """
        return self.recognizer.FinalResult()

    def reset(self):
        """
        Reset the recognizer state to start a new recognition session.

        This might be useful if I intend to process a completely new audio stream
        after finishing one and still use the existing instance of the class.
        """
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)


def convert_audio_frame_to_pcm(frame, target_sr=16000):
    """Return mono 16 bit PCM bytes, resampled to `target_sr`."""
    pcm = frame.to_ndarray().astype(np.int16)   # (ch, samples) or (samples,)
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=0).astype(np.int16)  # to mono
    # # If frame.sample_rate != target_sr, resample
    # if frame.sample_rate != target_sr:
    #     pcm = librosa.resample(pcm.astype(np.float32),
    #                            orig_sr=frame.sample_rate,
    #                            target_sr=target_sr).astype(np.int16)
    return pcm.tobytes()
