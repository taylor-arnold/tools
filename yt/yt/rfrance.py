import requests
import re
import os

def fetch_page_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching page: {e}")
        return None

def find_first_mp3_link(page_text):
    match = re.search(r'[^\"]+\.mp3', page_text)
    if match:
        return match.group(0)
    return None

def extract_filename_from_url(url):
    # Get the last path component
    slug = url.rstrip('/').split('/')[-1]
    # Remove trailing digits and optional dash (e.g., "-6038985")
    cleaned = re.sub(r'[-]?\d+$', '', slug)
    return f"{cleaned}.mp3"

def download_mp3(mp3_url, filename):
    try:
        print(f"Downloading MP3 from: {mp3_url}")
        response = requests.get(mp3_url, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"Saved as: {filename}")
    except Exception as e:
        print(f"Error downloading MP3: {e}")

def get_radio_france(url_path):
    page_text = fetch_page_content(url_path)
    if page_text:
        mp3_link = find_first_mp3_link(page_text)
        if mp3_link:
            filename = extract_filename_from_url(url_path)
            download_mp3(mp3_link, filename)
        else:
            print("No MP3 link found.")
    else:
        print("Failed to retrieve the page.")

