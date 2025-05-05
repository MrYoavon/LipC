# main.py

# fmt: off
import os
import random

# Third-party imports
import tensorflow as tf
import numpy as np

# # TensorFlow threading configuration
# tf.config.threading.set_intra_op_parallelism_threads(32)
# tf.config.threading.set_inter_op_parallelism_threads(32)
# tf.config.run_functions_eagerly(True)  # Uncomment for debugging

# Set random seeds for reproducibility
seed = 42
tf.random.set_seed(seed)
np.random.seed(seed)
random.seed(seed)


##############################
# Device and Precision Setup #
##############################

def configure_devices():
    """
    Configure TensorFlow to use GPU if available, fallback to CPU otherwise.
    """
    try:
        # Detect GPUs
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            # Enable memory growth and select the first GPU
            tf.config.experimental.set_memory_growth(gpus[0], True)
            tf.config.experimental.set_visible_devices(gpus[0], 'GPU')
            print(f"Using GPU: {gpus[0]}")
        else:
            print("No GPU detected, using CPU.")

        # Log TensorFlow and CUDA/ROCm information
        print(f"TensorFlow Version: {tf.__version__}")
        print(f"Is CUDA enabled: {tf.test.is_built_with_cuda()}")
        print(f"Is ROCm enabled: {tf.test.is_built_with_rocm()}")
    except RuntimeError as e:
        print(f"Error configuring TensorFlow devices: {e}")


# Configure devices on startup
configure_devices()

# Set mixed precision policy for performance
from tensorflow.keras import mixed_precision

mixed_precision.set_global_policy('mixed_float16')

##############################
# Local Application Imports  #
##############################

from core_model.training import ctc_loss
from model.utils.model_utils import decode_predictions
from model.data_processing.mouth_detection import MouthDetector
from model.data_processing.data_processing import DatasetPreparer
from model.data_processing.data_loader import DataLoader
from core_model.model import LipReadingModel
from constants import char_to_num, num_to_char

# fmt: on


##############################
# Model Training Function    #
##############################

def train_model():
    """
    Train the lip-reading model and save it to disk.
    """
    base_dir = "model/data/GRID_corpus/"
    video_dir = os.path.join(base_dir, "videos")

    # Initialize components for data preparation
    mouth_detector = MouthDetector()
    data_loader = DataLoader(detector=mouth_detector)
    dataset_preparer = DatasetPreparer(
        video_directory=video_dir, data_loader=data_loader)
    train_dataset, val_dataset = dataset_preparer.prepare_dataset(
        save_tfrecords=True)

    # Print dataset information
    print(f"Train dataset: {train_dataset.cardinality().numpy()} batches")
    print(f"Validation dataset: {val_dataset.cardinality().numpy()} batches")
    print(f"Train dataset element spec: {train_dataset.element_spec}")
    print(f"Validation dataset element spec: {val_dataset.element_spec}")

    # Initialize the lip-reading model
    model = LipReadingModel(num_classes=char_to_num.vocabulary_size())
    print(f"Model Input Shape: {model.model.input_shape}")
    print(f"Model Output Shape: {model.model.output_shape}")

    # Train the model
    from core_model.training import train_model as training_function
    trained_model, training_history = training_function(
        model.model, train_dataset, val_dataset)

    # Inspect training history
    print(f"Training history keys: {training_history.history.keys()}")

    # Save the trained model
    trained_model.save("model/models/final_model.keras")
    print("Model training complete and saved.")


##############################
# Model Testing Function     #
##############################

def test_model():
    """
    Load the trained model and test it on new data.

    NOTE: This function may need to be updated to reflect recent changes in the codebase.
    For example, the current implementation uses the validation dataset as test data and may
    require adjustments in decoding predictions or dataset preparation.
    """
    saved_model_path = "model/models/final_model.keras"
    if not os.path.exists(saved_model_path):
        print(
            f"Saved model not found at {saved_model_path}. Train the model first.")
        return

    # Load the saved model with custom loss
    model = tf.keras.models.load_model(
        saved_model_path, custom_objects={"ctc_loss": ctc_loss})
    print(f"Model loaded from {saved_model_path}.")
    model.summary()

    # Prepare test data (using validation dataset as test data)
    base_dir = "model/data/GRID_corpus/"
    video_dir = os.path.join(base_dir, "videos")

    mouth_detector = MouthDetector()
    data_loader = DataLoader(detector=mouth_detector)
    dataset_preparer = DatasetPreparer(
        video_directory=video_dir, data_loader=data_loader)
    _, test_dataset = dataset_preparer.prepare_dataset()

    # Evaluate the model on a single batch of test data
    for batch in test_dataset.take(1):
        videos, labels = batch
        print(f"Videos shape: {videos.shape}, Labels shape: {labels.shape}")
        predictions = model(videos, training=False)

        # Decode predictions using beam search (may need updating)
        decoded_predictions = decode_predictions(tf.cast(predictions, tf.float32), beam_width=10)
        dense_decoded = tf.sparse.to_dense(
            decoded_predictions[0], default_value=-1)

        # Display original labels and predictions
        for i, sequence in enumerate(dense_decoded):
            original = tf.strings.reduce_join(
                [num_to_char(word).numpy().decode('utf-8')
                 for word in labels[i].numpy() if word != -1]
            )
            prediction = tf.strings.reduce_join(
                [num_to_char(word).numpy().decode('utf-8')
                 for word in sequence.numpy() if word != -1]
            )
            print(f"Original: {original} | Prediction: {prediction}")


##############################
# Main Execution             #
##############################

def main():
    """
    Main function to train or test the model.
    """
    action = input(
        "Enter 'train' to train the model or 'test' to test the model: ").strip().lower()
    if action == 'train':
        train_model()
    elif action == 'test':
        test_model()
    else:
        print("Invalid action. Please enter 'train' or 'test'.")


if __name__ == "__main__":
    main()
