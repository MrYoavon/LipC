# data_processing/data_processing.py
import os

# Third-party imports
import tensorflow as tf

from model.constants import MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, VIDEO_TYPE, BATCH_SIZE, TRAIN_TFRECORDS_PATH, \
    VAL_TFRECORDS_PATH


class Augmentor:
    @staticmethod
    # def augment_video(video_tensor):
    #     """
    #     Apply augmentations to a video tensor.
    #     :param video_tensor: A tensor representing the video with shape [frames, height, width, channels].
    #     :return: Augmented video tensor.
    #     """
    #     video_tensor = tf.ensure_shape(video_tensor, [None, None, None, None, 1])  # Channels fixed to 1
    #
    #     # Random horizontal flip
    #     video_tensor = tf.image.random_flip_left_right(video_tensor)
    #
    #     # Random brightness adjustment
    #     video_tensor = tf.image.random_brightness(video_tensor, max_delta=0.2)
    #
    #     # Random contrast adjustment
    #     video_tensor = tf.image.random_contrast(video_tensor, lower=0.8, upper=1.2)
    #
    #     # Explicitly set shape
    #     video_tensor = tf.ensure_shape(video_tensor, [BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1])
    #     video_tensor = tf.cast(video_tensor, tf.float16)
    #     return video_tensor
    def augment_video(batch_video_tensor):
        """
        Apply augmentations to a batch of video tensors.
        :param batch_video_tensor: A tensor representing a batch of videos with shape [batch_size, frames, height, width, channels].
        :return: Augmented batch of video tensors.
        """
        batch_video_tensor = tf.ensure_shape(batch_video_tensor, [None, None, None, None, 1])  # Channels fixed to 1

        def augment_single_video(video_tensor):
            """
            Apply augmentations to a single video tensor.
            :param video_tensor: A tensor representing a single video with shape [frames, height, width, channels].
            :return: Augmented video tensor.
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

        # Explicitly set shape
        batch_video_tensor = tf.ensure_shape(batch_video_tensor, [BATCH_SIZE, MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1])
        batch_video_tensor = tf.cast(batch_video_tensor, tf.float16)
        return batch_video_tensor


class DatasetPreparer:
    def __init__(self, video_directory: str, data_loader):
        self.video_directory = video_directory
        self.data_loader = data_loader

    def prepare_dataset(self, save_tfrecords=False):
        """
        Prepare a TensorFlow dataset. If TFRecords files exist, load from them. Otherwise, create the dataset
        from raw video files and optionally save it to TFRecords files.

        Args:
            save_tfrecords (bool): Whether to save the datasets to TFRecords files.

        Returns:
            train_dataset (tf.data.Dataset): The training dataset.
            val_dataset (tf.data.Dataset): The validation dataset.
        """
        # Check if TFRecords files exist
        if os.path.exists(TRAIN_TFRECORDS_PATH) and os.path.exists(VAL_TFRECORDS_PATH):
            print(f"Loading datasets from TFRecords: {TRAIN_TFRECORDS_PATH} and {VAL_TFRECORDS_PATH}")
            # Load datasets from TFRecords
            train_dataset = self.load_tfrecords(TRAIN_TFRECORDS_PATH, is_training=True)
            val_dataset = self.load_tfrecords(VAL_TFRECORDS_PATH)
        else:
            print("TFRecords files not found. Creating datasets from raw files...")
            # Create the dataset from video files
            video_paths = f"{self.video_directory}/*/*.{VIDEO_TYPE}"
            dataset = tf.data.Dataset.list_files(video_paths, shuffle=False)  # Disable default shuffle for control

            # Shuffle the dataset
            # dataset = dataset.shuffle(buffer_size=100, reshuffle_each_iteration=True)

            # Map video paths to video and subtitle data
            dataset = dataset.map(
                lambda path: DatasetPreparer.video_path_to_data(path, self.data_loader),
                num_parallel_calls=tf.data.AUTOTUNE
            )

            # Calculate dataset size
            dataset_size = dataset.cardinality().numpy()
            if dataset_size == tf.data.UNKNOWN_CARDINALITY or dataset_size == tf.data.INFINITE_CARDINALITY:
                raise ValueError("Dataset size is unknown or infinite. Ensure the dataset is finite and valid.")

            train_size = int(0.8 * dataset_size)

            # Split into training and validation datasets
            train_dataset = dataset.take(train_size)
            val_dataset = dataset.skip(train_size)

            # Batch and pad the datasets to ensure consistent shapes
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

            # Cache and Prefetch datasets to prevent bottlenecks
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
        Prepares video and subtitle tensors.
        """
        video_path = video_path.numpy().decode('utf-8')
        subtitles_path = video_path.replace("videos", "transcriptions").replace(VIDEO_TYPE, "csv")

        video_tensor = data_loader.load_video(video_path)
        subtitle_tensor = data_loader.load_subtitles(subtitles_path)

        tf.cast(video_tensor, tf.float16)
        tf.cast(subtitle_tensor, tf.int8)

        return video_tensor, subtitle_tensor

    @staticmethod
    def video_path_to_data(video_path: tf.Tensor, data_loader):
        """
        A wrapper function that maps video path to frames and alignments.
        """
        return tf.py_function(
            func=lambda x: DatasetPreparer.prepare_video_and_subtitles(x, data_loader),
            inp=[video_path],
            Tout=[tf.float16, tf.int8]
        )

    def write_to_tfrecords(self, dataset, tfrecords_path):
        """
        Write the dataset to a TFRecords file.
        """
        with tf.io.TFRecordWriter(tfrecords_path) as writer:
            for video, subtitle in dataset:
                feature = {
                    'video': tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(video).numpy()])),
                    'subtitle': tf.train.Feature(
                        bytes_list=tf.train.BytesList(value=[tf.io.serialize_tensor(subtitle).numpy()])),
                }
                example = tf.train.Example(features=tf.train.Features(feature=feature))
                writer.write(example.SerializeToString())

    def parse_tfrecords(self, serialized_example):
        """
        Parse a single example from a TFRecords file.
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
        Save processed datasets to TFRecords files.
        """
        print("Saving training dataset...")
        self.write_to_tfrecords(train_dataset, train_path)
        print(f"Training dataset saved to {train_path}")

        print("Saving validation dataset...")
        self.write_to_tfrecords(val_dataset, val_path)
        print(f"Validation dataset saved to {val_path}")

    def load_tfrecords(self, tfrecords_path, is_training=False):
        """
        Load a TFRecords file and prepare it as a dataset.
        """
        dataset = tf.data.TFRecordDataset(tfrecords_path)
        dataset = dataset.map(self.parse_tfrecords, num_parallel_calls=tf.data.AUTOTUNE)

        if is_training:
            # Augment the training dataset
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
        """
        train_dataset, val_dataset = self.prepare_dataset()
        self.save_processed_dataset(train_dataset, val_dataset, train_path, val_path)

