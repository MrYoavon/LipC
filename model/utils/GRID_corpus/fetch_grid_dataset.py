"""
Download and extract the GRID corpus videos and alignments in parallel.

This script retrieves speaker-specific archives from the GRID corpus server,
downloads them with retry logic, extracts media and transcription files,
and organizes them into structured directories. Progress is tracked via a
command-line progress bar, and operations are parallelized using a
ThreadPoolExecutor.

Dependencies:
    - requests
    - tqdm
    - av
    - concurrent.futures

Usage:
    python3 fetch_grid_dataset.py
"""
import os
import zipfile
import tarfile
import requests
from tqdm import tqdm
import concurrent.futures
from functools import partial
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Base configuration
BASE_URL = "https://spandh.dcs.shef.ac.uk//gridcorpus/"
BASE_DATA_DIR = os.path.join('..', '..', 'data', 'GRID_corpus_normal')
DOWNLOADS_DIR = os.path.join(BASE_DATA_DIR, 'downloads')
VIDEOS_DIR = os.path.join(BASE_DATA_DIR, 'videos')
TRANSCRIPTIONS_DIR = os.path.join(BASE_DATA_DIR, 'transcriptions')

# Ensure directory structure exists
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)

# Configure HTTP session with retry policy for robustness
session = requests.Session()
retries = Retry(total=5, backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retries)
session.mount('https://', adapter)


def create_talker_dirs(talker: int) -> str:
    """
    Create subdirectories for a given talker under videos and transcriptions.

    Args:
        talker (int): Numeric identifier of the speaker (1-34, excluding 21).

    Returns:
        str: Folder name (e.g., 's1') used for this talker's files.
    """
    folder = f"s{talker}"
    os.makedirs(os.path.join(VIDEOS_DIR, folder), exist_ok=True)
    os.makedirs(os.path.join(TRANSCRIPTIONS_DIR, folder), exist_ok=True)
    return folder


def download_file(url: str, save_path: str) -> int:
    """
    Download a file using HTTP GET with streaming and retries.

    Args:
        url (str): Full URL of the resource to download.
        save_path (str): Local filesystem path to save the downloaded file.

    Returns:
        int: Total size in bytes of the downloaded file, or 0 on failure.
    """
    try:
        with session.get(url, stream=True, timeout=10) as response:
            response.raise_for_status()
            total = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
        return total
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return 0


def extract_zip(zip_path: str, extract_to: str) -> int:
    """
    Extract all files from a ZIP archive to a target directory.

    Args:
        zip_path (str): Path to the ZIP file.
        extract_to (str): Directory in which to unpack contents.

    Returns:
        int: Number of files extracted, or 0 on error.
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_to)
            return len(z.namelist())
    except Exception as e:
        print(f"Error extracting {zip_path}: {e}")
        return 0


def extract_tar(tar_path: str, person_folder: str, file_type: str) -> int:
    """
    Extract selected members from a TAR archive based on file type.

    Args:
        tar_path (str): Path to the TAR file.
        person_folder (str): Subdirectory name for the talker (e.g., 's1').
        file_type (str): 'video' to extract .mpg files or 'align' for .align files.

    Returns:
        int: Number of members extracted, or 0 on error.
    """
    try:
        target_root = VIDEOS_DIR if file_type == 'video' else TRANSCRIPTIONS_DIR
        target = os.path.join(target_root, person_folder)
        with tarfile.open(tar_path, 'r') as t:
            members = [m for m in t.getmembers()
                       if (file_type == 'video' and m.name.endswith('.mpg'))
                       or (file_type == 'align' and m.name.endswith('.align'))]
            # Prevent directory traversal by sanitizing member names
            for m in members:
                m.name = os.path.basename(m.name)
            t.extractall(path=target, members=members)
        return len(members)
    except Exception as e:
        print(f"Error extracting {tar_path}: {e}")
        return 0


def download_and_extract(url: str, save_path: str, person_folder: str, file_type: str) -> tuple[int, int]:
    """
    Wrapper to download an archive and extract its contents.

    Args:
        url (str): URL of the archive.
        save_path (str): Local path to save the archive.
        person_folder (str): Talker-specific folder identifier.
        file_type (str): 'video' or 'align' to determine extraction logic.

    Returns:
        tuple[int, int]: (bytes_downloaded, files_extracted)
    """
    size = download_file(url, save_path)
    extracted = 0
    if size > 0:
        if save_path.endswith('.zip'):
            extracted = extract_zip(
                save_path, os.path.join(VIDEOS_DIR, person_folder))
        elif save_path.endswith('.tar'):
            extracted = extract_tar(
                save_path, BASE_DATA_DIR, person_folder, file_type)
        os.remove(save_path)
    return size, extracted


def process_talker(talker: int, pbar: tqdm) -> None:
    """
    Download and extract both video and alignment archives for one talker.

    Args:
        talker (int): Numeric ID of the talker to process.
        pbar (tqdm): Progress bar to update per completed task.
    """
    folder = create_talker_dirs(talker)
    video_urls = [
        f"{BASE_URL}/s{talker}/video/s{talker}.mpg_6000.part1.tar",
        f"{BASE_URL}/s{talker}/video/s{talker}.mpg_6000.part2.tar"
    ]
    align_url = f"{BASE_URL}/s{talker}/align/s{talker}.tar"
    file_tasks = [
        (video_urls[0], os.path.join(DOWNLOADS_DIR,
         f"talker{talker}_pt1.tar"), "video"),
        (video_urls[1], os.path.join(DOWNLOADS_DIR,
         f"talker{talker}_pt2.tar"), "video"),
        (video_urls[0], os.path.join(DOWNLOADS_DIR,
         f"talker{talker}_video.zip"), "video"),
        (align_url, os.path.join(DOWNLOADS_DIR,
         f"talker{talker}_alignment.tar"), "align"),
    ]

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(download_and_extract, url, path, folder, ftype)
                   for url, path, ftype in file_tasks]
        for future in concurrent.futures.as_completed(futures):
            future.result()
            pbar.update(1)


if __name__ == '__main__':
    # Prepare list of talker IDs to process (1–34, skipping 21)
    talkers = [t for t in range(1, 35) if t != 21]
    total = len(talkers) * 2  # two tasks per talker
    # Execute with a progress bar and parallel threads
    with tqdm(total=total, desc="Processing Talkers", unit="task") as bar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as exec:
            exec.map(partial(process_talker, pbar=bar), talkers)
    print("All talkers processed successfully.")
