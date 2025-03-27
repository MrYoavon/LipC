# server/app.py
import tensorflow as tf

def configure_devices():
    """
    Configure TensorFlow to use GPU if available, fallback to CPU otherwise.
    """
    try:
        # Detect GPUs
        gpus = tf.config.experimental.list_physical_devices('GPU')
        print(gpus)

        if gpus:
            # Set memory growth to prevent memory allocation problems
            tf.config.experimental.set_memory_growth(gpus[0], True)
            tf.config.experimental.set_visible_devices(gpus[0], 'GPU')
            print(f"Using GPU: {gpus[0]}")
        else:
            print("No GPU detected, using CPU.")

        # Log TensorFlow ROCm or CUDA status (if applicable)
        print(f"TensorFlow Version: {tf.__version__}")
        print(f"Is CUDA enabled: {tf.test.is_built_with_cuda()}")
        print(f"Is ROCm enabled: {tf.test.is_built_with_rocm()}")

    except RuntimeError as e:
        print(f"Error configuring TensorFlow devices: {e}")

configure_devices()


import asyncio
from websockets import serve
import os

from handlers.connection import handle_connection
from services.logger  import setup_logger


def main():
    print("Starting WebSocket server...")
    setup_logger()
    host = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
    port = int(os.getenv("WEBSOCKET_PORT", 8765))
    asyncio.run(start_server(host, port))


async def start_server(host, port):
    async with serve(handle_connection, host, port):
        print(f"WebSocket server started on ws://{host}:{port}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    main()
