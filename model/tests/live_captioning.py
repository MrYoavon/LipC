import cv2
import datetime
import numpy as np
from tensorflow.keras.models import load_model

from model.data_processing.mouth_detection import MouthDetector
from model.training import decode_predictions, ctc_loss
from model.data_processing.data_processing import preprocess_frame_sequence  # Function for preprocessing frames


def initialize_resources():
    """
    Initialize the mouth detector, load the lip-reading model, and open the video capture device.

    Returns:
        tuple: A tuple containing:
            - mouth_detector (MouthDetector): Initialized mouth detector.
            - lip_reading_model: Loaded Keras lip-reading model.
            - video_capture: OpenCV VideoCapture object.
    """
    # Initialize MouthDetector with the provided model path
    mouth_detector = MouthDetector(model_path='../assets/face_landmarker.task', num_faces=1)

    # Load the pre-trained TensorFlow lip-reading model with custom CTC loss
    model_path = '../models/final_model.keras'
    lip_reading_model = load_model(model_path, custom_objects={"ctc_loss": ctc_loss})

    # Open video capture (0 for live camera, or provide a video file path)
    video_source = 0
    video_capture = cv2.VideoCapture(video_source)

    return mouth_detector, lip_reading_model, video_capture


def process_video_stream(mouth_detector, lip_reading_model, video_capture, sequence_length=64):
    """
    Process frames from the video stream in real-time. Detect and crop the mouth region,
    preprocess frames, run inference when enough frames are collected, and overlay the predicted caption.

    Args:
        mouth_detector (MouthDetector): Instance for detecting and cropping mouth regions.
        lip_reading_model: Loaded lip-reading model for inference.
        video_capture: OpenCV VideoCapture object.
        sequence_length (int): Number of frames required for one prediction.
    """
    frame_sequence = []  # Buffer to store preprocessed frames

    while True:
        result, video_frame = video_capture.read()
        if not result:
            break  # Exit loop if frame reading fails

        # Detect and crop the mouth region from the current frame
        cropped_mouth = mouth_detector.detect_and_crop_mouth(video_frame.copy())

        if cropped_mouth is not None:
            # Display the cropped mouth region
            cv2.imshow("Mouth", cropped_mouth)

            # Preprocess the cropped frame and add it to the sequence buffer
            preprocessed_frame = preprocess_frame_sequence(cropped_mouth)
            frame_sequence.append(preprocessed_frame)

            # Once we have collected enough frames, run inference
            if len(frame_sequence) == sequence_length:
                # Prepare the frame sequence as a batch tensor (batch size = 1)
                input_array = np.expand_dims(np.array(frame_sequence), axis=0)
                # Remove the oldest frame to maintain a constant sequence length
                frame_sequence.pop(0)

                predictions = lip_reading_model.predict(input_array)

                # Decode the model's predictions to text (assuming batch size = 1)
                predicted_caption = decode_predictions(predictions[0])
                print(f"Caption: {predicted_caption}")

                # Overlay the predicted caption on the original video frame
                cv2.putText(
                    video_frame, predicted_caption, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA
                )
        else:
            # Log if the mouth region could not be detected
            current_time = datetime.datetime.now().strftime('%H:%M:%S')
            print(f"{current_time} Unable to detect mouth")

        # Display the original video frame (with overlayed caption if available)
        cv2.imshow('Video', video_frame)

        # Break loop on pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Release resources
    video_capture.release()
    cv2.destroyAllWindows()


def main():
    """
    Main execution function to initialize resources and start video stream processing.
    """
    mouth_detector, lip_reading_model, video_capture = initialize_resources()
    process_video_stream(mouth_detector, lip_reading_model, video_capture)


if __name__ == "__main__":
    main()
