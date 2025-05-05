# tests/test_mouth_detection.py
import numpy as np
import cv2
import pytest
from data_processing.mouth_detection import MouthDetector


def test_expand_bounding_box_simple():
    xmin, ymin, xmax, ymax = 10, 10, 30, 20
    md = MouthDetector(model_path='assets/face_landmarker.task', num_faces=1)
    # padding_ratio default 0.4 → pad_w=8, pad_h=4
    exmin, eymin, exmax, eymax = md.expand_bounding_box(xmin, ymin, xmax, ymax)
    assert exmin == 2 and eymin == 6
    assert exmax == 38 and eymax == 24
