import subprocess

import pytest

# List of URLs to test
TEST_URLS = [
    "https://music.youtube.com/watch?v=HdX2COsY2Xk",  # YouTube Music
    "https://music.youtube.com/watch?v=8YwKlPH93Ps&list=PLC1og_v3eb4jE0bmdkWtizrSQ4zt86-3D",  # Playlist
    "https://www.youtube.com/watch?v=X0-AvRA7kB0",  # YouTube (video)
    "https://soundcloud.com/neffexmusic/fight-back",  # SoundCloud
    "https://music.youtube.com/playlist?list=PLC1og_v3eb4jE0bmdkWtizrSQ4zt86-3D",  # Album/Playlist
    "https://www.youtube.com/watch?v=pVjdMQ_iAh0",
    "https://www.youtube.com/watch?v=gLYWLobR248",
    "https://music.youtube.com/watch?v=5qdFjGI9948",
    "https://youtube.com/watch?v=5qdFjGI9948",
    "https://music.youtube.com/watch?v=FIrd5KJudrg",
    "https://www.youtube.com/watch?v=aN9_RkCGzGM",
    "https://soundcloud.com/alognaibiman/sets/kokeshi-anime-openings",  # SoundCloud Playlist
]

@pytest.mark.parametrize("url", TEST_URLS)
def test_download_url(url, temp_download_dir):
    """Test downloading a file from a URL."""
    final_path, temp_path = temp_download_dir

    # Run the CLI command
    command = [
        "python", "-m", "shiradl",
        url,
        "--final-path", str(final_path),
        "--temp-path", str(temp_path),
        "--log-level", "DEBUG",
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    # Check if the command completed successfully
    assert result.returncode == 0, f"Command failed with error: {result.stderr}"

    # Check if the downloaded file exists
    downloaded_files = list(final_path.rglob("*.*"))
    assert len(downloaded_files) > 0, "No files were downloaded."

    # Print the location of the downloaded files for debugging
    print(f"Downloaded files: {[str(f) for f in downloaded_files]}")