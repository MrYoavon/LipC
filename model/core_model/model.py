# model/model.py

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.regularizers import l2

from constants import MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, BATCH_SIZE


###########################################
# LipReadingModel Class Definition        #
###########################################

class LipReadingModel:
    def __init__(self, input_shape=(MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1), num_classes=5):
        """
        Initialize the LipReadingModel with the specified input shape and number of classes.

        Args:
            input_shape (tuple): Shape of the input video tensor.
            num_classes (int): Number of output classes.
        """
        self.input_shape = input_shape
        self.num_classes = num_classes
        self.model = self.create_model()

    def create_model(self):
        """
        Creates and compiles the lip-reading model using the Sequential API.

        Returns:
            A compiled tf.keras.Model.
        """
        model = models.Sequential()

        # Input layer with fixed batch size for consistency
        model.add(layers.Input(shape=self.input_shape, batch_size=BATCH_SIZE))
        print(f"Input Shape: {self.input_shape}")

        # 3D Convolution layers to extract spatial and temporal features
        model.add(layers.Conv3D(128, kernel_size=3,
                  padding='same', activation='relu'))
        model.add(layers.MaxPool3D((1, 2, 2), padding='same'))
        model.add(layers.Conv3D(256, kernel_size=3,
                  padding='same', activation='relu'))
        model.add(layers.MaxPool3D((1, 2, 2), padding='same'))
        model.add(layers.Conv3D(MAX_FRAMES, kernel_size=3,
                  padding='same', activation='relu'))
        model.add(layers.MaxPool3D((1, 2, 2), padding='same'))

        # Flatten the spatial dimensions across time using TimeDistributed
        model.add(layers.TimeDistributed(layers.Flatten()))

        # Masking layer to ignore padded values
        model.add(layers.Masking(mask_value=0.0))

        # First Bidirectional LSTM for temporal modeling
        model.add(layers.Bidirectional(
            layers.LSTM(
                units=128,
                return_sequences=True,
                kernel_initializer="Orthogonal",
                activation='tanh',
                recurrent_activation='sigmoid',
                recurrent_dropout=0.2,
                use_bias=True
            )
        ))
        print(f"After BiLSTM-1: {model.layers[-1].output[0].shape}")
        model.add(layers.Dropout(0.5))

        # Second Bidirectional LSTM layer
        model.add(layers.Bidirectional(
            layers.LSTM(
                units=128,
                return_sequences=True,
                kernel_initializer="Orthogonal",
                activation='tanh',
                recurrent_activation='sigmoid',
                recurrent_dropout=0.2,
                use_bias=True
            )
        ))
        print(f"After BiLSTM-2: {model.layers[-1].output[0].shape}")
        model.add(layers.Dropout(0.5))

        # Final Dense layer to produce logits for CTC loss
        model.add(layers.Dense(self.num_classes + 1,
                               kernel_initializer="he_normal",
                               kernel_regularizer=l2(1e-4)))
        print(f"Final Output Shape (Logits): {model.layers[-1].output.shape}")

        # Output the model summary for debugging purposes
        print(model.summary())

        return model

    def load(self, model_path):
        """
        Load a pre-trained model from the specified path.

        Args:
            model_path (str): Path to the saved model.
        """
        self.model = tf.keras.models.load_model(model_path)

    def predict(self, frames):
        """
        Predict the sequence of characters from input video frames.

        Args:
            frames: Tensor of video frames.

        Returns:
            Model predictions.
        """
        return self.model.predict(frames)

    def save(self, model_path):
        """
        Save the trained model to the specified path.

        Args:
            model_path (str): Path where the model should be saved.
        """
        self.model.save(model_path)
