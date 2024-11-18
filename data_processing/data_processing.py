# data_processing/data_processing.py
import csv
import os
import cv2
import tensorflow as tf
import pandas as pd
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

        # Normalize frames
        # mean = tf.math.reduce_mean(frames)
        # std = tf.math.reduce_std(tf.cast(frames, tf.float32))
        # return tf.cast((frames - mean), tf.float32) / std

        return tf.image.per_image_standardization(frames)

        # mean = tf.math.reduce_mean(frames, axis=[0, 1, 2], keepdims=True)
        # std = tf.math.reduce_std(tf.cast(frames, tf.float32), axis=[0, 1, 2], keepdims=True)
        # frames = tf.cast(frames, tf.float32)
        # normalized_frames = (frames - mean) / std
        # return normalized_frames

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
        tokenized = tf.strings.unicode_split(token_tensor, input_encoding='UTF-8')
        return char_to_num(tf.reshape(tokenized, [-1]))

    def split_video_by_frames(self, video_path, subtitles_path, output_dir, max_frames=128):
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
        Process each video in the video_directory, split it, and generate output.
        """
        for video_file in os.listdir(video_directory):
            if video_file.endswith(".mp4"):
                video_path = os.path.join(video_directory, video_file)
                subtitle_path = os.path.join(subtitles_directory, f"{os.path.splitext(video_file)[0]}.csv")
                self.split_video_by_frames(video_path, subtitle_path, output_directory)


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

        # Concatenate original and flipped frames along the batch dimension
        return tf.concat([frames, flipped_frames], axis=0)


class DatasetPreparer:
    def __init__(self, video_directory: str, data_loader: DataLoader):
        self.video_directory = video_directory
        self.data_loader = data_loader

    def prepare_dataset(self) -> tf.data.Dataset:
        """
        Prepare a dataset that reads videos and subtitles, applies augmentations, and batches data.
        """
        dataset = tf.data.Dataset.list_files(f"{self.video_directory}/*.mp4")
        dataset = dataset.shuffle(100)
        dataset = dataset.map(lambda path: PreProcessor.mappable_fn(path, self.data_loader))

        # 5400 frames in each training video (assuming 3 minutes 30 fps)
        # 240 tokens in each video (120 letters plus space token to separate)
        dataset = dataset.padded_batch(2, padded_shapes=([128, None, None, None], [12]))
        dataset = dataset.prefetch(tf.data.AUTOTUNE)

        dataset = dataset.map(lambda f, a: (Augmentor.augment_video(f), a))

        return dataset
