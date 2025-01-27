import imageio
import tensorflow as tf
import numpy as np


def generate_gif(dataset, num_to_char):
    # Fetch a batch of data
    data_iterator = dataset.as_numpy_iterator()
    video_frames, subtitle_tokens = data_iterator.next()

    # Process frames for saving as a GIF
    processed_frames = []
    for frame in video_frames[0]:  # Access the first video in the batch
        # Convert normalized frame to uint8
        frame = (frame.numpy() * 255).astype(np.uint8)

        # Check and reshape if necessary
        if frame.shape[-1] == 1:  # Grayscale with singleton dimension
            frame = np.squeeze(frame, axis=-1)  # Remove the last dimension for display

        processed_frames.append(frame)

    # Save frames as GIF
    imageio.mimsave("./animation.gif", processed_frames, fps=30)

    # Decode subtitle tokens to text for verification
    decoded_subtitles = tf.strings.reduce_join(
        [tf.compat.as_str_any(x) for x in num_to_char(subtitle_tokens[0]).numpy()])
    print("Decoded Subtitles:", decoded_subtitles.numpy().decode('utf-8'))