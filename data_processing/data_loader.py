import os

import cv2
import tensorflow as tf
import pandas as pd
import csv

from constants import char_to_num, MAX_FRAMES
from data_processing.mouth_detection import MouthDetector


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
            with tf.device('/CPU:0'):
                if frame is not None:
                    # Convert the OpenCV image (NumPy array) to a TensorFlow tensor
                    frame_tensor = tf.convert_to_tensor(frame, dtype=tf.float16)

                    # Normalize the values to range [0, 1]
                    frame_tensor = frame_tensor / 255.0

                    frame = tf.image.rgb_to_grayscale(frame_tensor)
                    frames.append(frame)

        cap.release()
        if len(frames) == 0:
            raise ValueError(f"No valid frames found in video {path}")

        frames = tf.convert_to_tensor(frames, dtype=tf.float16)  # Convert list to tensor
        return tf.cast(tf.image.per_image_standardization(frames), dtype=tf.float16)

    def load_subtitles(self, path: str) -> tf.Tensor:
        """
        Load subtitles and map them to character indices.
        """
        df = pd.read_csv(path, header=None, names=['start_time', 'end_time', 'subtitle'])
        tokens = []

        for _, row in df.iterrows():
            subtitle = row['subtitle'].strip().lower()
            if subtitle and (subtitle != 'idle' or subtitle != 'sil'):
                tokens.extend(list(subtitle) + [' '])

        with tf.device('/CPU:0'):
            tokens = tokens[:-1]  # Remove the last space
            # Convert tokens to a tensor of strings
            token_tensor = tf.constant(tokens, dtype=tf.string)
            tokenized = tf.strings.unicode_split(token_tensor, input_encoding='UTF-8')
            # return char_to_num(tokenized.flat_values)
            return tf.cast(char_to_num(tf.reshape(tokenized, [-1])), tf.int8)

    # def split_video_by_frames(self, video_path: str, subtitles_path: str, output_dir: str):
    #     """
    #     Split video into chunks of `MAX_FRAMES` or fewer, filling shorter chunks with repeated frames
    #     and adjusting subtitle timings accordingly.
    #     """
    #     # Load video and subtitle data
    #     cap = cv2.VideoCapture(video_path)
    #     df = pd.read_csv(subtitles_path, header=None, names=['start_time', 'end_time', 'subtitle'])
    #
    #     fps = cap.get(cv2.CAP_PROP_FPS)
    #     part_num = 1
    #     chunk_frames = []
    #     chunk_subtitles = []
    #     current_frame_count = 0
    #     start_time = 0
    #
    #     for index, row in df.iterrows():
    #         start_ms, end_ms, subtitle = row['start_time'], row['end_time'], row['subtitle']
    #
    #         # Convert start and end times to frame indices
    #         start_frame = int((start_ms / 1000) * fps)
    #         end_frame = int((end_ms / 1000) * fps)
    #         word_frame_count = end_frame - start_frame
    #
    #         if word_frame_count > MAX_FRAMES:
    #             print(f"Warning: Subtitle '{subtitle}' spans more than {MAX_FRAMES} frames. Skipping.")
    #             continue
    #
    #         if current_frame_count + word_frame_count > MAX_FRAMES:
    #             # Save current chunk
    #             self.save_chunk(chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps)
    #             part_num += 1
    #             chunk_frames = []
    #             chunk_subtitles = []
    #             current_frame_count = 0
    #             start_time = start_ms  # New start time for the new chunk
    #             continue
    #
    #         # Add word frames and subtitle
    #         chunk_subtitles.append((start_ms - start_time, end_ms - start_time, subtitle))
    #
    #         # Extract frames for this word
    #         cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    #         for _ in range(word_frame_count):
    #             ret, frame = cap.read()
    #             if not ret:
    #                 break
    #             chunk_frames.append(frame)
    #             current_frame_count += 1
    #
    #     # Save the last chunk
    #     if chunk_frames:
    #         self.save_chunk(chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps)
    #
    #     cap.release()
    #
    # def save_chunk(self, chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps):
    #     """
    #     Save a chunk of frames and its corresponding subtitles.
    #     """
    #     # Define output video and CSV paths
    #     file_name = os.path.splitext(os.path.basename(video_path))[0]
    #     output_video_path = os.path.join(output_dir, "videos", f"{file_name}_{part_num}.mp4")
    #     output_csv_path = os.path.join(output_dir, "transcriptions", f"{file_name}_{part_num}.csv")
    #
    #     # Save the video chunk
    #     height, width, _ = chunk_frames[0].shape
    #     fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    #     out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    #     for frame in chunk_frames:
    #         out.write(frame)
    #     out.release()
    #
    #     # Save the CSV chunk with adjusted timestamps
    #     with open(output_csv_path, mode='w', newline='') as csvfile:
    #         writer = csv.writer(csvfile)
    #         for start_ms, end_ms, subtitle in chunk_subtitles:
    #             writer.writerow([start_ms, end_ms, subtitle])
    #
    # def load_all_data(self, dataset_type, video_directory, subtitles_directory, output_directory):
    #     os.makedirs(output_directory, exist_ok=True)
    #     os.makedirs(os.path.join(output_directory, "videos"), exist_ok=True)
    #     os.makedirs(os.path.join(output_directory, "transcriptions"), exist_ok=True)
    #
    #     if dataset_type == "A_U_EE_E":
    #         videos = [os.path.join(video_directory, f) for f in os.listdir(video_directory) if f.endswith(".mp4")]
    #         transcriptions = [
    #             os.path.join(subtitles_directory, f) for f in os.listdir(subtitles_directory) if f.endswith(".csv")
    #         ]
    #     elif dataset_type == "GRID_corpus":
    #         videos = []
    #         transcriptions = []
    #         for person_folder in os.listdir(video_directory):
    #             person_video_dir = os.path.join(video_directory, person_folder)
    #             if os.path.isdir(person_video_dir):
    #                 videos += [
    #                     os.path.join(person_video_dir, f)
    #                     for f in os.listdir(person_video_dir)
    #                     if f.endswith(".mpg")
    #                 ]
    #             person_transcription_dir = os.path.join(subtitles_directory, person_folder)
    #             if os.path.isdir(person_transcription_dir):
    #                 transcriptions += [
    #                     os.path.join(person_transcription_dir, f)
    #                     for f in os.listdir(person_transcription_dir)
    #                     if f.endswith(".csv")
    #                 ]
    #     else:
    #         raise ValueError(f"Unknown dataset type: {dataset_type}")
    #
    #     for video_file in videos:
    #         file_name = os.path.splitext(os.path.basename(video_file))[0]
    #         # print(f"Processing video: {video_file}")
    #         subtitle_file = next(
    #             (s for s in transcriptions if os.path.splitext(os.path.basename(s))[0] == file_name), None
    #         )
    #
    #         if subtitle_file is None:
    #             print(f"Warning: No matching subtitle file found for video {video_file}")
    #             continue
    #
    #         try:
    #             # print(f"Processing video: {video_file}")
    #             # self.split_video_by_frames(video_file, subtitle_file, output_directory)
    #             # print(f"Successfully processed: {video_file}")
    #         except Exception as e:
    #             print(f"Error processing {video_file}: {e}")