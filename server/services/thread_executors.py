# services/thread_executors.py
"""
Thread pool executors for TensorFlow and speech processing tasks.

This module provides:
  - A singleton ThreadPoolExecutor for TensorFlow model inference (lip-reading).
  - A singleton ThreadPoolExecutor for speech-to-text transcription tasks (Vosk).
  - Convenience functions to submit tasks to the appropriate executor.
"""
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from services.lip_reading.lip_reader import LipReadingPipeline, get_lip_model
from services.lip_reading.vosk_helper import VoskRecognizer

# Determine CPU cores for sizing the speech executor
CPU_CORES = os.cpu_count() or 4

# -- TensorFlow executor for lip-reading ----------------------------------
_tf_executor = ThreadPoolExecutor(max_workers=1)
# Load TensorFlow lip-reading model eagerly to avoid event loop issues
_tf_model = asyncio.run(get_lip_model())
_tf_pipe = LipReadingPipeline(_tf_model)


def lip_read(frame_bgr):
    """
    Perform lip-reading inference on a single video frame.

    Args:
        frame_bgr (numpy.ndarray): Video frame in BGR color format.

    Returns:
        str or None: The predicted text from lip-reading, or None if no prediction.
    """
    return _tf_pipe.process_frame(frame_bgr)


def get_tf_executor() -> ThreadPoolExecutor:
    """
    Retrieve the ThreadPoolExecutor for TensorFlow inference tasks.

    Returns:
        ThreadPoolExecutor: Executor with a single worker for GPU-bound inference.
    """
    return _tf_executor


# -- Speech executor for Vosk transcription ------------------------------
_speech_executor = ThreadPoolExecutor(max_workers=min(4, CPU_CORES - 1))


def vosk_transcribe(recognizer: VoskRecognizer, pcm: bytes) -> dict:
    """
    Perform speech-to-text transcription on a chunk of audio.

    This function should be submitted to the speech executor.

    Args:
        recognizer (VoskRecognizer): Initialized Vosk recognizer instance.
        pcm (bytes): Raw PCM audio data.

    Returns:
        dict: Transcription result dictionary from Vosk, containing 'text' or 'partial'.
    """
    return recognizer.process_audio_chunk(pcm)


def get_speech_executor() -> ThreadPoolExecutor:
    """
    Retrieve the ThreadPoolExecutor for speech transcription tasks.

    Returns:
        ThreadPoolExecutor: Executor with multiple workers for CPU-bound audio processing.
    """
    return _speech_executor
