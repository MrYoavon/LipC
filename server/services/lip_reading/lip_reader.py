# lip_reader.py
import asyncio
import tensorflow as tf

from services.lip_reading.mouth_detection import MouthDetector
from constants import VIDEO_WIDTH, VIDEO_HEIGHT, num_to_char
from services.lip_reading.lip_reading_model_utils import (
    ctc_loss,
    CharacterErrorRate,
    WordErrorRate,
    decode_predictions
)

_MODEL = None
# Ensures only one model load in concurrent scenarios
_MODEL_LOCK = asyncio.Lock()


async def get_lip_model() -> tf.keras.Model:
    """
    Lazily load and cache the lip-reading TensorFlow model.

    This coroutine loads the model from disk only once, even if called
    concurrently, by using an async lock.

    Returns:
        tf.keras.Model: The loaded lip-reading model with custom objects.

    Raises:
        Exception: If model loading fails.
    """
    global _MODEL
    if _MODEL is None:
        async with _MODEL_LOCK:
            if _MODEL is None:    # second check after acquiring the lock
                _MODEL = await asyncio.to_thread(
                    tf.keras.models.load_model,
                    "models/final_model.keras",
                    custom_objects={
                        'ctc_loss': ctc_loss,
                        'CharacterErrorRate': CharacterErrorRate,
                        'WordErrorRate': WordErrorRate,
                    },
                )
    return _MODEL


class LipReadingPipeline:
    """
    Pipeline for frame-by-frame lip-reading inference.

    Buffers a fixed-length sequence of preprocessed frames, runs
    the model when the buffer is full, decodes CTC output, and resets buffer.
    """

    def __init__(self, shared_model: tf.Keras.Model, sequence_length: int = 75):
        """
        Initialize the lip-reading pipeline.

        Args:
            shared_model (tf.keras.Model): Pre-loaded TensorFlow model instance.
            sequence_length (int): Number of frames per inference cycle.
        """
        self.model = shared_model
        self.buffer = []
        self.sequence_length = sequence_length
        self.detector = MouthDetector()

    def process_frame(self, frame: tf.Tensor) -> str | None:
        """
        Process a single BGR frame and perform inference when buffer is ready.

        Workflow:
            1. Detect and crop the mouth region.
            2. Convert to grayscale, normalize, and standardize.
            3. Append to internal buffer.
            4. When buffer length == sequence_length:
               - Stack frames, run model.predict
               - Decode CTC output to text
               - Clear buffer and return text

        Args:
            frame (numpy.ndarray): Raw BGR image from video source.

        Returns:
            str | None: Decoded text prediction if sequence complete; otherwise None.
        """
        # 1. Detect and crop mouth
        cropped_mouth = self.detector.detect_and_crop_mouth(
            frame, target_size=(VIDEO_WIDTH, VIDEO_HEIGHT))
        if cropped_mouth is None:
            return None

        # 2. Preprocess
        frame_tensor = tf.convert_to_tensor(
            cropped_mouth, dtype=tf.float16) / 255.0
        frame_tensor = tf.image.rgb_to_grayscale(frame_tensor)
        frame_tensor = self.standardise(frame_tensor)
        self.buffer.append(frame_tensor)

        # 3. Inference on full buffer
        if len(self.buffer) == self.sequence_length:
            # Shape will be (sequence_length, height, width, 1)
            sequence = tf.stack(self.buffer, axis=0)
            # Expand dimensions to add batch dimension: (1, sequence_length, height, width, 1)
            sequence = tf.expand_dims(sequence, axis=0)
            # Run model inference
            prediction = self.model.predict(sequence)

            # 4. Decode predictions
            decoded = decode_predictions(
                tf.cast(prediction, tf.float32), beam_width=25
            )
            dense = tf.sparse.to_dense(decoded[0], default_value=-1)[0]
            text = ''.join(
                num_to_char(idx).numpy().decode('utf-8')
                for idx in dense.numpy() if idx != -1
            )
            self.buffer.clear()
            return text
        return None

    def standardise(self, image: tf.Tensor) -> tf.Tensor:
        """
        Standardize image tensor to zero mean and unit variance.

        Args:
            image (tf.Tensor): Grayscale image tensor, shape [H, W, 1].

        Returns:
            tf.Tensor: Standardized tensor of same shape.
        """
        image = tf.cast(image, tf.float32)
        mean = tf.reduce_mean(image)
        std = tf.math.reduce_std(image)
        # same safeguard that per_image_standardization uses,
        # but with *dynamic* size
        num_pixels = tf.size(image, out_type=tf.float32)
        std = tf.maximum(std, 1.0 / tf.sqrt(num_pixels))
        return (image - mean) / std
