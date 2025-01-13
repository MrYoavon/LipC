# data_processing/data_processing.py

# Third-party imports
import tensorflow as tf

from constants import MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, VIDEO_TYPE

class Augmentor:
    @staticmethod
    def augment_video(video_tensor):
        """
        Apply augmentations to a video tensor.
        :param video_tensor: A tensor representing the video with shape [frames, height, width, channels].
        :return: Augmented video tensor.
        """
        # Ensure the tensor has the correct rank and shape
        # if tf.rank(video_tensor) == 3:  # Missing channel dimension
        #     video_tensor = tf.expand_dims(video_tensor, axis=-1)  # Add channel dimension

        # Assert the tensor has the correct rank
        video_tensor = tf.ensure_shape(video_tensor, [None, None, None, 1])  # Channels fixed to 1

        # Random horizontal flip
        video_tensor = tf.image.random_flip_left_right(video_tensor)

        # Random brightness adjustment
        video_tensor = tf.image.random_brightness(video_tensor, max_delta=0.2)

        # Random contrast adjustment
        video_tensor = tf.image.random_contrast(video_tensor, lower=0.8, upper=1.2)

        # Random cropping
        crop_fraction = 0.9  # Keep 90% of the original frame size
        original_shape = tf.shape(video_tensor)
        crop_size = tf.cast(crop_fraction * tf.cast(original_shape[1:3], tf.float16), tf.int32)
        video_tensor = tf.image.resize_with_crop_or_pad(video_tensor, crop_size[0], crop_size[1])
        video_tensor = tf.image.resize(video_tensor, [original_shape[1], original_shape[2]])

        # Explicitly set shape
        video_tensor = tf.ensure_shape(video_tensor, [MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1])
        video_tensor = tf.cast(video_tensor, tf.float16)
        return video_tensor


class DatasetPreparer:
    def __init__(self, video_directory: str, data_loader):
        self.video_directory = video_directory
        self.data_loader = data_loader

    def prepare_dataset(self):
        """
        Prepare a TensorFlow dataset that reads videos and subtitles, splits into training and validation sets,
        and applies padding, batching, and shuffling.
        """
        # Create the dataset from video files
        video_paths = f"{self.video_directory}/*/*.mpg"
        dataset = tf.data.Dataset.list_files(video_paths, shuffle=False)  # I disabled the default shuffle because I want to have more control over it

        # Shuffle the dataset (reshuffling ensures random selection each iteration)
        dataset = dataset.shuffle(buffer_size=100, reshuffle_each_iteration=True)

        # Converts video path to tensors for video and subtitles
        dataset = dataset.map(
            lambda path: DatasetPreparer.video_path_to_data(path, self.data_loader),
            num_parallel_calls=tf.data.AUTOTUNE
        )

        # Calculate dataset size
        dataset_size = dataset.cardinality().numpy()
        if dataset_size == tf.data.UNKNOWN_CARDINALITY or dataset_size == tf.data.INFINITE_CARDINALITY:
            raise ValueError("Dataset size is unknown or infinite. Ensure the dataset is finite and valid.")

        train_size = int(0.8 * dataset_size)  # 80% for training

        # Split into training and validation datasets
        train_dataset = dataset.take(train_size)
        val_dataset = dataset.skip(train_size)

        # Augment the training dataset
        # train_dataset = train_dataset.map(
        #     lambda video, subtitle: (Augmentor.augment_video(video), subtitle),
        #     num_parallel_calls=tf.data.AUTOTUNE
        # )

        # Batch and pad the datasets to ensure consistent shapes
        batch_size = 2
        padded_shapes = ([MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1], [None])
        train_dataset = train_dataset.padded_batch(
            batch_size=batch_size,
            padded_shapes=padded_shapes,
            padding_values=(tf.constant(0.0, dtype=tf.float16), tf.constant(0, dtype=tf.int8))
        )
        val_dataset = val_dataset.padded_batch(
            batch_size=batch_size,
            padded_shapes=padded_shapes,
            padding_values=(tf.constant(0.0, dtype=tf.float16), tf.constant(0, dtype=tf.int8))
        )

        # Prefetch datasets to prevent bottlenecks
        train_dataset = train_dataset.prefetch(tf.data.AUTOTUNE)
        val_dataset = val_dataset.prefetch(tf.data.AUTOTUNE)

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
        return tf.py_function(lambda x: DatasetPreparer.prepare_video_and_subtitles(x, data_loader),
                              [video_path], [tf.float16, tf.int8])
