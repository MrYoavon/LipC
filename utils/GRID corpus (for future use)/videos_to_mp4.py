import subprocess
import os

# Directory containing the videos
input_directory = "../../data/GRID_corpus/original_videos"
output_directory = "../../data/GRID_corpus/videos"

# Create output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

# Loop through each subfolder in the input directory
for subfolder in os.listdir(input_directory):
    subfolder_path = os.path.join(input_directory, subfolder)

    # Skip if it's not a directory
    if not os.path.isdir(subfolder_path):
        continue

    # Create corresponding subfolder in the output directory
    output_subfolder = os.path.join(output_directory, subfolder)
    os.makedirs(output_subfolder, exist_ok=True)

    # Loop through each .mpg file in the subfolder
    for filename in os.listdir(subfolder_path):
        if filename.endswith(".mpg"):
            input_path = os.path.join(subfolder_path, filename)
            output_path = os.path.join(output_subfolder, f"{os.path.splitext(filename)[0]}.mp4")

            # Convert the video to .mp4 using FFmpeg
            subprocess.run([
                "ffmpeg", "-i", input_path,
                "-c:v", "libx264", "-c:a", "aac",
                output_path
            ])