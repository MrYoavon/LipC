import cv2
import datetime
import numpy as np
from model.data_processing.mouth_detection import MouthDetector
from tensorflow.keras.models import load_model
from model.training import decode_predictions, ctc_loss
from model.data_processing.data_processing import preprocess_frame_sequence  # Function for preprocessing frames

# Initialize MouthDetector with the model path
mouth_detector = MouthDetector(model_path='../assets/face_landmarker.task', num_faces=1)

# Load the TensorFlow lip-reading model
model_path = '../models/final_model.keras'
lip_reading_model = load_model(model_path, custom_objects={"ctc_loss": ctc_loss})

# Open video capture from live camera or video file
video_source = 0  # Use 0 for live camera, or provide a file path for saved videos
video_capture = cv2.VideoCapture(video_source)

# Parameters for real-time processing
sequence_length = 64  # Number of frames for a sequence
frame_sequence = []  # Buffer to store frames for prediction


def main():
    while True:
        result, video_frame = video_capture.read()  # Read frames from the video
        if not result:
            break  # Terminate the loop if the frame is not read successfully

        # Process the video frame and get the cropped mouth
        cropped_mouth = mouth_detector.detect_and_crop_mouth(video_frame.copy())

        if cropped_mouth is not None:
            # Display the processed mouth frame
            cv2.imshow("Mouth", cropped_mouth)

            # Preprocess the cropped frame
            preprocessed_frame = preprocess_frame_sequence(cropped_mouth)
            frame_sequence.append(preprocessed_frame)

            # If enough frames are collected, run inference
            if len(frame_sequence) == sequence_length:
                # Convert frame sequence to a batch tensor
                input_array = np.expand_dims(np.array(frame_sequence), axis=0)  # Add batch dimension
                frame_sequence.pop(0)  # Remove the oldest frame to maintain sequence length

                predictions = lip_reading_model.predict(input_array)

                # Decode predictions to text
                predicted_caption = decode_predictions(predictions[0])  # Assume batch size = 1
                print(f"Caption: {predicted_caption}")

                # Overlay the caption on the original video frame
                cv2.putText(video_frame, predicted_caption, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            1, (255, 255, 255), 2, cv2.LINE_AA)

        else:
            print(f"{datetime.datetime.now().strftime('%H:%M:%S')} Unable to detect mouth")

        # Display the original video with captions
        cv2.imshow('Video', video_frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):  # Exit on 'q' key press
            break

    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
