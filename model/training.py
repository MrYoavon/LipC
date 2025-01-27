# model/training.py

import math
import os
from datetime import datetime

import tensorflow as tf
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, LearningRateScheduler, TensorBoard
from tensorflow.keras.models import Sequential

from constants import num_to_char, TRAIN_TFRECORDS_PATH, VAL_TFRECORDS_PATH
from utils.model_utils import decode_predictions


def train_model(model: Sequential, train_data: tf.data.Dataset, validation_data: tf.data.Dataset|None) -> tuple[Sequential, tf.keras.callbacks.History]:
    # Compile the model with Adam optimizer, Word Error Rate and CTC loss
    cer = CharacterErrorRate()
    wer = WordErrorRate()
    model.compile(
                  optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
                  loss=ctc_loss,
                  metrics=[cer, wer]
                  )

    # Learning rate scheduler
    lr_scheduler_callback = LearningRateScheduler(lambda epoch: cosine_annealing_with_warm_restarts(epoch,
                                                                                                    T_0=10,
                                                                                                    T_mult=2,
                                                                                                    initial_lr=0.0001,
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

    # Calculate the number of steps per epoch
    def count_tfrecords(tfrecords_path):
        return sum(1 for _ in tf.data.TFRecordDataset(tfrecords_path))

    train_num_samples = count_tfrecords(TRAIN_TFRECORDS_PATH)
    val_num_samples = count_tfrecords(VAL_TFRECORDS_PATH)

    # Usually, we'd need to divide by the batch size, but since the dataset is already batched before saving to TFRecords,
    # we can just use the number of samples as the steps per epoch.
    train_steps_per_epoch = train_num_samples
    val_steps_per_epoch = val_num_samples

    history = None
    try:
        history = model.fit(
            train_data,
            validation_data=validation_data,
            steps_per_epoch=train_steps_per_epoch,
            validation_steps=val_steps_per_epoch,
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


class CharacterErrorRate(tf.keras.metrics.Metric):
    """A custom TensorFlow metric to compute the Character Error Rate (CER)."""
    def __init__(self, name='CER', **kwargs):
        super(CharacterErrorRate, self).__init__(name=name, **kwargs)
        self.cer_accumulator = tf.Variable(0.0, name="cer_accumulator", dtype=tf.float32)
        self.counter = tf.Variable(0, name="counter", dtype=tf.int32)

    def update_state(self, y_true, y_pred, sample_weight=None):
        y_true_sparse = tf.cast(tf.sparse.from_dense(y_true), tf.int64)

        input_length = tf.reduce_sum(tf.ones_like(y_pred[:, :, 0], dtype=tf.int32), axis=1)
        y_pred_transposed = tf.transpose(y_pred, perm=[1, 0, 2])  # Transpose to [time, batch, classes]
        decode_list, log = tf.nn.ctc_greedy_decoder(tf.cast(y_pred_transposed, tf.float32), input_length,
                                                    merge_repeated=True)

        decode = decode_list[0]  # ctc_greedy_decoder returns a list of one element
        decode = tf.sparse.retain(decode, tf.not_equal(decode.values, -1))

        distance = tf.edit_distance(decode, y_true_sparse, normalize=True)

        self.cer_accumulator.assign_add(tf.reduce_sum(distance))
        self.counter.assign_add(tf.shape(y_true)[0])

    def result(self):
        return tf.math.divide_no_nan(self.cer_accumulator, tf.cast(self.counter, tf.float32))

    def reset_states(self):
        self.cer_accumulator.assign(0.0)
        self.counter.assign(0)


class WordErrorRate(tf.keras.metrics.Metric):
    """A custom TensorFlow metric to compute the Word Error Rate (WER)."""
    def __init__(self, name='WER', **kwargs):
        super(WordErrorRate, self).__init__(name=name, **kwargs)
        self.wer_accumulator = tf.Variable(0.0, name="wer_accumulator", dtype=tf.float32)
        self.counter = tf.Variable(0, name="counter", dtype=tf.int32)

    def update_state(self, y_true, y_pred, sample_weight=None):
        input_length = tf.reduce_sum(tf.ones_like(y_pred[:, :, 0], dtype=tf.int32), axis=1)
        y_pred_transposed = tf.transpose(y_pred, perm=[1, 0, 2])  # Transpose to [time, batch, classes]
        decode_list, log = tf.nn.ctc_greedy_decoder(tf.cast(y_pred_transposed, tf.float32), input_length, merge_repeated=True)

        decoded_indices = decode_list[0]  # ctc_greedy_decoder returns a list of one element
        decoded_dense = tf.sparse.to_dense(decoded_indices, default_value=-1)
        decoded_chars = num_to_char(decoded_dense)  # Use your `num_to_char` layer
        decoded_text = tf.strings.reduce_join(decoded_chars, axis=-1)  # Shape: [batch_size]
        decoded_words = tf.strings.split(decoded_text, sep=" ")  # RaggedTensor [batch, num_words]

        y_true_text = tf.strings.reduce_join(num_to_char(y_true), axis=-1)  # Shape: [batch_size]
        y_true_words = tf.strings.split(y_true_text, sep=" ")  # RaggedTensor [batch, num_words]

        batch_size = tf.shape(y_true)[0]

        def _compute_wer(i):
            """Helper function to compute WER for a single sample."""
            # Extract words for the i-th sample
            pred_words_sample = decoded_words[i]
            true_words_sample = y_true_words[i]

            # Use tf.cond to handle the case where the true sequence is empty
            return tf.cond(
                tf.equal(tf.size(true_words_sample), 0),
                lambda: 0.0,
                lambda: _compute_distance(pred_words_sample, true_words_sample)
            )

        def _compute_distance(pred_words_sample, true_words_sample):
            """Helper function to compute the edit distance."""
            # Convert words to integer hashes (avoids vocabulary)
            num_buckets = 1000000  # Reduce collision risk
            pred_hashes = tf.strings.to_hash_bucket(pred_words_sample, num_buckets)
            true_hashes = tf.strings.to_hash_bucket(true_words_sample, num_buckets)

            # Reshape to 2D tensors with batch dimension [1, num_words]
            pred_hashes = tf.reshape(pred_hashes, [1, -1])  # Shape: [1, num_pred_words]
            true_hashes = tf.reshape(true_hashes, [1, -1])  # Shape: [1, num_true_words]

            # Create sparse tensors for edit distance
            pred_sparse = tf.sparse.from_dense(pred_hashes)
            true_sparse = tf.sparse.from_dense(true_hashes)

            # Compute edit distance (normalized by true word count)
            distance = tf.edit_distance(pred_sparse, true_sparse, normalize=True)
            return distance

        # Compute WER for all samples in the batch
        wer_values = tf.map_fn(
            _compute_wer,
            tf.range(batch_size),
            fn_output_signature=tf.float32
        )

        # Accumulate results
        self.wer_accumulator.assign_add(tf.reduce_sum(wer_values))
        self.counter.assign_add(batch_size)

    def result(self):
        return tf.math.divide_no_nan(self.wer_accumulator, tf.cast(self.counter, tf.float32))

    def reset_states(self):
        self.wer_accumulator.assign(0.0)
        self.counter.assign(0)


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

