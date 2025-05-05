import tensorflow as tf

###############################
#       Model Parameters      #
###############################

MAX_FRAMES = 75
VIDEO_WIDTH = 125
VIDEO_HEIGHT = 50
VIDEO_TYPE = "mp4"
BATCH_SIZE = 8

###############################
#       Data Paths            #
###############################

TRAIN_TFRECORDS_PATH = "model/data/GRID_corpus/train.tfrecords"
VAL_TFRECORDS_PATH = "model/data/GRID_corpus/val.tfrecords"

###############################
#  Vocabulary and Mappings    #
###############################

# Define vocabulary for character mapping.
# Uncomment the following line for a limited vocabulary:
# vocab = ["A", "U", "I", "E", " "]
vocab = [x for x in "abcdefghijklmnopqrstuvwxyz'?!123456789 "]

# Map characters to numeric indices.
char_to_num = tf.keras.layers.StringLookup(
    vocabulary=vocab,
    oov_token=""
)

# Invert the mapping: numeric indices to characters.
num_to_char = tf.keras.layers.StringLookup(
    vocabulary=char_to_num.get_vocabulary(),
    oov_token="",
    invert=True
)
