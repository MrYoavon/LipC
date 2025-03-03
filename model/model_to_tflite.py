import tensorflow as tf
from model.core_model.training import ctc_loss


def convert_model_to_tflite(keras_model_path: str, tflite_model_path: str) -> None:
    """
    Convert a saved Keras model to TensorFlow Lite format and save it to a file.

    Args:
        keras_model_path (str): Path to the saved Keras model.
        tflite_model_path (str): Destination file path to save the converted TFLite model.
    """
    # Load the saved Keras model, including the custom CTC loss function.
    model = tf.keras.models.load_model(keras_model_path, custom_objects={"ctc_loss": ctc_loss})

    # Create a TFLite converter from the Keras model.
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    # Configure converter to support both TFLite built-in ops and select TensorFlow ops.
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,  # Use default TFLite ops.
        tf.lite.OpsSet.SELECT_TF_OPS  # Use TensorFlow ops for unsupported functionalities.
    ]

    # Convert the model to TFLite format.
    tflite_model = converter.convert()

    # Save the converted TFLite model to file.
    with open(tflite_model_path, 'wb') as f:
        f.write(tflite_model)

    print(f"Model converted and saved to {tflite_model_path}")


if __name__ == "__main__":
    keras_model_path = 'models/final_model.keras'
    tflite_model_path = 'final_model.tflite'
    convert_model_to_tflite(keras_model_path, tflite_model_path)
