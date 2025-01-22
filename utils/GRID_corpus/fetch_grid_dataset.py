import os
import zipfile
import tarfile
import requests
from tqdm import tqdm
import concurrent.futures
from functools import partial
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set the base URL of the GRID corpus download page
BASE_URL = "https://spandh.dcs.shef.ac.uk//gridcorpus/"

# Define directories for saving the tar files and extracted contents
BASE_DATA_DIR = '../../data/GRID_corpus_normal/'
DOWNLOADS_DIR = os.path.join(BASE_DATA_DIR, 'downloads')
VIDEOS_DIR = os.path.join(BASE_DATA_DIR, 'videos')
TRANSCRIPTIONS_DIR = os.path.join(BASE_DATA_DIR, 'transcriptions')

# Batch directory creation
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)

# Set up a requests session with retries
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
session.mount('https://', adapter)

# Function to create directories for a talker
def create_talker_dirs(talker):
    person_folder = f"s{talker}"
    os.makedirs(os.path.join(VIDEOS_DIR, person_folder), exist_ok=True)
    os.makedirs(os.path.join(TRANSCRIPTIONS_DIR, person_folder), exist_ok=True)
    return person_folder

# Function to download a file with retries
def download_file(url, save_path):
    try:
        with session.get(url, stream=True, timeout=10) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
        return total_size
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return 0

# Function to extract .zip files
def extract_zip(zip_path, extract_to):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return len(zip_ref.namelist())
    except Exception as e:
        print(f"Error extracting {zip_path}: {e}")
        return 0

# Function to extract .tar files
def extract_tar(tar_path, extract_to, person_folder, file_type):
    try:
        target_dir = VIDEOS_DIR if file_type == "video" else TRANSCRIPTIONS_DIR
        target_path = os.path.join(target_dir, person_folder)
        with tarfile.open(tar_path, 'r') as tar:
            members = [
                member for member in tar.getmembers()
                if (file_type == "video" and member.name.endswith('.mpg')) or
                   (file_type == "align" and member.name.endswith('.align'))
            ]
            for member in members:
                member.name = os.path.basename(member.name)  # Avoid directory traversal
            tar.extractall(path=target_path, members=members)
        return len(members)
    except Exception as e:
        print(f"Error extracting {tar_path}: {e}")
        return 0

# Combined function for downloading and extracting
def download_and_extract(url, save_path, person_folder, file_type):
    downloaded_size = download_file(url, save_path)
    if downloaded_size > 0:
        if file_type == "video" and save_path.endswith('.zip'):
            extracted_files = extract_zip(save_path, os.path.join(VIDEOS_DIR, person_folder))
        elif file_type == "align" and save_path.endswith('.tar'):
            extracted_files = extract_tar(save_path, BASE_DATA_DIR, person_folder, file_type)
        else:
            extracted_files = 0
        os.remove(save_path)  # Clean up the archive file after extraction
        return downloaded_size, extracted_files
    return 0, 0

# Main function to process a single talker
def process_talker(talker, pbar):
    person_folder = create_talker_dirs(talker)
    video_urls = [
        f"{BASE_URL}/s{talker}/video/s{talker}.mpg_vcd.zip"
        # f"{BASE_URL}/s{talker}/video/s{talker}.mpg_6000.part1.tar",
        # f"{BASE_URL}/s{talker}/video/s{talker}.mpg_6000.part2.tar"
    ]
    transcript_url = f"{BASE_URL}/s{talker}/align/s{talker}.tar"
    file_tasks = [
        # (video_urls[0], os.path.join(DOWNLOADS_DIR, f"talker{talker}_pt1.tar"), "video"),
        # (video_urls[1], os.path.join(DOWNLOADS_DIR, f"talker{talker}_pt2.tar"), "video"),
        (video_urls[0], os.path.join(DOWNLOADS_DIR, f"talker{talker}_video.zip"), "video"),
        (transcript_url, os.path.join(DOWNLOADS_DIR, f"talker{talker}_alignment.tar"), "align"),
    ]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(download_and_extract, url, path, person_folder, ftype)
                   for url, path, ftype in file_tasks]
        for future in concurrent.futures.as_completed(futures):
            future.result()
            pbar.update(1)

# Main script
if __name__ == "__main__":
    talkers = [t for t in range(1, 35) if t != 21]
    total_tasks = len(talkers) * 2

    with tqdm(total=total_tasks, desc="Processing Talkers", unit="task") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(partial(process_talker, pbar=pbar), talkers)

    print("All talkers processed successfully.")
