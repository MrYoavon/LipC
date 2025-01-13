# model/training.py
import math
import os
import editdistance
from datetime import datetime

import tensorflow as tf
from tensorflow.keras.callbacks import Callback, ModelCheckpoint, EarlyStopping, LearningRateScheduler, TensorBoard
from tensorflow.keras.models import Sequential

from constants import num_to_char


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
        verbose=1
    )

    # Early stopping (stops training if loss stops improving)
    early_stopping_callback = EarlyStopping(monitor='val_loss', patience=10, verbose=1)

    # Produce one example
    example_callback = ProduceExample(validation_data)

    history = None
    try:
        history = model.fit(
            train_data,
            validation_data=validation_data,
            validation_freq=5,
            epochs=100,
            callbacks=[checkpoint_callback,
                       early_stopping_callback,
                       lr_scheduler_callback,
                       example_callback,
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
    y_true = tf.cast(y_true, dtype=tf.int8)
    y_pred = tf.cast(y_pred, dtype=tf.float16)

    input_length = tf.reduce_sum(tf.ones_like(y_pred[:, :, 0], dtype=tf.int8), axis=1)  # Length of each input sequence
    label_length = tf.reduce_sum(tf.ones_like(y_true, dtype=tf.int8), axis=1)  # Length of each label sequence

    loss = tf.nn.ctc_loss(
        labels=y_true,
        logits=y_pred,
        label_length=label_length,
        logit_length=input_length,
        logits_time_major=False,
        blank_index=-1
    )
    return tf.reduce_mean(loss)


def decode_predictions(y_pred, beam_width=10):
    # y_pred: (batch_size, timesteps, num_classes)
    y_pred = tf.transpose(y_pred, perm=[1, 0, 2])  # Convert to time-major format
    input_length = tf.fill([tf.shape(y_pred)[1]], tf.shape(y_pred)[0])  # Dynamic sequence lengths

    # Perform beam search decoding
    decoded, log_prob = tf.nn.ctc_beam_search_decoder(
        y_pred,
        sequence_length=input_length,
        beam_width=beam_width
    )
    return decoded


# def calculate_wer(ground_truth, prediction):
#     """
#     Calculate Word Error Rate (WER).
#
#     Args:
#         ground_truth (str): The correct transcription.
#         prediction (str): The predicted transcription.
#
#     Returns:
#         float: WER value.
#     """
#     # Split the sentences into words
#     gt_words = ground_truth.split()
#     pred_words = prediction.split()
#
#     # Calculate Levenshtein distance
#     distance = editdistance.eval(gt_words, pred_words)
#
#     # Compute WER
#     wer = distance / len(gt_words) if len(gt_words) > 0 else float('inf')
#     return wer
#
#
# class WordErrorRateMetric(tf.keras.metrics.Metric):
#     def __init__(self, name="wer", **kwargs):
#         super(WordErrorRateMetric, self).__init__(name=name, **kwargs)
#         self.total_wer = self.add_weight(name="total_wer", initializer="zeros", dtype=tf.float16)
#         self.count = self.add_weight(name="count", initializer="zeros", dtype=tf.float16)
#
#     def update_state(self, y_true, y_pred, sample_weight=None):
#         """
#         Update WER for a batch.
#
#         Args:
#             y_true: Ground truth labels (list of strings).
#             y_pred: Predicted labels (list of strings).
#         """
#         def logits_to_text(logits):
#             return tf.strings.reduce_join(num_to_char(logits), axis=-1)
#
#         true_str = logits_to_text(y_true)
#         pred_str = logits_to_text(y_pred)
#
#         tf.print("TRUE", true_str)
#         tf.print("PRED", pred_str)
#
#         # Use tf.py_function to calculate WER with Python logic
#         def calculate_batch_wer(true_text, pred_text):
#             total_wer = 0.0
#             count = 0
#             for gt, pred in zip(true_text, pred_text):
#                 wer = calculate_wer(gt.decode('utf-8'), pred.decode('utf-8'))
#                 total_wer += wer
#                 count += 1
#             return total_wer, count
#
#         batch_wer, batch_count = tf.py_function(
#             calculate_batch_wer,
#             [true_str, pred_str],
#             [tf.float32, tf.float32],
#         )
#
#         self.total_wer.assign_add(batch_wer)
#         self.count.assign_add(batch_count)
#
#     def result(self):
#         return self.total_wer / self.count
#
#     def reset_states(self):
#         self.total_wer.assign(0.0)
#         self.count.assign(0.0)

# class WordErrorRateMetric(tf.keras.metrics.Metric):
#     def __init__(self, name="wer", **kwargs):
#         super(WordErrorRateMetric, self).__init__(name=name, **kwargs)
#         self.total_wer = self.add_weight(name="total_wer", initializer="zeros", dtype=tf.float32)
#         self.count = self.add_weight(name="count", initializer="zeros", dtype=tf.float32)
#
#     def update_state(self, y_true, y_pred, sample_weight=None):
#         """
#         Update WER for a batch.
#
#         Args:
#             y_true: Ground truth labels (Tensor of strings).
#             y_pred: Predicted labels (Tensor of strings).
#         """
#         def logits_to_text(logits):
#             return tf.strings.reduce_join(num_to_char(logits), axis=-1)
#
#         # Convert logits to text
#         true_texts = logits_to_text(y_true)
#         pred_texts = logits_to_text(y_pred)
#
#         # Split strings into words
#         true_words = tf.strings.split(true_texts)
#         pred_words = tf.strings.split(pred_texts)
#
#         # Convert RaggedTensors to SparseTensors
#         # true_words_sparse = true_words.to_sparse()
#         # pred_words_sparse = pred_words.to_sparse()
#
#         # Calculate the edit distance (Levenshtein distance)
#         edit_distances = tf.edit_distance(pred_words, true_words, normalize=False)
#
#         # Calculate WER for each sample
#         true_lengths = tf.cast(true_words.row_lengths(), tf.float32)
#         sample_wer = tf.where(true_lengths > 0, edit_distances / true_lengths, tf.zeros_like(true_lengths))
#
#         # Update metric
#         self.total_wer.assign_add(tf.reduce_sum(sample_wer))
#         self.count.assign_add(tf.cast(tf.size(sample_wer), tf.float32))
#
#     def result(self):
#         return self.total_wer / self.count
#
#     def reset_states(self):
#         self.total_wer.assign(0.0)
#         self.count.assign(0.0)

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
            predictions = self.model.predict(videos)  # Predict logits from the model
            predictions = tf.cast(predictions, dtype=tf.float32)

            # Decode predictions
            decoded_predictions = decode_predictions(predictions, beam_width=5)
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

        except StopIteration:
            print("No more examples in the validation dataset.")
