# data_processing/data_processing.py
"""
Data processing utilities for preparing video and subtitle datasets for lip-reading models.

Includes:
  - Augmentor: applies on-the-fly augmentations to video tensors.
  - DatasetPreparer: builds TensorFlow datasets from raw video files or TFRecords,
    supports batching, shuffling, augmentation, and TFRecord serialization.
"""
import os
import tensorflow as tf

from model.constants import (
    MAX_FRAMES,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    VIDEO_TYPE,
    BATCH_SIZE,
    TRAIN_TFRECORDS_PATH,
    VAL_TFRECORDS_PATH,
)


class Augmentor:
    """
    Applies data augmentation transformations to batches of video tensors.

    Static methods allow augmentation without maintaining state.
    """

    @staticmethod
    def augment_video(batch_video_tensor):
        """
        Apply augmentations to each video in a batch.

        Augmentations include random horizontal flip, brightness, and contrast.
        Ensures the output tensor has expected shape and dtype.

        Args:
            batch_video_tensor (tf.Tensor): A batch of videos with shape
                [batch_size, frames, height, width, channels=1].

        Returns:
            tf.Tensor: Augmented batch with shape
                [BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1] and dtype float16.
        """
        # Ensure the video tensor has a fixed channel dimension (1)
        batch_video_tensor = tf.ensure_shape(
            batch_video_tensor, [None, None, None, None, 1])

        def augment_single_video(video_tensor):
            """
            Apply random augmentations to one video.

            Args:
                video_tensor (tf.Tensor): Video tensor of shape
                    [frames, height, width, 1].

            Returns:
                tf.Tensor: Augmented video tensor.
            """
            # Random horizontal flip
            video_tensor = tf.image.random_flip_left_right(video_tensor)
            # Random brightness adjustment
            video_tensor = tf.image.random_brightness(
                video_tensor, max_delta=0.2)
            # Random contrast adjustment
            video_tensor = tf.image.random_contrast(
                video_tensor, lower=0.8, upper=1.2)
            return video_tensor

        # Apply the augmentations to each video in the batch
        batch_video_tensor = tf.map_fn(
            augment_single_video, batch_video_tensor)

        # Set explicit shape and cast to float16
        batch_video_tensor = tf.ensure_shape(
            batch_video_tensor, [BATCH_SIZE, MAX_FRAMES,
                                 VIDEO_HEIGHT, VIDEO_WIDTH, 1]
        )
        batch_video_tensor = tf.cast(batch_video_tensor, tf.float16)
        return batch_video_tensor


class DatasetPreparer:
    """
    Prepares TensorFlow datasets for training and validation.

    Supports loading from raw video files with optional TFRecord caching,
    batching, padding, augmentation, and prefetching.
    """

    def __init__(
        self,
        video_directory: str,
        data_loader
    ) -> None:
        """
        Initialize with paths and a data loader instance.

        Args:
            video_directory (str): Root directory containing video files organized
                by subfolders (e.g., 'videos/s1/').
            data_loader: Object providing methods `.load_video(path)` and
                `.load_subtitles(path)` returning tensors.
        """
        self.video_directory = video_directory
        self.data_loader = data_loader

    def prepare_dataset(
        self,
        save_tfrecords: bool = False
    ) -> tuple[tf.data.Dataset, tf.data.Dataset]:
        """
        Build training and validation datasets.

        If TFRecord files exist, load from them; otherwise create from raw data,
        split 80/20, batch with padding, and optionally save to TFRecords.

        Args:
            save_tfrecords (bool): Whether to write the processed datasets to TFRecords.

        Returns:
            Tuple[tf.data.Dataset, tf.data.Dataset]: (train_dataset, val_dataset)
        """
        # Check for cached TFRecords
        if os.path.exists(TRAIN_TFRECORDS_PATH) and os.path.exists(VAL_TFRECORDS_PATH):
            train_ds = self.load_tfrecords(
                TRAIN_TFRECORDS_PATH, is_training=True)
            val_ds = self.load_tfrecords(VAL_TFRECORDS_PATH, is_training=False)
        else:
            # Create from raw video files
            pattern = os.path.join(self.video_directory,
                                   '*', f'*.{VIDEO_TYPE}')
            dataset = tf.data.Dataset.list_files(pattern, shuffle=False)

            # Map file paths to data tuples via py_function
            dataset = dataset.map(
                lambda p: DatasetPreparer.video_path_to_data(
                    p, self.data_loader),
                num_parallel_calls=tf.data.AUTOTUNE
            )

            size = dataset.cardinality().numpy()
            if size in (tf.data.UNKNOWN_CARDINALITY, tf.data.INFINITE_CARDINALITY):
                raise ValueError("Dataset size unknown or infinite.")
            train_count = int(0.8 * size)

            train_ds = dataset.take(train_count)
            val_ds = dataset.skip(train_count)

            # Batch with padding for variable-length subtitles
            pad_shapes = ([MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1], [None])
            pad_values = (tf.constant(0.0, tf.float16),
                          tf.constant(0, tf.int8))
            train_ds = train_ds.padded_batch(
                BATCH_SIZE, padded_shapes=pad_shapes, padding_values=pad_values
            ).prefetch(tf.data.AUTOTUNE)
            val_ds = val_ds.padded_batch(
                BATCH_SIZE, padded_shapes=pad_shapes, padding_values=pad_values
            ).prefetch(tf.data.AUTOTUNE)

            if save_tfrecords:
                self.save_processed_dataset(
                    train_ds, val_ds, TRAIN_TFRECORDS_PATH, VAL_TFRECORDS_PATH
                )

        return train_ds, val_ds

    @staticmethod
    def prepare_video_and_subtitles(
        video_path: tf.Tensor,
        data_loader
    ) -> tuple[tf.Tensor, tf.Tensor]:
        """
        Load a video tensor and its corresponding subtitle tensor.

        Args:
            video_path (tf.Tensor): Scalar string tensor of the video file path.
            data_loader: Loader with `.load_video(str)` and `.load_subtitles(str)`.

        Returns:
            Tuple[tf.Tensor, tf.Tensor]: (video_tensor, subtitle_tensor)
        """
        path = video_path.numpy().decode('utf-8')
        subs = path.replace('videos', 'transcriptions').replace(
            VIDEO_TYPE, 'csv')
        video = data_loader.load_video(path)
        subtitle = data_loader.load_subtitles(subs)
        return tf.cast(video, tf.float16), tf.cast(subtitle, tf.int8)

    @staticmethod
    def video_path_to_data(
        video_path: tf.Tensor,
        data_loader
    ) -> list[tf.Tensor]:
        """
        TensorFlow mapping wrapper to call prepare_video_and_subtitles.

        Args:
            video_path (tf.Tensor): Path tensor for a single video file.
            data_loader: Loader instance.

        Returns:
            list[tf.Tensor]: [video_tensor, subtitle_tensor] for batching.
        """
        return tf.py_function(
            func=lambda p: DatasetPreparer.prepare_video_and_subtitles(
                p, data_loader),
            inp=[video_path],
            Tout=[tf.float16, tf.int8]
        )

    def write_to_tfrecords(
        self,
        dataset: tf.data.Dataset,
        tfrecords_path: str
    ) -> None:
        """
        Serialize a dataset of (video, subtitle) into a TFRecords file.

        Args:
            dataset (tf.data.Dataset): Dataset of tuples to serialize.
            tfrecords_path (str): Output filepath for TFRecords.
        """
        with tf.io.TFRecordWriter(tfrecords_path) as writer:
            for video, subtitle in dataset:
                feature = {
                    'video': tf.train.Feature(
                        bytes_list=tf.train.BytesList(
                            value=[tf.io.serialize_tensor(video).numpy()]
                        )
                    ),
                    'subtitle': tf.train.Feature(
                        bytes_list=tf.train.BytesList(
                            value=[tf.io.serialize_tensor(subtitle).numpy()]
                        )
                    ),
                }
                example = tf.train.Example(
                    features=tf.train.Features(feature=feature))
                writer.write(example.SerializeToString())

    def parse_tfrecords(self, serialized: tf.Tensor) -> tuple[tf.Tensor, tf.Tensor]:
        """
        Parse TFRecord examples back into video and subtitle tensors.

        Args:
            serialized (tf.Tensor): Scalar string tensor of serialized Example.

        Returns:
            Tuple[tf.Tensor, tf.Tensor]: (video_tensor, subtitle_tensor) with
                enforced shapes for batching.
        """
        desc = {
            'video': tf.io.FixedLenFeature([], tf.string),
            'subtitle': tf.io.FixedLenFeature([], tf.string),
        }
        ex = tf.io.parse_single_example(serialized, desc)
        vid = tf.io.parse_tensor(ex['video'], tf.float16)
        sub = tf.io.parse_tensor(ex['subtitle'], tf.int8)
        vid = tf.ensure_shape(
            vid, [BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1])
        sub = tf.ensure_shape(sub, [BATCH_SIZE, None])
        return vid, sub

    def save_processed_dataset(
        self,
        train_dataset: tf.data.Dataset,
        val_dataset: tf.data.Dataset,
        train_path: str,
        val_path: str
    ) -> None:
        """
        Save both training and validation datasets to TFRecords.

        Args:
            train_dataset (tf.data.Dataset): Training dataset.
            val_dataset (tf.data.Dataset): Validation dataset.
            train_path (str): Output path for training TFRecords.
            val_path (str): Output path for validation TFRecords.
        """
        print("Saving training TFRecords...")
        self.write_to_tfrecords(train_dataset, train_path)
        print(f"Training saved at {train_path}")
        print("Saving validation TFRecords...")
        self.write_to_tfrecords(val_dataset, val_path)
        print(f"Validation saved at {val_path}")

    def load_tfrecords(
        self,
        tfrecords_path: str,
        is_training: bool = False
    ) -> tf.data.Dataset:
        """
        Load a TFRecords file and prepare it for training or validation.

        Args:
            tfrecords_path (str): Path to TFRecords file.
            is_training (bool): If True, apply augmentation and shuffle.

        Returns:
            tf.data.Dataset: Prepared dataset with optional augmentation.
        """
        ds = tf.data.TFRecordDataset(tfrecords_path)
        ds = ds.map(self.parse_tfrecords, num_parallel_calls=tf.data.AUTOTUNE)
        if is_training:
            ds = ds.map(
                lambda v, s: (Augmentor.augment_video(v), s),
                num_parallel_calls=tf.data.AUTOTUNE
            ).shuffle(100).prefetch(tf.data.AUTOTUNE)
        else:
            ds = ds.shuffle(100).prefetch(tf.data.AUTOTUNE)
        return ds

    def prepare_and_save_dataset(
        self,
        train_path: str,
        val_path: str
    ) -> None:
        """
        Convenience method: prepare dataset then save to TFRecords.

        Args:
            train_path (str): Output path for training TFRecords.
            val_path (str): Output path for validation TFRecords.
        """
        train_ds, val_ds = self.prepare_dataset()
        self.save_processed_dataset(train_ds, val_ds, train_path, val_path)
