import tensorflow as tf

from constants import num_to_char


def ctc_loss(y_true, y_pred):
    y_true = tf.cast(y_true, dtype=tf.int32)
    y_true_sparse = tf.sparse.from_dense(y_true)
    y_pred = tf.cast(y_pred, dtype=tf.float32)

    input_length = tf.reduce_sum(tf.ones_like(
        # Length of each input sequence
        y_pred[:, :, 0], dtype=tf.int32), axis=1)
    # Adding 1 because it starts at 0
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


class CharacterErrorRate(tf.keras.metrics.Metric):
    """A custom TensorFlow metric to compute the Character Error Rate (CER)."""

    def __init__(self, name='CER', **kwargs):
        super(CharacterErrorRate, self).__init__(name=name, **kwargs)
        self.cer_accumulator = tf.Variable(
            0.0, name="cer_accumulator", dtype=tf.float32)
        self.counter = tf.Variable(0, name="counter", dtype=tf.int32)

    def update_state(self, y_true, y_pred, sample_weight=None):
        y_true_sparse = tf.cast(tf.sparse.from_dense(y_true), tf.int64)

        input_length = tf.reduce_sum(tf.ones_like(
            y_pred[:, :, 0], dtype=tf.int32), axis=1)
        # Transpose to [time, batch, classes]
        y_pred_transposed = tf.transpose(y_pred, perm=[1, 0, 2])
        decode_list, log = tf.nn.ctc_greedy_decoder(tf.cast(y_pred_transposed, tf.float32), input_length,
                                                    merge_repeated=True)

        # ctc_greedy_decoder returns a list of one element
        decode = decode_list[0]
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
        self.wer_accumulator = tf.Variable(
            0.0, name="wer_accumulator", dtype=tf.float32)
        self.counter = tf.Variable(0, name="counter", dtype=tf.int32)

    def update_state(self, y_true, y_pred, sample_weight=None):
        input_length = tf.reduce_sum(tf.ones_like(
            y_pred[:, :, 0], dtype=tf.int32), axis=1)
        # Transpose to [time, batch, classes]
        y_pred_transposed = tf.transpose(y_pred, perm=[1, 0, 2])
        decode_list, log = tf.nn.ctc_greedy_decoder(
            tf.cast(y_pred_transposed, tf.float32), input_length, merge_repeated=True)

        # ctc_greedy_decoder returns a list of one element
        decoded_indices = decode_list[0]
        decoded_dense = tf.sparse.to_dense(decoded_indices, default_value=-1)
        # Use your `num_to_char` layer
        decoded_chars = num_to_char(decoded_dense)
        decoded_text = tf.strings.reduce_join(
            decoded_chars, axis=-1)  # Shape: [batch_size]
        # RaggedTensor [batch, num_words]
        decoded_words = tf.strings.split(decoded_text, sep=" ")

        y_true_text = tf.strings.reduce_join(
            num_to_char(y_true), axis=-1)  # Shape: [batch_size]
        # RaggedTensor [batch, num_words]
        y_true_words = tf.strings.split(y_true_text, sep=" ")

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
            pred_hashes = tf.strings.to_hash_bucket(
                pred_words_sample, num_buckets)
            true_hashes = tf.strings.to_hash_bucket(
                true_words_sample, num_buckets)

            # Reshape to 2D tensors with batch dimension [1, num_words]
            # Shape: [1, num_pred_words]
            pred_hashes = tf.reshape(pred_hashes, [1, -1])
            # Shape: [1, num_true_words]
            true_hashes = tf.reshape(true_hashes, [1, -1])

            # Create sparse tensors for edit distance
            pred_sparse = tf.sparse.from_dense(pred_hashes)
            true_sparse = tf.sparse.from_dense(true_hashes)

            # Compute edit distance (normalized by true word count)
            distance = tf.edit_distance(
                pred_sparse, true_sparse, normalize=True)
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


def decode_predictions(y_pred, beam_width=10):
    # y_pred: (batch_size, timesteps, num_classes)
    # Convert to time-major format
    y_pred = tf.transpose(y_pred, perm=[1, 0, 2])
    input_length = tf.fill([tf.shape(y_pred)[1]], tf.shape(y_pred)[
                           0])  # Dynamic sequence lengths

    # Perform beam search decoding
    decoded, log_prob = tf.nn.ctc_beam_search_decoder(
        y_pred,
        sequence_length=input_length,
        beam_width=beam_width
    )
    return decoded
