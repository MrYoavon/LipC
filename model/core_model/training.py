# model/training.py
"""
Training utilities for lip-reading model, including learning rate schedules,
CTC loss, custom metrics, callback classes for example generation, and
model training orchestration.
"""
##########################
#       Imports          #
##########################

import math
import os
from datetime import datetime

import tensorflow as tf
from tensorflow.keras.callbacks import (
    Callback,
    ModelCheckpoint,
    EarlyStopping,
    LearningRateScheduler,
    TensorBoard
)
from tensorflow.keras.models import Sequential

from model.constants import num_to_char, TRAIN_TFRECORDS_PATH, VAL_TFRECORDS_PATH
from model.utils.model_utils import decode_predictions


##########################
#   Helper Functions     #
##########################

def cosine_annealing_with_warm_restarts(
    epoch: int,
    T_0: int,
    T_mult: int = 1,
    initial_lr: float = 0.001,
    eta_min: float = 0.0
) -> float:
    """
    Compute learning rate using cosine annealing with warm restarts.

    Args:
        epoch (int): Current epoch index (0-based).
        T_0 (int): Initial number of epochs per cycle.
        T_mult (int): Cycle length multiplier after each restart.
        initial_lr (float): Base learning rate at cycle start.
        eta_min (float): Minimum learning rate at cycle end.

    Returns:
        float: Adjusted learning rate for this epoch.
    """
    t_cur = epoch % T_0
    if t_cur == 0 and epoch != 0:
        T_0 *= T_mult

    cos_inner = (math.pi * t_cur) / T_0
    lr = eta_min + (initial_lr - eta_min) * (1 + math.cos(cos_inner)) / 2
    return lr


def ctc_loss(y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
    """
    Compute the CTC (Connectionist Temporal Classification) loss.

    Args:
        y_true (tf.Tensor): Dense integer labels, shape [batch, label_length].
        y_pred (tf.Tensor): Logits from the model, shape [batch, time_steps, num_classes].

    Returns:
        tf.Tensor: Scalar mean CTC loss over the batch.
    """
    y_true = tf.cast(y_true, dtype=tf.int32)
    y_true_sparse = tf.sparse.from_dense(y_true)
    y_pred = tf.cast(y_pred, dtype=tf.float32)

    input_length = tf.reduce_sum(tf.ones_like(
        y_pred[:, :, 0], dtype=tf.int32), axis=1)
    # Adding 1 because labels start at 0
    label_length = tf.sparse.reduce_max(y_true_sparse, axis=1) + 1

    loss = tf.nn.ctc_loss(
        labels=y_true_sparse,
        logits=y_pred,
        label_length=label_length,
        logit_length=input_length,
        logits_time_major=False,
        blank_index=-1
    )
    return tf.reduce_mean(loss)


##########################
#    Custom Metrics      #
##########################

class CharacterErrorRate(tf.keras.metrics.Metric):
    """
    Custom TensorFlow metric to compute Character Error Rate (CER).

    Accumulates edit distance between predicted and true character sequences.
    """

    def __init__(self, name: str = 'CER', **kwargs) -> None:
        """
        Initialize CER metric.

        Args:
            name (str): Metric name.
            **kwargs: Additional metric args.
        """
        super().__init__(name=name, **kwargs)
        self.cer_accumulator = self.add_weight(
            name='cer_accumulator', initializer='zeros', dtype=tf.float32
        )
        self.counter = self.add_weight(
            name='counter', initializer='zeros', dtype=tf.int32
        )

    def update_state(
        self,
        y_true: tf.Tensor,
        y_pred: tf.Tensor,
        sample_weight=None
    ) -> None:
        """
        Update metric state with batch predictions.

        Args:
            y_true (tf.Tensor): True labels, shape [batch, label_length].
            y_pred (tf.Tensor): Logits, shape [batch, time_steps, num_classes].
            sample_weight: Optional sample weights (unused).
        """
        y_true_sparse = tf.cast(tf.sparse.from_dense(y_true), tf.int64)
        input_length = tf.reduce_sum(
            tf.ones_like(y_pred[:, :, 0], tf.int32), axis=1
        )
        y_pred_tm = tf.transpose(y_pred, perm=[1, 0, 2])
        decoded, _ = tf.nn.ctc_greedy_decoder(
            tf.cast(y_pred_tm, tf.float32), input_length, merge_repeated=True
        )
        sparse_decoded = tf.sparse.retain(
            decoded[0], tf.not_equal(decoded[0].values, -1))

        distances = tf.edit_distance(
            sparse_decoded, y_true_sparse, normalize=True)
        self.cer_accumulator.assign_add(tf.reduce_sum(distances))
        self.counter.assign_add(tf.cast(tf.shape(y_true)[0], tf.int32))

    def result(self) -> tf.Tensor:
        """
        Compute final CER value.

        Returns:
            tf.Tensor: Average character error rate.
        """
        return tf.math.divide_no_nan(
            self.cer_accumulator, tf.cast(self.counter, tf.float32)
        )

    def reset_states(self) -> None:
        """
        Reset accumulators for a new evaluation.
        """
        self.cer_accumulator.assign(0.0)
        self.counter.assign(0)


class WordErrorRate(tf.keras.metrics.Metric):
    """
    Custom TensorFlow metric to compute Word Error Rate (WER).

    Accumulates normalized edit distance between predicted and true word sequences.
    """

    def __init__(self, name: str = 'WER', **kwargs) -> None:
        """
        Initialize WER metric.

        Args:
            name (str): Metric name.
            **kwargs: Additional metric args.
        """
        super().__init__(name=name, **kwargs)
        self.wer_accumulator = self.add_weight(
            name='wer_accumulator', initializer='zeros', dtype=tf.float32
        )
        self.counter = self.add_weight(
            name='counter', initializer='zeros', dtype=tf.int32)

    def update_state(
        self,
        y_true: tf.Tensor,
        y_pred: tf.Tensor,
        sample_weight=None
    ) -> None:
        """
        Update metric state with batch predictions for WER.

        Args:
            y_true (tf.Tensor): True labels.
            y_pred (tf.Tensor): Logits.
            sample_weight: Optional sample weights.
        """
        input_length = tf.reduce_sum(
            tf.ones_like(y_pred[:, :, 0], tf.int32), axis=1
        )
        y_pred_tm = tf.transpose(y_pred, perm=[1, 0, 2])
        decoded, _ = tf.nn.ctc_greedy_decoder(
            tf.cast(y_pred_tm, tf.float32), input_length, merge_repeated=True
        )
        dense = tf.sparse.to_dense(decoded[0], default_value=-1)
        chars = num_to_char(dense)
        text = tf.strings.reduce_join(chars, axis=-1)
        words = tf.strings.split(text, sep=' ')

        true_text = tf.strings.reduce_join(num_to_char(y_true), axis=-1)
        true_words = tf.strings.split(true_text, sep=' ')

        batch_size = tf.shape(y_true)[0]

        def compute_distance(pw, tw):
            num_buckets = 1000000
            ph = tf.strings.to_hash_bucket(pw, num_buckets)
            th = tf.strings.to_hash_bucket(tw, num_buckets)
            ph = tf.reshape(ph, [1, -1])
            th = tf.reshape(th, [1, -1])
            return tf.edit_distance(
                tf.sparse.from_dense(ph), tf.sparse.from_dense(th), normalize=True
            )[0]

        wer_vals = tf.map_fn(
            lambda i: tf.cond(
                tf.equal(tf.size(true_words[i]), 0),
                lambda: 0.0,
                lambda: compute_distance(words[i], true_words[i])
            ),
            tf.range(batch_size),
            fn_output_signature=tf.float32
        )
        self.wer_accumulator.assign_add(tf.reduce_sum(wer_vals))
        self.counter.assign_add(batch_size)

    def result(self) -> tf.Tensor:
        """
        Compute final WER value.

        Returns:
            tf.Tensor: Average word error rate.
        """
        return tf.math.divide_no_nan(
            self.wer_accumulator, tf.cast(self.counter, tf.float32)
        )

    def reset_states(self) -> None:
        """
        Reset accumulators for a new evaluation.
        """
        self.wer_accumulator.assign(0.0)
        self.counter.assign(0)


##########################
#   Callback Classes     #
##########################

class ProduceExample(Callback):
    """
    Keras callback to generate and print example predictions after each epoch.

    Iterates over a provided dataset and compares model output to labels.
    """

    def __init__(self, dataset: tf.data.Dataset) -> None:
        """
        Initialize with dataset for example generation.

        Args:
            dataset (tf.data.Dataset): Validation dataset for examples.
        """
        super().__init__()
        self.dataset = dataset
        self.iterator = iter(dataset)

    def on_epoch_end(self, epoch: int, logs=None) -> None:
        """
        Called at end of each epoch to print model predictions vs. ground truth.

        Args:
            epoch (int): Epoch index.
            logs (dict): Metric logs from training.
        """
        try:
            videos, labels = next(self.iterator)
        except StopIteration:
            self.iterator = iter(self.dataset)
            videos, labels = next(self.iterator)

        preds = self.model.predict(videos)
        decoded = decode_predictions(tf.cast(preds, tf.float32))
        dense = tf.sparse.to_dense(decoded[0], default_value=-1)

        for i in range(tf.shape(dense)[0]):
            true = ''.join([num_to_char(idx).numpy().decode('utf-8')
                            for idx in labels[i].numpy() if idx != -1])
            pred = ''.join([num_to_char(idx).numpy().decode('utf-8')
                            for idx in dense[i].numpy() if idx != -1])
            print(f"Epoch {epoch}: True='{true}' -> Pred='{pred}'")


##########################
#   Training Function    #
##########################

def train_model(
    model: Sequential,
    train_data: tf.data.Dataset,
    validation_data: tf.data.Dataset | None = None
) -> tuple[Sequential, tf.keras.callbacks.History]:
    """
    Compile and train the lip-reading model with CTC loss and custom metrics.

    Args:
        model (Sequential): Keras model to train.
        train_data (tf.data.Dataset): Training dataset.
        validation_data (tf.data.Dataset | None): Validation dataset.

    Returns:
        tuple: (trained model, training history object).
    """
    cer = CharacterErrorRate()
    wer = WordErrorRate()

    optimizer = tf.keras.optimizers.Adam(learning_rate=1e-4)
    model.compile(
        optimizer=optimizer,
        loss=ctc_loss,
        metrics=[cer, wer]
    )

    # Learning rate scheduling via cosine annealing
    lr_callback = LearningRateScheduler(
        lambda epoch: cosine_annealing_with_warm_restarts(
            epoch, T_0=7, T_mult=2, initial_lr=2e-4, eta_min=1e-5
        )
    )

    # Setup model checkpointing
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join('model', 'models', f'run-{timestamp}')
    os.makedirs(run_dir, exist_ok=True)
    ckpt = ModelCheckpoint(
        os.path.join(run_dir, 'cp-{epoch:04d}.weights.h5'),
        monitor='val_loss', save_weights_only=True, save_best_only=True, verbose=1
    )

    early_stop = EarlyStopping(monitor='val_loss', patience=10, verbose=1)
    example_cb = ProduceExample(validation_data) if validation_data else None
    tb_log = os.path.join('model', 'logs', 'fit', timestamp)
    tb_cb = TensorBoard(log_dir=tb_log, histogram_freq=1)

    # Determine steps from TFRecords counts
    def count_records(path: str) -> int:
        return sum(1 for _ in tf.data.TFRecordDataset(path))

    train_steps = count_records(TRAIN_TFRECORDS_PATH)
    val_steps = count_records(VAL_TFRECORDS_PATH) if validation_data else None

    callbacks = [ckpt, lr_callback, early_stop, tb_cb]
    if example_cb:
        callbacks.append(example_cb)

    history = model.fit(
        train_data,
        validation_data=validation_data,
        steps_per_epoch=train_steps,
        validation_steps=val_steps,
        epochs=100,
        callbacks=callbacks,
        verbose=1
    )

    return model, history
