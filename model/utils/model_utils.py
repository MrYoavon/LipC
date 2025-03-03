import tensorflow as tf


def decode_predictions(y_pred: tf.Tensor, beam_width: int = 10):
    """
    Decode model predictions using beam search for CTC (Connectionist Temporal Classification).

    Args:
        y_pred (tf.Tensor): A tensor with shape [batch_size, timesteps, num_classes] containing model logits.
        beam_width (int): The beam width for beam search decoding (default is 10).

    Returns:
        List[tf.SparseTensor]: A list of sparse tensors representing the decoded sequences.
    """
    # Convert logits to time-major format: [timesteps, batch_size, num_classes]
    y_pred = tf.transpose(y_pred, perm=[1, 0, 2])

    # Create a tensor for sequence lengths (all sequences assumed to be of full length)
    input_length = tf.fill([tf.shape(y_pred)[1]], tf.shape(y_pred)[0])

    # Perform beam search decoding with CTC loss support
    decoded, log_prob = tf.nn.ctc_beam_search_decoder(
        y_pred,
        sequence_length=input_length,
        beam_width=beam_width
    )

    return decoded
