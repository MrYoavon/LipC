import tensorflow as tf

# Lip reading model
MAX_FRAMES = 75
VIDEO_WIDTH = 125
VIDEO_HEIGHT = 50
vocab = [x for x in "abcdefghijklmnopqrstuvwxyz'?!123456789 "]
char_to_num = tf.keras.layers.StringLookup(vocabulary=vocab, oov_token="")
num_to_char = tf.keras.layers.StringLookup(
    vocabulary=char_to_num.get_vocabulary(), oov_token="", invert=True)

# Vosk
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"
TARGET_CHUNK_SIZE = 500  # in ms

# SSL certificates
SSL_CERT_FILE = "certs/cert.pem"
SSL_KEY_FILE = "certs/key.pem"

# WebSocket
HEARTBEAT_INTERVAL = 10  # seconds
HEARTBEAT_TIMEOUT = 15   # seconds

# User data
PASSWORD_MAX_LENGTH = 128
USERNAME_MAX_LENGTH = 32
NAME_PART_MAX_LENGTH = 30
