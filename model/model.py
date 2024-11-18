# model/model.py

import tensorflow as tf
from tensorflow.keras import layers, models


class LipReadingModel:
    def __init__(self, input_shape=(250, 100), num_classes=5):
        self.input_shape = input_shape
        self.num_classes = num_classes
        self.model = self.create_model()

    def create_model(self):
        """
        Creates and compiles the lip-reading model using the Sequential API.
        """
        model = models.Sequential()

        model.add(layers.Input(shape=(128, 100, 250, 1)))

        model.add(layers.Conv3D(128,3, padding='same', activation='relu'))
        model.add(layers.MaxPool3D((1, 2, 2)))

        model.add(layers.Conv3D(256, 3, padding='same', activation='relu'))
        model.add(layers.MaxPool3D((1, 2, 2)))

        model.add(layers.Conv3D(128, 3, padding='same', activation='relu'))
        model.add(layers.MaxPool3D((1, 2, 2)))

        # model.add(layers.Masking(mask_value=0.0))

        model.add(layers.TimeDistributed(layers.Flatten()))

        model.add(layers.Bidirectional(layers.LSTM(128, kernel_initializer='Orthogonal', return_sequences=True)))
        model.add(layers.Dropout(.5))


        model.add(layers.Bidirectional(layers.LSTM(128, kernel_initializer='Orthogonal', return_sequences=True)))
        model.add(layers.Dropout(.5))

        model.add(layers.Dense(self.num_classes + 1, kernel_initializer='he_normal', activation='softmax'))

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
        frames = frames / 255.0  # Normalize frames
        return self.model.predict(frames)

    def save(self, model_path):
        """
        Save the trained model to the specified path.
        """
        self.model.save(model_path)
