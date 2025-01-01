# data_processing/data_processing.py

# Standard library imports
import csv
import os

# Third-party imports
import cv2
import tensorflow as tf
import pandas as pd

# Local application imports
from data_processing.mouth_detection import MouthDetector

# Define vocabulary for character mapping
vocab = ["A", "U", "EE", "E", " "]
char_to_num = tf.keras.layers.StringLookup(vocabulary=vocab, oov_token="")
num_to_char = tf.keras.layers.StringLookup(vocabulary=char_to_num.get_vocabulary(), oov_token="", invert=True)


class DataLoader:
    def __init__(self, detector: MouthDetector):
        self.detector = detector

    def load_video(self, path: str) -> tf.Tensor:
        """
        Load video frames, apply mouth detection, convert to grayscale, and normalize.
        """
        cap = cv2.VideoCapture(path)
        frames = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame = self.detector.detect_and_crop_mouth(frame)  # Crop to mouth region
            if frame is not None:
                frame = tf.image.rgb_to_grayscale(frame)
                frames.append(frame)

        cap.release()
        if len(frames) == 0:
            raise ValueError(f"No valid frames found in video {path}")

        frames = tf.convert_to_tensor(frames)  # Convert list to tensor
        # print(frames.shape)
        return tf.image.per_image_standardization(frames)

    def load_subtitles(self, path: str) -> tf.Tensor:
        """
        Load subtitles and map them to character indices.
        """
        df = pd.read_csv(path, header=None, names=['start_time', 'end_time', 'subtitle'])
        tokens = []

        for _, row in df.iterrows():
            subtitle = row['subtitle'].strip().upper()
            if subtitle and subtitle != 'IDLE':
                tokens.extend(list(subtitle) + [' '])

        tokens = tokens[:-1]
        # Convert tokens to a tensor of strings
        token_tensor = tf.constant(tokens, dtype=tf.string)
        print("Token tensor shape:", token_tensor.shape)
        tokenized = tf.strings.unicode_split(token_tensor, input_encoding='UTF-8')
        print("Tokenized shape:", tf.strings.unicode_split(token_tensor, input_encoding='UTF-8'))
        return char_to_num(tokenized.flat_values)
        # return char_to_num(tf.reshape(tokenized, [-1]))

    def split_video_by_frames(self, video_path: str, subtitles_path: str, output_dir: str, max_frames=128):
        """
        Split video into chunks of `max_frames` or fewer, keeping word boundaries intact.
        """
        # Load video and subtitle data
        cap = cv2.VideoCapture(video_path)
        df = pd.read_csv(subtitles_path, header=None, names=['start_time', 'end_time', 'subtitle'])

        fps = cap.get(cv2.CAP_PROP_FPS)
        part_num = 1
        chunk_frames = []
        chunk_subtitles = []
        current_frame_count = 0
        start_time = 0

        for index, row in df.iterrows():
            start_ms, end_ms, subtitle = row['start_time'], row['end_time'], row['subtitle']

            # Convert start and end times to frame indices
            start_frame = int((start_ms / 1000) * fps)
            end_frame = int((end_ms / 1000) * fps)
            word_frame_count = end_frame - start_frame

            if word_frame_count > max_frames:
                print(f"Warning: Subtitle '{subtitle}' spans more than {max_frames} frames. Skipping.")
                continue

            if current_frame_count + word_frame_count > max_frames:
                # Save current chunk if adding this word exceeds the max frame count
                self.save_chunk(chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps)
                part_num += 1
                chunk_frames = []
                chunk_subtitles = []
                current_frame_count = 0
                start_time = start_ms  # New start time for the new chunk

            # Add word frames and subtitle
            chunk_subtitles.append((start_ms - start_time, end_ms - start_time, subtitle))

            # Extract frames for this word
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            for _ in range(word_frame_count):
                ret, frame = cap.read()
                if not ret:
                    break
                chunk_frames.append(frame)
                current_frame_count += 1

        # Save the last chunk
        if chunk_frames:
            self.save_chunk(chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps)

        cap.release()

    def save_chunk(self, chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps):
        """
        Save a chunk of frames and its corresponding subtitles.
        """
        # Define output video and CSV paths
        file_name = os.path.splitext(os.path.basename(video_path))[0]
        output_video_path = os.path.join(output_dir, "videos", f"{file_name}_{part_num}.mp4")
        output_csv_path = os.path.join(output_dir, "subtitles", f"{file_name}_{part_num}.csv")

        # Save the video chunk
        height, width, _ = chunk_frames[0].shape
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
        for frame in chunk_frames:
            out.write(frame)
        out.release()

        # Save the CSV chunk with adjusted timestamps
        with open(output_csv_path, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            for start_ms, end_ms, subtitle in chunk_subtitles:
                writer.writerow([start_ms, end_ms, subtitle])

    def process_all_videos(self, video_directory, subtitles_directory, output_directory):
        """
        Process each video in `video_directory` along with subtitles, split them into chunks, and save them.
        """
        # Create output directories if they don't exist
        os.makedirs(output_directory, exist_ok=True)
        os.makedirs(os.path.join(output_directory, "videos"), exist_ok=True)
        os.makedirs(os.path.join(output_directory, "subtitles"), exist_ok=True)

        for video_file in os.listdir(video_directory):
            if video_file.endswith(".mp4"):
                video_path = os.path.join(video_directory, video_file)
                subtitle_path = os.path.join(subtitles_directory, f"{os.path.splitext(video_file)[0]}.csv")

                # Define preprocessed output paths
                processed_video_path = os.path.join(output_directory, "videos", f"{os.path.splitext(video_file)[0]}_1.mp4")
                processed_subtitle_path = os.path.join(output_directory, "subtitles", f"{os.path.splitext(video_file)[0]}_1.csv")

                # Skip processing if the preprocessed files already exist
                if os.path.exists(processed_video_path) and os.path.exists(processed_subtitle_path):
                    print(f"Skipping {video_file}: Preprocessed files already exist.")
                    continue

                # Process video and subtitles
                try:
                    print(f"Processing video: {video_file}")
                    self.split_video_by_frames(video_path, subtitle_path, output_directory)
                    print(f"Successfully processed: {video_file}")

                except FileNotFoundError as e:
                    print(f"Error: Missing file for {video_file} — {e}")
                except Exception as e:
                    print(f"Error processing {video_file}: {e}")


class PreProcessor:
    @staticmethod
    def prepare_video_and_subtitles(video_path: tf.Tensor, data_loader: DataLoader):
        """
        Prepares video and subtitle tensors.
        """
        video_path = video_path.numpy().decode('utf-8')
        base_dir = os.path.dirname(os.path.dirname(video_path))
        file_name = os.path.splitext(os.path.basename(video_path))[0]

        subtitles_path = os.path.join(base_dir, 'subtitles', f'{file_name}.csv')
        video_tensor = data_loader.load_video(video_path)
        subtitle_tensor = data_loader.load_subtitles(subtitles_path)

        return video_tensor, subtitle_tensor

    @staticmethod
    def mappable_fn(video_path: tf.Tensor, data_loader: DataLoader):
        """
        A wrapper function that maps video path to frames and alignments.
        """
        return tf.py_function(lambda x: PreProcessor.prepare_video_and_subtitles(x, data_loader), [video_path], [tf.float32, tf.int64])


class Augmentor:
    @staticmethod
    def augment_video(frames: tf.Tensor) -> tf.Tensor:
        """
        Augment video frames by applying transformations such as flipping and concatenating.
        """
        if frames.shape.rank == 5:
            # Apply flipping to each frame in the video sequence
            flipped_frames = tf.map_fn(lambda x: tf.image.flip_left_right(x), frames)
        elif frames.shape.rank == 4:
            # Apply flipping directly if frames already have 4D shape
            flipped_frames = tf.image.flip_left_right(frames)
        else:
            raise ValueError("Expected frames to have 4 or 5 dimensions, got shape: {}".format(frames.shape))

        return flipped_frames


class DatasetPreparer:
    def __init__(self, video_directory: str, data_loader: DataLoader):
        self.video_directory = video_directory
        self.data_loader = data_loader

    def prepare_dataset(self):
        """
        Prepare a TensorFlow dataset that reads videos and subtitles, splits into training and validation sets,
        and applies padding, batching, and shuffling.
        """
        # Create the dataset from video files
        dataset = tf.data.Dataset.list_files(f"{self.video_directory}/*.mp4")

        # Shuffle the dataset (reshuffling ensures random selection each iteration)
        dataset = dataset.shuffle(buffer_size=100, reshuffle_each_iteration=True)

        # Map preprocessing function (converts video path to tensors for video and subtitles)
        dataset = dataset.map(
            lambda path: PreProcessor.mappable_fn(path, self.data_loader),
            num_parallel_calls=tf.data.AUTOTUNE
        )

        # Calculate dataset size
        dataset_size = dataset.cardinality().numpy()
        train_size = int(0.8 * dataset_size)  # 80% for training

        # Split into training and validation datasets
        train_dataset = dataset.take(train_size)
        val_dataset = dataset.skip(train_size)

        # Batch and pad the datasets to ensure consistent shapes
        train_dataset = train_dataset.padded_batch(
            batch_size=1,  # Customize batch size as needed
            padded_shapes=([160, 100, 250, 1], [32]),  # Pad video and subtitles
            padding_values=(0.0, tf.constant(0, dtype=tf.int64))  # Pad video with zeros and labels with 0
        )
        val_dataset = val_dataset.padded_batch(
            batch_size=1,
            padded_shapes=([160, 100, 250, 1], [32]),
            padding_values=(0.0, tf.constant(0, dtype=tf.int64))
        )

        # Prefetch datasets to prevent bottlenecks
        train_dataset = train_dataset.prefetch(tf.data.AUTOTUNE)
        val_dataset = val_dataset.prefetch(tf.data.AUTOTUNE)

        return train_dataset, val_dataset
