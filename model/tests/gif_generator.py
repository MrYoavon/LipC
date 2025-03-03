import imageio
import tensorflow as tf
import numpy as np

def generate_gif(dataset: tf.data.Dataset, num_to_char) -> None:
    """
    Generate an animated GIF from the first video in a dataset batch and decode its subtitles.

    This function retrieves a batch from the provided dataset, processes the frames from the first video
    by converting normalized values to uint8 and removing unnecessary dimensions for grayscale images,
    and then saves the frames as an animated GIF. It also decodes the subtitle tokens using the provided
    `num_to_char` mapping and prints the resulting text.

    Args:
        dataset (tf.data.Dataset): A dataset yielding batches of (video_frames, subtitle_tokens).
                                   video_frames should have shape [batch, frames, height, width, channels]
                                   with normalized values in [0, 1].
        num_to_char: A mapping function or layer that converts numeric subtitle tokens into characters.
    """
    # Fetch a batch of data from the dataset
    data_iterator = dataset.as_numpy_iterator()
    video_frames, subtitle_tokens = data_iterator.next()

    # Process frames for saving as a GIF (using the first video in the batch)
    processed_frames = []
    for frame in video_frames[0]:
        # Convert normalized frame (float values in [0, 1]) to uint8 format
        frame_uint8 = (frame.numpy() * 255).astype(np.uint8)

        # If the frame is grayscale with a singleton channel, remove the extra dimension
        if frame_uint8.shape[-1] == 1:
            frame_uint8 = np.squeeze(frame_uint8, axis=-1)

        processed_frames.append(frame_uint8)

    # Save the processed frames as an animated GIF with 30 fps
    imageio.mimsave("./animation.gif", processed_frames, fps=30)

    # Decode the subtitle tokens to text for verification
    # Convert the first video's subtitle tokens to characters using the provided mapping
    decoded_chars = num_to_char(subtitle_tokens[0]).numpy()
    # Join the characters to form the decoded subtitle string
    decoded_subtitles = tf.strings.reduce_join(
        [tf.compat.as_str_any(x) for x in decoded_chars]
    )
    print("Decoded Subtitles:", decoded_subtitles.numpy().decode('utf-8'))
