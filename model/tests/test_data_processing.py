# tests/test_data_processing.py
import numpy as np
import tensorflow as tf
import pytest
from data_processing.data_processing import Augmentor, DatasetPreparer
from constants import MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, BATCH_SIZE


def make_dummy_record():
    # create a dummy video tensor and subtitle tensor
    video = tf.zeros([BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT,
                     VIDEO_WIDTH, 1], tf.float16)
    subtitle = tf.zeros([BATCH_SIZE, 10], tf.int8)
    feature = {
        'video': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(video).numpy()])),
        'subtitle': tf.train.Feature(bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(subtitle).numpy()]))
    }
    ex = tf.train.Example(features=tf.train.Features(feature=feature))
    return ex.SerializeToString()


def test_augmentor_shape_and_dtype():
    dummy = tf.zeros([BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT,
                     VIDEO_WIDTH, 1], tf.float16)
    aug = Augmentor.augment_video(dummy)
    # shape and dtype should match
    assert isinstance(aug, tf.Tensor)
    assert aug.shape == (BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1)
    assert aug.dtype == tf.float16


def test_tfrecord_parse_and_shapes(tmp_path):
    tfrec = tmp_path / "test.tfrecord"
    # write a few dummy records
    with tf.io.TFRecordWriter(str(tfrec)) as w:
        for _ in range(3):
            w.write(make_dummy_record())

    dp = DatasetPreparer(video_directory=".", data_loader=None)
    ds = dp.load_tfrecords(str(tfrec), is_training=False)
    for v, s in ds.take(1):
        # video batch should have 5 dims, subtitle batch 2 dims
        assert v.shape[1:] == (MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1)
        assert len(s.shape) == 2
