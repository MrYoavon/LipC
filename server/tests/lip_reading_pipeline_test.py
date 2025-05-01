import cv2

from server.services.lip_reading.lip_reader import LipReadingPipeline

# Update these paths as necessary
MODEL_PATH = "server/models/final_model.keras"
VIDEO_PATH = "server/tests/bbaq9s.mp4"  # Path to your video file

# Set the sequence length that your pipeline expects (e.g., 75)
SEQUENCE_LENGTH = 75


def main():
    """
    Run a lip-reading inference pipeline on a video file frame by frame.

    This function:
      1. Loads the lip-reading model and initializes the pipeline.
      2. Opens the specified video file with OpenCV.
      3. Reads frames in a loop, displaying each frame in a window.
      4. Processes each frame through the LipReadingPipeline until a prediction is returned.
      5. Prints the returned prediction.

    Args:
        None

    Returns:
        None

    Raises:
        Prints an error and returns early if the video file cannot be opened.
    """
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
            # Uncomment to stop after first prediction
            # break

    # Release resources
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
