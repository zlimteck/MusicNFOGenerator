import os
import subprocess
import json
from pathlib import Path
import shutil
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configuration
DISCOGS_API_URL = "https://api.discogs.com/database/search"
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")
TEMPLATE_PATH = "template.nfo"
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")

# Function for extracting metadata via MediaInfo
def get_media_info(file_path):
    if os.name == "nt":  # Windows
        mediainfo_path = r"C:\MediaInfo\mediainfo.exe"  # Specific path for Windows, change if your path is different
    elif os.name == "posix":  # macOS / Linux
        mediainfo_path = "mediainfo"  # Make sure MediaInfo is installed via Homebrew on macOS or APT on Linux
    else:
        raise EnvironmentError("Operating system not supported.")

    try:
        result = subprocess.run([
            mediainfo_path, "--Output=JSON", file_path
        ], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except FileNotFoundError:
        print(f"MediaInfo not found : {mediainfo_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error when running MediaInfo : {e}")
    return None

# Function to convert time in seconds to H:MM:SS format
def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}:{minutes:02}:{seconds:02}"

# Function to search for an album on Discogs
def search_discogs(artist, album):
    if not DISCOGS_TOKEN:
        print("No Discogs token configured. Please set DISCOGS_TOKEN.")
        return "Unknown"

    params = {
        "artist": artist,
        "release_title": album,
        "type": "release",
        "token": DISCOGS_TOKEN
    }

    try:
        response = requests.get(DISCOGS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("results"):
            uri = data["results"][0].get("uri", "Unknown")
            if uri.startswith("/"):
                uri = f"https://www.discogs.com{uri}"
            return uri
    except Exception as e:
        print(f"Discogs search error : {e}")

    return "Unknown"

# Function to generate an NFO file
def generate_nfo(folder_path, discogs_link=None):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as template_file:
        nfo_template = template_file.read()

    folder = Path(folder_path)
    audio_files = list(folder.glob("*.flac")) + list(folder.glob("*.wav")) + \
                  list(folder.glob("*.mp3")) + list(folder.glob("*.m4a")) + \
                  list(folder.glob("*.ogg")) + list(folder.glob("*.opus"))

    if not audio_files:
        print("No audio files found.")
        return

    total_duration = 0
    total_size = sum(f.stat().st_size for f in audio_files)
    artist, album, genre, source, year = None, None, None, None, None

    for audio_file in audio_files:
        media_info = get_media_info(str(audio_file))
        if not media_info:
            continue

        general_info = media_info.get("media", {}).get("track", [{}])[0]

        if artist is None:
            artist = general_info.get("Performer", "Unknown")
        if album is None:
            album = general_info.get("Album", "Unknown")
        if genre is None:
            genre = general_info.get("Genre", "Unknown")
        if source is None:
            source = general_info.get("OriginalSourceForm", general_info.get("Format", "Unknown"))
        if year is None:
            year = general_info.get("Recorded_Date", "Unknown")

        try:
            duration_str = general_info.get("Duration", "0")
            total_duration += float(duration_str)
        except ValueError:
            print(f"Unable to read duration for {audio_file}")

    if not discogs_link:
        discogs_link = search_discogs(artist, album)

    info = {
        "Release": folder.name,
        "Artist(s)": artist or "Unknown",
        "Album": album or "Unknown",
        "Genre": genre or "Unknown",
        "Source": source or "Unknown",
        "Annee": year or "Unknown",
        "Ripper": "dBpoweramp",
        "Encode": "dBpoweramp",
        "Qualite": "FLAC" if any(".flac" in str(f) for f in audio_files) else "WAV",
        "Link": discogs_link,
        "Duree": format_duration(int(total_duration)),
        "Taille": f"{round(total_size / (1024 ** 2), 2)} MB",
    }

    nfo_content = nfo_template.format(**info)
    nfo_path = folder / f"{folder.name}.nfo"
    with open(nfo_path, "w", encoding="utf-8") as nfo_file:
        nfo_file.write(nfo_content)

    print(f"Generated NFO file : {nfo_path}")

# Function for organizing albums
def process_albums():
    if not INPUT_DIR.exists():
        print(f"The entry file '{INPUT_DIR}' doesn't exist.")
        return

    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True)

    for album_folder in INPUT_DIR.iterdir():
        if not album_folder.is_dir():
            continue

        print(f"Processing the album : {album_folder.name}")

        generate_nfo(album_folder)

        destination_folder = OUTPUT_DIR / album_folder.name
        shutil.move(str(album_folder), destination_folder)
        print(f"Album moved to : {destination_folder}")

if __name__ == "__main__":
    process_albums()