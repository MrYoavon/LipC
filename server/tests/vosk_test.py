#!/usr/bin/env python3
"""
A simple script to capture microphone audio and feed it into the Vosk recognizer.
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
    This callback is called by sounddevice for each audio block.
    indata: raw bytes or numpy array depending on dtype
    """
    if status:
        print(f"Audio status: {status}")
    # Ensure we have raw PCM bytes
    q.put(bytes(indata))


def main():
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
