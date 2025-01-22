import os
import shutil
import cv2

def get_frame_count(video_path):
    """Returns the number of frames in a video."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video {video_path}")
        return 0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return frame_count

def filter_videos_by_frame_count(input_dir, output_dir, frame_count_target=75):
    """
    Loops through all videos in the input directory and its subdirectories,
    checks their frame count, and copies videos with the specified frame count to the output directory.

    Parameters:
        input_dir (str): Path to the directory containing subdirectories of videos.
        output_dir (str): Path to the directory where filtered videos will be saved.
        frame_count_target (int): Target frame count for filtering videos.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith((".mpg", ".mp4")):
                video_path = os.path.join(root, file)
                frame_count = get_frame_count(video_path)
                if frame_count == frame_count_target:
                    # Create corresponding subdirectory in output folder
                    relative_path = os.path.relpath(root, input_dir)
                    destination_dir = os.path.join(output_dir, relative_path)
                    if not os.path.exists(destination_dir):
                        os.makedirs(destination_dir)

                    # Copy video to output directory
                    destination_path = os.path.join(destination_dir, file)
                    # shutil.copy2(video_path, destination_path)
                    # print(f"Copied: {video_path} -> {destination_path} | Frames: {frame_count}")
                else:
                    print(f"Skipped: {video_path} (Frames: {frame_count}) | Frames: {frame_count}")

# Example usage
input_directory = "../../data/GRID_corpus/videos"  # Replace with the path to your input directory
output_directory = "../../data/GRID_corpus/videos_2"  # Replace with the path to your output directory
filter_videos_by_frame_count(input_directory, output_directory)
