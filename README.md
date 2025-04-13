# Shira UI

A lightweight PyQt6 interface for [shira](https://github.com/KraXen72/shira) - music downloader.

### Features
- Supports YouTube, YouTube Music, and SoundCloud
- Uses existing `cookies.txt` and config from `.shira/config.json`
- Real-time output logging
- Button to open download folder

### Requirements
- Python 3.11+
- PyQt6
- shira

### Run
```bash
python shira_ui.py
```

### Troubleshooting

If you experience issues such as downloads failing or no formats being available, try the following:
- **Update `yt-dlp`**:  
  
  ```bash
  yt-dlp -U
  ```
  If installed via pip:  
  ```bash
  pip install -U yt-dlp
  ```
- **Update `ffmpeg`**:  
  
  Make sure `ffmpeg` is installed and the latest version is available in your system PATH. You can download the latest from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html).
