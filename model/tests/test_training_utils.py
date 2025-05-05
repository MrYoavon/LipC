# tests/test_training_utils.py
import math
import tensorflow as tf
from core_model.training import (
    cosine_annealing_with_warm_restarts,
    ctc_loss,
    CharacterErrorRate,
    WordErrorRate
)


def test_cosine_scheduler_basic():
    # initial lr = 0.001, T_0=2, T_mult=2
    lrs = [cosine_annealing_with_warm_restarts(e, T_0=2, T_mult=2, initial_lr=0.001, eta_min=0.0)
           for e in range(4)]
    # epoch 0 → lr=initial
    assert math.isclose(lrs[0], 0.001, rel_tol=1e-6)
    # epoch 1 → halfway down
    assert 0.0005 <= lrs[1] < 0.001
    # epoch 2 → restart → lr≈initial
    assert math.isclose(lrs[2], 0.001, rel_tol=1e-6)


def test_ctc_loss_and_metrics_zero():
    # simple y_true, y_pred that match exactly
    y_true = tf.constant([[1, 2, 3]], dtype=tf.int32)
    y_pred = tf.one_hot([[1, 2, 3]], depth=5, dtype=tf.float32)
    loss = ctc_loss(y_true, y_pred)
    assert loss.numpy() >= 0

    # CER and WER should be zero for perfect match
    cer = CharacterErrorRate()
    wer = WordErrorRate()
    cer.update_state(y_true, y_pred)
    wer.update_state(y_true, y_pred)
    assert cer.result().numpy() == 0.0
    assert wer.result().numpy() == 0.0
