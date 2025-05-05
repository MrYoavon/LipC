"""
Application-wide constants for model configuration, Vosk settings, SSL, WebSocket, and user constraints.
"""
import tensorflow as tf

# --- Lip Reading Model Configuration ---
#: Number of video frames expected per input sequence for the lip-reading model.
MAX_FRAMES: int = 75
#: Width (in pixels) to resize input video frames for the model.
VIDEO_WIDTH: int = 125
#: Height (in pixels) to resize input video frames for the model.
VIDEO_HEIGHT: int = 50

# Character vocabulary for lip-reading output decoding
vocab = [x for x in "abcdefghijklmnopqrstuvwxyz'?!123456789 "]
#: Layer to map characters to numeric indices (for preprocessing).
char_to_num = tf.keras.layers.StringLookup(vocabulary=vocab, oov_token="")
#: Layer to map numeric indices back to characters (for decoding).
num_to_char = tf.keras.layers.StringLookup(
    vocabulary=char_to_num.get_vocabulary(),
    oov_token="",
    invert=True
)

# --- Vosk Speech Recognition Configuration ---
#: Filesystem path to the Vosk model directory.
VOSK_MODEL_PATH: str = "models/vosk-model-small-en-us-0.15"
#: Target audio chunk duration (in milliseconds) for Vosk transcription.
TARGET_CHUNK_SIZE: int = 500

# --- SSL Certificate Paths ---
#: Path to the server's SSL certificate file (PEM format).
SSL_CERT_FILE: str = "certs/cert.pem"
#: Path to the server's SSL private key file (PEM format).
SSL_KEY_FILE: str = "certs/key.pem"

# --- WebSocket Heartbeat Configuration ---
#: Interval (in seconds) between heartbeat pings to clients.
HEARTBEAT_INTERVAL: int = 10
#: Timeout (in seconds) to wait for a heartbeat pong before closing.
HEARTBEAT_TIMEOUT: int = 15

# --- User Data Constraints ---
#: Maximum length allowed for user passwords.
PASSWORD_MAX_LENGTH: int = 128
#: Maximum length allowed for usernames.
USERNAME_MAX_LENGTH: int = 32
#: Maximum length allowed for each part of a user's full name.
NAME_PART_MAX_LENGTH: int = 30
