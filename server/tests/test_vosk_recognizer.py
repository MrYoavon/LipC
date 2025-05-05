import pytest
from services.lip_reading.vosk_helper import VoskRecognizer


def test_vosk_recognizer_instantiation_and_final():
    recog = VoskRecognizer()
    final = recog.get_final_result()
    # Even with no audio fed, should be a dict with a 'text' key
    assert isinstance(final, dict) and "text" in final
