# data_processing/mouth_detection.py

# Standard library imports
import cv2
import numpy as np

# Third-party imports
import mediapipe as mp
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from constants import VIDEO_WIDTH, VIDEO_HEIGHT


class MouthDetector:
    def __init__(self, model_path='models/face_landmarker.task', num_faces=1):
        base_options = python.BaseOptions(model_asset_path=model_path, delegate=mp.tasks.BaseOptions.Delegate.GPU)
        # base_options = python.BaseOptions(model_asset_path=model_path, delegate=mp.tasks.BaseOptions.Delegate.CPU)
        options = vision.FaceLandmarkerOptions(base_options=base_options,
                                               output_face_blendshapes=True,
                                               output_facial_transformation_matrixes=True,
                                               num_faces=num_faces)
        self.detector = vision.FaceLandmarker.create_from_options(options)

    def expand_bounding_box(self, xmin, ymin, xmax, ymax, padding_ratio=0.4):
        width = xmax - xmin
        height = ymax - ymin
        pad_w = int(width * padding_ratio)
        pad_h = int(height * padding_ratio)
        xmin = max(xmin - pad_w, 0)
        ymin = max(ymin - pad_h, 0)
        xmax = xmax + pad_w
        ymax = ymax + pad_h
        return xmin, ymin, xmax, ymax

    def draw_landmarks_on_image(self, rgb_image, detection_result):
        face_landmarks_list = detection_result.face_landmarks
        annotated_image = np.copy(rgb_image)

        for idx in range(len(face_landmarks_list)):
            face_landmarks = face_landmarks_list[idx]

            face_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            face_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in face_landmarks
            ])

            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles
                .get_default_face_mesh_tesselation_style())
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles
                .get_default_face_mesh_contours_style())
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_IRISES,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles
                .get_default_face_mesh_iris_connections_style())

        return annotated_image

    def crop_mouth_from_landmarks(self, rgb_image, detection_result, target_size=(VIDEO_WIDTH, VIDEO_HEIGHT)):
        if detection_result and detection_result.face_landmarks:
            try:
                face_landmarks = detection_result.face_landmarks[0]
                # These are the landmarks for the mouth
                mouth_landmarks = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409,
                                   146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
                                   78, 191, 80, 81, 82, 13, 312, 311, 310, 415,
                                   95, 88, 178, 87, 14, 317, 402, 318, 324, 308]

                x_coords = [face_landmarks[landmark].x for landmark in mouth_landmarks]
                y_coords = [face_landmarks[landmark].y for landmark in mouth_landmarks]
                xmin, xmax = int(min(x_coords) * rgb_image.shape[1]), int(max(x_coords) * rgb_image.shape[1])
                ymin, ymax = int(min(y_coords) * rgb_image.shape[0]), int(max(y_coords) * rgb_image.shape[0])

                xmin, ymin, xmax, ymax = self.expand_bounding_box(xmin, ymin, xmax, ymax)
                cropped_mouth = rgb_image[ymin:ymax, xmin:xmax]
                return cv2.resize(cropped_mouth, target_size, interpolation=cv2.INTER_AREA)
            except cv2.error:
                return None
        return None

    def detect_and_crop_mouth(self, frame, target_size=(VIDEO_WIDTH, VIDEO_HEIGHT)):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image_input = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = self.detector.detect(mp_image_input)
        return self.crop_mouth_from_landmarks(mp_image_input.numpy_view(), detection_result, target_size=target_size)

    def detect_face_landmarks(self, frame):
        """
        Uses the face mesh model to detect facial landmarks.
        
        Args:
            frame: A BGR image (numpy array) from OpenCV.
        
        Returns:
            detection_result: The output from the face mesh model containing landmark data.
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image_input = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = self.detector.detect(mp_image_input)
        return detection_result