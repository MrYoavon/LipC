# lip_reader.py
import tensorflow as tf

from .mouth_detection import MouthDetector
from constants import VIDEO_WIDTH, VIDEO_HEIGHT, num_to_char
from .lip_reading_model_utils import ctc_loss, CharacterErrorRate, WordErrorRate, decode_predictions

class LipReadingPipeline:
    def __init__(self, model_path, sequence_length=75):
        # Load the TensorFlow model (ensure model_path is correct)
        self.model = tf.keras.models.load_model(model_path, custom_objects={'ctc_loss': ctc_loss, "CharacterErrorRate": CharacterErrorRate, "WordErrorRate": WordErrorRate})
        # Buffer to hold a sequence of processed frames
        self.buffer = []
        self.sequence_length = sequence_length
        # Instantiate your mouth detector
        self.detector = MouthDetector()

    def process_frame(self, frame):
        """
        Process a single video frame:
          - Detect and crop the mouth using the provided detector.
          - Convert to a tensor, normalize, and convert to grayscale.
          - Append to buffer and if 75 frames are collected, run inference.
        :param frame: Raw BGR frame (as obtained from WebRTC)
        :return: Model prediction if sequence is complete; otherwise, None.
        """
        # Use your detector to get the mouth region; set the target size to your model's expected input size.
        cropped_mouth = self.detector.detect_and_crop_mouth(frame, target_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
        if cropped_mouth is None:
            # Skip this frame if no mouth is detected.
            return None
        
        # Convert the cropped image to a TensorFlow tensor and normalize to [0, 1]
        frame_tensor = tf.convert_to_tensor(cropped_mouth, dtype=tf.float16) / 255.0
        # Convert RGB image to grayscale (if your model expects a single channel)
        frame_tensor = tf.image.rgb_to_grayscale(frame_tensor)
        # Optionally, standardize the image
        frame_tensor = tf.image.per_image_standardization(frame_tensor)
        
        # Append the processed frame to the buffer
        self.buffer.append(frame_tensor)
        print(f"Buffer size: {len(self.buffer)}")
        
        # When enough frames are accumulated, form a batch and run inference
        if len(self.buffer) == self.sequence_length:
            # Shape will be (sequence_length, height, width, 1)
            sequence = tf.stack(self.buffer, axis=0)
            # Expand dimensions to add batch dimension: (1, sequence_length, height, width, 1)
            sequence = tf.expand_dims(sequence, axis=0)
            # Run model inference
            prediction = self.model.predict(sequence)

            decoded_predictions = decode_predictions(tf.cast(prediction, dtype=tf.float32))
            dense_decoded = tf.sparse.to_dense(decoded_predictions[0], default_value=-1)[0]

            final_output = tf.strings.reduce_join(
                [num_to_char(word).numpy().decode('utf-8') for word in dense_decoded.numpy() if word != -1]
            )
            # Clear the buffer for the next sequence
            self.buffer = []
            return final_output
        return None
