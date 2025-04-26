# server/app.py
# fmt: off
# fmt on/off forces autopep8 to not auto format the code between the comments
# I want to keep the code initializing the GPU at the top, otherwise it won't work
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


from constants import SSL_CERT_FILE, SSL_KEY_FILE
from services.logger import setup_logger
from handlers.connection import handle_connection
import os
from websockets import serve
import ssl
import asyncio
# fmt: on


def main():
    print("Starting WebSocket server...")
    setup_logger()
    host = os.getenv("WEBSOCKET_HOST", "0.0.0.0")
    port = int(os.getenv("WEBSOCKET_PORT", 8765))
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(certfile=SSL_CERT_FILE, keyfile=SSL_KEY_FILE)
    asyncio.run(start_server(host, port, ssl_ctx))


async def start_server(host, port, ssl_ctx):
    async with serve(
            handler=handle_connection,
            host=host,
            port=port,
            ssl=ssl_ctx,  # Enable TLS
    ):
        print(f"WebSocket server started on wss://{host}:{port}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    main()
