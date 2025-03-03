import cv2
import datetime
from model.data_processing.mouth_detection import MouthDetector


def initialize_resources():
    """
    Initialize the MouthDetector and the video capture device.

    Returns:
        tuple: A tuple containing:
            - mouth_detector (MouthDetector): Initialized mouth detection instance.
            - video_capture (cv2.VideoCapture): Video capture object for live camera or file input.
    """
    # Initialize MouthDetector with the specified model asset and number of faces.
    mouth_detector = MouthDetector(model_path='../assets/face_landmarker.task', num_faces=1)

    # Open video capture: 0 for live camera, or provide a file path for a video file.
    video_source = 0
    video_capture = cv2.VideoCapture(video_source)

    return mouth_detector, video_capture


def main():
    """
    Main function to capture live video, detect and crop the mouth region, and display the results in real-time.

    The function reads frames from the video capture device, processes each frame to detect and crop the mouth,
    and displays both the original video and the cropped mouth region. It terminates when 'q' is pressed.
    """
    # Initialize resources
    mouth_detector, video_capture = initialize_resources()

    while True:
        # Read a frame from the video capture device
        result, video_frame = video_capture.read()
        if not result:
            break  # Exit loop if frame reading fails

        # Display the original video frame
        cv2.imshow('Video', video_frame)

        # Process the frame to detect and crop the mouth region
        cropped_mouth = mouth_detector.detect_and_crop_mouth(video_frame.copy())

        if cropped_mouth is not None:
            cv2.imshow("Mouth", cropped_mouth)  # Display the cropped mouth frame
        else:
            current_time = datetime.datetime.now().strftime('%H:%M:%S')
            print(f"{current_time} Unable to detect mouth")

        # Exit the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Release the video capture device and close all OpenCV windows
    video_capture.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
