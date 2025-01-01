# model/training.py
import os
import editdistance

import tensorflow as tf
from tensorflow.keras.callbacks import Callback, ModelCheckpoint, EarlyStopping, LearningRateScheduler
from tensorflow.keras.models import Sequential
from tensorflow.keras import mixed_precision

from data_processing.data_processing import num_to_char


def train_model(model: Sequential, train_data: tf.data.Dataset, validation_data: tf.data.Dataset|None) -> tuple[Sequential, tf.keras.callbacks.History]:
    # Step 1: Initialize and compile the model
    # Compile the model with Adam optimizer and CTC loss
    # # When using mixed precision, we need to use a special optimizer wrapper to avoid issues with numerical stability
    # base_optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)
    # optimizer = mixed_precision.LossScaleOptimizer(base_optimizer)
    model.compile(
                  # optimizer=optimizer,
                  optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss=ctc_loss,
                  # metrics=[wer_metric]
                  )

    # Step 2: Define Callbacks
    # Learning rate scheduler (adjusts lr based on epochs)
    lr_scheduler_callback = LearningRateScheduler(scheduler)

    # Model checkpoint
    checkpoint_dir = 'models'
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_callback = ModelCheckpoint(
        os.path.join(checkpoint_dir, 'checkpoint_epoch_{epoch:02d}.weights.h5'),
        monitor='val_loss',
        save_weights_only=True,
        verbose=1
    )

    # Early stopping (stops training if loss stops improving)
    early_stopping_callback = EarlyStopping(monitor='val_loss', patience=10, verbose=1)

    # Produce one example
    example_callback = ProduceExample(validation_data)

    # Compute sequence lengths
    # sequence_lengths = tf.reduce_sum(tf.cast(train_data != 0, tf.int32), axis=1)

    # Step 3: Train the model
    history = None
    try:
        history = model.fit(
            train_data,  # Outputs dictionary {"video", "input_length", "label_length"}
            validation_data=validation_data,
            epochs=5,
            callbacks=[checkpoint_callback,
                       early_stopping_callback,
                       lr_scheduler_callback,
                       example_callback,
                    ],
            verbose=1,
            # sample_weight=sequence_lengths.numpy()
        )
    except tf.errors.DataLossError as e:
        print("Error during training:", e)
        for frames, labels in train_data.take(1):
            print(frames.shape, labels.shape)

    return model, history


def scheduler(epoch, lr):
    updated_lr = lr if epoch < 30 else lr * tf.math.exp(-0.1)
    print(f"Epoch {epoch + 1}: Learning rate is {updated_lr}")
    return updated_lr


def ctc_loss(y_true, y_pred):
    y_true = tf.cast(y_true, dtype=tf.int64)
    y_pred = tf.cast(y_pred, dtype=tf.float32)

    input_length = tf.reduce_sum(tf.ones_like(y_pred[:, :, 0], dtype=tf.int64), axis=1)  # Length of each input sequence
    label_length = tf.reduce_sum(tf.ones_like(y_true, dtype=tf.int64), axis=1)  # Length of each label sequence

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


def wer_metric(y_true, y_pred):
    # Define the function that computes WER
    def compute_wer(true, pred):
        # Decode sequences of integers to characters (assumes num_to_char is available)
        # true_str = tf.strings.reduce_join(num_to_char(true), axis=-1).decode('utf-8')
        # pred_str = tf.strings.reduce_join(num_to_char(pred), axis=-1).decode('utf-8')
        for temp in true.numpy():
            for word1 in temp:
                print(word1)
        for temp2 in pred.numpy():
            for word2 in temp2:
                print(word2)
        true_str = tf.strings.reduce_join(
            [num_to_char(word).numpy().decode('utf-8') for batch in true.numpy() for word in batch if word != -1]
        )
        pred_str = tf.strings.reduce_join(
            [num_to_char(word).numpy().decode('utf-8') for batch in pred.numpy() for word in batch if word != -1]
        )

        # Split by spaces to calculate WER
        reference = true_str.split()
        hypothesis = pred_str.split()
        distance = editdistance.eval(reference, hypothesis)
        return distance / float(len(reference)) if len(reference) > 0 else 0.0

    # Use tf.py_function to call the Python function within the graph
    wer = tf.py_function(compute_wer, [y_true, y_pred], tf.float32)

    # tf.py_function returns a tensor, so we need to ensure it is returned properly
    wer.set_shape([])  # Setting shape to scalar
    return wer


class ProduceExample(tf.keras.callbacks.Callback):
    def __init__(self, dataset) -> None:
        super().__init__()
        self.dataset = dataset
        self.dataset_iter = iter(dataset)

    def on_epoch_end(self, epoch, logs=None) -> None:
        try:
            # data = next(self.dataset_iter)
            # yhat = self.model.predict(data[0])
            # decoded = tf.keras.backend.ctc_decode(
            #     yhat,
            #     input_length=tf.fill([tf.shape(yhat)[0]], tf.shape(yhat)[1]),
            #     greedy=True  # Use `False` for beam search
            # )[0][0].numpy()
            #
            # for x in range(len(yhat)):
            #     print('Original:', tf.strings.reduce_join(num_to_char(data[1][x])).numpy().decode('utf-8'))
            #     print('Prediction:', tf.strings.reduce_join(num_to_char(decoded[x])).numpy().decode('utf-8'))
            #     print('~' * 100)
            videos, labels = next(self.dataset_iter)
            predictions = self.model.predict(videos)  # Predict logits from the model

            # Decode predictions
            decoded_predictions = decode_predictions(predictions, beam_width=10)
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
