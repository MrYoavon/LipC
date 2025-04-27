# services/thread_executors.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from services.lip_reading.lip_reader import LipReadingPipeline, get_lip_model
from services.lip_reading.vosk_helper import VoskRecognizer

CPU_CORES = os.cpu_count() or 4

# -- 1 GPU / TensorFlow thread ---------------------------------------------
_tf_executor = ThreadPoolExecutor(max_workers=1)
_tf_model = asyncio.run(get_lip_model())
_tf_pipe = LipReadingPipeline(_tf_model)


def lip_read(frame_bgr):
    return _tf_pipe.process_frame(frame_bgr)


def get_tf_executor():
    return _tf_executor


# -- 2-4 speech threads ------------------------------------------------------
_speech_executor = ThreadPoolExecutor(max_workers=min(4, CPU_CORES - 1))


def vosk_transcribe(recognizer: VoskRecognizer, pcm: bytes):
    return recognizer.process_audio_chunk(pcm)


def get_speech_executor():
    return _speech_executor
