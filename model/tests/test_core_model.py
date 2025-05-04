# tests/test_core_model.py
import tensorflow as tf
import numpy as np
from core_model.model import LipReadingModel
from constants import MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, BATCH_SIZE


def test_lip_reading_model_shapes():
    num_classes = 10
    m = LipReadingModel(input_shape=(MAX_FRAMES, VIDEO_HEIGHT,
                        VIDEO_WIDTH, 1), num_classes=num_classes)
    model = m.model

    # check input & output shapes
    inp = model.input_shape  # (BATCH_SIZE, MAX_FRAMES, H, W, 1)
    out = model.output_shape  # (BATCH_SIZE, MAX_FRAMES, num_classes+1)
    assert inp == (BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1)
    assert out[-1] == num_classes + 1

    # a forward pass on random data
    dummy = np.zeros((BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT,
                     VIDEO_WIDTH, 1), dtype=np.float32)
    preds = model(dummy, training=False)
    assert isinstance(preds, tf.Tensor)
    assert preds.shape == out
