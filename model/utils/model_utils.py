import tensorflow as tf

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