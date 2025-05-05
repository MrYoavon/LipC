import pytest
import numpy as np
import tensorflow as tf
from constants import VIDEO_WIDTH, VIDEO_HEIGHT
from services.lip_reading.lip_reader import LipReadingPipeline, get_lip_model


@pytest.mark.asyncio
async def test_lip_model_loads_and_pipeline():
    model = await get_lip_model()
    assert isinstance(model, tf.keras.Model)

    # Pipeline should accept a dummy frame of correct size
    dummy = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)
    pipeline = LipReadingPipeline(model, sequence_length=1)
    result = pipeline.process_frame(dummy)
    # With sequence_length=1, it should return a (possibly empty) string or None
    assert result is None or isinstance(result, str)
