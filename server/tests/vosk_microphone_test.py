#!/usr/bin/env python3
"""
Microphone test for Vosk speech recognition.

This script captures raw audio from the default input device using sounddevice,
feeds each block to the VoskRecognizer, and prints intermediate and final
transcription results.

Requires:
    pip install sounddevice vosk
"""
import queue
import sounddevice as sd
from ..services.lip_reading.vosk_helper import VoskRecognizer

# Queue to communicate between audio callback and main thread
q = queue.Queue()


def audio_callback(indata, frames, time, status):
    """
    Callback for sounddevice RawInputStream.

    Captures raw audio blocks and enqueues PCM bytes for transcription.

    Args:
        indata (bytes or numpy.ndarray): Audio buffer from sounddevice.
        frames (int): Number of audio frames in this buffer.
        time (CData): Timestamp information (unused).
        status: Callback status indicator; logs if non-zero.

    Returns:
        None

    Side Effects:
        Prints status messages and enqueues audio data.
    """
    if status:
        print(f"Audio status: {status}")
    # Ensure we have raw PCM bytes
    q.put(bytes(indata))


def main():
    """
    Read microphone audio and process through VoskRecognizer.

    Initializes VoskRecognizer at 16 kHz, opens a RawInputStream, and
    continuously feeds audio chunks for transcription until interrupted.

    Args:
        None

    Returns:
        None

    Raises:
        KeyboardInterrupt: When user stops with Ctrl+C.
    """
    sample_rate = 16000
    rec = VoskRecognizer(sample_rate=sample_rate)
    print("Listening (press Ctrl+C to stop)...")

    # Open a raw input stream (mono, 16-bit PCM)
    with sd.RawInputStream(
        samplerate=sample_rate,
        blocksize=8000,
        dtype='int16',
        channels=1,
        callback=audio_callback
    ):
        try:
            while True:
                data = q.get()  # block until audio data is available
                ms = len(data) / 2 / sample_rate * 1000
                print(f"Feeding Vosk {ms:.1f} ms of audio")
                result = rec.process_audio_chunk(data)
                print(result)
        except KeyboardInterrupt:
            print("\nStopping...")
            final = rec.get_final_result()
            print("Final result:", final)


if __name__ == "__main__":
    main()
