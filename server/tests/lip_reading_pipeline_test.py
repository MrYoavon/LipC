import cv2
import tensorflow as tf

from server.services.lip_reading.lip_reader import LipReadingPipeline

# Update these paths as necessary
MODEL_PATH = "server/models/final_model.keras"
VIDEO_PATH = "server/tests/bbaq9s.mp4"  # Path to your video file

# Set the sequence length that your pipeline expects (e.g., 75)
SEQUENCE_LENGTH = 75


def main():
    # Instantiate the lip reading pipeline
    pipeline = LipReadingPipeline(MODEL_PATH, sequence_length=SEQUENCE_LENGTH)

    # Open the video file using OpenCV
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"Error: Could not open video file {VIDEO_PATH}")
        return

    frame_count = 0
    prediction = None

    while True:
        ret, frame = cap.read()
        if not ret:
            # End of video
            print("Reached end of video.")
            break

        # Optionally, you can display each frame
        cv2.imshow("Input Frame", frame)
        # This is needed to allow OpenCV to refresh the image window.
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # Feed the frame to your lip reading pipeline
        prediction = pipeline.process_frame(frame)
        frame_count += 1

        # When a complete sequence of frames is processed, a prediction will be returned.
        if prediction is not None:
            print(
                f"Prediction after processing {frame_count} frames: {prediction.numpy().decode('utf-8')}")
            # Optionally, clear the prediction or break if you just want one prediction:
            # break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
