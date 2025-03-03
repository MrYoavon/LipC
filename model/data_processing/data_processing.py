# data_processing/data_processing.py

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

###############################
# Video Augmentation Class    #
###############################

class Augmentor:
    @staticmethod
    def augment_video(batch_video_tensor):
        """
        Apply augmentations to a batch of video tensors.

        Args:
            batch_video_tensor: A tensor representing a batch of videos with shape
                                [batch_size, frames, height, width, channels].

        Returns:
            Augmented batch of video tensors.
        """
        # Ensure the video tensor has a fixed channel dimension (1)
        batch_video_tensor = tf.ensure_shape(batch_video_tensor, [None, None, None, None, 1])

        def augment_single_video(video_tensor):
            """
            Apply augmentations to a single video tensor.

            Args:
                video_tensor: A tensor representing a single video with shape
                            [frames, height, width, channels].

            Returns:
                Augmented video tensor.
            """
            # Random horizontal flip
            video_tensor = tf.image.random_flip_left_right(video_tensor)
            # Random brightness adjustment
            video_tensor = tf.image.random_brightness(video_tensor, max_delta=0.2)
            # Random contrast adjustment
            video_tensor = tf.image.random_contrast(video_tensor, lower=0.8, upper=1.2)
            return video_tensor

        # Apply the augmentations to each video in the batch
        batch_video_tensor = tf.map_fn(augment_single_video, batch_video_tensor)

        # Set explicit shape and cast to float16
        batch_video_tensor = tf.ensure_shape(
            batch_video_tensor, [BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1]
        )
        batch_video_tensor = tf.cast(batch_video_tensor, tf.float16)
        return batch_video_tensor


#################################
# Dataset Preparation Class     #
#################################

class DatasetPreparer:
    def __init__(self, video_directory: str, data_loader):
        """
        Initialize the DatasetPreparer.

        Args:
            video_directory: Directory where raw video files are located.
            data_loader: Instance for loading video and subtitle data.
        """
        self.video_directory = video_directory
        self.data_loader = data_loader

    def prepare_dataset(self, save_tfrecords=False):
        """
        Prepare a TensorFlow dataset. If TFRecords exist, load from them;
        otherwise, create the dataset from raw files and optionally save it.

        Args:
            save_tfrecords (bool): Whether to save the datasets to TFRecords files.

        Returns:
            Tuple (train_dataset, val_dataset)
        """
        if os.path.exists(TRAIN_TFRECORDS_PATH) and os.path.exists(VAL_TFRECORDS_PATH):
            print(f"Loading datasets from TFRecords: {TRAIN_TFRECORDS_PATH} and {VAL_TFRECORDS_PATH}")
            train_dataset = self.load_tfrecords(TRAIN_TFRECORDS_PATH, is_training=True)
            val_dataset = self.load_tfrecords(VAL_TFRECORDS_PATH)
        else:
            print("TFRecords files not found. Creating datasets from raw files...")
            video_paths = f"{self.video_directory}/*/*.{VIDEO_TYPE}"
            dataset = tf.data.Dataset.list_files(video_paths, shuffle=False)

            # Map video paths to video and subtitle data
            dataset = dataset.map(
                lambda path: DatasetPreparer.video_path_to_data(path, self.data_loader),
                num_parallel_calls=tf.data.AUTOTUNE
            )

            # Determine dataset size and validate
            dataset_size = dataset.cardinality().numpy()
            if dataset_size == tf.data.UNKNOWN_CARDINALITY or dataset_size == tf.data.INFINITE_CARDINALITY:
                raise ValueError("Dataset size is unknown or infinite. Ensure the dataset is finite and valid.")

            train_size = int(0.8 * dataset_size)

            # Split dataset into training and validation sets
            train_dataset = dataset.take(train_size)
            val_dataset = dataset.skip(train_size)

            # Define padded shapes for batching
            padded_shapes = ([MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1], [None])
            train_dataset = train_dataset.padded_batch(
                batch_size=BATCH_SIZE,
                padded_shapes=padded_shapes,
                padding_values=(tf.constant(0.0, dtype=tf.float16), tf.constant(0, dtype=tf.int8))
            )
            val_dataset = val_dataset.padded_batch(
                batch_size=BATCH_SIZE,
                padded_shapes=padded_shapes,
                padding_values=(tf.constant(0.0, dtype=tf.float16), tf.constant(0, dtype=tf.int8))
            )

            # Optimize with prefetching
            train_dataset = train_dataset.prefetch(tf.data.AUTOTUNE)
            val_dataset = val_dataset.prefetch(tf.data.AUTOTUNE)

            # Optionally save datasets to TFRecords
            if save_tfrecords:
                print("Saving datasets to TFRecords...")
                self.save_processed_dataset(train_dataset, val_dataset, TRAIN_TFRECORDS_PATH, VAL_TFRECORDS_PATH)
                print("Datasets saved to TFRecords.")

        return train_dataset, val_dataset

    @staticmethod
    def prepare_video_and_subtitles(video_path: tf.Tensor, data_loader):
        """
        Prepare video and subtitle tensors from a given video file.

        Args:
            video_path: Tensor containing the video file path.
            data_loader: Instance for loading video and subtitle data.

        Returns:
            Tuple (video_tensor, subtitle_tensor)
        """
        video_path_str = video_path.numpy().decode('utf-8')
        subtitles_path = video_path_str.replace("videos", "transcriptions").replace(VIDEO_TYPE, "csv")

        video_tensor = data_loader.load_video(video_path_str)
        subtitle_tensor = data_loader.load_subtitles(subtitles_path)

        # Cast to required data types
        tf.cast(video_tensor, tf.float16)
        tf.cast(subtitle_tensor, tf.int8)

        return video_tensor, subtitle_tensor

    @staticmethod
    def video_path_to_data(video_path: tf.Tensor, data_loader):
        """
        Convert a video file path to video and subtitle data.

        Args:
            video_path: Tensor containing the video file path.
            data_loader: Instance for loading data.

        Returns:
            A tuple (video_tensor, subtitle_tensor)
        """
        return tf.py_function(
            func=lambda x: DatasetPreparer.prepare_video_and_subtitles(x, data_loader),
            inp=[video_path],
            Tout=[tf.float16, tf.int8]
        )

    def write_to_tfrecords(self, dataset, tfrecords_path):
        """
        Write a dataset to a TFRecords file.

        Args:
            dataset: The dataset to be written.
            tfrecords_path: Path for saving the TFRecords file.
        """
        with tf.io.TFRecordWriter(tfrecords_path) as writer:
            for video, subtitle in dataset:
                feature = {
                    'video': tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(video).numpy()])
                    ),
                    'subtitle': tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(subtitle).numpy()])
                    ),
                }
                example = tf.train.Example(features=tf.train.Features(feature=feature))
                writer.write(example.SerializeToString())

    def parse_tfrecords(self, serialized_example):
        """
        Parse a single example from a TFRecords file.

        Args:
            serialized_example: A serialized TFRecord example.

        Returns:
            Tuple (video_tensor, subtitle_tensor)
        """
        feature_description = {
            'video': tf.io.FixedLenFeature([], tf.string),
            'subtitle': tf.io.FixedLenFeature([], tf.string),
        }
        example = tf.io.parse_single_example(serialized_example, feature_description)
        video = tf.io.parse_tensor(example['video'], out_type=tf.float16)
        subtitle = tf.io.parse_tensor(example['subtitle'], out_type=tf.int8)

        video = tf.ensure_shape(video, [BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1])
        subtitle = tf.ensure_shape(subtitle, [BATCH_SIZE, None])
        return video, subtitle

    def save_processed_dataset(self, train_dataset, val_dataset, train_path, val_path):
        """
        Save processed training and validation datasets to TFRecords files.

        Args:
            train_dataset: The training dataset.
            val_dataset: The validation dataset.
            train_path: File path for saving training dataset.
            val_path: File path for saving validation dataset.
        """
        print("Saving training dataset...")
        self.write_to_tfrecords(train_dataset, train_path)
        print(f"Training dataset saved to {train_path}")

        print("Saving validation dataset...")
        self.write_to_tfrecords(val_dataset, val_path)
        print(f"Validation dataset saved to {val_path}")

    def load_tfrecords(self, tfrecords_path, is_training=False):
        """
        Load and prepare a dataset from a TFRecords file.

        Args:
            tfrecords_path: Path to the TFRecords file.
            is_training (bool): If True, apply data augmentation and shuffling.

        Returns:
            A TensorFlow dataset.
        """
        dataset = tf.data.TFRecordDataset(tfrecords_path)
        dataset = dataset.map(self.parse_tfrecords, num_parallel_calls=tf.data.AUTOTUNE)

        if is_training:
            dataset = dataset.map(
                lambda video, subtitle: (Augmentor.augment_video(video), subtitle),
                num_parallel_calls=tf.data.AUTOTUNE
            )
            dataset = dataset.shuffle(buffer_size=100, reshuffle_each_iteration=True)
        else:
            dataset = dataset.shuffle(buffer_size=100, reshuffle_each_iteration=False)

        dataset = dataset.prefetch(tf.data.AUTOTUNE)
        return dataset

    def prepare_and_save_dataset(self, train_path, val_path):
        """
        Prepare the dataset and save it to TFRecords files.

        Args:
            train_path: File path for saving training dataset.
            val_path: File path for saving validation dataset.
        """
        train_dataset, val_dataset = self.prepare_dataset()
        self.save_processed_dataset(train_dataset, val_dataset, train_path, val_path)
