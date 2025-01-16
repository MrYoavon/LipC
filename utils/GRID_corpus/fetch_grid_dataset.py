import os
import tarfile
import requests
from tqdm import tqdm
import concurrent.futures
from functools import partial
from time import sleep

# Set the base URL of the GRID corpus download page
BASE_URL = "https://spandh.dcs.shef.ac.uk//gridcorpus/"

# Define directories for saving the tar files and extracted contents
BASE_DATA_DIR = '../../data/GRID_corpus/'
DOWNLOADS_DIR = os.path.join(BASE_DATA_DIR, 'downloads')
VIDEOS_DIR = os.path.join(BASE_DATA_DIR, 'videos')
TRANSCRIPTIONS_DIR = os.path.join(BASE_DATA_DIR, 'transcriptions')

for dir_path in [DOWNLOADS_DIR, VIDEOS_DIR, TRANSCRIPTIONS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Function to create directories for a talker
def create_talker_dirs(talker):
    person_folder = f"s{talker}"
    os.makedirs(os.path.join(VIDEOS_DIR, person_folder), exist_ok=True)
    os.makedirs(os.path.join(TRANSCRIPTIONS_DIR, person_folder), exist_ok=True)
    return person_folder

# Function to download a file with retries
def download_file(url, save_path, retries=3):
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                with open(save_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                return total_size
        except Exception as e:
            if attempt < retries - 1:
                sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"Failed to download {url}: {e}")
    return 0

# Function to extract .tar files
def extract_tar(tar_path, extract_to, person_folder, file_type):
    try:
        with tarfile.open(tar_path, 'r') as tar:
            members = tar.getmembers()
            target_dir = VIDEOS_DIR if file_type == "video" else TRANSCRIPTIONS_DIR
            target_path = os.path.join(target_dir, person_folder)
            for member in members:
                if file_type == "video" and member.name.endswith('.mpg') or \
                   file_type == "align" and member.name.endswith('.align'):
                    member.name = os.path.basename(member.name)
                    tar.extract(member, path=target_path)
            return len(members)
    except Exception as e:
        print(f"Error extracting {tar_path}: {e}")
        return 0

# Combined function for downloading and extracting
def download_and_extract(url, save_path, extract_to, person_folder, file_type):
    downloaded_size = download_file(url, save_path)
    if downloaded_size > 0:
        extracted_files = extract_tar(save_path, extract_to, person_folder, file_type)
        os.remove(save_path)  # Clean up .tar file after extraction
        return downloaded_size, extracted_files
    return 0, 0

# Main function to process a single talker
def process_talker(talker, pbar):
    person_folder = create_talker_dirs(talker)
    video_urls = [
        f"{BASE_URL}/s{talker}/video/s{talker}.mpg_6000.part1.tar",
        f"{BASE_URL}/s{talker}/video/s{talker}.mpg_6000.part2.tar"
    ]
    transcript_url = f"{BASE_URL}/s{talker}/align/s{talker}.tar"
    file_tasks = [
        (video_urls[0], os.path.join(DOWNLOADS_DIR, f"talker{talker}_pt1.tar"), "video"),
        (video_urls[1], os.path.join(DOWNLOADS_DIR, f"talker{talker}_pt2.tar"), "video"),
        (transcript_url, os.path.join(DOWNLOADS_DIR, f"talker{talker}_alignment.tar"), "align"),
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(download_and_extract, url, path, BASE_DATA_DIR, person_folder, ftype)
                   for url, path, ftype in file_tasks]
        for future in concurrent.futures.as_completed(futures):
            future.result()
            pbar.update(1)

# Main script
if __name__ == "__main__":
    talkers = [t for t in range(1, 35) if t != 21]
    total_tasks = len(talkers) * 3

    with tqdm(total=total_tasks, desc="Processing Talkers", unit="task") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            executor.map(partial(process_talker, pbar=pbar), talkers)

    print("All talkers processed successfully.")
