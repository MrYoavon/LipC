import cv2
import tensorflow as tf
import pandas as pd

from model.constants import char_to_num
from model.data_processing.mouth_detection import MouthDetector


###########################################
#              DataLoader Class           #
###########################################

class DataLoader:
    def __init__(self, detector: MouthDetector):
        """
        Initialize the DataLoader with a MouthDetector instance.

        Args:
            detector (MouthDetector): An instance of MouthDetector for mouth region detection.
        """
        self.detector = detector

    def load_video(self, path: str) -> tf.Tensor:
        """
        Load video frames, apply mouth detection and cropping, convert to grayscale,
        normalize, and standardize the frames.

        Args:
            path (str): File path to the video.

        Returns:
            tf.Tensor: A 4D tensor (batch, height, width, channels) of processed video frames.

        Raises:
            ValueError: If no valid frames are found or the tensor shape is not as expected.
        """
        with tf.device('/CPU:0'):
            cap = cv2.VideoCapture(path)
            frames = []

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                # Crop the frame to the mouth region using the detector.
                frame = self.detector.detect_and_crop_mouth(frame)
                if frame is not None:
                    # Convert frame (NumPy array) to TensorFlow tensor and normalize.
                    frame_tensor = tf.convert_to_tensor(frame, dtype=tf.float16) / 255.0
                    # Convert to grayscale.
                    frame = tf.image.rgb_to_grayscale(frame_tensor)
                    frames.append(frame)

            cap.release()
            if len(frames) == 0:
                raise ValueError(f"No valid frames found in video {path}")

            frames = tf.convert_to_tensor(frames, dtype=tf.float16)

            # Verify tensor has 4 dimensions: [batch, height, width, channels]
            if len(frames.shape) != 4:
                raise ValueError(f"Expected 4D tensor for frames, got shape: {frames.shape}")

            # Standardize each image and cast to float16.
            return tf.cast(tf.image.per_image_standardization(frames), dtype=tf.float16)

    def load_subtitles(self, path: str) -> tf.Tensor:
        """
        Load subtitles from a CSV file and map them to character indices.

        The CSV file is expected to have no header and three columns:
        start_time, end_time, and subtitle.

        Args:
            path (str): File path to the subtitles CSV.

        Returns:
            tf.Tensor: A tensor of subtitle tokens mapped to character indices.

        Raises:
            ValueError: If the token list is empty.
        """
        df = pd.read_csv(path, header=None, names=['start_time', 'end_time', 'subtitle'])
        tokens = []

        for _, row in df.iterrows():
            subtitle = row['subtitle'].strip().lower()
            # Skip empty or specific unwanted tokens.
            if subtitle and subtitle not in ['sil', 'idle']:
                tokens.extend(list(subtitle) + [' '])

        if not tokens:
            raise ValueError("Token list is empty. Check subtitle content.")

        with tf.device('/CPU:0'):
            tokens = tokens[:-1]  # Remove the trailing space.
            token_tensor = tf.constant(tokens, dtype=tf.string)
            tokenized = tf.strings.unicode_split(token_tensor, input_encoding='UTF-8')
            flattened = tf.reshape(tokenized, [-1])
            return tf.cast(char_to_num(flattened), tf.int8)


###########################################
#        Additional / Deprecated Methods  #
###########################################

# The following methods are commented out. They provide functionality for splitting videos
# into chunks based on frame count and adjusting subtitle timings. Uncomment and adjust as needed.
# Used for A U EE E dataset.

#    def split_video_by_frames(self, video_path: str, subtitles_path: str, output_dir: str):
#        """
#        Split a video into chunks of `MAX_FRAMES` or fewer, filling shorter chunks with repeated frames
#        and adjusting subtitle timings accordingly.
#        """
#        cap = cv2.VideoCapture(video_path)
#        df = pd.read_csv(subtitles_path, header=None, names=['start_time', 'end_time', 'subtitle'])
#        fps = cap.get(cv2.CAP_PROP_FPS)
#        part_num = 1
#        chunk_frames = []
#        chunk_subtitles = []
#        current_frame_count = 0
#        start_time = 0
#
#        for index, row in df.iterrows():
#            start_ms, end_ms, subtitle = row['start_time'], row['end_time'], row['subtitle']
#            start_frame = int((start_ms / 1000) * fps)
#            end_frame = int((end_ms / 1000) * fps)
#            word_frame_count = end_frame - start_frame
#
#            if word_frame_count > MAX_FRAMES:
#                print(f"Warning: Subtitle '{subtitle}' spans more than {MAX_FRAMES} frames. Skipping.")
#                continue
#
#            if current_frame_count + word_frame_count > MAX_FRAMES:
#                self.save_chunk(chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps)
#                part_num += 1
#                chunk_frames = []
#                chunk_subtitles = []
#                current_frame_count = 0
#                start_time = start_ms
#                continue
#
#            chunk_subtitles.append((start_ms - start_time, end_ms - start_time, subtitle))
#            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
#            for _ in range(word_frame_count):
#                ret, frame = cap.read()
#                if not ret:
#                    break
#                chunk_frames.append(frame)
#                current_frame_count += 1
#
#        if chunk_frames:
#            self.save_chunk(chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps)
#
#        cap.release()
#
#    def save_chunk(self, chunk_frames, chunk_subtitles, video_path, output_dir, part_num, fps):
#        """
#        Save a chunk of frames and corresponding subtitles.
#        """
#        file_name = os.path.splitext(os.path.basename(video_path))[0]
#        output_video_path = os.path.join(output_dir, "videos", f"{file_name}_{part_num}.mp4")
#        output_csv_path = os.path.join(output_dir, "transcriptions", f"{file_name}_{part_num}.csv")
#
#        height, width, _ = chunk_frames[0].shape
#        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
#        out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
#        for frame in chunk_frames:
#            out.write(frame)
#        out.release()
#
#        with open(output_csv_path, mode='w', newline='') as csvfile:
#            writer = csv.writer(csvfile)
#            for start_ms, end_ms, subtitle in chunk_subtitles:
#                writer.writerow([start_ms, end_ms, subtitle])
#
#    def load_all_data(self, dataset_type, video_directory, subtitles_directory, output_directory):
#        os.makedirs(output_directory, exist_ok=True)
#        os.makedirs(os.path.join(output_directory, "videos"), exist_ok=True)
#        os.makedirs(os.path.join(output_directory, "transcriptions"), exist_ok=True)
#
#        if dataset_type == "A_U_EE_E":
#            videos = [os.path.join(video_directory, f) for f in os.listdir(video_directory) if f.endswith(".mp4")]
#            transcriptions = [os.path.join(subtitles_directory, f) for f in os.listdir(subtitles_directory) if f.endswith(".csv")]
#        elif dataset_type == "GRID_corpus":
#            videos = []
#            transcriptions = []
#            for person_folder in os.listdir(video_directory):
#                person_video_dir = os.path.join(video_directory, person_folder)
#                if os.path.isdir(person_video_dir):
#                    videos += [os.path.join(person_video_dir, f) for f in os.listdir(person_video_dir) if f.endswith(".mpg")]
#                person_transcription_dir = os.path.join(subtitles_directory, person_folder)
#                if os.path.isdir(person_transcription_dir):
#                    transcriptions += [os.path.join(person_transcription_dir, f) for f in os.listdir(person_transcription_dir) if f.endswith(".csv")]
#        else:
#            raise ValueError(f"Unknown dataset type: {dataset_type}")
#
#        for video_file in videos:
#            file_name = os.path.splitext(os.path.basename(video_file))[0]
#            subtitle_file = next((s for s in transcriptions if os.path.splitext(os.path.basename(s))[0] == file_name), None)
#            if subtitle_file is None:
#                print(f"Warning: No matching subtitle file found for video {video_file}")
#                continue
#            try:
#                # self.split_video_by_frames(video_file, subtitle_file, output_directory)
#            except Exception as e:
#                print(f"Error processing {video_file}: {e}")
