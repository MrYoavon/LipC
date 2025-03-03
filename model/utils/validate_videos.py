import os
import cv2
import argparse
import logging


###############################
#      Logging Setup          #
###############################

def setup_logging(log_file: str = 'video_validation.log') -> None:
    """
    Set up the logging configuration.

    Args:
        log_file (str): File to which logs will be written.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


###############################
#   Video Validation Logic    #
###############################

def is_video_corrupted_opencv(video_path: str) -> tuple[bool, str]:
    """
    Check if a video is corrupted by attempting to read all its frames using OpenCV.

    Args:
        video_path (str): Path to the video file.

    Returns:
        tuple: (is_corrupted, error_message) where is_corrupted is True if the video is corrupted,
               and error_message describes the issue.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return True, "Cannot open video."

    frame_count = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        frame_count += 1

    cap.release()

    if frame_count == 0:
        return True, "No frames could be read."

    return False, ""


def validate_videos_opencv(video_directory: str) -> list[tuple[str, str]]:
    """
    Validate all videos in the specified directory using OpenCV.

    Args:
        video_directory (str): Root directory containing video files.

    Returns:
        list: A list of tuples for corrupted videos in the form (video_path, error_message).
    """
    corrupted_videos = []
    total_videos = 0

    for root, _, files in os.walk(video_directory):
        for file in files:
            if file.lower().endswith(('.mpg', '.mp4', '.avi', '.mkv')):
                total_videos += 1
                video_path = os.path.join(root, file)
                is_corrupted, error = is_video_corrupted_opencv(video_path)
                if is_corrupted:
                    corrupted_videos.append((video_path, error))
                    logging.warning(f"Corrupted Video: {video_path} | Reason: {error}")
                else:
                    logging.info(f"Valid Video: {video_path}")

    logging.info(f"Validation Complete: {total_videos} videos checked.")
    logging.info(f"Corrupted Videos Found: {len(corrupted_videos)}")

    return corrupted_videos


###############################
#          Main Block         #
###############################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate video dataset for corruption using OpenCV."
    )
    parser.add_argument(
        '--video_dir',
        type=str,
        required=True,
        help='Path to the root video directory.'
    )
    parser.add_argument(
        '--action',
        type=str,
        default='log',
        choices=['log', 'delete', 'move'],
        help='Action to take on corrupted videos: log, delete, or move.'
    )
    parser.add_argument(
        '--move_dir',
        type=str,
        default=None,
        help='Destination directory to move corrupted videos if action is "move".'
    )
    args = parser.parse_args()

    setup_logging()

    corrupted = validate_videos_opencv(args.video_dir)

    if args.action == 'delete':
        for video_path, _ in corrupted:
            try:
                os.remove(video_path)
                logging.info(f"Deleted Corrupted Video: {video_path}")
            except Exception as e:
                logging.error(f"Failed to delete {video_path}: {e}")
    elif args.action == 'move':
        if not args.move_dir:
            logging.error("Move directory not specified. Use --move_dir to specify the destination.")
            exit(1)
        os.makedirs(args.move_dir, exist_ok=True)
        for video_path, _ in corrupted:
            try:
                dest_path = os.path.join(args.move_dir, os.path.basename(video_path))
                os.rename(video_path, dest_path)
                logging.info(f"Moved Corrupted Video: {video_path} -> {dest_path}")
            except Exception as e:
                logging.error(f"Failed to move {video_path}: {e}")
    # If action is 'log', logging already handles output.
