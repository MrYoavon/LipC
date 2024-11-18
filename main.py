# main.py

import tensorflow as tf
print(tf.__version__)
print("Is ROCm enabled:", tf.test.is_built_with_rocm())
import os
os.environ['TF_CUDNN_WORKSPACE_LIMIT_IN_MB'] = '19406'

# Set memory growth for GPUs
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
    try:
        # Limit TensorFlow to only use the first GPU
        tf.config.experimental.set_visible_devices(gpus[0], 'GPU')

        # Enable memory growth
        tf.config.experimental.set_memory_growth(gpus[0], True)
    except RuntimeError as e:
        print(f"Error setting GPU configuration: {e}")


import numpy as np
import imageio

from data_processing.data_processing import DatasetPreparer, DataLoader, num_to_char, char_to_num
from data_processing.mouth_detection import MouthDetector
from model.model import LipReadingModel


def main():
    base_dir = "data/A_U_EE_E/temp/"
    original_video_dir = base_dir + "videos"
    original_subtitle_dir = base_dir + "subtitles"
    output_dir = base_dir + "separated"
    video_dir = output_dir + "/videos"
    subtitle_dir = output_dir + "/subtitles"

    mouth_detector = MouthDetector()

    # Instantiate DataLoader (or appropriate class) and DatasetPreparer
    data_loader = DataLoader(detector=mouth_detector)  # Initialize with any necessary parameters

    data_loader.process_all_videos(original_video_dir, original_subtitle_dir, output_dir)

    dataset_preparer = DatasetPreparer(video_directory=video_dir, data_loader=data_loader)  # Provide data_loader here

    dataset = dataset_preparer.prepare_dataset()

    # Fetch a batch of data
    data_iterator = dataset.as_numpy_iterator()
    video_frames, subtitle_tokens = data_iterator.next()

    # # Process frames for saving as a GIF
    # processed_frames = []
    # for frame in video_frames[0]:  # Access the first video in the batch
    #     # Convert normalized frame to uint8
    #     frame = (frame.numpy() * 255).astype(np.uint8)
    #
    #     # Check and reshape if necessary
    #     if frame.shape[-1] == 1:  # Grayscale with singleton dimension
    #         frame = np.squeeze(frame, axis=-1)  # Remove the last dimension for display
    #
    #     processed_frames.append(frame)
    #
    # # Save frames as GIF
    # imageio.mimsave("./animation.gif", processed_frames, fps=30)

    # # Decode subtitle tokens to text for verification
    # decoded_subtitles = tf.strings.reduce_join(
    #     [tf.compat.as_str_any(x) for x in num_to_char(subtitle_tokens[0]).numpy()])
    # print("Decoded Subtitles:", decoded_subtitles.numpy().decode('utf-8'))


    model = LipReadingModel(char_to_num.vocabulary_size())

    print("AAA")
    yhat = model.predict(video_frames)
    print("BBB")
    print(tf.strings.reduce_join([num_to_char(tf.argmax(x)) for x in yhat[0]]))
    print("CCC")
    print(model.input_shape)


if __name__ == "__main__":
    main()
