# data_processing/mouth_detection.py

###############################
#         Imports             #
###############################

# Standard library imports
import cv2
import numpy as np

# Third-party imports
import mediapipe as mp
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# Local application imports
from model.constants import VIDEO_WIDTH, VIDEO_HEIGHT


###############################
#       MouthDetector Class   #
###############################

class MouthDetector:
    """
    A class for detecting and cropping the mouth region from video frames using MediaPipe.

    Attributes:
        detector: An instance of MediaPipe's FaceLandmarker configured for mouth detection.
    """

    def __init__(self, model_path='model/assets/face_landmarker.task', num_faces=1):
        """
        Initialize the MouthDetector with specified model path and number of faces.

        Args:
            model_path (str): Path to the face landmarker task asset.
            num_faces (int): Number of faces to detect.
        """
        base_options = python.BaseOptions(
            model_asset_path=model_path,
            delegate=mp.tasks.BaseOptions.Delegate.GPU
        )
        # Uncomment the following line to use CPU instead of GPU:
        # base_options = python.BaseOptions(model_asset_path=model_path, delegate=mp.tasks.BaseOptions.Delegate.CPU)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=num_faces
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)

    def expand_bounding_box(self, xmin, ymin, xmax, ymax, padding_ratio=0.4):
        """
        Expand the bounding box by a given padding ratio.

        Args:
            xmin (int): Initial x-coordinate of the bounding box.
            ymin (int): Initial y-coordinate of the bounding box.
            xmax (int): Initial maximum x-coordinate of the bounding box.
            ymax (int): Initial maximum y-coordinate of the bounding box.
            padding_ratio (float): Ratio by which to expand the box dimensions.

        Returns:
            Tuple (xmin, ymin, xmax, ymax) with updated coordinates.
        """
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
        """
        Draw facial landmarks on a copy of the input image.

        Args:
            rgb_image (np.array): The original RGB image.
            detection_result: The detection result from the face landmarker containing landmarks.

        Returns:
            Annotated image with drawn landmarks.
        """
        face_landmarks_list = detection_result.face_landmarks
        annotated_image = np.copy(rgb_image)

        for face_landmarks in face_landmarks_list:
            # Convert landmarks to a protobuf format required by MediaPipe drawing utils
            face_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            face_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z)
                for landmark in face_landmarks
            ])

            # Draw different parts of the face mesh
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles.get_default_face_mesh_tesselation_style()
            )
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles.get_default_face_mesh_contours_style()
            )
            solutions.drawing_utils.draw_landmarks(
                image=annotated_image,
                landmark_list=face_landmarks_proto,
                connections=mp.solutions.face_mesh.FACEMESH_IRISES,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp.solutions.drawing_styles.get_default_face_mesh_iris_connections_style()
            )

        return annotated_image

    def crop_mouth_from_landmarks(self, rgb_image, detection_result, target_size=(VIDEO_WIDTH, VIDEO_HEIGHT)):
        """
        Crop and resize the mouth region from the input image based on detected landmarks.

        Args:
            rgb_image (np.array): The RGB image from which to crop.
            detection_result: The detection result containing facial landmarks.
            target_size (tuple): Desired output size (width, height).

        Returns:
            The cropped and resized mouth image, or None if cropping fails.
        """
        if detection_result and detection_result.face_landmarks:
            try:
                face_landmarks = detection_result.face_landmarks[0]
                # Predefined indices corresponding to mouth landmarks
                mouth_landmarks = [
                    61, 185, 40, 39, 37, 0, 267, 269, 270, 409,
                    146, 91, 181, 84, 17, 314, 405, 321, 375, 291,
                    78, 191, 80, 81, 82, 13, 312, 311, 310, 415,
                    95, 88, 178, 87, 14, 317, 402, 318, 324, 308
                ]
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
        """
        Detect facial landmarks in the frame and crop the mouth region.

        Args:
            frame (np.array): The input frame in BGR format.
            target_size (tuple): Desired output size (width, height).

        Returns:
            Cropped mouth image if detection is successful, otherwise None.
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image_input = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = self.detector.detect(mp_image_input)
        return self.crop_mouth_from_landmarks(mp_image_input.numpy_view(), detection_result, target_size=target_size)
