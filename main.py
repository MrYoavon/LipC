# main.py

# Standard library imports
import os

# Third-party imports
import numpy as np
import tensorflow as tf
from tensorflow.keras import mixed_precision
from tensorflow.keras.layers import Reshape, LSTM, Dense, Bidirectional, TimeDistributed, Conv3D, MaxPool3D

# Disable GPU for Tensorflow
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

# Increase max GPU VRAM usage
os.environ["TF_CUDNN_WORKSPACE_LIMIT_IN_MB"] = "16384"

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
            tf.config.experimental.set_virtual_device_configuration(
                gpus[0],
                [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=19000)]  # Example: Allocate 4GB
            )
            print(f"Using GPU: {gpus[0]}")
        else:
            print("No GPU detected, using CPU.")

        # Log TensorFlow ROCm status (if applicable)
        print(f"TensorFlow Version: {tf.__version__}")
        print(f"Is ROCm enabled: {tf.test.is_built_with_rocm()}")

    except RuntimeError as e:
        print(f"Error configuring TensorFlow devices: {e}")

# Call the device configuration function
configure_devices()
mixed_precision.set_global_policy('mixed_float16')

# Local application imports
from model.training import decode_predictions, ctc_loss
from data_processing.data_processing import DatasetPreparer, DataLoader, num_to_char, char_to_num
from data_processing.mouth_detection import MouthDetector
from model.model import LipReadingModel

def train_model():
    """
    Train the lip-reading model and save it to disk.
    """
    base_dir = "data/A_U_EE_E/"
    original_video_dir = base_dir + "videos"
    original_subtitle_dir = base_dir + "subtitles"
    output_dir = base_dir + "separated"
    video_dir = output_dir + "/videos"

    mouth_detector = MouthDetector()

    # Instantiate DataLoader and DatasetPreparer
    data_loader = DataLoader(detector=mouth_detector)  # Initialize with any necessary parameters
    data_loader.process_all_videos(original_video_dir, original_subtitle_dir, output_dir)
    dataset_preparer = DatasetPreparer(video_directory=video_dir, data_loader=data_loader)  # Provide data_loader here
    train_dataset, val_dataset = dataset_preparer.prepare_dataset()

    model = LipReadingModel(num_classes=char_to_num.vocabulary_size())
    # Print the model's input and output shapes
    print(f"Model Input Shape: {model.model.input_shape}")
    print(f"Model Output Shape: {model.model.output_shape}")

    from model.training import train_model
    trained_model, training_history = train_model(model.model, train_dataset, val_dataset)

    # Inspect the training history
    print(f"Training history keys: {training_history.history.keys()}")

    # Save the final model
    trained_model.save("models/final_model.h5")
    print("Model training complete and saved.")

def test_model():
    """
    Load the trained model and test it on new data.
    """
    # Load the saved model
    saved_model_path = "models/final_model.h5"
    if not os.path.exists(saved_model_path):
        print(f"Saved model not found at {saved_model_path}. Train the model first.")
        return

    model = tf.keras.models.load_model(saved_model_path, custom_objects={"ctc_loss": ctc_loss, "Reshape": Reshape, "LSTM": LSTM})  # Add custom losses if needed
    print(f"Model loaded from {saved_model_path}.")
    print(model.summary())

    # Prepare test data
    base_dir = "data/A_U_EE_E/temp/"
    output_dir = base_dir + "separated"
    video_dir = output_dir + "/videos"

    mouth_detector = MouthDetector()
    data_loader = DataLoader(detector=mouth_detector)
    dataset_preparer = DatasetPreparer(video_directory=video_dir, data_loader=data_loader)
    _, test_dataset = dataset_preparer.prepare_dataset()  # Assuming you have a separate test set

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
    action = input("Enter 'train' to train the model or 'test' to test the model: ").strip().lower()
    if action == 'train':
        train_model()
    elif action == 'test':
        test_model()
    else:
        print("Invalid action. Please enter 'train' or 'test'.")

if __name__ == "__main__":
    main()
