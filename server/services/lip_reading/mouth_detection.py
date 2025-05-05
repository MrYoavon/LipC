# data_processing/mouth_detection.py

import cv2
import numpy as np
import mediapipe as mp
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from constants import VIDEO_WIDTH, VIDEO_HEIGHT


class MouthDetector:
    """
    Detects and crops the mouth region from video frames using MediaPipe FaceLandmarker.

    This class loads a face landmark detection model and provides methods to
    detect face landmarks, draw landmarks, expand bounding boxes, and crop
    the mouth region for downstream processing.
    """

    def __init__(self, model_path: str = 'models/face_landmarker.task', num_faces: int = 1) -> None:
        """
        Initialize the MouthDetector with a MediaPipe FaceLandmarker model.

        Args:
            model_path (str): Filesystem path to the FaceLandmarker task model.
            num_faces (int): Maximum number of faces to detect per frame.

        Raises:
            Exception: If model creation fails.
        """
        base_options = python.BaseOptions(
            model_asset_path=model_path,
            delegate=mp.tasks.BaseOptions.Delegate.GPU
        )
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=num_faces
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)

    def expand_bounding_box(
        self,
        xmin: int,
        ymin: int,
        xmax: int,
        ymax: int,
        padding_ratio: float = 0.4
    ) -> tuple[int, int, int, int]:
        """
        Expand a bounding box by a padding ratio, clamped to image origin.

        Args:
            xmin (int): Minimum x-coordinate of the box.
            ymin (int): Minimum y-coordinate of the box.
            xmax (int): Maximum x-coordinate of the box.
            ymax (int): Maximum y-coordinate of the box.
            padding_ratio (float): Fractional padding to apply to width/height.

        Returns:
            tuple[int, int, int, int]: Expanded (xmin, ymin, xmax, ymax).
        """
        width = xmax - xmin
        height = ymax - ymin
        pad_w = int(width * padding_ratio)
        pad_h = int(height * padding_ratio)
        return (
            max(xmin - pad_w, 0),
            max(ymin - pad_h, 0),
            xmax + pad_w,
            ymax + pad_h
        )

    def draw_landmarks_on_image(
        self,
        rgb_image: np.ndarray,
        detection_result
    ) -> np.ndarray:
        """
        Annotate an RGB image with face mesh landmarks and connections.

        Args:
            rgb_image (np.ndarray): Input image in RGB color space.
            detection_result (FaceLandmarkerResult): Landmark detection output.

        Returns:
            np.ndarray: Annotated image copy with landmarks drawn.
        """
        annotated = rgb_image.copy()
        for landmarks in detection_result.face_landmarks:
            proto = landmark_pb2.NormalizedLandmarkList()
            proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=lm.x, y=lm.y, z=lm.z)
                for lm in landmarks
            ])
            # Draw tessellation, contours, and irises
            for conn, style in [
                (mp.solutions.face_mesh.FACEMESH_TESSELATION,
                 solutions.drawing_styles.get_default_face_mesh_tesselation_style()),
                (mp.solutions.face_mesh.FACEMESH_CONTOURS,
                 solutions.drawing_styles.get_default_face_mesh_contours_style()),
                (mp.solutions.face_mesh.FACEMESH_IRISES,
                 solutions.drawing_styles.get_default_face_mesh_iris_connections_style())
            ]:
                solutions.drawing_utils.draw_landmarks(
                    image=annotated,
                    landmark_list=proto,
                    connections=conn,
                    landmark_drawing_spec=None,
                    connection_drawing_spec=style
                )
        return annotated

    def crop_mouth_from_landmarks(
        self,
        rgb_image: np.ndarray,
        detection_result,
        target_size: tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)
    ) -> np.ndarray | None:
        """
        Crop and resize the mouth region from an RGB image based on landmarks.

        Args:
            rgb_image (np.ndarray): Input image in RGB color space.
            detection_result (FaceLandmarkerResult): Landmark detection output.
            target_size (tuple[int, int]): Desired output (width, height).

        Returns:
            np.ndarray | None: Resized mouth crop, or None if detection fails.
        """
        if not detection_result.face_landmarks:
            return None
        try:
            landmarks = detection_result.face_landmarks[0]
            mouth_idxs = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 146, 91, 181, 84, 17, 314, 405, 321, 375,
                          291, 78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308]
            xs = [landmarks[i].x for i in mouth_idxs]
            ys = [landmarks[i].y for i in mouth_idxs]
            h, w, _ = rgb_image.shape
            xmin, xmax = int(min(xs)*w), int(max(xs)*w)
            ymin, ymax = int(min(ys)*h), int(max(ys)*h)
            xmin, ymin, xmax, ymax = self.expand_bounding_box(
                xmin, ymin, xmax, ymax)
            crop = rgb_image[ymin:ymax, xmin:xmax]
            return cv2.resize(crop, target_size, interpolation=cv2.INTER_AREA)
        except Exception:
            return None

    def detect_and_crop_mouth(
        self,
        frame: np.ndarray,
        target_size: tuple[int, int] = (VIDEO_WIDTH, VIDEO_HEIGHT)
    ) -> np.ndarray | None:
        """
        Full pipeline: detect face, then crop and resize mouth region.

        Args:
            frame (np.ndarray): Input BGR image from video source.
            target_size (tuple[int, int]): Desired mouth crop size.

        Returns:
            np.ndarray | None: RGB mouth crop resized, or None on failure.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.detector.detect(mp_image)
        return self.crop_mouth_from_landmarks(mp_image.numpy_view(), result, target_size)

    def detect_face_landmarks(
        self,
        frame: np.ndarray
    ):
        """
        Detect facial landmarks in a BGR image using the face mesh model.

        Args:
            frame (np.ndarray): Input BGR image.

        Returns:
            FaceLandmarkerResult: Detection result with landmark lists.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        return self.detector.detect(mp_image)
