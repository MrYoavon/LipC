import os
import tarfile
import requests
from tqdm import tqdm
import concurrent.futures

# Set the base URL of the GRID corpus download page
base_url = "https://spandh.dcs.shef.ac.uk//gridcorpus/"

# Define the range of talkers to download (1 to 34)
talkers = range(1, 35)

# Define directories for saving the tar files and extracted contents
base_data_dir = 'data/GRID_corpus/'
os.makedirs(f'{base_data_dir}downloads', exist_ok=True)
os.makedirs(f'{base_data_dir}videos', exist_ok=True)
os.makedirs(f'{base_data_dir}transcriptions', exist_ok=True)


# Function to download a file
def download_file(url, save_path):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        return total_size
    except Exception as e:
        print(f"Error downloading {save_path}: {e}")
        return 0


# Function to extract .tar files
def extract_tar(tar_path, extract_to, person_folder, file_type):
    try:
        with tarfile.open(tar_path, 'r') as tar:
            members = tar.getmembers()
            for member in members:
                # Handle video files inside the nested "video" folder
                if file_type == "video" and member.name.endswith('.mpg'):
                    member.name = os.path.basename(member.name)  # Keep only the file name
                    tar.extract(member, path=f"{extract_to}/videos/{person_folder}")
                # Handle align files inside the nested "align" folder
                elif file_type == "align" and member.name.endswith('.align'):
                    member.name = os.path.basename(member.name)  # Keep only the file name
                    tar.extract(member, path=f"{extract_to}/transcriptions/{person_folder}")
        return len(members)
    except Exception as e:
        print(f"Error extracting {tar_path}: {e}")
        return 0


# Combined function for downloading and extracting a file
def download_and_extract(url, save_path, extract_to, person_folder, file_type):
    downloaded_size = download_file(url, save_path)
    if downloaded_size > 0:
        extracted_files = extract_tar(save_path, extract_to, person_folder, file_type)
        return downloaded_size, extracted_files
    return 0, 0


# Wrapper function for processing a talker's video and transcription files in separate threads
def process_talker(talker, pbar):
    # Create directories for each talker
    person_folder = f"s{talker}"
    os.makedirs(f"{base_data_dir}videos/{person_folder}", exist_ok=True)
    os.makedirs(f"{base_data_dir}transcriptions/{person_folder}", exist_ok=True)

    # Construct URLs for high-quality videos and transcriptions
    video_url_pt1 = f"{base_url}/s{talker}/video/s{talker}.mpg_6000.part1.tar"
    video_url_pt2 = f"{base_url}/s{talker}/video/s{talker}.mpg_6000.part2.tar"
    transcript_url = f"{base_url}/s{talker}/align/s{talker}.tar"

    # Define local save paths
    video_save_pt1 = f"{base_data_dir}downloads/talker{talker}_pt1.tar"
    video_save_pt2 = f"{base_data_dir}downloads/talker{talker}_pt2.tar"
    transcript_save = f"{base_data_dir}downloads/talker{talker}_alignment.tar"

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(download_and_extract, video_url_pt1, video_save_pt1, base_data_dir, person_folder, "video"),
            executor.submit(download_and_extract, video_url_pt2, video_save_pt2, base_data_dir, person_folder, "video"),
            executor.submit(download_and_extract, transcript_url, transcript_save, base_data_dir, person_folder, "align"),
        ]

        for future in concurrent.futures.as_completed(futures):
            future.result()
            pbar.update(1)  # Update the progress bar when a thread completes


# Main: Process all talkers concurrently with three threads per talker
if __name__ == "__main__":
    total_talkers = len(talkers) - 1  # talker 21 is missing from the GRID corpus

    # Each talker has 3 tasks (2 video downloads + 1 transcription download)
    total_tasks = total_talkers * 3

    with tqdm(total=total_tasks, desc="Processing Talkers", unit='task') as pbar:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_talker, talker, pbar) for talker in talkers if talker != 21]

            for future in concurrent.futures.as_completed(futures):
                future.result()  # Ensure any errors are raised
    print("All talkers processed successfully")
