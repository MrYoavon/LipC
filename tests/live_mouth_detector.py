import cv2
import datetime
from data_processing.mouth_detection import MouthDetector

# Initialize MouthDetector with the model path
mouth_detector = MouthDetector(model_path='../assets/face_landmarker.task', num_faces=1)

# Open video capture from live camera or video file
video_source = 0  # Use 0 for live camera, or provide a file path for saved videos
video_capture = cv2.VideoCapture(video_source)

def main():
    while True:
        result, video_frame = video_capture.read()  # Read frames from the video
        if not result:
            break  # Terminate the loop if the frame is not read successfully

        cv2.imshow('Video', video_frame)

        # Process the video frame and get the cropped mouth
        cropped_mouth = mouth_detector.detect_and_crop_mouth(video_frame.copy())

        if cropped_mouth is not None:
            cv2.imshow("Mouth", cropped_mouth)  # Display the processed mouth frame
        else:
            print(f"{datetime.datetime.now().strftime('%H:%M:%S')} Unable to detect mouth")

        if cv2.waitKey(1) & 0xFF == ord("q"):  # Exit on 'q' key press
            break

    video_capture.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
