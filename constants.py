import tensorflow as tf

MAX_FRAMES = 75
VIDEO_WIDTH = 125
VIDEO_HEIGHT = 50
VIDEO_TYPE = "mp4"

# Define vocabulary for character mapping
# vocab = ["A", "U", "I", "E", " "]
vocab = [x for x in "abcdefghijklmnopqrstuvwxyz'?!123456789 "]
char_to_num = tf.keras.layers.StringLookup(vocabulary=vocab, oov_token="")
num_to_char = tf.keras.layers.StringLookup(vocabulary=char_to_num.get_vocabulary(), oov_token="", invert=True)
