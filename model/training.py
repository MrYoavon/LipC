# model/training.py

import math
import os
from datetime import datetime

import tensorflow as tf
from tensorflow.keras.callbacks import Callback, ModelCheckpoint, EarlyStopping, LearningRateScheduler, TensorBoard
from tensorflow.keras.models import Sequential

from constants import num_to_char
from utils.model_utils import decode_predictions


def train_model(model: Sequential, train_data: tf.data.Dataset, validation_data: tf.data.Dataset|None) -> tuple[Sequential, tf.keras.callbacks.History]:
    # Compile the model with Adam optimizer, Word Error Rate and CTC loss
    cwer_metric = CWERMetric()
    model.compile(
                  optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss=ctc_loss,
                  metrics=[cwer_metric]
                  )

    # Learning rate scheduler
    lr_scheduler_callback = LearningRateScheduler(lambda epoch: cosine_annealing_with_warm_restarts(epoch,
                                                                                                    T_0=10,
                                                                                                    T_mult=1,
                                                                                                    initial_lr=0.001,
                                                                                                    eta_min=0.0001))

    # Model checkpoint
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join('models', f'run-{timestamp}')
    os.makedirs(run_dir, exist_ok=True)
    checkpoint_callback = ModelCheckpoint(
        os.path.join(run_dir, 'cp-{epoch:04d}.weights.h5'),
        monitor='val_loss',
        save_weights_only=True,
        save_best_only=True,
        verbose=1
    )

    # Early stopping (stops training if loss stops improving)
    early_stopping_callback = EarlyStopping(monitor='val_loss', patience=10, verbose=1)

    # Produce one example
    example_callback = ProduceExample(validation_data)

    # Tensorboard
    log_dir = f"logs/fit/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    tensorboard_callback = TensorBoard(
        log_dir=log_dir,
        histogram_freq=1,
    )

    history = None
    try:
        history = model.fit(
            train_data,
            validation_data=validation_data,
            # validation_freq=5,
            epochs=100,
            callbacks=[checkpoint_callback,
                       early_stopping_callback,
                       lr_scheduler_callback,
                       example_callback,
                       tensorboard_callback
                    ],
            verbose=1,
        )
    except tf.errors.DataLossError as e:
        print("Error during training:", e)
        for frames, labels in train_data.take(1):
            print(frames.shape, labels.shape)

    return model, history


def cosine_annealing_with_warm_restarts(epoch, T_0, T_mult=1, initial_lr=0.001, eta_min=0.0):
    """
    Args:
        epoch: Current epoch.
        T_0: Number of epochs for the first cycle.
        T_mult: Multiplier to increase the cycle length after each restart.
        initial_lr: Initial learning rate.
        eta_min: Minimum learning rate.
    """
    t_cur = epoch % T_0
    if t_cur == 0 and epoch != 0:
        T_0 *= T_mult

    cos_inner = (math.pi * t_cur) / T_0
    lr = eta_min + (initial_lr - eta_min) * (1 + math.cos(cos_inner)) / 2
    return lr


def ctc_loss(y_true, y_pred):
    y_true = tf.cast(y_true, dtype=tf.int32)
    y_true_sparse = tf.sparse.from_dense(y_true)
    y_pred = tf.cast(y_pred, dtype=tf.float32)

    input_length = tf.reduce_sum(tf.ones_like(y_pred[:, :, 0], dtype=tf.int32), axis=1)  # Length of each input sequence
    label_length = tf.sparse.reduce_max(y_true_sparse, axis=1) + 1  # Adding 1 because it starts at 0

    loss = tf.nn.ctc_loss(
        labels=y_true_sparse,
        logits=y_pred,
        label_length=label_length,
        logit_length=input_length,
        logits_time_major=False,
        blank_index=-1
    )
    return tf.reduce_mean(loss)


class CWERMetric(tf.keras.metrics.Metric):
    """ A custom TensorFlow metric to compute the Character Error Rate
    """
    def __init__(self, name='CWER', **kwargs):
        super(CWERMetric, self).__init__(name=name, **kwargs)
        self.cer_accumulator = tf.Variable(0.0, name="cer_accumulator", dtype=tf.float32)
        self.wer_accumulator = tf.Variable(0.0, name="wer_accumulator", dtype=tf.float32)
        self.counter = tf.Variable(0, name="counter", dtype=tf.int32)

    def update_state(self, y_true, y_pred, sample_weight=None):
        input_shape = tf.shape(y_pred)

        input_length = tf.ones(shape=input_shape[0], dtype='int32') * tf.cast(input_shape[1], 'int32')

        decode, log = tf.keras.backend.ctc_decode(tf.cast(y_pred, dtype=tf.float32), input_length, greedy=True)

        decode = tf.keras.backend.ctc_label_dense_to_sparse(decode[0], input_length)
        y_true_sparse = tf.cast(tf.keras.backend.ctc_label_dense_to_sparse(y_true, input_length), "int64")

        decode = tf.sparse.retain(decode, tf.not_equal(decode.values, -1))
        distance = tf.edit_distance(decode, y_true_sparse, normalize=True)

        correct_words_amount = tf.reduce_sum(tf.cast(tf.not_equal(distance, 0), tf.float32))

        self.wer_accumulator.assign_add(correct_words_amount)
        self.cer_accumulator.assign_add(tf.reduce_sum(distance))
        self.counter.assign_add(tf.shape(y_true)[0])

    def result(self):
        return {
                "CER": tf.math.divide_no_nan(self.cer_accumulator, tf.cast(self.counter, tf.float32)),
                "WER": tf.math.divide_no_nan(self.wer_accumulator, tf.cast(self.counter, tf.float32))
        }


class ProduceExample(tf.keras.callbacks.Callback):
    def __init__(self, dataset) -> None:
        super().__init__()
        self.dataset = dataset
        self.dataset_iter = iter(dataset)

    def on_epoch_end(self, epoch, logs=None) -> None:
        try:
            videos, labels = next(self.dataset_iter)
        except StopIteration:
            self.dataset_iter = iter(self.dataset)
            videos, labels = next(self.dataset_iter)

        predictions = self.model.predict(videos)  # Predict logits from the model
        decoded_predictions = decode_predictions(tf.cast(predictions, dtype=tf.float32))
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

