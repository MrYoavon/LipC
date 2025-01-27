# main.py

import os

# Third-party imports
import tensorflow as tf
# tf.config.run_functions_eagerly(True)  # Enable eager execution for debugging purposes
import numpy as np
import random

# Set random seeds for reproducibility
seed = 42
tf.random.set_seed(seed)
np.random.seed(seed)
random.seed(seed)

# Disable GPU for Tensorflow
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

def configure_devices():
    """
    Configure TensorFlow to use GPU if available, fallback to CPU otherwise.
    """
    try:
        # Detect GPUs
        gpus = tf.config.experimental.list_physical_devices('GPU')
        print(gpus)

        if gpus:
            # Set memory growth to prevent memory allocation problems
            tf.config.experimental.set_memory_growth(gpus[0], True)
            tf.config.experimental.set_visible_devices(gpus[0], 'GPU')
            print(f"Using GPU: {gpus[0]}")
        else:
            print("No GPU detected, using CPU.")

        # Log TensorFlow ROCm or CUDA status (if applicable)
        print(f"TensorFlow Version: {tf.__version__}")
        print(f"Is CUDA enabled: {tf.test.is_built_with_cuda()}")
        print(f"Is ROCm enabled: {tf.test.is_built_with_rocm()}")

    except RuntimeError as e:
        print(f"Error configuring TensorFlow devices: {e}")

# Call the device configuration function
configure_devices()
from tensorflow.keras import mixed_precision
mixed_precision.set_global_policy('mixed_float16')

# Local application imports
from model.training import ctc_loss
from model.utils.model_utils import decode_predictions
from model.data_processing.mouth_detection import MouthDetector
from model.data_processing.data_processing import DatasetPreparer
from model.data_processing.data_loader import DataLoader
from model.model import LipReadingModel
from constants import char_to_num, num_to_char


def train_model():
    """
    Train the lip-reading model and save it to disk.
    """
    base_dir = "data/GRID_corpus_normal/"
    video_dir = base_dir + "videos"

    mouth_detector = MouthDetector()

    # Instantiate DataLoader and DatasetPreparer
    data_loader = DataLoader(detector=mouth_detector)
    dataset_preparer = DatasetPreparer(video_directory=video_dir, data_loader=data_loader)
    train_dataset, val_dataset = dataset_preparer.prepare_dataset(save_tfrecords=True)

    # Print information about the datasets
    print(f"Train dataset: {train_dataset.cardinality().numpy()} batches")
    print(f"Validation dataset: {val_dataset.cardinality().numpy()} batches")
    print(f"Train dataset element spec: {train_dataset.element_spec}")
    print(f"Validation dataset element spec: {val_dataset.element_spec}")

    # print(f"Number of elements: {len(list(train_dataset))} | {len(list(val_dataset))}")

    # for videos, labels in train_dataset:
    #     print(f"Videos shape (train): {videos.shape}, Labels shape: {labels.shape} | {videos.dtype}, {labels.dtype}")
    #
    # for videos, labels in val_dataset:
    #     print(f"Videos shape (val): {videos.shape}, Labels shape: {labels.shape}")

    # for videos, labels in train_dataset.take(1):
    #     y_true = labels
    #     print(labels)
    #     y_pred = tf.random.uniform((8, 75, char_to_num.vocabulary_size() + 1), minval=0, maxval=1, dtype=tf.float16)
    #     print(y_pred)
    #     wer_metric = WordErrorRate()
    #     wer_metric.update_state(y_true, y_pred)
    #     wer = wer_metric.result()
    #     print(f"Initial WER: {wer}")


    model = LipReadingModel(num_classes=char_to_num.vocabulary_size())
    print(f"Model Input Shape: {model.model.input_shape}")
    print(f"Model Output Shape: {model.model.output_shape}")

    from model.training import train_model
    trained_model, training_history = train_model(model.model, train_dataset, val_dataset)

    # Inspect the training history
    print(f"Training history keys: {training_history.history.keys()}")

    # Save the final model
    trained_model.save("models/final_model.keras")
    print("Model training complete and saved.")

def test_model():
    """
    Load the trained model and test it on new data.
    """
    # Load the saved model
    saved_model_path = "models/final_model.keras"
    if not os.path.exists(saved_model_path):
        print(f"Saved model not found at {saved_model_path}. Train the model first.")
        return

    model = tf.keras.models.load_model(saved_model_path, custom_objects={"ctc_loss": ctc_loss})
    print(f"Model loaded from {saved_model_path}.")
    print(model.summary())

    # Prepare test data
    base_dir = "model/data/GRID_corpus/"
    video_dir = base_dir + "videos"

    mouth_detector = MouthDetector()
    data_loader = DataLoader(detector=mouth_detector)
    dataset_preparer = DatasetPreparer(video_directory=video_dir, data_loader=data_loader)
    _, test_dataset = dataset_preparer.prepare_dataset()  # Using the validation dataset as test

    # Evaluate the model
    for batch in test_dataset.take(1):  # Test on a single batch
        videos, labels = batch
        print(f"Videos shape: {videos.shape}, Labels shape: {labels.shape}")
        predictions = model(videos, training=False)  # Predict logits from the model

        # Decode predictions
        decoded_predictions = decode_predictions(predictions, beam_width=10)
        dense_decoded = tf.sparse.to_dense(decoded_predictions[0], default_value=-1)

        # Display results
        for i, sequence in enumerate(dense_decoded):
            original = tf.strings.reduce_join(
                [num_to_char(word).numpy().decode('utf-8') for word in labels[i].numpy() if word != -1]
            )
            prediction = tf.strings.reduce_join(
                [num_to_char(word).numpy().decode('utf-8') for word in sequence.numpy() if word != -1]
            )
            print(f"Original: {original} | Prediction: {prediction}")

def main():
    """
    Main function to train or test the model.
    """
    # Choose between training and testing
    # action = input("Enter 'train' to train the model or 'test' to test the model: ").strip().lower()
    action = 'train'
    if action == 'train':
        train_model()
    elif action == 'test':
        test_model()
    else:
        print("Invalid action. Please enter 'train' or 'test'.")

if __name__ == "__main__":
    main()
