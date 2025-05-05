"""
Custom utilities for CTC loss and lip-reading evaluation metrics.
Includes:
  - ctc_loss: CTC loss function wrapper for TensorFlow.
  - CharacterErrorRate: Metric to compute Character Error Rate (CER).
  - WordErrorRate: Metric to compute Word Error Rate (WER).
  - decode_predictions: Beam search decoding for CTC model outputs.
"""
import tensorflow as tf
from constants import num_to_char


def ctc_loss(y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
    """
    Compute the CTC (Connectionist Temporal Classification) loss.

    This function prepares dense labels for CTC by converting them to sparse format,
    computes input and label sequence lengths, and applies TensorFlow's ctc_loss.

    Args:
        y_true (tf.Tensor): Dense integer labels with padding, shape [batch_size, max_label_length].
        y_pred (tf.Tensor): Logits from the model, shape [batch_size, time_steps, num_classes].

    Returns:
        tf.Tensor: Scalar tensor representing the mean CTC loss over the batch.

    Raises:
        InvalidArgumentError: If tensor shapes are incompatible for CTC loss.
    """
    # Convert true labels to sparse representation
    y_true = tf.cast(y_true, dtype=tf.int32)
    y_true_sparse = tf.sparse.from_dense(y_true)
    # Cast predictions to float
    y_pred = tf.cast(y_pred, dtype=tf.float32)

    # Determine lengths of model logit sequences (time dimension)
    input_length = tf.reduce_sum(
        tf.ones_like(y_pred[:, :, 0], dtype=tf.int32), axis=1
    )
    # Determine lengths of label sequences by finding max index + 1
    label_length = tf.sparse.reduce_max(y_true_sparse, axis=1) + 1

    # Compute CTC loss across the batch
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
    """
    TensorFlow metric for Character Error Rate (CER).

    This metric accumulates normalized edit distances between predicted and true
    character sequences and computes their average.
    """

    def __init__(self, name='CER', **kwargs):
        """
        Initialize the CharacterErrorRate metric.

        Args:
            name (str): Name identifier for the metric.
            **kwargs: Additional arguments passed to base Metric class.
        """
        super().__init__(name=name, **kwargs)
        self.cer_accumulator = self.add_weight(
            name='cer_accumulator', initializer='zeros', dtype=tf.float32
        )
        self.counter = self.add_weight(
            name='counter', initializer='zeros', dtype=tf.int32
        )

    def update_state(self, y_true: tf.Tensor, y_pred: tf.Tensor, sample_weight=None) -> None:
        """
        Update the metric state with a new batch of predictions.

        Args:
            y_true (tf.Tensor): Dense true labels, shape [batch_size, label_length].
            y_pred (tf.Tensor): Logits, shape [batch_size, time_steps, num_classes].
            sample_weight: Optional weighting factor (unused).
        """
        # Convert true labels to sparse format
        y_true_sparse = tf.cast(tf.sparse.from_dense(y_true), tf.int64)
        # Compute sequence lengths for predictions
        input_length = tf.reduce_sum(
            tf.ones_like(y_pred[:, :, 0], dtype=tf.int32), axis=1
        )
        # Transpose logits for decoder
        y_pred_transposed = tf.transpose(y_pred, perm=[1, 0, 2])
        # Greedy CTC decoding
        decoded, _ = tf.nn.ctc_greedy_decoder(
            tf.cast(y_pred_transposed, tf.float32), input_length, merge_repeated=True
        )
        sparse_decoded = tf.sparse.retain(
            decoded[0], tf.not_equal(decoded[0].values, -1))

        # Compute normalized edit distance per sample
        distances = tf.edit_distance(
            sparse_decoded, y_true_sparse, normalize=True)
        # Accumulate total distance and sample count
        self.cer_accumulator.assign_add(tf.reduce_sum(distances))
        self.counter.assign_add(tf.cast(tf.shape(y_true)[0], tf.int32))

    def result(self) -> tf.Tensor:
        """
        Compute the final CER metric.

        Returns:
            tf.Tensor: The average character error rate.
        """
        return tf.math.divide_no_nan(
            self.cer_accumulator, tf.cast(self.counter, tf.float32)
        )

    def reset_states(self) -> None:
        """
        Reset the metric accumulators to initial state.
        """
        self.cer_accumulator.assign(0.0)
        self.counter.assign(0)


class WordErrorRate(tf.keras.metrics.Metric):
    """
    TensorFlow metric for Word Error Rate (WER).

    This metric computes normalized edit distance at the word level between
    predicted and true text sequences.
    """

    def __init__(self, name: str = 'WER', **kwargs):
        """
        Initialize the WordErrorRate metric.

        Args:
            name (str): Name identifier for the metric.
            **kwargs: Additional arguments passed to base Metric class.
        """
        super().__init__(name=name, **kwargs)
        self.wer_accumulator = self.add_weight(
            name='wer_accumulator', initializer='zeros', dtype=tf.float32
        )
        self.counter = self.add_weight(
            name='counter', initializer='zeros', dtype=tf.int32
        )

    def update_state(self, y_true: tf.Tensor, y_pred: tf.Tensor, sample_weight=None) -> None:
        """
        Update the metric state with a new batch for WER computation.

        Args:
            y_true (tf.Tensor): Dense true labels, shape [batch_size, label_length].
            y_pred (tf.Tensor): Logits, shape [batch_size, time_steps, num_classes].
            sample_weight: Optional weighting factor (unused).
        """
        # Sequence lengths for model logits
        input_length = tf.reduce_sum(
            tf.ones_like(y_pred[:, :, 0], dtype=tf.int32), axis=1
        )
        # Transpose for CTC decoding
        y_pred_transposed = tf.transpose(y_pred, perm=[1, 0, 2])
        decoded, _ = tf.nn.ctc_greedy_decoder(
            tf.cast(y_pred_transposed, tf.float32), input_length, merge_repeated=True
        )
        dense_decoded = tf.sparse.to_dense(decoded[0], default_value=-1)
        # Map token indices to characters
        decoded_chars = num_to_char(dense_decoded)
        decoded_text = tf.strings.reduce_join(decoded_chars, axis=-1)
        decoded_words = tf.strings.split(decoded_text, sep=' ')

        # True text and word splitting
        true_text = tf.strings.reduce_join(num_to_char(y_true), axis=-1)
        true_words = tf.strings.split(true_text, sep=' ')

        batch_size = tf.shape(y_true)[0]

        def _compute_distance(pred_words, true_words):
            """
            Compute normalized edit distance between word sequences.

            Args:
                pred_words (tf.Tensor): Predicted words.
                true_words (tf.Tensor): True words.

            Returns:
                tf.Tensor: Scalar distance.
            """
            # Hash words to integers to build sparse tensors
            num_buckets = 1000000
            pred_hash = tf.strings.to_hash_bucket(pred_words, num_buckets)
            true_hash = tf.strings.to_hash_bucket(true_words, num_buckets)
            pred_sparse = tf.sparse.from_dense(tf.reshape(pred_hash, [1, -1]))
            true_sparse = tf.sparse.from_dense(tf.reshape(true_hash, [1, -1]))
            return tf.edit_distance(pred_sparse, true_sparse, normalize=True)[0]

        # Compute WER per sample
        wer_vals = tf.map_fn(
            lambda i: tf.cond(
                tf.equal(tf.size(true_words[i]), 0),
                lambda: tf.constant(0.0),
                lambda: _compute_distance(decoded_words[i], true_words[i])
            ),
            tf.range(batch_size),
            fn_output_signature=tf.float32
        )
        # Accumulate
        self.wer_accumulator.assign_add(tf.reduce_sum(wer_vals))
        self.counter.assign_add(batch_size)

    def result(self) -> tf.Tensor:
        """
        Compute the final WER metric.

        Returns:
            tf.Tensor: The average word error rate.
        """
        return tf.math.divide_no_nan(
            self.wer_accumulator, tf.cast(self.counter, tf.float32)
        )

    def reset_states(self) -> None:
        """
        Reset the metric accumulators to initial state.
        """
        self.wer_accumulator.assign(0.0)
        self.counter.assign(0)


def decode_predictions(y_pred: tf.Tensor, beam_width: int = 10) -> list:
    """
    Perform beam search decoding on CTC model logits.

    Args:
        y_pred (tf.Tensor): Logits, shape [batch_size, time_steps, num_classes].
        beam_width (int): Beam width for the decoder.

    Returns:
        list of tf.SparseTensor: Decoded sequences as sparse tensors.
    """
    # Convert to time-major [time_steps, batch_size, num_classes]
    y_pred_tm = tf.transpose(y_pred, perm=[1, 0, 2])
    seq_len = tf.fill([tf.shape(y_pred_tm)[1]], tf.shape(y_pred_tm)[0])
    decoded, _ = tf.nn.ctc_beam_search_decoder(
        y_pred_tm, sequence_length=seq_len, beam_width=beam_width
    )
    return decoded
