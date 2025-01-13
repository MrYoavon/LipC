# model/model.py

import tensorflow as tf
from tensorflow.keras import layers, models
from tensorflow.keras.regularizers import l2

from constants import MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH


class LipReadingModel:
    def __init__(self, input_shape=(MAX_FRAMES, VIDEO_HEIGHT, VIDEO_WIDTH, 1), num_classes=5):
        self.input_shape = input_shape
        self.num_classes = num_classes
        self.model = self.create_model()

    def create_model(self):
        """
        Creates and compiles the lip-reading model using the Sequential API.
        """
        model = models.Sequential()

        # Input layer
        model.add(layers.Input(shape=self.input_shape))
        print(f"Input Shape: {self.input_shape}")

        # 3D Convolution layers for spatial and temporal features
        model.add(layers.Conv3D(128, kernel_size=3, padding='same', activation='relu'))
        print(f"After Conv3D-1: {model.layers[-1].output.shape}")
        model.add(layers.MaxPool3D((1, 2, 2), padding='same'))
        print(f"After MaxPool3D-1: {model.layers[-1].output.shape}")

        model.add(layers.Conv3D(256, kernel_size=3, padding='same', activation='relu'))
        print(f"After Conv3D-2: {model.layers[-1].output.shape}")
        model.add(layers.MaxPool3D((1, 2, 2), padding='same'))
        print(f"After MaxPool3D-2: {model.layers[-1].output.shape}")

        model.add(layers.Conv3D(MAX_FRAMES, kernel_size=3, padding='same', activation='relu'))
        print(f"After Conv3D-3: {model.layers[-1].output.shape}")
        model.add(layers.MaxPool3D((1, 2, 2), padding='same'))
        print(f"After MaxPool3D-3: {model.layers[-1].output.shape}")

        # TimeDistributed for applying to each frame in the sequence
        # Flatten spatial dimensions for LSTMs
        model.add(layers.TimeDistributed(layers.Flatten()))
        print(f"After TimeDistributed Flatten: {model.layers[-1].output.shape}")

        # Bidirectional LSTMs for temporal modeling
        model.add(layers.Bidirectional(layers.LSTM(128, return_sequences=True)))
        print(f"After BiLSTM-1: {model.layers[-1].output[0].shape}")
        model.add(layers.Dropout(0.5))

        model.add(layers.Bidirectional(layers.LSTM(128, return_sequences=True)))
        print(f"After BiLSTM-2: {model.layers[-1].output[0].shape}")
        model.add(layers.Dropout(0.5))

        # Output layer (logits for CTC loss)
        model.add(layers.Dense(self.num_classes + 1, activation="softmax", kernel_initializer="he_normal", kernel_regularizer=l2(1e-4)))
        print(f"Final Output Shape (Logits): {model.layers[-1].output.shape}")

        print(model.summary())

        return model

    def load(self, model_path):
        """
        Load a pre-trained model from a given path.
        """
        self.model = tf.keras.models.load_model(model_path)

    def predict(self, frames):
        """
        Predict the sequence of characters from video frames.
        """
        return self.model.predict(frames)

    def save(self, model_path):
        """
        Save the trained model to the specified path.
        """
        self.model.save(model_path)