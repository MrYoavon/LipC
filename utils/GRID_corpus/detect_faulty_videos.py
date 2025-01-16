import os
import subprocess

def check_videos(directory):
    faulty_videos = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.mp4', '.mkv', '.mpg')):  # Add other formats if needed
                video_path = os.path.join(root, file)
                # print(video_path)
                try:
                    result = subprocess.run(
                        ['ffmpeg', '-v', 'error', '-i', video_path, '-f', 'null', '-'],
                        stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True
                    )
                    if result.stderr:
                        print(f"Errors found in: {video_path}")
                        faulty_videos.append(video_path)
                except Exception as e:
                    print(f"Failed to process {video_path}: {e}")
    return faulty_videos

dataset_directory = "../../data/GRID_corpus/videos"
faulty_videos = check_videos(dataset_directory)

if faulty_videos:
    print("Faulty videos detected:")
    for video in faulty_videos:
        print(video)
else:
    print("No faulty videos detected.")
