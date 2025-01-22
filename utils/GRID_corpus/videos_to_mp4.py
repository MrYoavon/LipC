import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Directory containing the videos
input_directory = "../../data/GRID_corpus_normal/original_videos"
output_directory = "../../data/GRID_corpus_normal/videos"

# Create output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

def convert_video(input_path, output_path):
    """Convert a single video from .mpg to .mp4."""
    subprocess.run([
        "ffmpeg", "-i", input_path,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",  # Audio compression
        "-y",  # Overwrite output files if they exist
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # Suppress output for cleaner logs

# Create a list of tasks for conversion
tasks = []
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

            # Add the task to the list
            tasks.append((input_path, output_path))

# Process conversions in parallel with progress bars
with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
    # Wrap tasks in tqdm for a progress bar
    with tqdm(total=len(tasks), desc="Converting videos", unit="video") as pbar:
        futures = {executor.submit(convert_video, *task): task for task in tasks}
        for future in as_completed(futures):
            pbar.update(1)  # Update progress bar as each task completes
